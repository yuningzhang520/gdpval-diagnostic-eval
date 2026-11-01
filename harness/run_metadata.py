"""Run-level metadata of one unit's Inspect log: counts and enumerated types only (trusted host side, never
model-visible). Permitted before a task's grader reveal and for sealed validation units: message counts by role,
model-call and tool-call counts, tool calls by tool name, tool errors by tool name and Inspect error type, error
streaks, tool calls per model turn, and the sample's limit event. Never returned or printed: tool arguments, tool
outputs, message text, reasoning, error messages, file content. Inspect's bash and python tools report a non-zero
exit status inside the tool output, not as a tool error, so failed shell commands are not visible here.

Suspected tool-error loop (stop rule for the Gemini batches, 2026-11-01): at least LOOP_STREAK consecutive tool
calls that ended in an Inspect tool error, or at least LOOP_MIN_ERRORS tool errors that make up at least
LOOP_ERROR_SHARE of all tool calls. A suspected loop stops further Gemini launches for human review; it never
changes the unit's recorded outcome.

Usage: python -m harness.run_metadata <path to .eval>   (prints the JSON summary)"""
import json
import sys
from collections import Counter

LOOP_STREAK = 10
LOOP_MIN_ERRORS = 20
LOOP_ERROR_SHARE = 0.5
RULE_VERSION = "tool-error-loop-2026-11-01.1"


def summarize_sample(sample) -> dict:
    roles = Counter(getattr(m, "role", "unknown") for m in (getattr(sample, "messages", None) or []))
    per_turn = [len(getattr(m, "tool_calls", None) or []) for m in (getattr(sample, "messages", None) or []) if getattr(m, "role", None) == "assistant"]
    model_calls = model_errors = 0
    tools, tool_errors = Counter(), Counter()
    streak = longest = same_streak = longest_same = 0
    last_key = None
    for ev in getattr(sample, "events", None) or []:
        kind = getattr(ev, "event", None)
        if kind == "model":
            model_calls += 1
            if getattr(ev, "error", None):
                model_errors += 1
        elif kind == "tool":
            name = getattr(ev, "function", None) or "unknown"
            tools[name] += 1
            err = getattr(ev, "error", None)
            if err is not None:
                key = f"{name}:{getattr(err, 'type', 'unknown')}"
                tool_errors[key] += 1
                streak += 1
                same_streak = same_streak + 1 if key == last_key else 1
                last_key = key
            else:
                streak = same_streak = 0
                last_key = None
            longest, longest_same = max(longest, streak), max(longest_same, same_streak)
    n_tools, n_errors = sum(tools.values()), sum(tool_errors.values())
    limit = getattr(sample, "limit", None)
    suspected = longest >= LOOP_STREAK or (n_errors >= LOOP_MIN_ERRORS and n_tools and n_errors / n_tools >= LOOP_ERROR_SHARE)
    return {
        "rule_version": RULE_VERSION,
        "messages": {"total": sum(roles.values()), "by_role": dict(sorted(roles.items()))},
        "model_calls": model_calls, "model_call_errors": model_errors,
        "tool_calls": n_tools, "tool_calls_by_name": dict(sorted(tools.items())),
        "tool_errors": n_errors, "tool_errors_by_name_and_type": dict(sorted(tool_errors.items())),
        "longest_error_streak": longest, "longest_same_error_streak": longest_same,
        "tool_calls_per_turn": {"turns": len(per_turn), "mean": round(sum(per_turn) / len(per_turn), 3) if per_turn else None, "max": max(per_turn) if per_turn else None,
                                "distribution": dict(sorted(Counter(per_turn).items()))},
        "limit": {"type": getattr(limit, "type", None), "limit": getattr(limit, "limit", None)} if limit is not None else None,
        "suspected_tool_error_loop": bool(suspected),
        "loop_rule": {"streak": LOOP_STREAK, "min_errors": LOOP_MIN_ERRORS, "error_share": LOOP_ERROR_SHARE},
    }


def summarize_log(path: str) -> dict:
    from inspect_ai.log import read_eval_log
    log = read_eval_log(path)
    samples = list(log.samples or [])
    if len(samples) != 1:
        return {"log_samples": len(samples), "error": "expected exactly one sample"}
    cfg = getattr(log.eval, "config", None)
    return {"log_status": log.status, "config_message_limit": getattr(cfg, "message_limit", None), "config_token_limit": getattr(cfg, "token_limit", None),
            "config_time_limit": getattr(cfg, "time_limit", None), "config_cost_limit": getattr(cfg, "cost_limit", None), **summarize_sample(samples[0])}


if __name__ == "__main__":
    print(json.dumps(summarize_log(sys.argv[1]), indent=1, default=str))
