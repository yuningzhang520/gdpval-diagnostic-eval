"""Fixed, verdict-independent review queue (adopted 2026-11-01): membership from the rubric inventory, item types,
critical mappings, visual categories and a seed only; deterministic; deduplicated; shortfalls reported; queue packets
carry no grader location or verdict; the comparison uses the queued items only. No model, judge or provider call."""
import builtins
import csv
import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from grading import label_batch as LB
from grading import review as R
from grading import review_queue as RQ
from grading.grade import TASK_MODULES

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class QueueSelectionTests(unittest.TestCase):
    def test_reads_nothing_but_the_rubric_file(self):
        real_open = builtins.open
        seen = []

        def guarded(path, *a, **k):
            seen.append(str(path))
            if not str(path).startswith(os.path.join(ROOT, "private", "rubric")):
                raise AssertionError(f"queue selection opened {path}")
            return real_open(path, *a, **k)
        builtins.open = guarded
        try:
            for t in TASK_MODULES:
                RQ.build_queue(t, 7)
        finally:
            builtins.open = real_open
        self.assertTrue(seen)

    def test_categories_dedup_counts_and_determinism(self):
        for t in TASK_MODULES:
            ck = RQ.task_module(t)
            q = RQ.build_queue(t, 20261101)
            items = [x["item"] for x in q["items"]]
            self.assertEqual(len(items), len(set(items)))
            crit = set(RQ._critical_items(getattr(ck, "CRITICAL_PREREGISTERED", None) or ck.CRITICAL)) | set(RQ._critical_items(ck.CRITICAL))
            self.assertTrue(crit | set(getattr(ck, "V_ITEMS", [])) <= set(items), t)
            rd = [x["item"] for x in q["items"] if "random_deterministic" in x["categories"]]
            rj = [x["item"] for x in q["items"] if "random_judge" in x["categories"]]
            self.assertTrue(set(rd) <= set(ck.D_ITEMS) - crit - set(getattr(ck, "V_ITEMS", [])) and set(rj) <= set(ck.J_ITEMS) - crit - set(getattr(ck, "V_ITEMS", [])))
            self.assertEqual(len(rd), min(5, len(set(ck.D_ITEMS) - crit - set(getattr(ck, "V_ITEMS", [])))))
            self.assertEqual(len(rj), min(5, len(set(ck.J_ITEMS) - crit - set(getattr(ck, "V_ITEMS", [])))))
            self.assertEqual(q, RQ.build_queue(t, 20261101))  # same seed, same queue
        self.assertNotEqual(RQ.build_queue("c357f0e2-963d-4eb7-a6fa-3078fe55b3ba", 1), RQ.build_queue("c357f0e2-963d-4eb7-a6fa-3078fe55b3ba", 2))

    def test_preregistered_critical_items_stay_in_the_queue(self):
        q = RQ.build_queue("2ea2e5b5-257f-42e6-a7dc-93763f28b19d", 20261101)
        cats = {x["item"]: x["categories"] for x in q["items"]}
        self.assertIn(10, cats); self.assertTrue(any(c.startswith("critical:C2") for c in cats[10]))  # preregistered C2 member (revised definition removed it)

    def test_shortfall_reported(self):
        mod = SimpleNamespace(D_ITEMS=[1, 2, 3], J_ITEMS=[4], V_ITEMS=[5], CRITICAL={"C1": {"items": [1]}})
        q = RQ.build_queue("x" * 36, 3, module=mod, n_items=5)
        self.assertEqual(q["shortfall"], {"random_deterministic": 3, "random_judge": 4})
        self.assertEqual(q["counts"]["total_unique"], 5)


