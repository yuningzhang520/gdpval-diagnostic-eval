"""Cost accounting: generation cost per run from recorded usage x unit prices (the ledger's
settlement when available) and grading cost from judge usage. Everything is labelled by its source;
nothing here estimates what was not measured. Human review time is recorded by the reviewer in the
run's cost record (run_cost_record human_minutes), not generated here."""
import datetime as dt
import os

from harness.budget import usage_cost


def generation_cost(usage_by_model: dict, prices: dict, retries_by_model: dict | None = None) -> dict:
    """usage_by_model: {model: {input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}}."""
    out = {"per_model": {}, "total_usd": "0", "flags": [], "retry_estimate_usd": "0"}
    total = 0
    retry_est = 0
    for model, usage in usage_by_model.items():
        price = prices.get(model)
        if price is None:
            out["flags"].append(f"no price for {model}: cost unknown")
            out["per_model"][model] = {"status": "unknown_price", "usage": usage}
            continue
        c = usage_cost(usage, price)
        out["per_model"][model] = {k: str(v) for k, v in c.items() if k != "flags"} | {"flags": c["flags"], "usage": usage}
        total += c["total"]
        n = (retries_by_model or {}).get(model, 0)
        if n:
            retry_est += c["input"] * n
            out["flags"].append(f"{model}: {n} retried request(s) estimated at {n} x uncached input cost")
    out["total_usd"] = str(total)
    out["retry_estimate_usd"] = str(retry_est)
    out["total_with_retry_estimate_usd"] = str(total + retry_est)
    out["estimated"] = bool(out["flags"])
    return out


def grading_cost(judge_usage_by_model: dict, prices: dict) -> dict:
    c = generation_cost(judge_usage_by_model, prices)
    c["kind"] = "judge"
    return c


def run_cost_record(run_uuid: str, generation: dict, grading: dict | None, human_minutes: float | None = None) -> dict:
    return {"run_uuid": run_uuid, "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "generation": generation,
            "grading": grading, "human_minutes": human_minutes, "human_minutes_source": "recorded by the reviewer" if human_minutes is not None else "not recorded"}
