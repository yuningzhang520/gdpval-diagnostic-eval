"""Gold-first verification of the 7d7fc9a7 grader: the expert workbook grades to its declared baseline (fast path on
cached values, and under GOLD_RECALC_DOCKER=1 through LibreOffice), the values-only twin grades to the twin baseline
(item 7 additionally fails: no formulas), and every catalog variant grades to its declared full map. Observed
transitions go to $GRADING_REGRESSION_LOG_DIR/gold_transitions_7d7fc9a7.json.
Run: harness/tests/run_isolated.sh <root> unittest grading.tests.test_gold_7d7fc9a7"""
import json
import os
import shutil
import tempfile
import unittest

import openpyxl

from grading import checks_7d7fc9a7 as CK, extract as X
from grading import gold_variants_7d7fc9a7 as GV

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{GV.TASK}.json"), encoding="utf-8"))
TABLE: dict = {}


def grade(final: str, work: str, *, recalc: bool = False) -> dict:
    ex = X.extract_all(final, work, recalc=recalc)
    res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "ex": ex, "map": {i: r["verdict"] for i, r in res["items"].items()}, "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def implied_critical(vmap: dict) -> dict:
    out = {}
    for cid, spec in CK.CRITICAL.items():
        vs = [vmap.get(i, "pending") for i in spec["items"]]
        out[cid] = "fail" if "fail" in vs else ("pass" if all(v == "pass" for v in vs) else "not_confirmed")
    return out


def _dump(name):
    out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(TABLE, f, indent=1, default=str)


class GoldAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_7d7f_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.gold_final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, cls.gold_final)
        cls.twin_final = GV.build_twin(os.path.join(cls.base, "twin"))
        cls.gold = grade(cls.gold_final, os.path.join(cls.base, "work_gold"))
        cls.twin = grade(cls.twin_final, os.path.join(cls.base, "work_twin"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "twin_map": cls.twin["map"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_7d7fc9a7.json")
        cls.tmp.cleanup()

    def test_gold_original_grades_to_the_declared_baseline(self):
        self.assertEqual(set(self.gold["map"]), set(CK.D_ITEMS))
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "pass", "C2": "fail", "C3": "pass", "C4": "fail"})
        items = self.gold["res"]["items"]
        self.assertIn("no cell on the summary shows the total prepaid balance", items[10]["note"])  # expert defect: no total cell (A-10b)
        self.assertIn("no variance figure", items[30]["note"])  # expert defect: 1250 variance row without monthly figures (A-30)
        sch = self.gold["res"]["schedules"]
        self.assertEqual((sch["1250"]["lines"], sch["1251"]["lines"], len(sch["1250"]["match"]["matched"]), len(sch["1251"]["match"]["matched"])), (41, 22, 41, 25))  # BCBS: four invoices on one consolidated line
        found = self.gold["res"]["summary"]["found"]
        self.assertEqual({k: v["how"] for k, v in found.items()}, {"balance_1250": "value", "balance_1251": "value", "total": "absent", "ytd_1250": "value", "ytd_1251": "value"})
        self.assertTrue(all(found[k]["formula"] for k in ("balance_1250", "balance_1251", "ytd_1250", "ytd_1251")))

    def test_values_only_twin_grades_to_the_twin_baseline(self):
        self.assertEqual(self.twin["map"], GV.TWIN_BASELINE, {i: v for i, v in self.twin["map"].items() if v != GV.TWIN_BASELINE[i]})
        self.assertIn("literal value", self.twin["res"]["items"][7]["note"])


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_7d7f_variants_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.twin_final = GV.build_twin(os.path.join(cls.base, "twin"))
        cls.variants_dir = os.path.join(cls.base, "variants")

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_7d7fc9a7.json")
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        final = GV.build_variant(name, self.twin_final, self.variants_dir)
        g = grade(final, os.path.join(self.base, "work", name))
        expected = GV.expected_map(name)
        diff = {i: {"expected": expected[i], "actual": g["map"].get(i), "note": (g["res"]["items"][i]["note"] or "")[:220] if i in g["res"]["items"] else None} for i in expected if g["map"].get(i) != expected[i]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed_fail": sorted(i for i, v in g["map"].items() if v == "fail"),
                       "observed_cannot_assess": sorted(i for i, v in g["map"].items() if v == "cannot_assess"), "critical": g["critical"], "diff": diff}
        self.assertEqual(set(g["map"]), set(CK.D_ITEMS))
        self.assertEqual(diff, {}, f"{name} ({spec['kind']}): " + json.dumps(diff, indent=1, default=str))
        for i, a in spec.get("attribution", {}).items():
            self.assertEqual(g["res"]["items"][i].get("attribution"), a, f"{name}: item {i} attribution")
        self.assertEqual(g["critical"], implied_critical(expected), f"{name}: critical status must follow the expected item map")


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


@unittest.skipUnless(os.environ.get("GOLD_RECALC_DOCKER") == "1", "set GOLD_RECALC_DOCKER=1 to run the LibreOffice path in the pinned image")
class GoldRecalcDockerTests(unittest.TestCase):
    """The expert workbook (470 formulas) through the real recalculation; the summary linkage cases that need formulas:
    hard-coded summary (7 fails alone), and a total prepaid balance added as a formula over the two balances (10 passes,
    7 unaffected)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_7d7f_recalc_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_7d7fc9a7_recalc.json")
        cls.tmp.cleanup()

    def _variant(self, name, mutate):
        final = os.path.join(self.base, name, "final"); shutil.copytree(GV.GOLD_DIR, final)
        p = os.path.join(final, GV.XLSX); wb = openpyxl.load_workbook(p); mutate(wb); wb.save(p)  # openpyxl drops the cached values: everything depends on the recalculation
        return grade(final, os.path.join(self.base, f"work_{name}"), recalc=True)

    def test_gold_original_through_recalculation_matches_the_baseline(self):
        final = os.path.join(self.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        g = grade(final, os.path.join(self.base, "work_gold"), recalc=True)
        cmp_ = g["ex"]["xlsx"][GV.XLSX]["recalc_comparison"]
        TABLE["gold_recalc_path"] = {"map": g["map"], "recalc_comparison": cmp_}
        self.assertEqual((cmp_["differs"], cmp_["recalculation_failed"]), (0, 0))
        self.assertEqual(g["map"], GV.GOLD_BASELINE, {i: v for i, v in g["map"].items() if v != GV.GOLD_BASELINE[i]})

    def test_summary_hard_coded_fails_only_item_7(self):
        def mutate(wb):
            wv = openpyxl.load_workbook(os.path.join(GV.GOLD_DIR, GV.XLSX), data_only=True)[GV.SUMMARY]
            ws = wb[GV.SUMMARY]
            for r in (7, 8, 9, 12, 13, 14):
                ws.cell(r, 2).value = wv.cell(r, 2).value
        g = self._variant("summary_hard_coded", mutate)
        expected = {**GV.GOLD_BASELINE, 7: "fail"}
        TABLE["summary_hard_coded_recalc"] = {"map": g["map"]}
        self.assertEqual(g["map"], expected, {i: v for i, v in g["map"].items() if v != expected[i]})

    def test_total_prepaid_added_as_a_formula_passes_item_10(self):
        def mutate(wb):
            ws = wb[GV.SUMMARY]; ws.cell(16, 1).value = "Total Prepaid Balance - 4/30/2025"; ws.cell(16, 2).value = "=B9+B14"
        g = self._variant("total_formula", mutate)
        expected = {**GV.GOLD_BASELINE, 10: "pass"}
        TABLE["total_formula_recalc"] = {"map": g["map"]}
        self.assertEqual(g["map"], expected, {i: v for i, v in g["map"].items() if v != expected[i]})


if __name__ == "__main__":
    unittest.main()
