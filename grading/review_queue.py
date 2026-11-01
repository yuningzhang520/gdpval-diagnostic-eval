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
    ap.add_argument("command", choices=("freeze", "verify", "show", "freeze-v2", "verify-v2", "freeze-v3", "verify-v3"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "grading", "review_queue", "queue_v1.json"))
    args = ap.parse_args(argv)
    if args.command in ("freeze-v3", "verify-v3"):
        out = args.out if args.out != os.path.join(ROOT, "grading", "review_queue", "queue_v1.json") else os.path.join(ROOT, "grading", "review_queue", "queue_v3.json")
        if args.command == "freeze-v3":
            if args.seed is None:
                raise SystemExit("freeze-v3 needs --seed (recorded in the queue)")
            rec = freeze_v3(args.seed, out)
            print(json.dumps({"dev_tasks": rec["dev_tasks"], "workload_total": rec["workload_total"]}, indent=1))
        else:
            print(json.dumps(verify_v3(out), indent=1))
        return 0
    if args.command in ("freeze-v2", "verify-v2"):
        out = args.out if args.out != os.path.join(ROOT, "grading", "review_queue", "queue_v1.json") else os.path.join(ROOT, "grading", "review_queue", "queue_v2.json")
        if args.command == "freeze-v2":
            if args.seed is None:
                raise SystemExit("freeze-v2 needs --seed (recorded in the queue)")
            rec = freeze_v2(args.seed, out)
            print(json.dumps(rec["workload"], indent=1))
        else:
            print(json.dumps(verify_v2(out), indent=1))
        return 0
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



# ============================================================================= policy v2 (amended 2026-11-01)
POLICY_VERSION_V2 = "review-queue-2026-11-01.2"
FULL_CALIBRATION_TASKS = ("f841ddcf-2a28-4f6d-bac3-61b607219d3e", "47ef842d-8eac-4b90-bda8-dd934c228c96", "1137e2bb-bdf9-4876-b572-f29b7de5e595",
                          "2ea2e5b5-257f-42e6-a7dc-93763f28b19d", "a45bc83b-22f9-4def-8d89-9c5661b2b86f")
FULL_CALIBRATION_RATIONALE = ("chosen for deliverable-type coverage, not for grader performance: three xlsx tasks with dev outputs available "
                              "(f841ddcf, 47ef842d, 1137e2bb), one pptx (2ea2e5b5), one docx/pdf (a45bc83b)")
SAMPLE_V2 = 3
ALGORITHM_V2 = ("per task and phase: rng = random.Random(int(sha256(f'{seed}:{phase}:{task_id}').hexdigest()[:16], 16)). "
                "critical = union of the preregistered and current definitions; non-critical pools exclude critical and visual items. "
                "dev/full: every critical criterion at criterion level, every visual item, the v1 random picks (5 D + 5 J, seed 20261101, "
                "review-queue-2026-11-01.1), individual labels for items that differ between a criterion's preregistered and revised "
                "definition. dev/smoke: rng.choice of one critical criterion (sorted ids) and of one judge-only item (non-critical J pool, "
                "else any J item). validation and formal: every critical criterion, every visual item, rng.sample of 3 non-critical D and "
                "then 3 non-critical J (all when fewer), plus the differing items; formal uses the same item ids for both candidates.")


def criterion_definitions(task_id: str) -> dict:
    """{criterion id: {name, text}} parsed from the task's section of preregistration.md (read by the human packet only)."""
    import re
    with open(os.path.join(ROOT, "preregistration.md"), encoding="utf-8") as f:
        t = f.read()
    m = re.search(rf"\n### 2\.\d+ `{task_id}`(.*?)(?=\n### |\Z)", t, re.S)
    out = {}
    if m:
        for c in re.finditer(r"\n- (C\d+) ([^\n]*?)\((APPROVED[^)]*)\)\.?\s*(.*?)(?=\n- |\n### |\Z)", m.group(1), re.S):
            out[c.group(1)] = {"name": c.group(2).strip(), "approved": c.group(3), "text": re.sub(r"\s+", " ", c.group(4)).strip()}
    return out