class QueuePacketTests(unittest.TestCase):
    MD = """# Review packet

This packet carries no automated verdict.

## Item 1 (weight 2)

**Criterion:** A

**Where to look:** {"sheet": "S", "cell": "B7"}

## Item 2 (weight 1)

**Criterion:** B

**Where to look:** {"file": "f.xlsx"}

**Source material / independent reference:** src

**Deliverable excerpt:**

```
X
```

## Item 3 (weight 1)

**Criterion:** C

**Source material / independent reference:** src3

**Deliverable excerpt:**

```
Y
```
"""

    def test_where_to_look_removed_and_judge_excerpts_only_for_judge_items(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "items.md"); open(p, "w").write(self.MD)
            out = LB._queue_items_md(p, {1: ["critical:C1"], 2: ["random_judge"]}, judge_items={2, 3})
        self.assertNotIn("Where to look", out); self.assertNotIn("B7", out)
        self.assertIn("## Item 1", out); self.assertIn("## Item 2", out); self.assertNotIn("## Item 3", out)
        self.assertIn("**Queue category:** critical:C1", out); self.assertIn("Deliverable excerpt", out)

    def test_comparison_restricted_to_the_queue(self):
        with tempfile.TemporaryDirectory() as d:
            csvp = os.path.join(d, "l.csv")
            with open(csvp, "w", newline="") as f:
                w = csv.writer(f); w.writerow(["run_uuid", "item", "weight", "criterion", "label", "evidence"])
                w.writerow(["u", 1, 2, "A", "pass", "x"]); w.writerow(["u", 9, 1, "Z", "fail", "y"])
            R.save_label_checkpoint(d, "u", csvp, "tester")
            grades = [{"item": 1, "verdict": "pass", "source": "D", "weight": 2}, {"item": 2, "verdict": "cannot_assess", "source": "D", "weight": 1}, {"item": 9, "verdict": "pass", "source": "D", "weight": 1}]
            out = R.compare_labels(d, "u", grades, queue_items=[1, 2])
        self.assertEqual((out["labelled_items"], out["queue_unlabelled"], out["labels_outside_queue_ignored"]), (1, [2], [9]))


class PolicyV2Tests(unittest.TestCase):
    """Policy v2 (amended 2026-11-01): dev full / smoke, validation and formal plans with criterion-level labels."""
    SEED = 20261101

    def test_plan_reads_nothing_but_the_rubric_file(self):
        real_open = builtins.open

        def guarded(path, *a, **k):
            if not str(path).startswith(os.path.join(ROOT, "private", "rubric")):
                raise AssertionError(f"plan selection opened {path}")
            return real_open(path, *a, **k)
        builtins.open = guarded
        try:
            for t in TASK_MODULES:
                RQ.build_plan_v2(t, self.SEED)
        finally:
            builtins.open = real_open

    def test_phases_follow_the_policy(self):
        for t in TASK_MODULES:
            ck = RQ.task_module(t)
            plan = RQ.build_plan_v2(t, self.SEED)
            crit = set(RQ._critical_items(getattr(ck, "CRITICAL_PREREGISTERED", None) or ck.CRITICAL)) | set(RQ._critical_items(ck.CRITICAL))
            vis = set(getattr(ck, "V_ITEMS", []) or [])
            dpool, jpool = set(ck.D_ITEMS) - crit - vis, set(ck.J_ITEMS) - crit - vis
            self.assertEqual(plan, RQ.build_plan_v2(t, self.SEED))
            dev = plan["phases"]["dev"]
            with self.subTest(task=t):
                if t in RQ.FULL_CALIBRATION_TASKS:
                    self.assertEqual(dev["criteria"], sorted(ck.CRITICAL, key=lambda c: int(c[1:])))
                    v1 = {x["item"] for x in RQ.build_queue(t, 20261101)["items"] if {"random_deterministic", "random_judge"} & set(x["categories"])}
                    self.assertEqual({x["item"] for x in dev["items"] if any("v1 pick" in c for c in x["categories"])}, v1)
                    self.assertTrue(vis <= {x["item"] for x in dev["items"]})
                else:
                    self.assertLessEqual(len(dev["criteria"]), 1); self.assertLessEqual(len([x for x in dev["items"] if any(c.startswith("smoke") for c in x["categories"])]), 1)
                    self.assertIn("exploratory", dev["evidence_class"])
                for ph in ("validation", "formal"):
                    pp = plan["phases"][ph]
                    rd = {x["item"] for x in pp["items"] if "random_noncritical_deterministic" in x["categories"]}
                    rj = {x["item"] for x in pp["items"] if "random_noncritical_judge" in x["categories"]}
                    self.assertTrue(rd <= dpool and rj <= jpool)
                    self.assertEqual((len(rd), len(rj)), (min(3, len(dpool)), min(3, len(jpool))))
                    self.assertEqual(pp["criteria"], sorted(ck.CRITICAL, key=lambda c: int(c[1:])))
                    self.assertTrue(vis <= {x["item"] for x in pp["items"]})
                self.assertEqual(plan["phases"]["formal"]["outputs"], 2)

    def test_sensitivity_item_and_workload(self):
        plan = RQ.build_plan_v2("2ea2e5b5-257f-42e6-a7dc-93763f28b19d", self.SEED)
        self.assertEqual(plan["differing_items"], [10])
        for ph in ("dev", "validation", "formal"):
            self.assertIn(10, [x["item"] for x in plan["phases"][ph]["items"]])
        w = RQ.workload(plan)
        self.assertEqual((w["validation"]["criterion_labels_per_output"], w["validation"]["evidence_items_per_output"]), (3, 60))
        self.assertEqual(w["formal"]["csv_labels_total"], 2 * w["formal"]["csv_labels_per_output"])

    def test_criterion_rows_and_derived_preregistered_status(self):
        with tempfile.TemporaryDirectory() as d:
            csvp = os.path.join(d, "l.csv")
            with open(csvp, "w", newline="") as f:
                w = csv.writer(f); w.writerow(["run_uuid", "item", "weight", "criterion", "label", "evidence"])
                w.writerow(["u", "C2", "", "Activity shares", "pass", "x"]); w.writerow(["u", 10, 1, "hours", "fail", "y"])
            rows = R.read_labels(csvp)
            self.assertEqual([r["item"] for r in rows], ["C2", 10])
            R.save_label_checkpoint(d, "u", csvp, "tester")
            out = R.compare_labels(d, "u", [{"item": 10, "verdict": "fail", "source": "D", "weight": 1}], queue_items=[10],
                                   critical_status={"C2": "pass"}, sensitivity={"C2": {"preregistered_status": "fail", "differing_items": [10]}})
        c2 = out["criteria"]["rows"][0]
        self.assertEqual((c2["class"], c2["preregistered"]["human_derived"], c2["preregistered"]["class"]), ("agree", "fail", "agree"))


