"""Item 5 regressions: cumulative file-count and byte caps across scorer and cleanup passes of
one sample, idempotent re-collection not counted twice, no bypass through repeated passes, an
enforceable deadline on in-flight reads, and compatibility with the run_outcome contract.
Fake sandbox, no Docker, no model. Run: python -m unittest harness.tests.test_collect_limits_unit -v"""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness import collect as c
from harness.tests.test_collect_unit import RUN, FakeSandbox, entry


class SlowSandbox(FakeSandbox):
    def __init__(self, listing, contents, slow: dict[str, float]):
        super().__init__(listing, contents)
        self.slow = slow

    async def read_file(self, path, text=True):
        self.reads.append(path)
        await asyncio.sleep(self.slow.get(path, 0))
        return self.contents[path]


def listing(entries):
    return {"ok": True, "root": c.FINAL_DIR, "root_state": "dir", "entries": entries, "skipped": [], "errors": []}


class CumulativeLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="limits_unit_")
        self.host = str(Path(os.path.realpath(self.tmp.name)) / "runs" / RUN["uuid"])
        c.bind_run(self.host, dict(RUN), None, "solver")

    def tearDown(self):
        self.tmp.cleanup()

    def collect(self, entries, contents, note="pass", sb=None):
        sb = sb or FakeSandbox(listing(entries), contents)
        return asyncio.run(c.collect_final_outputs(self.host, note, dict(RUN), sb=sb)), sb

    def test_file_count_cap_is_cumulative_and_idempotent(self):
        with patch.dict(c.LIMITS, {"max_files": 3}):
            data1 = {"/output/final/a.txt": b"a", "/output/final/b.txt": b"b"}
            rec1, _ = self.collect([entry(k, v) for k, v in data1.items()], data1, "scorer")
            self.assertEqual(rec1["status"], "complete")
            data2 = dict(data1, **{"/output/final/c.txt": b"c", "/output/final/d.txt": b"d", "/output/final/e.txt": b"e"})
            rec2, sb = self.collect([entry(k, v) for k, v in data2.items()], data2, "cleanup")
            by = {f["sandbox_path"]: f for f in rec2["files"]}
            self.assertEqual(by["/output/final/a.txt"]["status"], "collected")  # kept from pass 1, not re-read
            self.assertEqual(by["/output/final/c.txt"]["status"], "collected")  # the one remaining slot
            self.assertEqual((by["/output/final/d.txt"]["reason"], by["/output/final/e.txt"]["reason"]), ("file_limit", "file_limit"))
            self.assertEqual(sb.reads, ["/output/final/c.txt"])
            self.assertEqual(rec2["file_count"], 3)
            self.assertEqual(rec2["passes"][1]["cumulative"]["files_after_pass"], 3)
            self.assertEqual(rec2["status"], "partial")

    def test_repeated_passes_cannot_bypass_the_cap(self):
        with patch.dict(c.LIMITS, {"max_files": 2}):
            data = {f"/output/final/f{i}.txt": bytes([65 + i]) for i in range(5)}
            entries = [entry(k, v) for k, v in data.items()]
            for n in range(4):  # four passes, the cap stays two files in total
                rec, _ = self.collect(entries, data, f"pass{n}")
            self.assertEqual(rec["file_count"], 2)
            self.assertEqual(sum(1 for f in rec["files"] if f.get("reason") == "file_limit"), 3)
            self.assertEqual(len(rec["passes"]), 4)

    def test_byte_cap_is_cumulative_and_already_collected_not_double_counted(self):
        with patch.dict(c.LIMITS, {"max_total_bytes": 150}):
            data1 = {"/output/final/a.bin": b"x" * 100}
            self.collect([entry(k, v) for k, v in data1.items()], data1, "scorer")
            data2 = dict(data1, **{"/output/final/b.bin": b"y" * 40, "/output/final/c.bin": b"z" * 40})
            rec, _ = self.collect([entry(k, v) for k, v in data2.items()], data2, "cleanup")
            by = {f["sandbox_path"]: f for f in rec["files"]}
            self.assertEqual(by["/output/final/a.bin"]["status"], "collected")
            self.assertEqual(by["/output/final/b.bin"]["status"], "collected")  # 100 + 40 = 140 <= 150
            self.assertEqual(by["/output/final/c.bin"]["reason"], "total_limit")  # 180 > 150
            self.assertEqual(rec["bytes_collected"], 140)
            self.assertEqual(rec["passes"][1]["cumulative"]["bytes_after_pass"], 140)

    def test_deadline_interrupts_in_flight_read_and_skips_the_rest(self):
        with patch.dict(c.LIMITS, {"time_budget_s": 0.4}):
            data = {"/output/final/a.txt": b"fast", "/output/final/b.txt": b"slow", "/output/final/c.txt": b"after"}
            sb = SlowSandbox(listing([entry(k, v) for k, v in data.items()]), data, slow={"/output/final/b.txt": 5.0})
            t0 = asyncio.get_event_loop_policy().get_event_loop if False else None  # placeholder to keep flake tools quiet
            import time
            start = time.monotonic()
            rec, _ = self.collect(None, None, "scorer", sb=sb)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 3.0, "the in-flight read must be interrupted at the deadline, not awaited to completion")
            by = {f["sandbox_path"]: f for f in rec["files"]}
            self.assertEqual(by["/output/final/a.txt"]["status"], "collected")
            self.assertEqual(by["/output/final/b.txt"]["reason"], "read_deadline_exceeded")
            self.assertEqual(by["/output/final/c.txt"]["reason"], "time_budget_exceeded")
            self.assertEqual(sb.reads, ["/output/final/a.txt", "/output/final/b.txt"])  # c.txt never attempted
            self.assertTrue(rec["passes"][0]["deadline_hit"])
            self.assertEqual(rec["status"], "partial")
            self.assertEqual(Path(by["/output/final/a.txt"]["host_path"]).read_bytes(), b"fast")
            self.assertFalse(os.path.exists(os.path.join(self.host, "final", "b.txt")))

    def test_originals_untouched_when_a_later_pass_hits_limits(self):
        with patch.dict(c.LIMITS, {"max_files": 1}):
            data1 = {"/output/final/a.txt": b"original"}
            self.collect([entry(k, v) for k, v in data1.items()], data1, "scorer")
            a = Path(self.host, "final", "a.txt"); st = a.stat(); before = (a.read_bytes(), st.st_ino, st.st_mtime_ns)
            data2 = {"/output/final/a.txt": b"changed!", "/output/final/b.txt": b"b"}
            rec, _ = self.collect([entry(k, v) for k, v in data2.items()], data2, "cleanup")
            by = {f["sandbox_path"]: f for f in rec["files"]}
            self.assertEqual(by["/output/final/a.txt"]["reason"], "conflict_existing_differs")
            self.assertEqual(by["/output/final/b.txt"]["reason"], "file_limit")
            st = a.stat(); self.assertEqual(before, (a.read_bytes(), st.st_ino, st.st_mtime_ns))

    def test_limited_collection_is_a_harness_error_in_the_outcome_contract(self):
        with patch.dict(c.LIMITS, {"max_files": 1}):
            data = {"/output/final/a.txt": b"a", "/output/final/b.txt": b"b"}
            rec, _ = self.collect([entry(k, v) for k, v in data.items()], data, "scorer")
            execution = {"status": "completed", "errors": [], "limits": [], "limit_types": [], "solver_finished": True, "collector_scorer_executed": True}
            out = c.write_run_outcome(self.host, dict(RUN), rec, execution)
            self.assertEqual((out["collection_status"], out["harness_error"], out["grading_eligible"], out["outcome_class"]),
                             ("partial", False, False, "requires_adjudication"))  # file_limit is not attributed by its name
            with self.assertRaises(c.OutcomeValidationError):
                c.load_run_outcome(self.host, dict(RUN))
            loaded = c.load_run_outcome(self.host, dict(RUN), for_grading=False)
            self.assertEqual([f["reason"] for f in loaded["collection"]["files"] if f["status"] == "error"], ["file_limit"])


if __name__ == "__main__":
    unittest.main()
