"""Fixed, verdict-independent human review queue (policy adopted 2026-11-01 on the human's instruction; it replaces the
earlier outcome-driven selection and was not preregistered before that date; some grader outputs had already been
inspected during calibration).

Per task, the queue holds:
- every preregistered critical rubric item (deterministic, judge or visual), taken from the union of the task's
  preregistered critical definition (CRITICAL_PREREGISTERED where a task revised it, otherwise CRITICAL) and its
  current one;
- every designated human-scored visual item (V_ITEMS);
- five deterministic items drawn at random from the remaining D_ITEMS;
- five judge-only items drawn at random from the remaining J_ITEMS.

A pool with fewer than five remaining items is taken whole and the shortfall is reported. Items are deduplicated, and
an item in several categories is listed once with all of them.

Inputs, and nothing else: the task module's item lists and critical mappings, the rubric's length (from the rubric
file) and the recorded seed. No grade, verdict, judge output, `cannot_assess` status or model output is read.

The frozen queue (grading/review_queue/queue_v1.json) records the membership, seed, algorithm, timestamp and the hashes
of the inputs. Usage: python -m grading.review_queue freeze --seed 20261101 --out grading/review_queue/queue_v1.json."""
import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_VERSION = "review-queue-2026-11-01.1"
SAMPLE_D, SAMPLE_J = 5, 5
ALGORITHM = ("per task: rng = random.Random(int(sha256(f'{seed}:{task_id}').hexdigest()[:16], 16)); selected = critical items "
             "(union of the preregistered and current definitions) | visual items; D pool = sorted(D_ITEMS - selected); "
             "J pool = sorted(J_ITEMS - selected); random_D = sorted(rng.sample(D pool, min(5, len))); then random_J = sorted(rng.sample(J pool, min(5, len)))")


def task_module(task_id: str):
    return importlib.import_module(f"grading.checks_{task_id[:8]}")


def rubric_length(task_id: str) -> int:
    with open(os.path.join(ROOT, "private", "rubric", f"{task_id}.json"), encoding="utf-8") as f:
        return len(json.load(f))


def _critical_items(spec: dict) -> dict:
    out = {}
    for cid, s in spec.items():
        for i in list(s.get("items", [])) + list(s.get("judge_items", [])) + list(s.get("visual_items", [])):
            out.setdefault(i, set()).add(cid)
    return out


def build_queue(task_id: str, seed: int, *, module=None, n_items: int | None = None) -> dict:
    ck = module or task_module(task_id)
    n = n_items if n_items is not None else rubric_length(task_id)
    pre = getattr(ck, "CRITICAL_PREREGISTERED", None) or ck.CRITICAL
    crit = _critical_items(pre)
    for i, cids in _critical_items(ck.CRITICAL).items():
        crit.setdefault(i, set()).update(cids)
    cats: dict[int, list[str]] = {}
    for i in sorted(crit):
        cats.setdefault(i, []).append("critical:" + "+".join(sorted(crit[i])))
    for i in sorted(getattr(ck, "V_ITEMS", []) or []):
        cats.setdefault(i, []).append("visual")
    rng = random.Random(int(hashlib.sha256(f"{seed}:{task_id}".encode()).hexdigest()[:16], 16))
    d_pool = sorted(set(ck.D_ITEMS) - set(cats))
    rd = sorted(rng.sample(d_pool, min(SAMPLE_D, len(d_pool))))
    j_pool = sorted(set(ck.J_ITEMS) - set(cats))
    rj = sorted(rng.sample(j_pool, min(SAMPLE_J, len(j_pool))))
    for i in rd:
        cats.setdefault(i, []).append("random_deterministic")
    for i in rj:
        cats.setdefault(i, []).append("random_judge")
    bad = [i for i in cats if not 1 <= i <= n]
    if bad:
        raise ValueError(f"{task_id}: queue items outside the rubric 1..{n}: {bad}")
    counts = {"critical": len(crit), "visual": len(getattr(ck, "V_ITEMS", []) or []), "random_deterministic": len(rd), "random_judge": len(rj), "total_unique": len(cats)}
    shortfall = {k: SAMPLE_D - v for k, v in (("random_deterministic", len(rd)), ("random_judge", len(rj))) if v < SAMPLE_D}
    return {"task_id": task_id, "rubric_items": n, "items": [{"item": i, "categories": cats[i]} for i in sorted(cats)], "counts": counts, "shortfall": shortfall,
            "pools": {"deterministic_remaining": len(d_pool), "judge_remaining": len(j_pool)}}


def input_hashes(task_ids: list[str]) -> dict:
    """SHA-256 of the selection inputs: this module, each task module, each rubric file."""
    def sha(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    out = {"grading/review_queue.py": sha(os.path.abspath(__file__))}
    for t in task_ids:
        out[f"grading/checks_{t[:8]}.py"] = sha(os.path.join(ROOT, "grading", f"checks_{t[:8]}.py"))
        out[f"private/rubric/{t}.json"] = sha(os.path.join(ROOT, "private", "rubric", f"{t}.json"))
    return out


def freeze(seed: int, out_path: str, task_ids: list[str] | None = None) -> dict:
    from .grade import TASK_MODULES
    task_ids = sorted(task_ids or TASK_MODULES)
    queues = {t: build_queue(t, seed) for t in task_ids}
    rec = {"policy_version": POLICY_VERSION, "adopted": "2026-11-01, on the human's instruction; replaces the outcome-driven selection; not preregistered before this date",
           "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seed": seed, "algorithm": ALGORITHM, "sample_sizes": {"deterministic": SAMPLE_D, "judge": SAMPLE_J},
           "inputs_sha256": input_hashes(task_ids), "verdict_independent": "membership is computed from the inputs above only; no grade, verdict, judge output or model output is read",
           "queues": queues}
    if os.path.exists(out_path):
        raise FileExistsError(f"{out_path} exists; a frozen queue is never overwritten (write a new version)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    return rec


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify(path: str) -> dict:
    """Recompute every task's queue from the recorded seed and the current inputs; report any difference."""
    rec = load(path)
    diffs = {t: True for t, q in rec["queues"].items() if build_queue(t, rec["seed"]) != q}
    return {"path": path, "seed": rec["seed"], "tasks": len(rec["queues"]), "reproduced": not diffs, "differs": sorted(diffs),
            "inputs_changed": sorted(k for k, v in input_hashes(sorted(rec["queues"])).items() if rec["inputs_sha256"].get(k) != v)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fixed, verdict-independent human review queue")
    ap.add_argument("command", choices=("freeze", "verify", "show"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "grading", "review_queue", "queue_v1.json"))
    args = ap.parse_args(argv)
    if args.command == "freeze":
        if args.seed is None:
            raise SystemExit("freeze needs --seed (recorded in the queue)")
        rec = freeze(args.seed, args.out)
        print(json.dumps({t: q["counts"] | ({"shortfall": q["shortfall"]} if q["shortfall"] else {}) for t, q in rec["queues"].items()}, indent=1))
    elif args.command == "verify":
        print(json.dumps(verify(args.out), indent=1))
    else:
        rec = load(args.out)
        print(json.dumps({t: [(x["item"], x["categories"]) for x in q["items"]] for t, q in rec["queues"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
