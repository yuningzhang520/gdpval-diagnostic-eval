"""I1 regressions: staging verification fails closed on tampered files, symlinked or traversing
paths, cross-task sources, duplicate destinations, missing and extra files; and passes for the
real repository data against config.json. No Docker, no model.
Run: python -m unittest harness.tests.test_staging_unit -v"""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from harness import samples as S

TID_A = "aaaaaaaa-0000-4000-8000-000000000001"
TID_B = "bbbbbbbb-0000-4000-8000-000000000002"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class StagingVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="staging_unit_")
        self.root = os.path.realpath(self.tmp.name)
        self.a_dir = Path(self.root, "data", "inputs", TID_A)
        self.b_dir = Path(self.root, "data", "inputs", TID_B)
        self.r_dir = Path(self.root, "data", "resources", TID_A, "pages")
        for d in (self.a_dir, self.b_dir, self.r_dir):
            d.mkdir(parents=True)
        (self.a_dir / "a.xlsx").write_bytes(b"alpha workbook")
        (self.b_dir / "b.xlsx").write_bytes(b"beta workbook")
        (self.r_dir / "p.html").write_bytes(b"<html>page</html>")
        self.files = {f"{S.INPUTS_MOUNT}/a.xlsx": str(self.a_dir / "a.xlsx"),
                      f"{S.RESOURCES_MOUNT}/pages/p.html": str(self.r_dir / "p.html")}
        self.expected = {dst: {"source": os.path.relpath(src, self.root), "bytes": os.path.getsize(src), "sha256": sha(Path(src).read_bytes())}
                         for dst, src in self.files.items()}

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, files=None, expected=None):
        return S.verify_staged_files(TID_A, files or self.files, expected or self.expected, [TID_A, TID_B], root=self.root)

    def test_clean_set_passes(self):
        rep = self.verify()
        self.assertEqual(rep["files_verified"], 2)

    def test_tampered_file_fails(self):
        (self.a_dir / "a.xlsx").write_bytes(b"alpha workbook!")
        with self.assertRaisesRegex(S.StagingError, "size .* differs"):
            self.verify()
        (self.a_dir / "a.xlsx").write_bytes(b"alpha workbooX")  # same size, different bytes
        with self.assertRaisesRegex(S.StagingError, "sha256 .* differs"):
            self.verify()

    def test_symlinked_source_fails(self):
        link = self.a_dir / "link.xlsx"
        link.symlink_to(self.a_dir / "a.xlsx")
        files = dict(self.files); files[f"{S.INPUTS_MOUNT}/link.xlsx"] = str(link)
        with self.assertRaisesRegex(S.StagingError, "symlink"):
            self.verify(files)

    def test_symlinked_directory_component_fails(self):
        alias = Path(self.root, "data", "inputs", "alias")
        alias.symlink_to(self.a_dir, target_is_directory=True)
        files = {f"{S.INPUTS_MOUNT}/a.xlsx": str(alias / "a.xlsx")}
        with self.assertRaises(S.StagingError):
            self.verify(files, {f"{S.INPUTS_MOUNT}/a.xlsx": self.expected[f"{S.INPUTS_MOUNT}/a.xlsx"]})

    def test_traversal_in_destination_or_source_fails(self):
        files = {f"{S.INPUTS_MOUNT}/../etc/x": str(self.a_dir / "a.xlsx")}
        with self.assertRaisesRegex(S.StagingError, "not normalised"):
            self.verify(files, {})
        files = {f"{S.INPUTS_MOUNT}/a.xlsx": str(self.a_dir / ".." / TID_B / "b.xlsx")}
        with self.assertRaisesRegex(S.StagingError, "not normalised"):
            self.verify(files, {})
        files = {"/etc/passwd": str(self.a_dir / "a.xlsx")}
        with self.assertRaisesRegex(S.StagingError, "outside the workspace mounts"):
            self.verify(files, {})

    def test_cross_task_source_fails(self):
        files = {f"{S.INPUTS_MOUNT}/b.xlsx": str(self.b_dir / "b.xlsx")}
        with self.assertRaisesRegex(S.StagingError, "another task|outside this task"):
            self.verify(files, {})

    def test_missing_and_extra_files_fail(self):
        files = dict(self.files); files.pop(f"{S.RESOURCES_MOUNT}/pages/p.html")
        with self.assertRaisesRegex(S.StagingError, "not staged"):
            self.verify(files)
        files = dict(self.files); (self.a_dir / "extra.txt").write_bytes(b"x"); files[f"{S.INPUTS_MOUNT}/extra.txt"] = str(self.a_dir / "extra.txt")
        with self.assertRaisesRegex(S.StagingError, "not recorded"):
            self.verify(files)

    def test_duplicate_destination_refused_when_building_the_map(self):
        files: dict[str, str] = {}
        S._add(files, f"{S.INPUTS_MOUNT}/a.xlsx", "/one/a.xlsx", TID_A)
        S._add(files, f"{S.INPUTS_MOUNT}/a.xlsx", "/one/a.xlsx", TID_A)  # identical repeat is harmless
        with self.assertRaisesRegex(S.StagingError, "duplicate destination"):
            S._add(files, f"{S.INPUTS_MOUNT}/a.xlsx", "/two/a.xlsx", TID_A)

    def test_all_problems_reported_at_once(self):
        (self.a_dir / "a.xlsx").write_bytes(b"changed!!")
        files = dict(self.files); files.pop(f"{S.RESOURCES_MOUNT}/pages/p.html")
        with self.assertRaises(S.StagingError) as cm:
            self.verify(files)
        msg = str(cm.exception)
        self.assertIn("3 problem(s)", msg)  # size, sha256 and the missing file are all reported together
        self.assertIn("not staged", msg)
        self.assertIn("sha256", msg)


