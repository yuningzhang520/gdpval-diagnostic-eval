"""Persistent pilot budget ledger: reservations before a unit starts, settlements from actual
usage after it ends, engineering-failure and stop records, and the approved stop conditions.

A *unit* is one sample execution or one independent judge batch. The launcher calls
``reserve()`` before starting a unit (refused when the remaining budget cannot cover the
estimate, when a stop condition holds, or when an unresolved unknown-cost settlement awaits
manual review), ``settle()`` after it ends (actual usage x unit prices, split by category,
released exactly once), or ``void()`` when the unit never started. Totals and stop state are
always recomputed from the append-only, schema-validated event list, so a restart loses
nothing, never double-counts, and keeps every stop condition. Unknown event types or malformed
events make the ledger refuse to load. Writes are atomic (temporary file + rename + fsync) under
an advisory file lock that also guards first creation. The ledger bounds what may be *started*;
a running unit can still take the actual cumulative cost above the ceiling.

Costs are USD per million tokens with Decimal arithmetic. Prices may carry tiers: ``cache_write``
(default retention), ``cache_write_extended`` (longer retention), and ``long_context`` with a
``threshold_input_tokens`` and its own rates. Pricing is per model call when per-call usage is
available; aggregated usage above a threshold is priced conservatively at the long-context tier
and flagged. Usage that cannot be priced reliably is never settled as zero: it is settled at the
larger of the priced part and the reservation, flagged ``estimated_unknown_cost``, and puts the
ledger on manual-review hold. When a unit carries two usage sources (the sample's aggregated
``model_usage`` and the per-call ModelEvent usages) they are reconciled per category; a conflict
is settled at the figure that does not understate the cost, both raw values and the differences
are kept, and the unit is held for manual review before any further paid start.
"""
import datetime as dt
import fcntl
import json
import os
import secrets
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.000001")
CATEGORIES = ("input", "output", "cache_read", "cache_write")
EVENT_TYPES = ("reservation", "settlement", "void", "engineering_failure", "stop", "review_cleared")
LEDGER_VERSION = 2


class BudgetError(Exception):
    """Base class for ledger refusals."""


class BudgetExhausted(BudgetError):
    """Remaining budget cannot cover the requested reservation; the unit must not start."""


class LedgerConflict(BudgetError):
    """The requested change contradicts the recorded history (settled unit, mismatched kind, ...)."""


