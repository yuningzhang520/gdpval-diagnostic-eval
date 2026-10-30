"""Persistent pilot budget ledger: reservations before a unit starts, settlements from actual
usage after it ends, and the approved stop conditions.

A *unit* is one sample execution or one independent judge batch. The launcher calls
``reserve()`` before starting a unit (refused when the remaining budget cannot cover the
estimate), ``settle()`` after it ends (actual usage x unit prices, split by category, released
exactly once), or ``void()`` when the unit never started. Totals are always recomputed from the
append-only entry list, so a restart loses nothing and never double-counts. Writes are atomic
(temporary file + rename + fsync) under an advisory file lock. The ledger bounds what may be
*started*; a unit already running can still take the cumulative actual cost above the ceiling,
so the ceiling is not an absolute billing cap. Reservation atomicity under concurrency above one
is not yet verified (formal-run gate).

Costs are in USD, computed with Decimal from prices per million tokens. Categories: input,
output, cache_read, cache_write, judge (the same four for judge units), billable retries.
Retry usage that cannot be isolated is recorded as an estimate (``retry_estimate_usd``) with the
rule used, never as a measured figure.
"""
import datetime as dt
import fcntl
import json
import os
import secrets
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.000001")
CATEGORIES = ("input", "output", "cache_read", "cache_write")


class BudgetError(Exception):
    """Base class for ledger refusals."""


class BudgetExhausted(BudgetError):
    """Remaining budget cannot cover the requested reservation; the unit must not start."""