def _members(spec: dict) -> list[int]:
    return sorted(set(spec.get("items", [])) | set(spec.get("judge_items", [])) | set(spec.get("visual_items", [])))


def build_plan_v2(task_id: str, seed: int, *, module=None, n_items: int | None = None) -> dict:
    ck = module or task_module(task_id)
    n = n_items if n_items is not None else rubric_length(task_id)
    cur, pre = ck.CRITICAL, getattr(ck, "CRITICAL_PREREGISTERED", None) or ck.CRITICAL
    crit_union = set(_critical_items(pre)) | set(_critical_items(cur))
    visual = sorted(getattr(ck, "V_ITEMS", []) or [])
    criteria = [{"id": cid, "members": _members(cur[cid]), **({"preregistered_members": _members(pre[cid])} if cid in pre and _members(pre[cid]) != _members(cur[cid]) else {})}
                for cid in sorted(cur, key=lambda c: int(c[1:]))]
    differing = sorted({i for c in criteria if "preregistered_members" in c for i in set(c["members"]) ^ set(c["preregistered_members"])})
    d_pool = sorted(set(ck.D_ITEMS) - crit_union - set(visual))
    j_pool = sorted(set(ck.J_ITEMS) - crit_union - set(visual))

    def rng(phase):
        return random.Random(int(hashlib.sha256(f"{seed}:{phase}:{task_id}".encode()).hexdigest()[:16], 16))

    def item_rows(cat_map):
        return [{"item": i, "categories": sorted(set(cs))} for i, cs in sorted(cat_map.items())]

    phases = {}
    if task_id in FULL_CALIBRATION_TASKS:
        v1 = build_queue(task_id, 20261101, module=ck, n_items=n)
        cats = {}
        for i in visual:
            cats.setdefault(i, []).append("visual")
        for x in v1["items"]:
            for c in x["categories"]:
                if c in ("random_deterministic", "random_judge"):
                    cats.setdefault(x["item"], []).append(c + " (v1 pick)")
        for i in differing:
            cats.setdefault(i, []).append("sensitivity: differs between the preregistered and revised criterion")
        phases["dev"] = {"mode": "full", "evidence_class": "dev calibration (labels inform the judge prompt; not held-out agreement)",
                         "criteria": [c["id"] for c in criteria], "items": item_rows(cats)}
    else:
        r = rng("dev")
        cids = sorted(cur, key=lambda c: int(c[1:]))
        pick_c = r.choice(cids) if cids else None
        jp = j_pool or sorted(ck.J_ITEMS)
        pick_j = r.choice(jp) if jp else None
        cats = {}
        if pick_j is not None:
            cats[pick_j] = ["smoke: judge-only item" + ("" if j_pool else " (critical member; no non-critical judge item)")]
        for i in differing if pick_c and any(c["id"] == pick_c and "preregistered_members" in c for c in criteria) else []:
            cats.setdefault(i, []).append("sensitivity: differs between the preregistered and revised criterion")
        phases["dev"] = {"mode": "smoke", "evidence_class": "exploratory calibration (not held-out agreement evidence)",
                         "criteria": [pick_c] if pick_c else [], "items": item_rows(cats),
                         "shortfall": {k: "none available" for k, v in (("judge_item", pick_j), ("critical_criterion", pick_c)) if v is None}}
    for phase in ("validation", "formal"):
        r = rng(phase)
        rd = sorted(r.sample(d_pool, min(SAMPLE_V2, len(d_pool))))
        rj = sorted(r.sample(j_pool, min(SAMPLE_V2, len(j_pool))))
        cats = {}
        for i in visual:
            cats.setdefault(i, []).append("visual")
        for i in rd:
            cats.setdefault(i, []).append("random_noncritical_deterministic")
        for i in rj:
            cats.setdefault(i, []).append("random_noncritical_judge")
        for i in differing:
            cats.setdefault(i, []).append("sensitivity: differs between the preregistered and revised criterion")
        phases[phase] = {"mode": "criteria+visual+3+3", "criteria": [c["id"] for c in criteria], "items": item_rows(cats),
                         "shortfall": {k: SAMPLE_V2 - v for k, v in (("random_noncritical_deterministic", len(rd)), ("random_noncritical_judge", len(rj))) if v < SAMPLE_V2},
                         **({"applies_to": "both candidates, identical item ids", "outputs": 2} if phase == "formal" else {"outputs": 1})}
    bad = [x["item"] for p in phases.values() for x in p["items"] if not 1 <= x["item"] <= n]
    if bad:
        raise ValueError(f"{task_id}: plan items outside 1..{n}: {bad}")
    return {"task_id": task_id, "rubric_items": n, "criteria": criteria, "visual_items": visual, "differing_items": differing,
            "pools": {"noncritical_deterministic": len(d_pool), "noncritical_judge": len(j_pool)}, "phases": phases}


