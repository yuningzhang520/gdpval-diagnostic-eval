"""Focused B1-B3 closeout contracts; synthetic inputs and external temporary directories only."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness import collect as c
from harness.tests.test_collect_unit import RUN, FakeSandbox, entry


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="closeout_unit_")
        self.base = Path(self.tmp.name)
        self.host = str(self.base / "runs" / RUN["uuid"])
        self.binding = dict(RUN)
        self.execution = {"status": "completed", "errors": [], "limits": [], "solver_finished": True,
                          "collector_scorer_executed": True}

    def tearDown(self):
        self.tmp.cleanup()

    def listing(self, entries=None):
        return {"ok": True, "root": c.FINAL_DIR, "root_state": "dir", "entries": entries or [], "skipped": [], "errors": []}

    def collect(self, listing=None, contents=None, host=None, **kw):
        return asyncio.run(c.collect_final_outputs(host or self.host, "unit pass", self.binding,
                           sb=FakeSandbox(listing or self.listing(), contents), **kw))

    def complete(self):
        c.bind_run(self.host, self.binding, "unit-label", "solver")
        data = b"original bytes"
        rec = self.collect(self.listing([entry("/output/final/a.txt", data)]), {"/output/final/a.txt": data})
        return c.write_run_outcome(self.host, self.binding, rec, self.execution)

    def hashes(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(self.host).rglob("*") if p.is_file()}

    def test_malformed_listing_schema_is_never_empty_success(self):
        bad = [42, [], None, {"ok": True}]
        for key, values in {"entries": [[42], [None], [{}], [{"path": "x"}], "bad"],
                            "skipped": [[42], [{}], [{"path": "x", "reason": 2}]],
                            "errors": [[42], [{"path": "x"}]], "root_state": [42], "root": ["/else"]}.items():
            bad += [{**self.listing(), key: v} for v in values]
        for field, value in [("size", True), ("size", -1), ("nlink", 0), ("sha256", "z" * 64), ("path", 42)]:
            bad.append(self.listing([{**entry("/output/final/a", b"a"), field: value}]))
        for i, value in enumerate(bad):
            with self.subTest(i=i):
                from harness.tests.test_collect_unit import ExecResult
                sb = FakeSandbox(exec_result=ExecResult(stdout=json.dumps(value)))
                rec = asyncio.run(c.collect_final_outputs(str(self.base / f"schema{i}"), "malformed", self.binding, sb=sb))
                self.assertEqual(rec["status"], "listing_failed")
                self.assertTrue(rec["harness_error"])
                self.assertFalse(sb.reads)

    def test_host_ancestor_symlink_refused_before_any_write(self):
        outside = self.base / "outside"; outside.mkdir()
        link = self.base / "ancestor"; link.symlink_to(outside, target_is_directory=True)
        rec = self.collect(host=str(link / "runs" / self.binding["uuid"]))
        self.assertEqual(rec["status"], "listing_failed")
        self.assertEqual(list(outside.iterdir()), [])

    def test_fixed_tmp_symlink_is_not_used(self):
        Path(self.host).mkdir(parents=True)
        target = self.base / "sentinel"; target.write_text("unchanged")
        (Path(self.host) / "collection.json.tmp").symlink_to(target)
        self.complete()
        self.assertEqual(target.read_text(), "unchanged")
        self.assertFalse((Path(self.host) / "collection.json").is_symlink())
        self.assertTrue(c.load_run_outcome(self.host, self.binding)["grading_eligible"])

    def test_malicious_record_targets_and_names_refused(self):
        Path(self.host).mkdir(parents=True)
        target = self.base / "sentinel"; target.write_text("unchanged")
        for name in ("collection.json", "run_outcome.json", "run.json"):
            path = Path(self.host) / name; path.symlink_to(target)
            with self.assertRaises(ValueError): c._atomic_json(self.host, name, {"bad": True})
            self.assertEqual(target.read_text(), "unchanged")
            path.unlink()
        for name in ("../sentinel", str(target), "a\x00b"):
            with self.assertRaises(ValueError): c._atomic_json(self.host, name, {})
        self.assertEqual(target.read_text(), "unchanged")

    def test_atomic_failure_leaves_old_record_and_removes_random_temp(self):
        self.complete()
        before = self.hashes()
        with patch.object(c.os, "replace", side_effect=OSError("synthetic rename failure")):
            with self.assertRaises(OSError): c._atomic_json(self.host, "run_outcome.json", {"new": True})
        self.assertEqual(self.hashes(), before)
        self.assertFalse(list(Path(self.host).glob(".*.tmp")))

    def test_complete_binding_mismatch_never_changes_records(self):
        self.complete(); before = self.hashes()
        for key, value in [("model", "mockllm/other"), ("task_id", "other-task"), ("epoch", 2),
                           ("sample_id", "other-sample"), ("eval_id", "other-eval"), ("uuid", "other-uuid")]:
            binding = {**self.binding, key: value}
            with self.subTest(key=key):
                with self.assertRaises(c.OutcomeValidationError): c.bind_run(self.host, binding, None, "cleanup")
                rec = asyncio.run(c.collect_final_outputs(self.host, "mismatch", binding, sb=FakeSandbox()))
                self.assertEqual(rec["status"], "listing_failed")
                self.assertEqual(self.hashes(), before)

    def test_partial_then_cleanup_complete_keeps_failure_and_original(self):
        c.bind_run(self.host, self.binding, None, "solver")
        data = {"/output/final/a": b"a", "/output/final/b": b"b"}
        listing = self.listing([entry(k, v) for k, v in data.items()])
        first = self.collect(listing, data, _simulate_read_failure={"/output/final/b"})
        a = Path(self.host) / "final/a"; st = a.stat(); before = (a.read_bytes(), st.st_ino, st.st_mtime_ns)
        partial = c.write_run_outcome(self.host, self.binding, first, self.execution)
        # a read failure is not attributed by its name: no harness-error verdict, no model-failure verdict
        self.assertFalse(partial["harness_error"])
        self.assertEqual(partial["outcome_class"], "requires_adjudication")
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)
        second = self.collect(listing, data)
        c.write_run_outcome(self.host, self.binding, second, self.execution)
        outcome = c.load_run_outcome(self.host, self.binding)
        self.assertFalse(outcome["harness_error"])
        self.assertEqual([p["status"] for p in outcome["collection"]["passes"]], ["partial", "complete"])
        self.assertIn("read_failed", json.dumps(outcome["collection"]["passes"][0]["files"]))
        st = a.stat(); self.assertEqual(before, (a.read_bytes(), st.st_ino, st.st_mtime_ns))

    def test_missing_corrupt_mismatched_and_nonfinal_outcomes_fail_closed(self):
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)
        good = self.complete()
        path = Path(self.host) / "run_outcome.json"; path.write_text("{broken")
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)
        for key, value in [("final", False), ("run", {**self.binding, "epoch": 9}), ("collection_status", "invented"),
                           ("harness_error", True), ("grading_eligible", False), ("collection", {})]:
            with self.subTest(key=key):
                c._atomic_json(self.host, "run_outcome.json", {**good, key: value})
                with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)
        c._atomic_json(self.host, "run_outcome.json", good)
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, {**self.binding, "model": "mockllm/other"})

    def test_raw_mutation_fails_closed(self):
        self.complete()
        raw = Path(self.host) / "final/a.txt"; raw.chmod(0o600); raw.write_bytes(b"changed")
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)

    def test_stale_outcome_and_false_complete_fail_closed(self):
        good = self.complete()
        changed = json.loads(json.dumps(good["collection"]))
        changed["listing_ok"] = False
        c._atomic_json(self.host, "collection.json", changed)
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)
        # Even if both files agree, a claimed complete status cannot contradict listing evidence.
        good["collection"] = changed
        c._atomic_json(self.host, "run_outcome.json", good)
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)

    def test_confirmed_empty_after_normal_execution_is_distinct(self):
        c.bind_run(self.host, self.binding, None, "cleanup")
        rec = self.collect()
        c.write_run_outcome(self.host, self.binding, rec, self.execution)
        outcome = c.load_run_outcome(self.host, self.binding)
        self.assertEqual(outcome["collection_status"], "no_files_confirmed")
        self.assertEqual(outcome["outcome_class"], "no_deliverable_files_confirmed")
        self.assertFalse(outcome["harness_error"])

    def test_listing_failed_outcome_has_no_model_non_delivery(self):
        c.bind_run(self.host, self.binding, None, "cleanup")
        rec = self.collect({**self.listing(), "entries": [42]})
        c.write_run_outcome(self.host, self.binding, rec, self.execution)
        out = c.load_run_outcome(self.host, self.binding, for_grading=False)
        self.assertEqual(out["outcome_class"], "harness_collection_error")
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)

    def test_execution_error_is_preserved_despite_complete_collection(self):
        out = self.complete()
        error = {**self.execution, "status": "error", "solver_finished": False, "collector_scorer_executed": False,
                 "errors": [{"event_uuid": "test", "message": "synthetic generation error"}]}
        c.write_run_outcome(self.host, self.binding, out["collection"], error)
        out = c.load_run_outcome(self.host, self.binding, for_grading=False)
        self.assertFalse(out["harness_error"])
        self.assertEqual(out["outcome_class"], "execution_error")
        self.assertFalse(out["grading_eligible"])
        with self.assertRaises(c.OutcomeValidationError): c.load_run_outcome(self.host, self.binding)


if __name__ == "__main__":
    unittest.main()