class QueueV3Tests(unittest.TestCase):
    """Time-bounded policy v3: reproducible, verdict-independent, bounded Dev workload, one formal list for both candidates."""

    @classmethod
    def setUpClass(cls):
        from grading import review_queue as RQ
        from grading.grade import TASK_MODULES
        cls.RQ, cls.tasks = RQ, sorted(TASK_MODULES)
        cls.built = RQ.build_plans_v3(20261101, cls.tasks)

    def test_reproducible(self):
        self.assertEqual(self.RQ.build_plans_v3(20261101, self.tasks), self.built)

    def test_dev_one_task_per_family_and_bounded(self):
        fams = sorted(self.built["plans"][t]["family"] for t in self.built["dev_tasks"])
        self.assertEqual(fams, ["document", "presentation", "spreadsheet"])
        w = self.RQ.workload_v3(self.built["plans"])
        self.assertTrue(15 <= w["dev"]["labels"] <= 25, w["dev"])
        for t, p in self.built["plans"].items():
            if t not in self.built["dev_tasks"]:
                self.assertEqual((p["phases"]["dev"]["criteria"], p["phases"]["dev"]["items"]), ([], []))

    def test_phase_items_and_shortfalls(self):
        for phase in ("validation", "formal"):
            for t, p in self.built["plans"].items():
                ph = p["phases"][phase]
                kinds = [c for x in ph["items"] for c in x["categories"]]
                self.assertEqual(sum("random deterministic" in c for c in kinds), 1)
                self.assertEqual(sum("random judge-only" in c for c in kinds) + ph["shortfall"].get("judge", 0), 1)
            self.assertEqual(self.built["plans"]["b5d2e6f1-62a2-433a-bcdd-95b260cdd860"]["phases"][phase]["shortfall"], {"judge": 1})
        formal_v = [x for p in self.built["plans"].values() for x in p["phases"]["formal"]["items"] if any("visual" in c for c in x["categories"])]
        self.assertEqual(formal_v, [])
        self.assertTrue(all(p["phases"]["formal"]["outputs"] == 2 for p in self.built["plans"].values()))
        self.assertEqual(sum(len(p["phases"]["validation"]["criteria"]) for p in self.built["plans"].values()), 4)
        self.assertEqual(sum(len(p["phases"]["formal"]["criteria"]) for p in self.built["plans"].values()), 3)


if __name__ == "__main__":
    unittest.main()