def workload(plan: dict) -> dict:
    """Per phase: CSV labels (criteria + item rows, per output) and the evidence-review load: the distinct rubric items
    whose evidence a reviewer must examine (every member of each labelled criterion, judged on its full evidence, plus
    the labelled items), per output and in total."""
    members = {c["id"]: set(c["members"]) | set(c.get("preregistered_members", [])) for c in plan["criteria"]}
    out = {}
    for ph, p in plan["phases"].items():
        outputs = p.get("outputs", 1)
        evid = set().union(*[members[c] for c in p["criteria"]]) if p["criteria"] else set()
        evid |= {x["item"] for x in p["items"]}
        labels = len(p["criteria"]) + len(p["items"])
        out[ph] = {"mode": p["mode"], "outputs": outputs, "csv_labels_per_output": labels, "criterion_labels_per_output": len(p["criteria"]),
                   "item_labels_per_output": len(p["items"]), "evidence_items_per_output": len(evid), "csv_labels_total": labels * outputs, "evidence_items_total": len(evid) * outputs}
    return out


def freeze_v2(seed: int, out_path: str, task_ids: list[str] | None = None) -> dict:
    from .grade import TASK_MODULES
    task_ids = sorted(task_ids or TASK_MODULES)
    plans = {t: build_plan_v2(t, seed) for t in task_ids}
    rec = {"policy_version": POLICY_VERSION_V2, "amends": POLICY_VERSION + " (queue_v1.json, never labelled)",
           "adopted": "2026-11-01, on the human's instruction, before any human label; not preregistered",
           "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seed": seed, "algorithm": ALGORITHM_V2,
           "full_calibration_tasks": list(FULL_CALIBRATION_TASKS), "full_calibration_rationale": FULL_CALIBRATION_RATIONALE,
           "inputs_sha256": input_hashes(task_ids), "verdict_independent": "membership is computed from item lists, critical mappings, visual categories and the seed only",
           "plans": plans, "workload": {t: workload(p) for t, p in plans.items()}}
    if os.path.exists(out_path):
        raise FileExistsError(f"{out_path} exists; a frozen queue is never overwritten (write a new version)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    return rec


def verify_v2(path: str) -> dict:
    rec = load(path)
    diffs = sorted(t for t, p in rec["plans"].items() if build_plan_v2(t, rec["seed"]) != p)
    return {"path": path, "seed": rec["seed"], "tasks": len(rec["plans"]), "reproduced": not diffs, "differs": diffs,
            "inputs_changed": sorted(k for k, v in input_hashes(sorted(rec["plans"])).items() if rec["inputs_sha256"].get(k) != v)}



# ============================================================================= policy v3 (amended 2026-11-01, time-bounded review)
# Human review is bounded: Dev calibrates on three tasks (one per deliverable family); Validation and Formal label one
# deterministic and one judge-only item per task plus a small stratified critical / visual subset. Membership is drawn
# from item lists, critical mappings, visual categories, deliverable families and the seed only (no verdict).
POLICY_VERSION_V3 = "review-queue-2026-11-01.3"
FAMILY = {"2ea2e5b5-257f-42e6-a7dc-93763f28b19d": "presentation", "a45bc83b-22f9-4def-8d89-9c5661b2b86f": "document"}  # every other task: spreadsheet
DEV_SPREADSHEET_CANDIDATES = ("1137e2bb-bdf9-4876-b572-f29b7de5e595", "47ef842d-8eac-4b90-bda8-dd934c228c96", "f841ddcf-2a28-4f6d-bac3-61b607219d3e")  # v2 full-calibration xlsx tasks
DEV_V3 = {"criteria": 1, "deterministic": 2, "judge": 3}
VALIDATION_V3 = {"deterministic": 1, "judge": 1, "criteria_by_family": {"spreadsheet": 2, "presentation": 1, "document": 1}, "visual_by_family": {"spreadsheet": 2, "presentation": 1, "document": 1}, "visual_total": 3}
FORMAL_V3 = {"deterministic": 1, "judge": 1, "criteria_by_family": {"spreadsheet": 1, "presentation": 1, "document": 1}}
ALGORITHM_V3 = ("rng(key) = random.Random(int(sha256(f'{seed}:v3:{key}').hexdigest()[:16], 16)). Dev tasks: the presentation and document tasks plus "
                "rng('dev-spreadsheet').choice(DEV_SPREADSHEET_CANDIDATES). Per Dev task (rng('dev:'+task)): one criterion (choice of sorted ids), 2 deterministic and 3 judge-only "
                "items sampled from the non-critical pools, topped up from the items outside the chosen criterion when a pool is short. Per phase P in (validation, formal), per task "
                "(rng(P+':'+task)): 1 deterministic and 1 judge-only item by the same rule. Critical subset (rng(P+':criteria')): per family, tasks sampled from the sorted family list, "
                "one criterion each (rng(P+':criterion:'+task)). Visual subset (validation only, rng('validation:visual')): per family, tasks with visual items sampled, one item each, "
                "capped at 3 in family order presentation, document, spreadsheet. Items that differ between the preregistered and revised definition of a chosen criterion are added. "
                "Formal uses one list for both candidates.")


def _rng3(seed: int, key: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{seed}:v3:{key}".encode()).hexdigest()[:16], 16))


def _family(task_id: str) -> str:
    return FAMILY.get(task_id, "spreadsheet")


def _task_facts(task_id: str) -> dict:
    ck = task_module(task_id)
    n = rubric_length(task_id)
    cur, pre = ck.CRITICAL, getattr(ck, "CRITICAL_PREREGISTERED", None) or ck.CRITICAL
    crit_union = set(_critical_items(pre)) | set(_critical_items(cur))
    visual = sorted(getattr(ck, "V_ITEMS", []) or [])
    criteria = [{"id": cid, "members": _members(cur[cid]), **({"preregistered_members": _members(pre[cid])} if cid in pre and _members(pre[cid]) != _members(cur[cid]) else {})}
                for cid in sorted(cur, key=lambda c: int(c[1:]))]
    return {"n": n, "criteria": criteria, "visual": visual, "D": sorted(set(ck.D_ITEMS) - set(visual)), "J": sorted(set(ck.J_ITEMS) - set(visual)), "crit_union": crit_union,
            "differing": sorted({i for c in criteria if "preregistered_members" in c for i in set(c["members"]) ^ set(c["preregistered_members"])})}


def _pick(r: random.Random, pool: list[int], k: int, fallback: list[int]) -> tuple[list[int], int]:
    """k items from pool; a short pool is topped up from fallback (sorted, disjoint); returns (items, shortfall)."""
    got = r.sample(pool, min(k, len(pool)))
    rest = [i for i in fallback if i not in got]
    if len(got) < k and rest:
        got += r.sample(rest, min(k - len(got), len(rest)))
    return sorted(got), k - len(got)


def build_plans_v3(seed: int, task_ids: list[str]) -> dict:
    facts = {t: _task_facts(t) for t in task_ids}
    fam = {f: sorted(t for t in task_ids if _family(t) == f) for f in ("spreadsheet", "presentation", "document")}
    dev_tasks = sorted([t for f in ("presentation", "document") for t in fam[f]] + [_rng3(seed, "dev-spreadsheet").choice(sorted(DEV_SPREADSHEET_CANDIDATES))])
    plans = {t: {"task_id": t, "family": _family(t), "rubric_items": facts[t]["n"], "criteria": facts[t]["criteria"], "visual_items": facts[t]["visual"],
                 "differing_items": facts[t]["differing"], "phases": {}} for t in task_ids}

    def items_for(r, t, kd, kj, exclude=()):
        f = facts[t]
        ex = set(exclude)
        d_pool = [i for i in f["D"] if i not in f["crit_union"] and i not in ex]
        j_pool = [i for i in f["J"] if i not in f["crit_union"] and i not in ex]
        d, sd = _pick(r, d_pool, kd, [i for i in f["D"] if i not in ex and i not in d_pool])
        j, sj = _pick(r, j_pool, kj, [i for i in f["J"] if i not in ex and i not in j_pool])
        return d, j, {k: v for k, v in (("deterministic", sd), ("judge", sj)) if v}

    def sensitivity(t, cids):
        return [i for c in facts[t]["criteria"] if c["id"] in cids and "preregistered_members" in c for i in set(c["members"]) ^ set(c["preregistered_members"])]

    for t in task_ids:
        if t in dev_tasks:
            r = _rng3(seed, f"dev:{t}")
            cids = [c["id"] for c in facts[t]["criteria"]]
            cid = r.choice(cids)
            members = next(c for c in facts[t]["criteria"] if c["id"] == cid)["members"]
            d, j, short = items_for(r, t, DEV_V3["deterministic"], DEV_V3["judge"], exclude=members)
            cats = {i: ["dev: deterministic"] for i in d} | {i: ["dev: judge-only"] for i in j}
            for i in sensitivity(t, [cid]):
                cats.setdefault(i, []).append("sensitivity: differs between the preregistered and revised criterion")
            plans[t]["phases"]["dev"] = {"mode": "v3 dev calibration", "evidence_class": "dev calibration (labels inform the judge prompt and graders; not held-out agreement)",
                                         "criteria": [cid], "items": [{"item": i, "categories": sorted(c)} for i, c in sorted(cats.items())], "shortfall": short, "outputs": 1}
        else:
            plans[t]["phases"]["dev"] = {"mode": "automatic only (no human label under v3)", "evidence_class": "none", "criteria": [], "items": [], "outputs": 1}
    for phase, rule in (("validation", VALIDATION_V3), ("formal", FORMAL_V3)):
        chosen_c = {}
        rc = _rng3(seed, f"{phase}:criteria")
        for f, k in rule["criteria_by_family"].items():
            for t in sorted(rc.sample(fam[f], min(k, len(fam[f])))):
                chosen_c[t] = _rng3(seed, f"{phase}:criterion:{t}").choice([c["id"] for c in facts[t]["criteria"]])
        chosen_v = {}
        if phase == "validation":
            rv = _rng3(seed, "validation:visual")
            for f in ("presentation", "document", "spreadsheet"):
                cand = [t for t in fam[f] if facts[t]["visual"]]
                for t in sorted(rv.sample(cand, min(rule["visual_by_family"][f], len(cand)))):
                    if len(chosen_v) < rule["visual_total"]:
                        chosen_v[t] = rv.choice(facts[t]["visual"])
        for t in task_ids:
            r = _rng3(seed, f"{phase}:{t}")
            d, j, short = items_for(r, t, rule["deterministic"], rule["judge"])
            cats = {i: [f"{phase}: random deterministic"] for i in d} | {i: [f"{phase}: random judge-only"] for i in j}
            if t in chosen_v:
                cats.setdefault(chosen_v[t], []).append(f"{phase}: stratified visual")
            for i in sensitivity(t, [chosen_c[t]] if t in chosen_c else []):
                cats.setdefault(i, []).append("sensitivity: differs between the preregistered and revised criterion")
            plans[t]["phases"][phase] = {"mode": f"v3 {phase}", "evidence_class": f"{phase} blind agreement sample" + ("; identical item ids for both candidates, identity hidden" if phase == "formal" else ""),
                                         "criteria": [chosen_c[t]] if t in chosen_c else [], "items": [{"item": i, "categories": sorted(c)} for i, c in sorted(cats.items())],
                                         "shortfall": short, "outputs": 2 if phase == "formal" else 1}
    for t, pl in plans.items():
        bad = [x["item"] for ph in pl["phases"].values() for x in ph["items"] if not 1 <= x["item"] <= facts[t]["n"]]
        if bad:
            raise ValueError(f"{t}: plan items outside 1..{facts[t]['n']}: {bad}")
    return {"dev_tasks": dev_tasks, "plans": plans}


def workload_v3(plans: dict) -> dict:
    tot = {}
    for t, pl in plans.items():
        for ph, w in workload(pl).items():
            a = tot.setdefault(ph, {"criterion_labels": 0, "item_labels": 0, "labels": 0, "evidence_items": 0})
            a["criterion_labels"] += w["criterion_labels_per_output"] * w["outputs"]; a["item_labels"] += w["item_labels_per_output"] * w["outputs"]
            a["labels"] += w["csv_labels_total"]; a["evidence_items"] += w["evidence_items_total"] if w["csv_labels_total"] else 0
    return tot


def freeze_v3(seed: int, out_path: str, task_ids: list[str] | None = None) -> dict:
    from .grade import TASK_MODULES
    task_ids = sorted(task_ids or TASK_MODULES)
    built = build_plans_v3(seed, task_ids)
    rec = {"policy_version": POLICY_VERSION_V3, "amends": POLICY_VERSION_V2 + " (queue_v2.json, never labelled; kept)",
           "adopted": "2026-11-01, on the human's instruction (time-bounded review), before any human label; not preregistered",
           "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seed": seed, "algorithm": ALGORITHM_V3,
           "rules": {"dev": DEV_V3, "validation": VALIDATION_V3, "formal": FORMAL_V3, "families": {t: _family(t) for t in task_ids}, "dev_spreadsheet_candidates": list(DEV_SPREADSHEET_CANDIDATES)},
           "dev_tasks": built["dev_tasks"], "inputs_sha256": input_hashes(task_ids),
           "verdict_independent": "membership is computed from item lists, critical mappings, visual categories, deliverable families and the seed only",
           "not_covered": "visual items outside the validation subset and every formal visual item are reported as not evaluated unless a human verdict is obtained; "
                          "no judge verdict substitutes for them. Critical criteria outside the subsets are not human-verified (critical FAILs that are reported are verified separately).",
           "plans": built["plans"], "workload": {t: workload(p) for t, p in built["plans"].items()}, "workload_total": workload_v3(built["plans"])}
    if os.path.exists(out_path):
        raise FileExistsError(f"{out_path} exists; a frozen queue is never overwritten (write a new version)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    return rec


def verify_v3(path: str) -> dict:
    rec = load(path)
    built = build_plans_v3(rec["seed"], sorted(rec["plans"]))
    diffs = sorted(t for t, p in rec["plans"].items() if built["plans"][t] != p)
    return {"path": path, "seed": rec["seed"], "tasks": len(rec["plans"]), "reproduced": not diffs and built["dev_tasks"] == rec["dev_tasks"], "differs": diffs,
            "inputs_changed": sorted(k for k, v in input_hashes(sorted(rec["plans"])).items() if rec["inputs_sha256"].get(k) != v)}


if __name__ == "__main__":
    sys.exit(main())
