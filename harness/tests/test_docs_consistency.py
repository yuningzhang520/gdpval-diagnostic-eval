"""README and config consistency (B2-3): every CLI flag mentioned in the README exists in the corresponding
argparse parser, the config's grader version equals the code's, and the README names the modules that exist.
No model, provider or docker call."""
import os
import re
import unittest

from grading.grade import ENGINE_VERSION, TASK_MODULES
from harness import launcher as L

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def argparse_flags(path: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        return set(re.findall(r'add_argument\("(--[a-z-]+)"', f.read()))


class DocsConsistencyTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.readme = f.read()

    def test_readme_flags_exist_in_the_cli_parsers(self):
        known = (argparse_flags(os.path.join(ROOT, "harness", "launcher.py")) | argparse_flags(os.path.join(ROOT, "grading", "run_grading.py"))
                 | argparse_flags(os.path.join(ROOT, "harness", "ledger_admin.py")) | argparse_flags(os.path.join(ROOT, "harness", "batch.py"))
                 | argparse_flags(os.path.join(ROOT, "harness", "scheduler.py")))
        mentioned = set(re.findall(r"(--[a-z][a-z-]+)", self.readme)) - {"--frozen", "--revision-file", "--out", "--parquet", "--deep", "--supplementary", "--tasks", "--log", "--task-id", "--format"}
        unknown = sorted(f for f in mentioned if f not in known and f not in ("--dry-run", "--real-run"))
        self.assertEqual(unknown, [], unknown)
        self.assertTrue({"--dry-run", "--real-run", "--confirm", "--judge", "--rejudge", "--confirm-judge", "--resolution", "--run-label", "--confirm-batch"} <= known)

    def test_readme_modules_exist_and_grader_version_matches_config(self):
        for mod in ("harness/launcher.py", "harness/task.py", "harness/samples.py", "harness/tools.py", "harness/collect.py", "harness/budget.py", "harness/ledger_admin.py",
                    "grading/run_grading.py", "grading/grade.py", "grading/extract.py", "grading/checks_1137e2bb.py", "grading/judge.py", "grading/review.py", "grading/costs.py",
                    "harness/tests/run_isolated.sh", "grading/tests/regress_grading_cli.py", "docs/pilot_a_request.md",
                    "harness/batch.py", "harness/scheduler.py", "harness/unit_gate.py", "harness/run_metadata.py", "grading/gold_variants_1137e2bb.py", "grading/tests/test_gold_1137e2bb.py", "grading/gold_variants_7d7fc9a7.py", "grading/tests/test_gold_7d7fc9a7.py", "grading/engine/"):
            self.assertIn(f"`{mod}`", self.readme, mod); self.assertTrue(os.path.exists(os.path.join(ROOT, mod)), mod)
        cfg = L.load_config(os.path.join(ROOT, "config.json"))
        self.assertEqual(cfg["grading"]["engine_version"], ENGINE_VERSION)
        self.assertEqual(cfg["grading"]["task_grader_versions"], {t: m["version"] for t, m in TASK_MODULES.items()})
        self.assertNotIn("Blocking", cfg["generation"]["token_semantics"]["launcher_wiring"])

    def test_readme_paid_examples_are_placeholders_not_runnable_commands(self):
        for line in self.readme.splitlines():
            if "harness.launcher --real-run" in line or "--judge-model" in line:  # the paid command examples, not the prose that names the flags
                self.assertTrue("<" in line and ">" in line, line)  # every paid example carries placeholders


if __name__ == "__main__":
    unittest.main()
