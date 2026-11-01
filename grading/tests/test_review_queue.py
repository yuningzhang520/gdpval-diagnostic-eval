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


if __name__ == "__main__":
    unittest.main()
