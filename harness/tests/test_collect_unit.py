"""Unit tests for harness.collect with a fake sandbox (no Docker, no model). They exercise the host
side of the collector: path validation against an untrusted listing, host-side symlink boundaries,
listing-failure handling, per-file failure isolation, limits, resume and conflict behaviour.
Run: python -m unittest harness.tests.test_collect_unit -v"""
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("INSPECT_DISABLE_MODEL_API", "1")

from harness import collect  # noqa: E402

RUN = {"uuid": "unit-run-0001", "model": "mockllm/model", "task_id": "unit-task", "eval_id": "unit-eval", "sample_id": "unit-sample", "epoch": 1}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class ExecResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode
        self.success = returncode == 0


class FakeSandbox:
    """Returns a scripted listing and scripted file contents; records what the host asked for."""

    def __init__(self, listing=None, contents=None, exec_result=None, read_errors=None):
        self.listing = listing or {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "entries": [], "skipped": [], "errors": []}
        self.contents = contents or {}
        self.exec_result = exec_result
        self.read_errors = read_errors or set()
        self.reads = []

    async def exec(self, cmd, timeout=None):
        if self.exec_result is not None:
            return self.exec_result
        return ExecResult(stdout="noise line\n" + json.dumps(self.listing) + "\n")

    async def read_file(self, path, text=True):
        self.reads.append(path)
        if path in self.read_errors:
            raise RuntimeError("read error")
        return self.contents[path]


def entry(path: str, data: bytes, nlink: int = 1, size=None, sha256=None):
    return {"path": path, "size": len(data) if size is None else size, "nlink": nlink, "sha256": sha(data) if sha256 is None else sha256}


class CollectUnitTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="collect_unit_")
        self.host = os.path.join(self.base, "run", "task", "epoch1")
        self.outside = os.path.join(self.base, "outside")
        os.makedirs(self.outside)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def collect(self, sb, host=None, run=RUN, **kw):
        return run_collect(sb, host or self.host, run, **kw)

    def outside_tree(self):
        return sorted(os.path.relpath(os.path.join(dp, f), self.outside) for dp, _, fn in os.walk(self.outside) for f in fn)

    # B1: untrusted paths ---------------------------------------------------------------------
    def test_traversal_and_outside_paths_rejected_without_writes(self):
        good = b"good"
        evil = b"evil"
        sentinel_dir = os.path.join(self.base, "tmp", "x")
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [
            entry("/output/final/../../tmp/x/sentinel.txt", evil),
            entry("/output/final/sub/../../../etc/sentinel2.txt", evil),
            entry("/output/final/./a.txt", evil),
            entry("/output/final//double.txt", evil),
            entry("/output/finalx/prefix_trick.txt", evil),
            entry("/etc/passwd", evil),
            entry("relative.txt", evil),
            entry("/output/final/nul\x00byte.txt", evil),
            entry("/output/final/ok.txt", good),
        ]}
        sb = FakeSandbox(listing, {"/output/final/ok.txt": good})
        info = self.collect(sb)
        self.assertEqual(sb.reads, ["/output/final/ok.txt"], "only the valid path may be read")
        self.assertEqual([f["sandbox_path"] for f in info["files"] if f["status"] == "collected"], ["/output/final/ok.txt"])
        self.assertEqual(len(info["rejected"]), 8)
        self.assertEqual(info["status"], "partial")
        self.assertFalse(os.path.exists(sentinel_dir))
        root_real = os.path.realpath(os.path.join(self.host, "final"))
        written = [os.path.join(dp, f) for dp, _, fn in os.walk(self.base) for f in fn if f.endswith(".txt")]
        for w in written:
            self.assertTrue(os.path.realpath(w).startswith(root_real + os.sep), w)
        self.assertEqual(self.outside_tree(), [])

    def test_host_component_symlink_rejected(self):
        os.makedirs(os.path.join(self.host, "final"))
        os.symlink(self.outside, os.path.join(self.host, "final", "sub"))
        data = b"through the link"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/sub/file.txt", data)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/sub/file.txt": data}))
        self.assertEqual(info["rejected"][0]["reason"], "host_path_component_symlink")
        self.assertEqual(self.outside_tree(), [])
        self.assertEqual(info["status"], "partial")

    def test_host_final_root_symlink_rejected(self):
        os.makedirs(self.host)
        os.symlink(self.outside, os.path.join(self.host, "final"))
        data = b"x"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/a.txt", data)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/a.txt": data}))
        self.assertEqual(info["status"], "listing_failed")
        self.assertEqual(info["listing_errors"][0]["reason"], "host_final_root_not_a_directory")
        self.assertEqual(self.outside_tree(), [])

    def test_host_destination_symlink_rejected_and_target_unchanged(self):
        os.makedirs(os.path.join(self.host, "final"))
        target = os.path.join(self.outside, "victim.txt")
        with open(target, "wb") as f:
            f.write(b"original")
        os.symlink(target, os.path.join(self.host, "final", "a.txt"))
        data = b"overwrite attempt"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/a.txt", data)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/a.txt": data}))
        self.assertEqual(info["rejected"][0]["reason"], "host_destination_not_regular_file")
        with open(target, "rb") as f:
            self.assertEqual(f.read(), b"original")

    def test_hardlink_entry_collected_as_regular_file(self):
        data = b"hardlinked content"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/hard.txt", data, nlink=2)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/hard.txt": data}))
        self.assertEqual(info["status"], "complete")
        self.assertEqual(info["files"][0]["nlink"], 2)
        with open(info["files"][0]["host_path"], "rb") as f:
            self.assertEqual(f.read(), data)

    def test_no_extension_and_nested_names_collected(self):
        a, b = b"A", b"B"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [],
                   "entries": [entry("/output/final/README", a), entry("/output/final/sub dir/deep/f i l e.xlsx", b)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/README": a, "/output/final/sub dir/deep/f i l e.xlsx": b}))
        self.assertEqual(info["status"], "complete")
        self.assertTrue(os.path.isfile(os.path.join(self.host, "final", "sub dir", "deep", "f i l e.xlsx")))
        self.assertEqual(oct(os.stat(info["files"][0]["host_path"]).st_mode & 0o777), "0o444")

    # B2: enumeration failure and per-file failures -----------------------------------------
    def test_listing_exec_failure_is_harness_error_not_model_absence(self):
        info = self.collect(FakeSandbox(exec_result=ExecResult(stdout="", stderr="Traceback", returncode=1)))
        self.assertEqual(info["status"], "listing_failed")
        self.assertFalse(info["all_intact"])
        self.assertTrue(info["harness_error"])
        self.assertEqual(info["outcome_class"], "harness_collection_error")
        self.assertNotEqual(info["status"], "no_files_confirmed")

    def test_listing_garbage_output_is_listing_failed(self):
        for out in ("", "[]", "not json", json.dumps({"ok": False}), json.dumps({"ok": True, "entries": "x"})):
            shutil.rmtree(self.host, ignore_errors=True)
            info = self.collect(FakeSandbox(exec_result=ExecResult(stdout=out)))
            self.assertEqual(info["status"], "listing_failed", out)
            self.assertFalse(info["all_intact"])

    def test_listing_timeout_is_listing_failed(self):
        class Timeout(FakeSandbox):
            async def exec(self, cmd, timeout=None):
                raise TimeoutError("exec timed out")
        info = self.collect(Timeout())
        self.assertEqual(info["status"], "listing_failed")
        self.assertIn("TimeoutError", info["listing_errors"][0]["reason"])

    def test_root_unreadable_is_listing_failed(self):
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "unreadable", "skipped": [], "errors": [{"path": collect.FINAL_DIR, "reason": "scandir:PermissionError"}], "entries": []}
        info = self.collect(FakeSandbox(listing))
        self.assertEqual(info["status"], "listing_failed")
        self.assertTrue(info["harness_error"])

    def test_empty_directory_is_no_files_confirmed(self):
        info = self.collect(FakeSandbox())
        self.assertEqual(info["status"], "no_files_confirmed")
        self.assertFalse(info["harness_error"])
        self.assertEqual(info["outcome_class"], "no_deliverable_files_confirmed")

    def test_missing_directory_is_no_files_confirmed(self):
        info = self.collect(FakeSandbox({"ok": True, "root": collect.FINAL_DIR, "root_state": "missing", "skipped": [], "errors": [], "entries": []}))
        self.assertEqual(info["status"], "no_files_confirmed")

    def test_only_skipped_entries_is_partial_not_no_files(self):
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "entries": [], "errors": [], "skipped": [{"path": "/output/final/link", "reason": "symlink_broken", "target": "/nowhere"}]}
        info = self.collect(FakeSandbox(listing))
        self.assertEqual(info["status"], "partial")

    def test_single_read_failure_does_not_block_others(self):
        a, b, c = b"a", b"b", b"c"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [],
                   "entries": [entry("/output/final/a.txt", a), entry("/output/final/b.txt", b), entry("/output/final/c.txt", c)]}
        sb = FakeSandbox(listing, {"/output/final/a.txt": a, "/output/final/b.txt": b, "/output/final/c.txt": c}, read_errors={"/output/final/b.txt"})
        info = self.collect(sb)
        by = {f["sandbox_path"]: f for f in info["files"]}
        self.assertEqual(by["/output/final/a.txt"]["status"], "collected")
        self.assertEqual(by["/output/final/c.txt"]["status"], "collected")
        self.assertEqual(by["/output/final/b.txt"]["status"], "error")
        self.assertTrue(by["/output/final/b.txt"]["reason"].startswith("read_failed:"))
        self.assertEqual(info["status"], "partial")
        self.assertTrue(info["harness_error"])

    def test_integrity_mismatch_recorded_not_written(self):
        listed = b"listed content"
        actual = b"different content"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/a.txt", listed)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/a.txt": actual}))
        self.assertEqual(info["files"][0]["reason"], "integrity_mismatch")
        self.assertFalse(os.path.exists(os.path.join(self.host, "final", "a.txt")))

    def test_oversized_between_small_files(self):
        small1, small2 = b"first", b"last"
        big_size = collect.LIMITS["max_file_bytes"] + 1
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [
            entry("/output/final/a.txt", small1), {"path": "/output/final/m_big.bin", "size": big_size, "nlink": 1, "sha256": None},
            entry("/output/final/z.txt", small2)]}
        sb = FakeSandbox(listing, {"/output/final/a.txt": small1, "/output/final/z.txt": small2})
        info = self.collect(sb)
        by = {f["sandbox_path"]: f for f in info["files"]}
        self.assertEqual(by["/output/final/a.txt"]["status"], "collected")
        self.assertEqual(by["/output/final/z.txt"]["status"], "collected")
        self.assertEqual(by["/output/final/m_big.bin"]["reason"], "oversized")
        self.assertNotIn("/output/final/m_big.bin", sb.reads)
        self.assertEqual(info["status"], "partial")
        self.assertEqual(info["limits"], collect.LIMITS)

    def test_file_count_limit_records_rest(self):
        n = collect.LIMITS["max_files"] + 3
        contents = {f"/output/final/f{i:04d}.txt": f"{i}".encode() for i in range(n)}
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry(p, d) for p, d in contents.items()]}
        info = self.collect(FakeSandbox(listing, contents))
        self.assertEqual(sum(1 for f in info["files"] if f["status"] == "collected"), collect.LIMITS["max_files"])
        self.assertEqual(sum(1 for f in info["files"] if f.get("reason") == "file_limit"), 3)

    # B3: immutability, resume, conflicts -------------------------------------------------------
    def test_resume_skips_identical_collects_missing_keeps_history(self):
        a, b = b"a-content", b"b-content"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/a.txt", a), entry("/output/final/b.txt", b)]}
        contents = {"/output/final/a.txt": a, "/output/final/b.txt": b}
        first = self.collect(FakeSandbox(listing, contents, read_errors={"/output/final/b.txt"}), note="scorer")
        self.assertEqual(first["status"], "partial")
        a_path = os.path.join(self.host, "final", "a.txt")
        st_before = os.stat(a_path)
        second_sb = FakeSandbox(listing, contents)
        second = self.collect(second_sb, note="cleanup")
        self.assertEqual(second["status"], "complete")
        self.assertEqual(second_sb.reads, ["/output/final/b.txt"], "identical existing file is not re-read")
        by = {f["sandbox_path"]: f for f in second["files"]}
        self.assertEqual(by["/output/final/a.txt"]["status"], "collected")
        self.assertEqual(by["/output/final/b.txt"]["status"], "collected")
        self.assertEqual([p["note"] for p in second["passes"]], ["scorer", "cleanup"])
        self.assertEqual(second["passes"][0]["status"], "partial")
        st_after = os.stat(a_path)
        self.assertEqual((st_before.st_ino, st_before.st_mtime_ns), (st_after.st_ino, st_after.st_mtime_ns))

    def test_conflict_same_name_different_content_not_overwritten(self):
        os.makedirs(os.path.join(self.host, "final"))
        host_file = os.path.join(self.host, "final", "x.txt")
        with open(host_file, "wb") as f:
            f.write(b"earlier content")
        with open(os.path.join(self.host, "collection.json"), "w") as f:
            json.dump({"run": RUN, "status": "partial", "files": [], "passes": []}, f)
        data = b"new content"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/x.txt", data)]}
        info = self.collect(FakeSandbox(listing, {"/output/final/x.txt": data}))
        self.assertEqual(info["files"][0]["reason"], "conflict_existing_differs")
        self.assertEqual(info["status"], "partial")
        with open(host_file, "rb") as f:
            self.assertEqual(f.read(), b"earlier content")

    def test_other_run_record_refused(self):
        os.makedirs(self.host)
        with open(os.path.join(self.host, "collection.json"), "w") as f:
            json.dump({"run": {**RUN, "uuid": "other-run"}, "status": "complete", "files": [], "passes": []}, f)
        data = b"d"
        listing = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/a.txt", data)]}
        sb = FakeSandbox(listing, {"/output/final/a.txt": data})
        info = self.collect(sb)
        self.assertEqual(sb.reads, [])
        self.assertIn("run_binding_mismatch", info["error"])
        with open(os.path.join(self.host, "collection.json")) as f:
            self.assertEqual(json.load(f)["run"]["uuid"], "other-run")
        self.assertEqual(os.listdir(self.host), ["collection.json"])

    def test_two_runs_use_separate_directories_and_first_unchanged(self):
        data1, data2 = b"run one", b"run two"
        host1 = os.path.join(self.base, "runs", "run-1", "task", "epoch1")
        host2 = os.path.join(self.base, "runs", "run-2", "task", "epoch1")
        l1 = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/out.txt", data1)]}
        l2 = {"ok": True, "root": collect.FINAL_DIR, "root_state": "dir", "skipped": [], "errors": [], "entries": [entry("/output/final/out.txt", data2)]}
        i1 = run_collect(FakeSandbox(l1, {"/output/final/out.txt": data1}), host1, {**RUN, "uuid": "unit-run-0001"})
        i2 = run_collect(FakeSandbox(l2, {"/output/final/out.txt": data2}), host2, {**RUN, "uuid": "unit-run-0002"})
        self.assertEqual(i1["status"], "complete")
        self.assertEqual(i2["status"], "complete")
        with open(os.path.join(host1, "final", "out.txt"), "rb") as f:
            self.assertEqual(sha(f.read()), sha(data1))
        self.assertEqual(i1["files"][0]["sha256_collected"], sha(data1))
        self.assertEqual(i2["files"][0]["sha256_collected"], sha(data2))

    def test_validate_sandbox_path(self):
        self.assertEqual(collect.validate_sandbox_path("/output/final/a/b.txt"), (["a", "b.txt"], None))
        for bad in ("/output/final", "/output/final/", "/output/final/../x", "/output/final/a/./b", "/output/finalx/a", "a", None, "/output/final/a//b"):
            segs, why = collect.validate_sandbox_path(bad)
            self.assertIsNone(segs, bad)
            self.assertTrue(why, bad)


def run_collect(sb, host, run_binding, note="scorer", **kw):
    return asyncio.run(collect.collect_final_outputs(host, note=note, run_binding=run_binding, sb=sb, **kw))


if __name__ == "__main__":
    unittest.main()
