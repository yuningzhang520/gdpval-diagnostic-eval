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
import re
import os
import secrets
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY = Decimal("0.000001")
CATEGORIES = ("input", "output", "cache_read", "cache_write")
EVENT_TYPES = ("reservation", "settlement", "void", "engineering_failure", "stop", "review_cleared", "manual_resolution")
RESOLUTIONS = ("settled_amount", "unresolvable")
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


def _money_in(x, what: str = "amount") -> Decimal:
    """Validate a money input BEFORE quantization: a finite, non-negative Decimal (so -0.0000001, NaN and
    Infinity are refused instead of rounding to a legal zero). Returns the quantized value."""
    try:
        raw = Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        raise LedgerConflict(f"{what} is not a decimal number: {x!r}")
    if not raw.is_finite():
        raise LedgerConflict(f"{what} must be finite: {x!r}")
    if raw < 0:
        raise LedgerConflict(f"{what} must not be negative: {x!r}")
    return _d(raw)


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
    elif t == "manual_resolution":
        _require(isinstance(e.get("unit_id"), str) and e["unit_id"], f"event {index} (manual_resolution) lacks unit_id")
        _require(e.get("resolution") in RESOLUTIONS, f"event {index}: resolution must be one of {RESOLUTIONS}")
        _require(isinstance(e.get("by"), str) and e["by"] and isinstance(e.get("basis"), str) and e["basis"], f"event {index}: manual resolution needs by and basis")
        if e["resolution"] == "settled_amount":
            _require(_is_money(e.get("amount_usd")) and Decimal(e["amount_usd"]) >= 0 and e.get("currency") == "USD", f"event {index}: settled_amount needs amount_usd (string) and currency USD")
        if "inferred" in e:  # an inferred (not provider-confirmed) amount: only on settled_amount, with its calculation
            _require(e["resolution"] == "settled_amount" and isinstance(e["inferred"], dict) and isinstance(e["inferred"].get("basis"), str) and e["inferred"]["basis"],
                     f"event {index}: an inferred resolution is a settled_amount carrying its calculation basis")


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
                self._write({"version": LEDGER_VERSION, "label": label, "ceiling_usd": str(self.ceiling), "created_at": _now(), "ledger_id": secrets.token_hex(16), "entries": []})
            else:
                state = self._read()
                if _d(state["ceiling_usd"]) != self.ceiling:
                    raise LedgerConflict(f"ledger ceiling {state['ceiling_usd']} differs from configured {self.ceiling}; refuse to continue silently")
                if state.get("label") not in (None, label):  # run classes are never mixed: a ledger belongs to one class
                    raise LedgerConflict(f"ledger label {state.get('label')!r} differs from the requested run class {label!r}; refuse to continue")
                if not state.get("ledger_id"):  # ledgers created before the identity existed: assign one persistent id once (identity metadata, not an event)
                    state["ledger_id"] = secrets.token_hex(16)
                    self._write(state)

    @classmethod
    def open_existing(cls, path: str, prices: dict | None = None) -> "BudgetLedger":
        """Open a ledger that already exists with the ceiling and label it was created with (grading, reporting and
        reconciliation never decide a ceiling; only the launcher creates a ledger, from the batch controls)."""
        real = os.path.realpath(path)
        if not os.path.isfile(real):
            raise LedgerConflict(f"ledger {path} does not exist; only the launcher creates ledgers")
        with open(real, encoding="utf-8") as f:
            state = json.load(f)
        _require(isinstance(state, dict) and _is_money(state.get("ceiling_usd")), "ledger file malformed")
        return cls(real, state["ceiling_usd"], prices, label=state.get("label") or "pilot")

    def identity(self) -> dict:
        """Canonical identity a run binds to: the real path of the ledger file and its persistent id."""
        return {"ledger_path": self.path, "ledger_id": self._read().get("ledger_id")}

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
        resolutions: dict[str, dict] = {}
        unresolvable: dict[str, dict] = {}
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
            elif t == "manual_resolution":
                # Human reconciliation of one unit after investigation. settled_amount on an OPEN reservation (an unknown-outcome
                # unit) closes it at the verified amount; on an estimated settlement it adjusts that unit's cost to the verified
                # amount and lifts its review hold. The original reservation / settlement events stay in the ledger untouched.
                # unresolvable records the investigation only: the reservation stays open, the hold stays, nothing is released.
                _require(uid in open_res or uid in settled, f"event {i}: manual resolution for an unknown unit {uid}")
                resolutions[uid] = e
                if e["resolution"] == "settled_amount":
                    amount = Decimal(e["amount_usd"])
                    if uid in open_res:
                        res = open_res.pop(uid)
                        settled[uid] = {"type": "settlement", "unit_id": uid, "kind": res["kind"], "cost_usd": str(_d(amount)), "breakdown": {c: "0" for c in CATEGORIES},
                                        "retry_estimate_usd": "0", "estimated": bool(e.get("inferred")), "manual_review_required": False,
                                        "flags": ["manual_resolution: inferred amount, not provider-confirmed" if e.get("inferred") else "manual_resolution: verified amount"],
                                        **({"inferred": e["inferred"]} if e.get("inferred") else {}),
                                        "raw_usage": {}, "note": f"manual resolution by {e['by']}: {e['basis']}", "reserved_usd": res["estimated_usd"], "at": e["at"], "resolved_from": "open_reservation"}
                        settled_total += amount
                        if res["kind"] == "judge":
                            by_cat["judge"] += amount
                    else:
                        prev = settled[uid]
                        delta = amount - Decimal(prev["cost_usd"])
                        settled_total += delta
                        if prev.get("estimated"):
                            estimated_total -= Decimal(prev["cost_usd"])
                        if e.get("inferred"):  # an inferred amount stays an estimate; only its hold is lifted
                            estimated_total += amount
                        if prev["kind"] == "judge":
                            by_cat["judge"] += delta
                        settled[uid] = {**prev, "cost_usd": str(_d(amount)), "estimated": bool(e.get("inferred")), "manual_review_required": False, "resolved_from": "estimated_settlement",
                                        "previous_cost_usd": prev["cost_usd"], **({"inferred": e["inferred"]} if e.get("inferred") else {}),
                                        "flags": list(prev.get("flags", [])) + ["manual_resolution: inferred amount, not provider-confirmed" if e.get("inferred") else "manual_resolution: verified amount"]}
                        review_pending.pop(uid, None)
                else:
                    unresolvable[uid] = e
        reserved_total = sum((Decimal(r["estimated_usd"]) for r in open_res.values()), Decimal(0))
        return {"open_reservations": open_res, "settled": settled, "voided": voided, "settled_total": settled_total,
                "reserved_total": reserved_total, "estimated_total": estimated_total, "by_category": by_cat,
                "engineering_failures": failures, "failure_events": failure_events, "stops": stops, "review_pending": review_pending,
                "resolutions": resolutions, "unresolvable": unresolvable}

    def snapshot(self) -> dict:
        state = self._read()
        d = self._derive(state["entries"])
        remaining = self.ceiling - d["settled_total"] - d["reserved_total"]
        return {"ceiling_usd": str(self.ceiling), "settled_usd": str(_d(d["settled_total"])), "reserved_usd": str(_d(d["reserved_total"])),
                "remaining_usd": str(_d(remaining)), "estimated_portion_usd": str(_d(d["estimated_total"])),
                "by_category_usd": {k: str(_d(v)) for k, v in d["by_category"].items()},
                "open_reservations": sorted(d["open_reservations"]), "settled_units": sorted(d["settled"]), "voided_units": sorted(d["voided"]),
                "engineering_failures": dict(d["engineering_failures"]), "stops": [s["reasons"] for s in d["stops"]],
                "review_pending_units": sorted(d["review_pending"]), "unresolvable_units": sorted(d["unresolvable"]), "resolved_units": sorted(d["resolutions"]),
                "ledger_id": state.get("ledger_id"), "entries": len(state["entries"])}

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

    def reserve(self, unit_id: str, kind: str, estimated_usd, meta: dict | None = None, *, claim: bool = False) -> dict:
        """Reserve before a unit starts. Default (bookkeeping) contract unchanged: idempotent for an open
        reservation of the same unit with the same kind, estimate and binding; any difference is a conflict;
        refuses settled or voided units, a standing stop condition, a pending manual review, and an
        estimate the remaining budget cannot cover.
        ``claim=True`` (B2 remediation, approved 2026-10-31) is the atomic right to make the paid call: inside the
        same lock it additionally refuses when ANY other unit has an open reservation (unknown outcome) and when
        this unit already has one (an executor claimed it before and did not settle: reconcile, never re-run);
        the reservation it writes carries ``claim: true``. Every real paid call path reserves with claim=True;
        the lock covers only this check-and-write, never a provider request."""
        if kind not in ("sample", "judge"):
            raise LedgerConflict(f"unknown unit kind {kind!r}")
        est = _money_in(estimated_usd, "estimate")
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
                if claim:
                    raise LedgerConflict(f"unit {unit_id} already has an open reservation (claimed earlier, outcome unknown); reconcile it (void or manual resolution) before any re-run")
                same = existing["kind"] == kind and _d(existing["estimated_usd"]) == est and all(existing["meta"].get(k) == meta.get(k) for k in ("model", "task", "sample_id", "run"))
                if not same:
                    raise LedgerConflict(f"unit {unit_id} already reserved with a different kind, estimate or binding")
                return existing
            reasons = self._stop_reasons(d, next_estimate_usd=est)
            if claim and d["open_reservations"]:
                reasons.append(f"open reservation(s) of unknown outcome must be reconciled before a new paid unit starts: {sorted(d['open_reservations'])}")
            if reasons:
                raise BudgetExhausted("; ".join(reasons))
            entry = {"type": "reservation", "unit_id": unit_id, "kind": kind, "estimated_usd": str(est), "at": _now(), "meta": meta, **({"claim": True} if claim else {})}
            return self._append(state, entry)

    def settle(self, unit_id: str, usage_by_model: dict, *, retries_by_model: dict | None = None, note: str = "",
               estimated: bool = False, fallback_to_reservation: bool = False, calls_by_model: dict | None = None, scope: dict | None = None,
               hold: bool = False, incomplete: bool = False, recovered: dict | None = None) -> dict:
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
            inferred = None
            if recovered and not (hold or incomplete) and not unpriced:
                # Approved 2026-11-01 (Gemini dev / validation): usage-less attempts that are recovered HTTP 429 / 5xx
                # retries are settled at the reported usage plus ONE average metered call per unit, marked inferred
                # (not provider-confirmed), without a hold; the dashboard reconciliation stays a requirement.
                # Engine .8 judge batches (approved 2026-11-01): ``buffer_calls`` average metered calls instead of one
                # (1 + max_retries per failed request); without any metered call nothing can be inferred and the unit is held.
                metered = sum(len((calls_by_model or {}).get(m_) or []) for m_ in per_model)
                priced = sum(breakdown.values(), Decimal(0))
                n_buf = max(1, int(recovered.get("buffer_calls") or 1))
                if not metered:
                    incomplete = True
                    flags.append("inferred buffer impossible: no metered call to average; conservative settlement applies")
                else:
                    buffer = _d(priced / metered * n_buf)
                    total += buffer
                    inferred = {"buffer_usd": str(buffer), "buffer_calls": n_buf, "basis": f"{n_buf} average metered call(s): {_d(priced)} USD / {metered} metered call(s) x {n_buf}",
                                "reported_usd": str(_d(priced)), "recovered_attempts": recovered, "reconciliation_required": "provider dashboard"}
                    flags.append(f"inferred: {recovered.get('recovered')} recovered 429/5xx attempt(s) without usage; settled at reported usage {_d(priced)} + buffer {buffer} USD ({n_buf} average metered call(s)); not provider-confirmed")
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
            if hold or incomplete:
                # Approved policy (2026-10-31): missing or incomplete usage (any call whose usage is unknown, or an exception
                # after calls were made) is accounted conservatively - never below the reservation, never below the known
                # part - AND holds further paid starts until a human reconciles the unit (manual_resolution settled_amount).
                floor = Decimal(res["estimated_usd"])
                if total < floor:
                    flags.append(f"incomplete usage: priced known part {_d(total)} USD is below the reservation; settled at the reservation {_d(floor)} USD")
                    total = floor
                estimated = True
                manual_review = True
                flags.append("hold: usage missing or incomplete; conservative estimate; manual reconciliation required before further paid starts")
            entry = {"type": "settlement", "unit_id": unit_id, "kind": res["kind"], "cost_usd": str(_d(total)),
                     "breakdown": {c: str(_d(v)) for c, v in breakdown.items()}, "retry_estimate_usd": str(_d(retry_est)),
                     "per_model": per_model, "raw_usage": usage_by_model or {}, "raw_calls": calls_by_model or {}, "usage_scope": scope,
                     "usage_reconciliation": reconciliation, "inspect_total_cost_usd": str(_d(inspect_cost_total)) if inspect_cost_known else None,
                     "estimated": bool(estimated or retry_est > 0), "inferred": inferred,
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

    def effective_settlement(self, unit_id: str) -> dict:
        """The authoritative cost of one unit: the ledger's DERIVED settlement (manual resolutions applied: adjusted
        amount with previous_cost_usd / resolved_from, or the synthetic settlement of a resolved open reservation)
        plus the unit's raw events and its resolution for provenance. ``effective`` is None for an unsettled unit."""
        state = self._read()
        d = self._derive(state["entries"])
        return {"unit_id": unit_id, "effective": d["settled"].get(unit_id), "open": unit_id in d["open_reservations"], "review_pending": unit_id in d["review_pending"],
                "resolution": d["resolutions"].get(unit_id), "events": [e for e in state["entries"] if e.get("unit_id") == unit_id]}

    def units_for_run(self, run_uuid: str, generation_unit_id: str | None = None) -> dict:
        """Every event of the units that belong to one model run: judge units are named '<run_uuid>:judge:<ts>';
        the generation unit is named by the run's ledger binding. Grouped by unit with its derived state."""
        state = self._read()
        d = self._derive(state["entries"])
        prefix = f"{run_uuid}:judge:"
        units: dict[str, dict] = {}
        for e in state["entries"]:
            uid = e.get("unit_id")
            if uid and (uid.startswith(prefix) or (generation_unit_id and uid == generation_unit_id)):
                units.setdefault(uid, {"events": [], "kind": None})["events"].append(e)
        for uid, u in units.items():
            u["kind"] = next((e.get("kind") for e in u["events"] if e.get("kind")), None)
            u["open"] = uid in d["open_reservations"]
            u["settled"] = uid in d["settled"]
            u["voided"] = uid in d["voided"]
            u["review_pending"] = uid in d["review_pending"]
            u["resolution"] = (d["resolutions"].get(uid) or {}).get("resolution")
        return {"units": units, "judge_units": sorted(u for u in units if u.startswith(prefix)), "open": sorted(u for u, v in units.items() if v["open"]),
                "review_pending": sorted(u for u, v in units.items() if v["review_pending"]), "unresolvable": sorted(u for u, v in units.items() if v["resolution"] == "unresolvable")}

    def resolve_manually(self, unit_id: str, *, resolution: str, by: str, basis: str, amount_usd=None, currency: str = "USD", inferred: dict | None = None) -> dict:
        """Append a human reconciliation of one unit (never overwrites an event). settled_amount must carry the verified
        amount; it closes an open reservation at that amount or adjusts an estimated settlement and lifts that unit's hold.
        With ``inferred`` (a dict with its calculation ``basis``), the amount is an inferred, not provider-confirmed figure
        the human authorized: the unit stays estimated and flagged inferred, and the reconciliation requirement travels
        with it. unresolvable records the investigation and changes no balance, hold or reservation."""
        if resolution not in RESOLUTIONS:
            raise LedgerConflict(f"resolution must be one of {RESOLUTIONS}")
        if inferred is not None and (resolution != "settled_amount" or not isinstance(inferred, dict) or not inferred.get("basis")):
            raise LedgerConflict("an inferred resolution is a settled_amount carrying its calculation basis")
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id not in d["open_reservations"] and unit_id not in d["settled"]:
                raise LedgerConflict(f"unit {unit_id} has no reservation or settlement to resolve")
            if unit_id in d["resolutions"] and d["resolutions"][unit_id]["resolution"] == "settled_amount":
                raise LedgerConflict(f"unit {unit_id} already resolved with a verified amount")
            entry = {"type": "manual_resolution", "unit_id": unit_id, "resolution": resolution, "by": str(by), "basis": str(basis), "at": _now()}
            if resolution == "settled_amount":
                if amount_usd is None:
                    raise LedgerConflict("settled_amount needs amount_usd")
                entry.update({"amount_usd": str(_money_in(amount_usd, "amount_usd")), "currency": currency})
            if inferred is not None:
                entry["inferred"] = dict(inferred)
            return self._append(state, entry)

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


def model_usage_to_dict(usage) -> dict | None:
    """The one Inspect ModelUsage -> ledger usage mapping (uncached input, output, cache read, cache write; None -> 0).
    ModelUsage.input_tokens excludes cached tokens; cache reads and writes are separate fields."""
    if usage is None:
        return None
    return {"input_tokens": int(getattr(usage, "input_tokens", 0) or 0), "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "cache_read_tokens": int(getattr(usage, "input_tokens_cache_read", 0) or 0), "cache_write_tokens": int(getattr(usage, "input_tokens_cache_write", 0) or 0)}


def usage_from_eval_sample(sample) -> tuple[dict, dict]:
    """({model: aggregated usage}, {model: retries}) from an Inspect EvalSample. Retries come from ModelEvent.retries."""
    usage = {}
    for model, u in (getattr(sample, "model_usage", None) or {}).items():
        usage[model] = model_usage_to_dict(u)
    retries: dict[str, int] = {}
    for e in getattr(sample, "events", []) or []:
        if getattr(e, "event", None) == "model" and getattr(e, "retries", None):
            retries[e.model] = retries.get(e.model, 0) + int(e.retries)
    return usage, retries


def model_events_usage(sample) -> dict:
    """Per-call usage from the ModelEvents of an Inspect EvalSample, with completeness: {"calls": {model: [usage]},
    "unknown_calls": n, "total_calls": m}. A model event without usage is COUNTED (unknown cost), never skipped."""
    calls: dict[str, list[dict]] = {}
    unknown, total = 0, 0
    for e in getattr(sample, "events", []) or []:
        if getattr(e, "event", None) != "model":
            continue
        total += 1
        u = getattr(getattr(e, "output", None), "usage", None)
        if u is None:
            unknown += 1
            continue
        rec = model_usage_to_dict(u)
        tc = getattr(u, "total_cost", None)
        if isinstance(tc, (int, float)):
            rec["total_cost"] = float(tc)  # Inspect's own pricing of this call (TTL-aware); kept as a floor
        calls.setdefault(e.model, []).append(rec)
    return {"calls": calls, "unknown_calls": unknown, "total_calls": total}


# the HTTP status token that directly follows the exception name on an exception line, e.g.
# "google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED" or "openai.InternalServerError: Error code: 502 - ..."
_STATUS_LINE = re.compile(r"(?:ClientError|ServerError|APIError|APIStatusError|RateLimitError|InternalServerError):\s*(?:Error code:\s*)?(\d{3})\b")


def _attempt_status(text: str) -> int | None:
    """Status code of the LAST exception line in a recorded traceback / error text (the exception actually raised)."""
    codes = [int(m.group(1)) for m in (_STATUS_LINE.search(line) for line in str(text or "").splitlines()) if m]
    return codes[-1] if codes else None


def recovered_attempts(sample) -> dict:
    """Usage-less model attempts of an EvalSample and whether each is a RECOVERED HTTP 429 / 5xx attempt (approved
    2026-11-01 for the Gemini dev and validation classes): the status code read from the recorded exception line of the
    attempt's traceback (e.g. ``google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED``), a later model call of the
    sample with reported usage (Inspect retried and the turn went on), and the attempt's output absent from the
    transcript. Returns {"unknown": n, "recovered": k, "attempts": [{"index", "status", "recovered"}]}."""
    evs = [e for e in (getattr(sample, "events", None) or []) if getattr(e, "event", None) == "model"]
    asst = {getattr(m, "id", None) for m in (getattr(sample, "messages", None) or []) if getattr(m, "role", None) == "assistant"}
    out = {"unknown": 0, "recovered": 0, "attempts": []}
    for i, e in enumerate(evs):
        if getattr(getattr(e, "output", None), "usage", None) is not None:
            continue
        out["unknown"] += 1
        code = _attempt_status(getattr(e, "traceback", None) or getattr(e, "error", None) or "")
        later = any(getattr(getattr(x, "output", None), "usage", None) is not None for x in evs[i + 1:])
        choices = getattr(getattr(e, "output", None), "choices", None) or []
        in_transcript = bool(choices) and getattr(getattr(choices[0], "message", None), "id", None) in asst
        rec = code is not None and (code == 429 or 500 <= code <= 599) and later and not in_transcript
        out["attempts"].append({"index": i, "status": code, "recovered": bool(rec)})
        out["recovered"] += int(bool(rec))
    return out


def calls_from_eval_sample(sample) -> dict:
    """{model: [per-call usage]} from the ModelEvents of an Inspect EvalSample (for per-call tiering); see
    model_events_usage for the completeness counts."""
    return model_events_usage(sample)["calls"]