class LedgerConflict(BudgetError):
    """The requested change contradicts the recorded history (settled unit, mismatched kind, ...)."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _d(x) -> Decimal:
    return Decimal(str(x)).quantize(MONEY, rounding=ROUND_HALF_UP)


def usage_cost(usage: dict, price: dict) -> dict:
    """usage: input_tokens (uncached), output_tokens, cache_read_tokens, cache_write_tokens;
    price: USD per million tokens for input, output, cache_read, cache_write. Missing price
    fields are treated as the input price (conservative) and flagged."""
    out, flags = {}, []
    for cat, tok_key in (("input", "input_tokens"), ("output", "output_tokens"),
                         ("cache_read", "cache_read_tokens"), ("cache_write", "cache_write_tokens")):
        tokens = int(usage.get(tok_key, 0) or 0)
        if cat in price and price[cat] is not None:
            rate = Decimal(str(price[cat]))
        else:
            rate = Decimal(str(price.get("input", 0)))
            if tokens:
                flags.append(f"no {cat} price; charged at the input rate")
        out[cat] = _d(Decimal(tokens) * rate / Decimal(1_000_000))
    out["total"] = _d(sum(out[c] for c in CATEGORIES))
    out["flags"] = flags
    return out


class BudgetLedger:
    def __init__(self, path: str, ceiling_usd, prices: dict | None = None, label: str = "pilot"):
        self.path = os.path.realpath(path)
        self.lock_path = self.path + ".lock"
        self.ceiling = _d(ceiling_usd)
        self.prices = prices or {}
        self.label = label
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"version": 1, "label": label, "ceiling_usd": str(self.ceiling), "created_at": _now(), "entries": []})
        else:
            state = self._read()
            if _d(state["ceiling_usd"]) != self.ceiling:
                raise LedgerConflict(f"ledger ceiling {state['ceiling_usd']} differs from configured {self.ceiling}; refuse to continue silently")

    # ------------------------------------------------------------------ persistence
    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

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

    # ------------------------------------------------------------------ derived totals
    @staticmethod
    def _derive(entries: list[dict]) -> dict:
        open_res: dict[str, dict] = {}
        settled: dict[str, dict] = {}
        voided: set[str] = set()
        settled_total = Decimal(0)
        estimated_total = Decimal(0)
        by_cat: dict[str, Decimal] = {c: Decimal(0) for c in CATEGORIES}
        by_cat.update({"judge": Decimal(0), "retry_estimate": Decimal(0)})
        for e in entries:
            if e["type"] == "reservation":
                open_res[e["unit_id"]] = e
            elif e["type"] == "settlement":
                open_res.pop(e["unit_id"], None)
                settled[e["unit_id"]] = e
                settled_total += Decimal(e["cost_usd"])
                if e.get("estimated"):
                    estimated_total += Decimal(e["cost_usd"])
                for c in CATEGORIES:
                    by_cat[c] += Decimal(e["breakdown"].get(c, "0"))
                if e["kind"] == "judge":
                    by_cat["judge"] += Decimal(e["cost_usd"]) - Decimal(e.get("retry_estimate_usd", "0"))
                by_cat["retry_estimate"] += Decimal(e.get("retry_estimate_usd", "0"))
            elif e["type"] == "void":
                open_res.pop(e["unit_id"], None)
                voided.add(e["unit_id"])
        reserved_total = sum((Decimal(r["estimated_usd"]) for r in open_res.values()), Decimal(0))
        return {"open_reservations": open_res, "settled": settled, "voided": voided, "settled_total": settled_total,
                "reserved_total": reserved_total, "estimated_total": estimated_total, "by_category": by_cat}

    def snapshot(self) -> dict:
        state = self._read()
        d = self._derive(state["entries"])
        remaining = self.ceiling - d["settled_total"] - d["reserved_total"]
        return {"ceiling_usd": str(self.ceiling), "settled_usd": str(_d(d["settled_total"])), "reserved_usd": str(_d(d["reserved_total"])),
                "remaining_usd": str(_d(remaining)), "estimated_portion_usd": str(_d(d["estimated_total"])),
                "by_category_usd": {k: str(_d(v)) for k, v in d["by_category"].items()},
                "open_reservations": sorted(d["open_reservations"]), "settled_units": sorted(d["settled"]), "voided_units": sorted(d["voided"]),
                "entries": len(state["entries"])}

    def remaining(self) -> Decimal:
        return Decimal(self.snapshot()["remaining_usd"])

    def can_start(self, estimated_usd) -> bool:
        return _d(estimated_usd) <= self.remaining()

    # ------------------------------------------------------------------ mutations
    def reserve(self, unit_id: str, kind: str, estimated_usd, meta: dict | None = None) -> dict:
        """Reserve before a unit starts. Idempotent for an open reservation of the same unit;
        refuses a unit that was already settled or voided; refuses when the remaining budget
        (ceiling - settled - open reservations) cannot cover the estimate."""
        if kind not in ("sample", "judge"):
            raise LedgerConflict(f"unknown unit kind {kind!r}")
        est = _d(estimated_usd)
        if est < 0:
            raise LedgerConflict("negative estimate")
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id in d["settled"]:
                raise LedgerConflict(f"unit {unit_id} is already settled")
            if unit_id in d["voided"]:
                raise LedgerConflict(f"unit {unit_id} was voided; use a new unit id")
            existing = d["open_reservations"].get(unit_id)
            if existing:
                if existing["kind"] != kind:
                    raise LedgerConflict(f"unit {unit_id} reserved as {existing['kind']}")
                return existing
            remaining = self.ceiling - d["settled_total"] - d["reserved_total"]
            if est > remaining:
                raise BudgetExhausted(f"remaining {remaining} USD cannot cover reservation {est} USD for {kind} {unit_id}")
            entry = {"type": "reservation", "unit_id": unit_id, "kind": kind, "estimated_usd": str(est), "at": _now(), "meta": meta or {}}
            state["entries"].append(entry)
            self._write(state)
            return entry

    def settle(self, unit_id: str, usage_by_model: dict, *, retries_by_model: dict | None = None, note: str = "",
               estimated: bool = False, fallback_to_reservation: bool = False) -> dict:
        """Settle a unit from actual usage ({model: usage dict}); releases its reservation exactly
        once. A second settlement of the same unit returns the first and changes nothing.
        ``retries_by_model`` ({model: retry count}) adds a conservative estimate: each retry is
        charged one more time the unit's uncached input cost for that model (the provider's own
        billing of failed attempts cannot be observed), flagged as an estimate.
        ``fallback_to_reservation`` settles a unit with no usable usage at its reserved amount,
        flagged as estimated (never silently as zero)."""
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
            for model, usage in (usage_by_model or {}).items():
                price = self.prices.get(model)
                if price is None:
                    flags.append(f"no price for {model}; settlement uses the reservation amount as a conservative figure")
                    estimated = True
                    continue
                cost = usage_cost(usage, price)
                per_model[model] = {k: str(v) for k, v in cost.items() if k != "flags"} | {"flags": cost["flags"]}
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
            if (not usage_by_model or any(self.prices.get(m) is None for m in usage_by_model)) and fallback_to_reservation:
                total = max(total, Decimal(res["estimated_usd"]))
                estimated = True
                flags.append("settled at the reserved amount (conservative)")
            elif not usage_by_model and not fallback_to_reservation:
                raise LedgerConflict("no usage given; pass fallback_to_reservation=True to settle conservatively or void() a unit that never ran")
            entry = {"type": "settlement", "unit_id": unit_id, "kind": res["kind"], "cost_usd": str(_d(total)),
                     "breakdown": {c: str(_d(v)) for c, v in breakdown.items()}, "retry_estimate_usd": str(_d(retry_est)),
                     "per_model": per_model, "estimated": bool(estimated or retry_est > 0), "flags": flags, "note": note,
                     "reserved_usd": res["estimated_usd"], "at": _now()}
            state["entries"].append(entry)
            self._write(state)
            return entry

    def void(self, unit_id: str, reason: str) -> dict:
        """Release the reservation of a unit that never started (no usage possible)."""
        with self._locked():
            state = self._read()
            d = self._derive(state["entries"])
            if unit_id in d["settled"]:
                raise LedgerConflict(f"unit {unit_id} is settled; cannot void")
            if unit_id not in d["open_reservations"]:
                raise LedgerConflict(f"unit {unit_id} has no open reservation")
            entry = {"type": "void", "unit_id": unit_id, "reason": reason, "at": _now()}
            state["entries"].append(entry)
            self._write(state)
            return entry

    # ------------------------------------------------------------------ stop conditions
    def stop_reasons(self, *, next_estimate_usd=None, per_task_costs: dict | None = None, per_task_estimate_usd=None,
                     engineering_failures: dict | None = None) -> list[str]:
        """Approved stop conditions. Returns the reasons that currently apply (empty = may continue)."""
        reasons = []
        snap = self.snapshot()
        remaining = Decimal(snap["remaining_usd"])
        if remaining <= 0:
            reasons.append(f"budget ceiling reached (remaining {remaining} USD)")
        if next_estimate_usd is not None and _d(next_estimate_usd) > remaining:
            reasons.append(f"remaining {remaining} USD cannot cover the next reservation {_d(next_estimate_usd)} USD")
        if per_task_costs and per_task_estimate_usd is not None:
            for task, cost in per_task_costs.items():
                if Decimal(str(cost)) > 2 * _d(per_task_estimate_usd):
                    reasons.append(f"task {task} cost {cost} USD exceeds 2x the estimate {_d(per_task_estimate_usd)} USD")
        for cls, n in (engineering_failures or {}).items():
            if n >= 2:
                reasons.append(f"engineering failure class {cls!r} occurred {n} times")
        return reasons


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
    """Map an Inspect EvalSample to ({model: usage}, {model: retries}) for settle().
    ModelUsage.input_tokens excludes cached tokens; cache reads and writes are separate fields.
    Retries come from ModelEvent.retries (count only; failed attempts' usage is unobservable)."""
    usage = {}
    for model, u in (sample.model_usage or {}).items():
        usage[model] = {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
                        "cache_read_tokens": u.input_tokens_cache_read or 0, "cache_write_tokens": u.input_tokens_cache_write or 0}
    retries: dict[str, int] = {}
    for e in getattr(sample, "events", []) or []:
        if getattr(e, "event", None) == "model" and getattr(e, "retries", None):
            retries[e.model] = retries.get(e.model, 0) + int(e.retries)
    return usage, retries
