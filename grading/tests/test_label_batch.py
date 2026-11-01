"""Labeling batch assembly (grading/label_batch.py): gates (three tasks, ready tasks only, existing tag, development class
only, canonical runs only, no overwrite) and contents (verdict-free packet copies, the independent-judgments template,
read-only deliverable copies with matching hashes, a manifest; the sealed verdict file is never copied). Runs are built
through the real collector from the expert deliverables of three ready tasks; the grading pass is the production
grade_run with the judge disabled. No model, judge, provider or Docker call."""
import asyncio
import json
import os
import stat
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import label_batch as LB
from grading.grade import grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = LB.ROOT
TASKS = ["1137e2bb-bdf9-4876-b572-f29b7de5e595", "2ea2e5b5-257f-42e6-a7dc-93763f28b19d", "a45bc83b-22f9-4def-8d89-9c5661b2b86f"]


def _load(task):
    rub = json.load(open(os.path.join(ROOT, "private", "rubric", f"{task}.json"), encoding="utf-8"))
    ref_p = os.path.join(ROOT, "private", "checks", "recalc", f"{task}.json")
    ref = json.load(open(ref_p, encoding="utf-8")) if os.path.exists(ref_p) else {}
    prompt = open(os.path.join(ROOT, "data", "prompts", f"{task}.txt"), encoding="utf-8").read()
    return rub, ref, prompt


class LabelBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="label_batch_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.runs = []
        dev_runs = os.path.join(cls.base, "dev", "runs"); os.makedirs(dev_runs)
        for n, task in enumerate(TASKS):
            uuid = f"labelbatch{n:011d}"
            b = {**RUN, "uuid": uuid, "sample_id": task, "task_id": "gdpval-dev", "eval_id": f"evalLB{n}"}
            host = os.path.join(dev_runs, uuid)
            C.bind_run(host, b, "dev", "solver")
            lst, contents = fixture_listing(os.path.join(ROOT, "private", "gold", task))
            rec = asyncio.run(C.collect_final_outputs(host, "scorer", b, sb=FakeSandbox(lst, contents)))
            C.write_run_outcome(host, b, rec, EXEC_OK)
            with open(os.path.join(dev_runs, "run_inventory.jsonl"), "a") as f:
                f.write(json.dumps({"kind": "sample", "task_id": task, "model": "google/gemini-3.8-flash", "run_uuid": uuid, "unit_id": f"{task}:g:{n}", "log_file": "x.eval"}) + "\n")
            with open(os.path.join(dev_runs, "canonical_designations.jsonl"), "a") as f:
                f.write(json.dumps({"run_uuid": uuid, "designation": "canonical"}) + "\n")
            cls.runs.append(("dev", task, uuid, b))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def resolved(self, runs=None, **kw):
        return LB.check_runs([(l, t, u) for l, t, u, _ in (runs or self.runs)], base=self.base, tag_check=kw.pop("tag_check", lambda tag: True), **kw)

    def passes(self, resolved):
        out = []
        for r, (_, task, uuid, b) in zip(resolved, self.runs):
            rub, ref, prompt = _load(task)
            out.append(grade_run(r["host_dir"], fake_log(b), uuid, task_id=task, rubric=rub, task_prompt=prompt, reference=ref, out_dir=r["grading_out"], judge=None, recalc=False))
        return out

    def test_batch_contents_are_verdict_free_and_complete(self):
        res = self.resolved()
        out = LB.assemble("batch_a", res, self.passes(res), os.path.join(self.base, "labeling"))
        man = json.load(open(out["manifest"]))
        self.assertEqual([r["task_id"] for r in man["runs"]], TASKS)
        for r, p in zip(man["runs"], [LB._latest_pass(x["grading_out"], x["run_uuid"]) for x in res]):
            sub = os.path.join(out["folder"], r["folder"])
            self.assertEqual(sorted(os.listdir(sub)), ["deliverables", "items.md", "labels.csv"])  # no sealed verdict file
            self.assertEqual(open(os.path.join(sub, "items.md")).read(), open(p["review_materials"]["items"]).read())
            for d in r["deliverables"]:
                self.assertTrue(d["matches_original"])
                mode = os.stat(os.path.join(sub, "deliverables", d["path"])).st_mode
                self.assertFalse(mode & stat.S_IWUSR)  # read-only copy
            self.assertTrue(r["sealed_verdicts_path"].endswith("_judge_verdicts.json") and os.path.exists(r["sealed_verdicts_path"]))
        allfiles = [os.path.join(dp, f) for dp, _, fs in os.walk(out["folder"]) for f in fs]
        self.assertFalse(any("judge_verdicts" in f for f in allfiles))
        readme = open(os.path.join(out["folder"], "README.md")).read()
        self.assertIn("save-labels", readme); self.assertIn("Written for: the human labeller", readme)
        with self.assertRaisesRegex(LB.BatchError, "never overwritten"):
            LB.assemble("batch_a", res, self.passes(res), os.path.join(self.base, "labeling"))

    def test_gates(self):
        with self.assertRaisesRegex(LB.BatchError, "at least three tasks"):
            self.resolved(self.runs[:2])
        v = [("validation",) + self.runs[0][1:]] + self.runs[1:]
        with self.assertRaisesRegex(LB.BatchError, "stay sealed"):
            self.resolved(v)
        nr = [("dev", "7d7fc9a7-21a7-4b83-906f-416dea5ad04f", self.runs[0][2], None)] + self.runs[1:]
        with self.assertRaisesRegex(LB.BatchError, "Codex Review 1 closure pending"):
            self.resolved(nr)
        with self.assertRaisesRegex(LB.BatchError, "does not exist"):
            self.resolved(tag_check=lambda tag: False)
        other = [("dev", TASKS[0], "notcanonical0000000000", None)] + self.runs[1:]
        with self.assertRaisesRegex(LB.BatchError, "no sample record"):
            self.resolved(other)

    def test_readiness_file_lists_tagged_tasks_and_keeps_7d7fc9a7_closed(self):
        r = LB.readiness()
        self.assertEqual(sorted(r["ready"]), sorted(TASKS))
        self.assertIn("7d7fc9a7-21a7-4b83-906f-416dea5ad04f", r["not_ready"])
        for t, v in r["ready"].items():
            self.assertTrue(LB.tag_exists(v["tag"]), v["tag"])


if __name__ == "__main__":
    unittest.main()
