#!/usr/bin/env python
"""Deterministic regression checks for the prepaid task's quantization (7d7fc9a7). Each assertion
names a specific value; no assertion claims that the two total paths are equal in general.
Usage: .venv/bin/python -I scripts/recalc/test_7d7fc9a7_quantization.py"""
import os
import sys
from decimal import Decimal
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import task_7d7fc9a7_prepaid as t  # noqa: E402


def main():
    checks = []
    # Boundary value stated in the adjudication: 185870861/200 = 929354.305 quantizes HALF_UP to .31.
    v = t.q_cents(Fraction(185870861, 200))
    checks.append(("q_cents(185870861/200) == 929354.31", v == Decimal("929354.31"), v))
    # HALF_UP semantics on the rational: ties go away from zero; below-tie values round down.
    checks.append(("q_cents(5/1000) == 0.01", t.q_cents(Fraction(5, 1000)) == Decimal("0.01"), t.q_cents(Fraction(5, 1000))))
    checks.append(("q_cents(-5/1000) == -0.01", t.q_cents(Fraction(-5, 1000)) == Decimal("-0.01"), t.q_cents(Fraction(-5, 1000))))
    checks.append(("q_cents(4999/1000000) == 0.00", t.q_cents(Fraction(4999, 1000000)) == Decimal("0.00"), t.q_cents(Fraction(4999, 1000000))))
    # The task's own figures, recomputed from the invoice PDFs.
    r = t.compute()
    tot = r["totals"]
    checks.append(("exact total == 185870861/200", tot["exact_total"] == Fraction(185870861, 200), tot["exact_total"]))
    checks.append(("path (i) sum of quantized balances == 929354.31", tot["path_i_sum_of_quantized_balances"] == Decimal("929354.31"), tot["path_i_sum_of_quantized_balances"]))
    checks.append(("path (ii) quantize exact sum once == 929354.31", tot["path_ii_quantize_exact_sum_once"] == Decimal("929354.31"), tot["path_ii_quantize_exact_sum_once"]))
    checks.append(("1250 April == 559377.61", t.q_cents(r["ending_1250"][4]) == Decimal("559377.61"), t.q_cents(r["ending_1250"][4])))
    checks.append(("1251 April == 369976.70", t.q_cents(r["ending_1251"][4]) == Decimal("369976.70"), t.q_cents(r["ending_1251"][4])))
    checks.append(("1251 March == 415537.13 (exact 415537.125)", t.q_cents(r["ending_1251"][3]) == Decimal("415537.13") and r["ending_1251"][3] == Fraction(415537125, 1000), t.q_cents(r["ending_1251"][3])))
    failed = [c for c in checks if not c[1]]
    for name, ok, val in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  (got {val})")
    if failed:
        raise SystemExit(f"{len(failed)} check(s) failed")
    print(f"all {len(checks)} checks passed")


if __name__ == "__main__":
    main()
