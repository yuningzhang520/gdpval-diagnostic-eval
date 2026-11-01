"""Every rubric item of every registered task is counted exactly once: the task module's D, J and V lists partition
1..N (N = the rubric's length, computed from the rubric file). Corrections P-2.5-1 and P-2.6-1 (approved 2026-11-01)
are pinned. No model, judge or provider call."""
import json
import os
import unittest

from grading import grade as G

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ItemPartitionTests(unittest.TestCase):
    def test_each_item_is_in_exactly_one_list(self):
        import importlib
        for task, mod in G.TASK_MODULES.items():
            ck = next(m for m in (importlib.import_module(f"grading.checks_{task[:8]}"),))
            rubric = json.load(open(os.path.join(ROOT, "private", "rubric", f"{task}.json"), encoding="utf-8"))
            lists = {"D": list(ck.D_ITEMS), "J": list(ck.J_ITEMS), "V": list(getattr(ck, "V_ITEMS", []))}
            allv = [i for l in lists.values() for i in l]
            with self.subTest(task=task):
                self.assertEqual(sorted(allv), list(range(1, len(rubric) + 1)), {k: len(v) for k, v in lists.items()})
                self.assertEqual(len(allv), len(set(allv)))

    def test_approved_corrections(self):
        from grading import checks_c3525d4d as C4, checks_7b08cd4d as C6
        self.assertTrue({37, 38, 39, 41} <= set(C4.D_ITEMS) and not {37, 38, 39, 41} & set(C4.J_ITEMS))  # P-2.5-1
        self.assertTrue(set(range(41, 49)) <= set(C6.J_ITEMS) and 52 in C6.D_ITEMS)  # P-2.6-1


if __name__ == "__main__":
    unittest.main()