class LedgerCorrupt(BudgetError):
    """The ledger file holds an unknown event type, a malformed event or an impossible transition."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _d(x) -> Decimal:
    return Decimal(str(x)).quantize(MONEY, rounding=ROUND_HALF_UP)


# ----------------------------------------------------------------------------- pricing
def _tier_for(usage: dict, price: dict) -> tuple[dict, str, list[str]]:
    """Choose the price tier for one call's usage. ``long_context`` applies when the call's prompt
    (uncached input + cache reads + cache writes) exceeds the threshold."""
    flags = []
    lc = price.get("long_context")
    prompt_tokens = sum(int(usage.get(k, 0) or 0) for k in ("input_tokens", "cache_read_tokens", "cache_write_tokens"))
    if lc and prompt_tokens > int(lc["threshold_input_tokens"]):
        tier = {k: lc.get(k, price.get(k)) for k in ("input", "output", "cache_read", "cache_write")}
        return tier, "long_context", flags
    return {k: price.get(k) for k in ("input", "output", "cache_read", "cache_write")}, "standard", flags


def usage_cost(usage: dict, price: dict, *, aggregated: bool = False) -> dict:
    """usage: input_tokens (uncached), output_tokens, cache_read_tokens, cache_write_tokens;
    price: USD per million tokens with optional tiers. Missing category prices are charged at
    the input rate (conservative) and flagged. ``aggregated`` usage spanning several calls whose
    total prompt exceeds a long-context threshold is priced at the long-context tier for every
    token and flagged (per-call sizes are unknown)."""
    tier, tier_name, flags = _tier_for(usage, price)
    if aggregated and tier_name == "long_context":
        flags.append("aggregated usage above the long-context threshold: whole call set priced at the long-context tier (conservative; per-call prompt sizes unknown)")
    if price.get("cache_write_extended") is not None and int(usage.get("cache_write_tokens", 0) or 0):
        flags.append(f"cache writes priced at the {price.get('cache_write_basis', 'configured')} rate ({tier.get('cache_write')} USD/MTok); "
                     "the usage record does not split cache-write retention tiers")
    out = {}
    for cat, tok_key in (("input", "input_tokens"), ("output", "output_tokens"), ("cache_read", "cache_read_tokens"), ("cache_write", "cache_write_tokens")):
        tokens = int(usage.get(tok_key, 0) or 0)
        rate_v = tier.get(cat)
        if rate_v is None:
            rate = Decimal(str(tier.get("input", price.get("input", 0))))
            if tokens:
                flags.append(f"no {cat} price; charged at the input rate")
        else:
            rate = Decimal(str(rate_v))
        out[cat] = _d(Decimal(tokens) * rate / Decimal(1_000_000))
    out["total"] = _d(sum(out[c] for c in CATEGORIES))
    out["tier"] = tier_name
    out["flags"] = flags
    return out


def price_calls(calls: list[dict], price: dict) -> dict:
    """Price a list of per-call usages and sum them (exact tiering per call)."""
    totals = {c: Decimal(0) for c in CATEGORIES}
    flags, tiers = [], {}
    for u in calls:
        c = usage_cost(u, price)
        for k in CATEGORIES:
            totals[k] += c[k]
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
        for f in c["flags"]:
            if f not in flags:
                flags.append(f)
    return {**{k: _d(v) for k, v in totals.items()}, "total": _d(sum(totals.values(), Decimal(0))), "tiers": tiers, "flags": flags, "calls": len(calls)}


def reconcile_usage(aggregated: dict, calls: list[dict]) -> dict:
    """Compare the sample's aggregated usage with the sum of its per-call usages, category by
    category (input excludes cached tokens on every provider; output already includes reasoning
    tokens, which are therefore never added again). Returns the two views, their differences and
    a ``conservative`` usage that takes the larger token count per category."""
    agg = {k: int(aggregated.get(k, 0) or 0) for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")}
    per = {k: sum(int(c.get(k, 0) or 0) for c in calls) for k in agg}
    diff = {k: agg[k] - per[k] for k in agg}
    by_cat = {"input": "input_tokens", "output": "output_tokens", "cache_read": "cache_read_tokens", "cache_write": "cache_write_tokens"}
    return {"aggregated": {c: agg[k] for c, k in by_cat.items()}, "per_call": {c: per[k] for c, k in by_cat.items()},
            "difference": {c: diff[k] for c, k in by_cat.items()}, "conflict": any(diff.values()), "calls": len(calls),
            "conservative": {k: max(agg[k], per[k]) for k in agg}}


# ----------------------------------------------------------------------------- validation
def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LedgerCorrupt(msg)


def _is_money(s) -> bool:
    try:
        Decimal(str(s))
        return isinstance(s, str)
    except Exception:
        return False


def validate_event(e: dict, index: int) -> None:
    """Strict per-type schema; any deviation refuses the whole ledger."""
    _require(isinstance(e, dict), f"event {index} is not an object")
    t = e.get("type")
    _require(t in EVENT_TYPES, f"event {index} has unknown type {t!r}")
    _require(isinstance(e.get("at"), str) and e["at"], f"event {index} lacks a timestamp")
    if t in ("reservation", "settlement", "void", "review_cleared"):
        _require(isinstance(e.get("unit_id"), str) and e["unit_id"], f"event {index} ({t}) lacks unit_id")
    if t == "reservation":
        _require(e.get("kind") in ("sample", "judge"), f"event {index}: reservation kind invalid")
        _require(_is_money(e.get("estimated_usd")) and Decimal(e["estimated_usd"]) >= 0, f"event {index}: reservation estimate invalid")
        _require(isinstance(e.get("meta"), dict), f"event {index}: reservation meta invalid")
    elif t == "settlement":
        _require(e.get("kind") in ("sample", "judge"), f"event {index}: settlement kind invalid")
        _require(_is_money(e.get("cost_usd")) and Decimal(e["cost_usd"]) >= 0, f"event {index}: settlement cost invalid")
        _require(isinstance(e.get("breakdown"), dict) and set(e["breakdown"]) == set(CATEGORIES) and all(_is_money(v) for v in e["breakdown"].values()),
                 f"event {index}: settlement breakdown invalid")
        _require(_is_money(e.get("retry_estimate_usd")), f"event {index}: retry estimate invalid")
        _require(isinstance(e.get("estimated"), bool) and isinstance(e.get("flags"), list), f"event {index}: settlement flags invalid")
        _require(isinstance(e.get("manual_review_required"), bool), f"event {index}: settlement review flag invalid")
        _require(isinstance(e.get("raw_usage"), dict), f"event {index}: settlement raw usage invalid")
    elif t == "void":
        _require(isinstance(e.get("reason"), str), f"event {index}: void reason invalid")
    elif t == "engineering_failure":
        _require(isinstance(e.get("failure_class"), str) and e["failure_class"], f"event {index}: failure class invalid")
        _require(isinstance(e.get("unit_id"), str), f"event {index}: failure unit_id invalid")
        _require(isinstance(e.get("detail"), str), f"event {index}: failure detail invalid")
    elif t == "stop":
        _require(isinstance(e.get("reasons"), list) and e["reasons"] and all(isinstance(r, str) for r in e["reasons"]), f"event {index}: stop reasons invalid")
    elif t == "review_cleared":
        _require(isinstance(e.get("by"), str) and e["by"] and isinstance(e.get("basis"), str) and e["basis"], f"event {index}: review clearance needs by and basis")


class BudgetLedger:
    def __init__(self, path: str, ceiling_usd, prices: dict | None = None, label: str = "pilot"):
        self.path = os.path.realpath(path)
        self.lock_path = self.path + ".lock"
        self.ceiling = _d(ceiling_usd)
        self.prices = prices or {}
        self.label = label
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with self._locked():  # first creation and the ceiling check happen under the inter-process lock
            if not os.path.exists(self.path):
                self._write({"version": LEDGER_VERSION, "label": label, "ceiling_usd": str(self.ceiling), "created_at": _now(), "entries": []})
            else:
                state = self._read()
                if _d(state["ceiling_usd"]) != self.ceiling:
                    raise LedgerConflict(f"ledger ceiling {state['ceiling_usd']} differs from configured {self.ceiling}; refuse to continue silently")

    # ------------------------------------------------------------------ persistence
    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            state = json.load(f)
        _require(isinstance(state, dict) and isinstance(state.get("entries"), list) and _is_money(state.get("ceiling_usd")), "ledger file malformed")
        _require(state.get("version") in (1, LEDGER_VERSION), f"ledger version {state.get('version')!r} unsupported")
        for i, e in enumerate(state["entries"]):
            validate_event(e, i)
        self._derive(state["entries"])  # transition validation
        return state

    def _write(self, state: dict) -> None:
        tmp = f"{self.path}.{secrets.token_hex(8)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        dfd = os.open(os.path.dirname(self.path), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def _locked(self):
        return _FileLock(self.lock_path)

    # ------------------------------------------------------------------ derived state
    @staticmethod
    def _derive(entries: list[dict]) -> dict:
        open_res: dict[str, dict] = {}
        settled: dict[str, dict] = {}
        voided: set[str] = set()
        settled_total = Decimal(0)
        estimated_total = Decimal(0)
        by_cat: dict[str, Decimal] = {c: Decimal(0) for c in CATEGORIES}
        by_cat.update({"judge": Decimal(0), "retry_estimate": Decimal(0)})
        failures: dict[str, int] = {}
        failure_events: list[dict] = []
        stops: list[dict] = []
        review_pending: dict[str, dict] = {}
        for i, e in enumerate(entries):
            t = e["type"]
            uid = e.get("unit_id")
            if t == "reservation":
                _require(uid not in open_res, f"event {i}: duplicate open reservation for {uid}")
                _require(uid not in settled and uid not in voided, f"event {i}: reservation for a settled or voided unit {uid}")
                open_res[uid] = e
            elif t == "settlement":
                _require(uid in open_res, f"event {i}: settlement without an open reservation for {uid}")
                _require(e["kind"] == open_res[uid]["kind"], f"event {i}: settlement kind differs from the reservation for {uid}")
                open_res.pop(uid)
                settled[uid] = e
                settled_total += Decimal(e["cost_usd"])
                if e.get("estimated"):
                    estimated_total += Decimal(e["cost_usd"])
                for c in CATEGORIES:
                    by_cat[c] += Decimal(e["breakdown"][c])
                if e["kind"] == "judge":
                    by_cat["judge"] += Decimal(e["cost_usd"]) - Decimal(e["retry_estimate_usd"])
                by_cat["retry_estimate"] += Decimal(e["retry_estimate_usd"])
                if e.get("manual_review_required"):
                    review_pending[uid] = e
            elif t == "void":
                _require(uid in open_res, f"event {i}: void without an open reservation for {uid}")
                open_res.pop(uid)
                voided.add(uid)
            elif t == "engineering_failure":
                failures[e["failure_class"]] = failures.get(e["failure_class"], 0) + 1
                failure_events.append(e)
            elif t == "stop":
                stops.append(e)
            elif t == "review_cleared":
                _require(uid in review_pending, f"event {i}: review clearance for a unit not awaiting review ({uid})")
                review_pending.pop(uid)
        reserved_total = sum((Decimal(r["estimated_usd"]) for r in open_res.values()), Decimal(0))
        return {"open_reservations": open_res, "settled": settled, "voided": voided, "settled_total": settled_total,
                "reserved_total": reserved_total, "estimated_total": estimated_total, "by_category": by_cat,
                "engineering_failures": failures, "failure_events": failure_events, "stops": stops, "review_pending": review_pending}

    def snapshot(self) -> dict:
        state = self._read()
        d = self._derive(state["entries"])
        remaining = self.ceiling - d["settled_total"] - d["reserved_total"]
        return {"ceiling_usd": str(self.ceiling), "settled_usd": str(_d(d["settled_total"])), "reserved_usd": str(_d(d["reserved_total"])),
                "remaining_usd": str(_d(remaining)), "estimated_portion_usd": str(_d(d["estimated_total"])),
                "by_category_usd": {k: str(_d(v)) for k, v in d["by_category"].items()},
                "open_reservations": sorted(d["open_reservations"]), "settled_units": sorted(d["settled"]), "voided_units": sorted(d["voided"]),
                "engineering_failures": dict(d["engineering_failures"]), "stops": [s["reasons"] for s in d["stops"]],
                "review_pending_units": sorted(d["review_pending"]), "entries": len(state["entries"])}

    def remaining(self) -> Decimal:
        return Decimal(self.snapshot()["remaining_usd"])

    def can_start(self, estimated_usd) -> bool:
        return _d(estimated_usd) <= self.remaining() and not self.stop_reasons(next_estimate_usd=estimated_usd)

    # ------------------------------------------------------------------ mutations
    def _append(self, state: dict, entry: dict) -> dict:
        validate_event(entry, len(state["entries"]))
        state["entries"].append(entry)
        self._derive(state["entries"])
        self._write(state)
        return entry

    def reserve(self, unit_id: str, kind: str, estimated_usd, meta: dict | None = None) -> dict:
        """Reserve before a unit starts. Idempotent only for an open reservation of the same unit
        with the same kind, estimate and binding (model, task, sample); any difference is a
        conflict. Refuses settled or voided units, a standing stop condition, a pending manual
        review, and an estimate the remaining budget cannot cover."""
        if kind not in ("sample", "judge"):
            raise LedgerConflict(f"unknown unit kind {kind!r}")
        est = _d(estimated_usd)
        if est < 0:
            raise LedgerConflict("negative estimate")
        meta = dict(meta or {})
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id in d["settled"]:
                raise LedgerConflict(f"unit {unit_id} is already settled")
            if unit_id in d["voided"]:
                raise LedgerConflict(f"unit {unit_id} was voided; use a new unit id")
            existing = d["open_reservations"].get(unit_id)
            if existing:
                same = existing["kind"] == kind and _d(existing["estimated_usd"]) == est and all(existing["meta"].get(k) == meta.get(k) for k in ("model", "task", "sample_id", "run"))
                if not same:
                    raise LedgerConflict(f"unit {unit_id} already reserved with a different kind, estimate or binding")
                return existing
            reasons = self._stop_reasons(d, next_estimate_usd=est)
            if reasons:
                raise BudgetExhausted("; ".join(reasons))
            entry = {"type": "reservation", "unit_id": unit_id, "kind": kind, "estimated_usd": str(est), "at": _now(), "meta": meta}
            return self._append(state, entry)

    def settle(self, unit_id: str, usage_by_model: dict, *, retries_by_model: dict | None = None, note: str = "",
               estimated: bool = False, fallback_to_reservation: bool = False, calls_by_model: dict | None = None, scope: dict | None = None) -> dict:
        """Settle a unit from actual usage ({model: usage dict}); releases its reservation exactly
        once (a repeat returns the first settlement unchanged). ``calls_by_model`` ({model: [per-call
        usage]}) enables exact per-call tier pricing. Each recorded retry adds one more uncached
        input cost (estimate). Usage with no reliable price is never settled as zero: the unit is
        settled at the larger of the priced part and the reservation, flagged
        ``estimated_unknown_cost`` and put on manual-review hold. ``fallback_to_reservation``
        settles a unit with no usable usage at its reserved amount (flagged). ``scope`` records
        where the two usage sources come from (same sample, same model set); per-call usage is
        reconciled with the aggregated usage only when the scope says both describe the same
        sample, otherwise the aggregated figure is priced and the mismatch flagged."""
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id in d["settled"]:
                return d["settled"][unit_id]
            res = d["open_reservations"].get(unit_id)
            if res is None:
                raise LedgerConflict(f"unit {unit_id} has no open reservation to settle")
            breakdown = {c: Decimal(0) for c in CATEGORIES}
            flags: list[str] = []
            per_model = {}
            unpriced = []
            manual_review = False
            reconciliation: dict[str, dict] = {}
            scope = dict(scope or {})
            same_scope = scope.get("same_sample") is True
            inspect_cost_total = Decimal(0)
            inspect_cost_known = False
            for model, usage in (usage_by_model or {}).items():
                price = self.prices.get(model)
                if price is None:
                    unpriced.append(model)
                    continue
                calls = (calls_by_model or {}).get(model)
                if calls and not same_scope:
                    flags.append(f"{model}: per-call usage ignored for pricing: its scope is not confirmed to be this sample; aggregated usage priced conservatively")
                    calls = None
                rec = reconcile_usage(usage, calls) if calls else None
                if rec is not None and rec["conflict"]:
                    cost_calls = price_calls(calls, price)
                    cost_agg = usage_cost(rec["conservative"], price, aggregated=True)
                    cost = cost_calls if cost_calls["total"] >= cost_agg["total"] else {**cost_agg, "tiers": {cost_agg["tier"]: len(calls)}}
                    cost = dict(cost)
                    cost["flags"] = list(cost.get("flags", [])) + [
                        "usage_sources_conflict: aggregated sample usage and per-call usage disagree "
                        + "; ".join(f"{c}: aggregated {rec['aggregated'][c]} vs per-call {rec['per_call'][c]} (diff {rec['difference'][c]})" for c in CATEGORIES if rec["difference"][c])
                        + f"; settled at the larger figure ({_d(cost['total'])} USD); estimated; manual review required before further paid starts"]
                    reconciliation[model] = rec | {"cost_per_call": str(cost_calls["total"]), "cost_conservative_aggregate": str(cost_agg["total"])}
                    estimated = True
                    manual_review = True
                elif rec is not None:
                    cost = price_calls(calls, price)
                    reconciliation[model] = rec
                else:
                    cost = usage_cost(usage, price, aggregated=True)
                # Inspect's own per-call total_cost (computed with the TTL it knows) is a floor: never settle below it.
                known = [c.get("total_cost") for c in (calls or []) if isinstance(c.get("total_cost"), (int, float))]
                if known and len(known) == len(calls):
                    inspect_cost_known = True
                    inspect_total = _d(sum(Decimal(str(k)) for k in known))
                    inspect_cost_total += inspect_total
                    if inspect_total > _d(cost["total"]):
                        flags.append(f"{model}: Inspect recorded total_cost {inspect_total} USD above the ledger pricing {_d(cost['total'])} USD; settled at the Inspect figure (difference added to input)")
                        cost = dict(cost)
                        cost["input"] = _d(cost["input"] + (inspect_total - _d(cost["total"])))
                        cost["total"] = inspect_total
                        estimated = True
                per_model[model] = {k: str(v) for k, v in cost.items() if k not in ("flags", "tiers")} | {"flags": cost["flags"], "tiers": cost.get("tiers", {cost.get("tier", "standard"): 1})}
                flags.extend(f"{model}: {f}" for f in cost["flags"])
                for c in CATEGORIES:
                    breakdown[c] += cost[c]
            retry_est = Decimal(0)
            for model, n in (retries_by_model or {}).items():
                if n and model in per_model:
                    retry_est += Decimal(per_model[model]["input"]) * Decimal(int(n))
                    flags.append(f"{model}: {n} retried request(s); usage of failed attempts unknown, estimated at {n} x uncached input cost")
                elif n:
                    flags.append(f"{model}: {n} retried request(s) with no priced usage; unknown cost")
                    estimated = True
            total = sum(breakdown.values(), Decimal(0)) + retry_est
            if unpriced:
                total = max(total, Decimal(res["estimated_usd"]))
                estimated = True
                manual_review = True
                flags.append(f"estimated_unknown_cost: no reliable price for {sorted(unpriced)}; settled at max(priced part, reservation) = {_d(total)} USD; "
                             "the reservation is not a bill; manual account review required before further paid starts")
            if not usage_by_model:
                if not fallback_to_reservation:
                    raise LedgerConflict("no usage given; pass fallback_to_reservation=True to settle conservatively or void() a unit that never ran")
                total = max(total, Decimal(res["estimated_usd"]))
                estimated = True
                flags.append("settled at the reserved amount (no usage available; conservative)")
            entry = {"type": "settlement", "unit_id": unit_id, "kind": res["kind"], "cost_usd": str(_d(total)),
                     "breakdown": {c: str(_d(v)) for c, v in breakdown.items()}, "retry_estimate_usd": str(_d(retry_est)),
                     "per_model": per_model, "raw_usage": usage_by_model or {}, "raw_calls": calls_by_model or {}, "usage_scope": scope,
                     "usage_reconciliation": reconciliation, "inspect_total_cost_usd": str(_d(inspect_cost_total)) if inspect_cost_known else None,
                     "estimated": bool(estimated or retry_est > 0),
                     "manual_review_required": manual_review, "flags": flags, "note": note, "reserved_usd": res["estimated_usd"], "at": _now()}
            return self._append(state, entry)

    def void(self, unit_id: str, reason: str) -> dict:
        """Release the reservation of a unit that never started (no usage possible)."""
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id in d["settled"]:
                raise LedgerConflict(f"unit {unit_id} is settled; cannot void")
            if unit_id not in d["open_reservations"]:
                raise LedgerConflict(f"unit {unit_id} has no open reservation")
            return self._append(state, {"type": "void", "unit_id": unit_id, "reason": reason, "at": _now()})

    def record_engineering_failure(self, failure_class: str, unit_id: str, detail: str) -> dict:
        """Persist one engineering failure (launcher exception, or a terminal Inspect error returned
        with fail_on_error=false). Counted by class for the second-occurrence stop rule."""
        with self._locked():
            state = self._read()
            return self._append(state, {"type": "engineering_failure", "failure_class": str(failure_class)[:120], "unit_id": unit_id, "detail": str(detail)[:300], "at": _now()})

    def record_stop(self, reasons: list[str]) -> dict:
        with self._locked():
            state = self._read()
            return self._append(state, {"type": "stop", "reasons": [str(r)[:300] for r in reasons], "at": _now()})

    def clear_review(self, unit_id: str, by: str, basis: str) -> dict:
        """Human clearance of an unknown-cost settlement after the account was checked."""
        with self._locked():
            state = self._read()
            return self._append(state, {"type": "review_cleared", "unit_id": unit_id, "by": by, "basis": basis, "at": _now()})

    # ------------------------------------------------------------------ stop conditions
    def _stop_reasons(self, d: dict, *, next_estimate_usd=None, per_task_costs: dict | None = None, per_task_estimate_usd=None) -> list[str]:
        reasons = []
        remaining = self.ceiling - d["settled_total"] - d["reserved_total"]
        if remaining <= 0:
            reasons.append(f"budget ceiling reached (remaining {_d(remaining)} USD)")
        if next_estimate_usd is not None and _d(next_estimate_usd) > remaining:
            reasons.append(f"remaining {_d(remaining)} USD cannot cover the next reservation {_d(next_estimate_usd)} USD")
        for cls, n in d["engineering_failures"].items():
            if n >= 2:
                reasons.append(f"engineering failure class {cls!r} occurred {n} times")
        for uid, s in d["settled"].items():
            est = Decimal(s["reserved_usd"])
            if est > 0 and Decimal(s["cost_usd"]) > 2 * est:
                reasons.append(f"unit {uid} cost {s['cost_usd']} USD exceeds 2x its estimate {s['reserved_usd']} USD")
        if per_task_costs and per_task_estimate_usd is not None:
            for task, cost in per_task_costs.items():
                if Decimal(str(cost)) > 2 * _d(per_task_estimate_usd):
                    reasons.append(f"task {task} cost {cost} USD exceeds 2x the estimate {_d(per_task_estimate_usd)} USD")
        if d["review_pending"]:
            reasons.append(f"unknown actual cost pending manual review for unit(s) {sorted(d['review_pending'])}")
        for s in d["stops"]:
            reasons.append("recorded stop: " + "; ".join(s["reasons"]))
        return reasons

    def stop_reasons(self, *, next_estimate_usd=None, per_task_costs: dict | None = None, per_task_estimate_usd=None,
                     engineering_failures: dict | None = None) -> list[str]:
        """Approved stop conditions (persisted state plus optional extra counts). Empty = may continue."""
        state = self._read()
        d = self._derive(state["entries"])
        if engineering_failures:
            merged = dict(d["engineering_failures"])
            for k, v in engineering_failures.items():
                merged[k] = merged.get(k, 0) + int(v)
            d = {**d, "engineering_failures": merged}
        return self._stop_reasons(d, next_estimate_usd=next_estimate_usd, per_task_costs=per_task_costs, per_task_estimate_usd=per_task_estimate_usd)


class _FileLock:
    def __init__(self, path: str):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None


def usage_from_eval_sample(sample) -> tuple[dict, dict]:
    """({model: aggregated usage}, {model: retries}) from an Inspect EvalSample. ModelUsage.input_tokens
    excludes cached tokens; cache reads and writes are separate. Retries come from ModelEvent.retries."""
    usage = {}
    for model, u in (getattr(sample, "model_usage", None) or {}).items():
        usage[model] = {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
                        "cache_read_tokens": u.input_tokens_cache_read or 0, "cache_write_tokens": u.input_tokens_cache_write or 0}
    retries: dict[str, int] = {}
    for e in getattr(sample, "events", []) or []:
        if getattr(e, "event", None) == "model" and getattr(e, "retries", None):
            retries[e.model] = retries.get(e.model, 0) + int(e.retries)
    return usage, retries


def calls_from_eval_sample(sample) -> dict:
    """{model: [per-call usage]} from the ModelEvents of an Inspect EvalSample (for per-call tiering)."""
    calls: dict[str, list[dict]] = {}
    for e in getattr(sample, "events", []) or []:
        if getattr(e, "event", None) != "model":
            continue
        u = getattr(getattr(e, "output", None), "usage", None)
        if u is None:
            continue
        rec = {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
               "cache_read_tokens": u.input_tokens_cache_read or 0, "cache_write_tokens": u.input_tokens_cache_write or 0}
        tc = getattr(u, "total_cost", None)
        if isinstance(tc, (int, float)):
            rec["total_cost"] = float(tc)  # Inspect's own pricing of this call (TTL-aware); kept as a floor
        calls.setdefault(e.model, []).append(rec)
    return calls