class RealDataTests(unittest.TestCase):
    def test_repository_data_matches_config(self):
        samples = S.build_samples(verify_config=S.CONFIG)
        self.assertEqual(len(samples), 10)
        self.assertEqual(sum(len(s.files) for s in samples), 43)
        gcp = next(s for s in samples if s.id == S.RESOURCES_TASK)
        self.assertEqual(len(gcp.files), 27)
        for s in samples:
            self.assertEqual(s.metadata["staging_verified"]["files_verified"], len(s.files))

    def test_config_hash_mismatch_fails_closed(self):
        expected = S.expected_staged_from_config(S.CONFIG)
        tid = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
        files = S.task_files(tid, S.load_json(S.MANIFEST))
        bad = {k: dict(v, sha256="0" * 64) for k, v in expected[tid].items()}
        with self.assertRaisesRegex(S.StagingError, "sha256"):
            S.verify_staged_files(tid, files, bad, list(expected))


if __name__ == "__main__":
    unittest.main()


class TaskSetTests(unittest.TestCase):
    """Run classes (2026-11-01): the compatibility task comes from its own manifest and config block; the formal set is untouched."""
    def test_compat_task_set_builds_from_its_own_manifest_and_verifies_against_config(self):
        samples = S.build_samples(task_set="compat", verify_config=S.CONFIG)
        self.assertEqual([s.id for s in samples], ["87da214f-fd92-4c58-9854-f4d0d10adce0"])
        self.assertEqual(sorted(os.path.basename(k) for k in samples[0].files), ["ID Theft Policy (1).docx", "Policy Reimbursement Account Sample.xlsx"])
        self.assertEqual((samples[0].metadata["task_set"], samples[0].metadata["staging_verified"]["files_verified"]), ("compat", 2))
        self.assertEqual(S.task_set_for_manifest("data/selected_tasks.json"), "selected"); self.assertEqual(S.task_set_for_manifest("data/compat_tasks.json"), "compat")
        with self.assertRaises(ValueError):
            S.task_set_for_manifest("data/other.json")
        formal_ids = {t["task_id"] for t in S.load_json(S.SELECTED)["tasks"]}
        self.assertNotIn("87da214f-fd92-4c58-9854-f4d0d10adce0", formal_ids)  # the formal list is unchanged
        self.assertEqual(len(S.build_samples(verify_config=S.CONFIG)), 10)
