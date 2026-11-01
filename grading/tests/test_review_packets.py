"""Verdict-free review packets, label checkpoints and comparison (2026-11-01): the packet never carries an automated
verdict; the sealed file does; labels are checkpointed with a hash before any comparison; the comparison refuses to
run without a checkpoint and reports false PASS / false FAIL / coverage loss with numerators and denominators.
Run: harness/tests/run_isolated.sh <root> unittest grading.tests.test_review_packets -v"""
import csv
import json
import os
import tempfile
import unittest

from grading import review as R

RUBRIC = [{"score": 2, "criterion": "The deliverable is a workbook"}, {"score": 1, "criterion": "Totals equal 15"}, {"score": 1, "criterion": "Summary names the top SKU"}]
CHECKS = {"task": "t", "items": {1: {"verdict": "pass", "note": "readable .xlsx", "attribution": None, "evidence": {"files": ["a.xlsx"]}, "deliverable_value": True, "reference_value": True},
                                 2: {"verdict": "fail", "note": "confirmed violation: sum 14 != 15 [sum]", "attribution": "model_caused", "evidence": {"file": "a.xlsx", "sheet": "S", "violations": [{"kind": "sum", "detail": "14 != 15"}], "cells": ["I2"]}, "deliverable_value": 14, "reference_value": 15}}}
UNITS = [{"item": 3, "source_material": "reference: SKU-0103 has the most errors", "deliverable_excerpt": "Document: begin with SKU-0103"}]
VERDICTS = [{"item": 3, "verdict": "pass", "rationale": "stub keyword rule", "evidence": [], "judge_id": "stub"}]
EXTRACTION = {"inventory": [{"path": "a.xlsx"}, {"path": "b.docx"}]}


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="packets_"); self.out = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_packet_is_verdict_free_and_the_sealed_file_holds_both_verdict_kinds(self):
        rv = R.write_review_materials(os.path.join(self.out, "review"), "run1", RUBRIC, CHECKS, UNITS, VERDICTS, EXTRACTION, grading_pass="p1")
        md = open(rv["items"]).read()
        for leak in ("pass", "fail", "confirmed violation", "14 != 15", "stub keyword rule", "violations", "model_caused", "I2"):
            self.assertNotIn(leak, md.replace("pass, fail or cannot_tell", "").replace("(pass/fail/cannot_tell)", ""), leak)
        self.assertIn("Where to look", md); self.assertIn('"sheet": "S"', md); self.assertIn("reference: SKU-0103", md); self.assertIn("Write your independent judgment", md)
        sealed = json.load(open(rv["judge_verdicts"]))
        self.assertEqual((sealed["deterministic"]["2"]["verdict"], sealed["verdicts"][0]["rationale"], sealed["grading_pass"]), ("fail", "stub keyword rule", "p1"))
        self.assertTrue(sealed["note"].startswith("SEALED"))

    def test_checkpoint_then_compare_and_refusal_without_checkpoint(self):
        rv = R.write_review_materials(os.path.join(self.out, "review"), "run1", RUBRIC, CHECKS, UNITS, VERDICTS, EXTRACTION)
        grades = [{"run_uuid": "run1", "item": 1, "weight": 2, "source": "D", "verdict": "pass", "grading_pass": "p1"}, {"run_uuid": "run1", "item": 2, "weight": 1, "source": "D", "verdict": "fail", "grading_pass": "p1"},
                  {"run_uuid": "run1", "item": 3, "weight": 1, "source": "J", "verdict": "pass", "grading_pass": "p1"}]
        with self.assertRaisesRegex(RuntimeError, "no saved label checkpoint"):
            R.compare_labels(self.out, "run1", grades)
        with open(rv["independent_template"], newline="") as f:
            rows = list(csv.reader(f))
        rows[1][4], rows[1][5] = "pass", "a.xlsx"; rows[2][4], rows[2][5] = "pass", "S!I2 (human says 15)"; rows[3][4] = "fail"
        filled = os.path.join(self.out, "filled.csv")
        with open(filled, "w", newline="") as f:
            csv.writer(f).writerows(rows)
        cp = R.save_label_checkpoint(self.out, "run1", filled, "tester")
        self.assertEqual((cp["labelled_items"], cp["counts"]), ([1, 2, 3], {"pass": 2, "fail": 1, "cannot_tell": 0}))
        self.assertTrue(os.path.exists(cp["copy"]) and os.path.exists(cp["checkpoint"]) and cp["sha256"] == R._sha(cp["copy"]))
        cmp_ = R.compare_labels(self.out, "run1", grades)
        self.assertEqual((cmp_["false_fail_items"], cmp_["false_pass_items"]), ([2], [3]))
        self.assertEqual((cmp_["summary"]["D"]["agreement"], cmp_["summary"]["J"]["agreement"]), ("1/2", "0/1"))
        with self.assertRaisesRegex(ValueError, "unknown label"):
            rows[1][4] = "maybe"
            with open(filled, "w", newline="") as f:
                csv.writer(f).writerows(rows)
            R.save_label_checkpoint(self.out, "run1", filled, "tester")


if __name__ == "__main__":
    unittest.main()
