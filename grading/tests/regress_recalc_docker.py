"""B5 regression (Codex review rounds logs/pilot-a-review-6uxm37u9, logs/pilot-final-review-ogcsjzyp, logs/pilot-closeout-review-wzwtf89y) through the real converter (LibreOffice headless in the trusted image, no
network): a formula-only PO audit workbook is recalculated in a fresh scratch directory and graded
end to end (every deterministic item passes from recalculated values); a damaged input through the
same code path fails with no values and no reuse of the earlier output; a later valid conversion
still works. Input files are never modified (hashes before and after).
Usage: harness/tests/run_isolated.sh <root> grading.tests.regress_recalc_docker --output-root <new dir>"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import openpyxl

from grading import checks_1137e2bb as CK, extract as X
from grading.fixtures_1137e2bb import TASK, build_fixture

ROOT = os.environ.get("HARNESS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--output-root", required=True); args = ap.parse_args()
    root = Path(args.output_root); root.mkdir(parents=True, exist_ok=False)
    rubric = json.load(open(os.path.join(ROOT, "private", "rubric", f"{TASK}.json"), encoding="utf-8"))
    reference = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{TASK}.json"), encoding="utf-8"))
    build_fixture(str(root / "formula"), "positive")
    final = root / "formula" / "final"
    xlsx = final / "PO_Audit.xlsx"
    wb = openpyxl.load_workbook(xlsx)
    s = wb["RawData"]
    for r in range(2, s.max_row + 1):  # the flag columns become formulas without cached values
        s.cell(r, 9, f"=IF(ROUND(D{r},2)<>ROUND(E{r},2),1,0)")
        s.cell(r, 10, f'=IF(AND(F{r}="CASE",MOD(C{r},G{r})<>0),1,0)')
        s.cell(r, 12, f"=I{r}+J{r}")
    wb.save(xlsx)
    hashes_before = {str(p): sha(p) for p in (xlsx, final / "PO_Audit_Summary.docx")}
    evidence = {"image": X.IMAGE, "hashes_before": hashes_before}

    # 1. real recalculation of the formula workbook, graded end to end
    ex = X.extract_all(str(final), str(root / "work_graded"), recalc=True)
    rc1 = ex["xlsx"]["PO_Audit.xlsx"]["recalc"]
    check("formula workbook: recalculation status ok with soffice exit 0", rc1["status"] == "ok" and rc1["soffice_rc"] == 0, {k: rc1.get(k) for k in ("status", "reason", "soffice_rc", "runner_rc", "soffice_stderr")})
    check("formula workbook: output newly produced in the fresh scratch directory", rc1.get("recalculated_copy", "").startswith(rc1["scratch"]) and os.path.getsize(rc1["recalculated_copy"]) > 0, rc1.get("recalculated_copy"))
    check("formula workbook: converter version and image ID recorded", bool(rc1.get("converter_version")) and rc1.get("image", "").startswith("sha256:") and rc1["image"] == X.IMAGE, {k: rc1.get(k) for k in ("converter_version", "image")})
    check("formula workbook: working copy verified against the original before conversion", ex["xlsx"]["PO_Audit.xlsx"]["copy_verified"] is True and ex["originals_unchanged"] is True)
    filled = ex["xlsx"]["PO_Audit.xlsx"]["value_sources"]["recalculated_cells"]
    check("formula workbook: 123 formula cells filled from the recalculation", len(filled) == 123, len(filled))
    cmp_ = ex["xlsx"]["PO_Audit.xlsx"]["recalc_comparison"]
    check("formula workbook: comparison classes = 123 cached_missing, 0 differs, 0 failed", (cmp_["cached_missing"], cmp_["differs"], cmp_["recalculation_failed"]) == (123, 0, 0), cmp_)
    res = CK.run_checks(ex, reference, rubric, integrity={"PO_Audit.xlsx": True, "PO_Audit_Summary.docx": True})
    fails = sorted(i for i, r in res["items"].items() if r["verdict"] == "fail"); cannot = sorted(i for i, r in res["items"].items() if r["verdict"] == "cannot_assess")
    check("formula workbook: every deterministic item passes from recalculated values", not fails and not cannot, {"fail": fails, "cannot": cannot})
    evidence["formula_recalc"] = {k: rc1.get(k) for k in ("status", "scratch", "input_path", "output_path", "input_sha256", "output_sha256", "soffice_rc", "runner_rc", "converter_version", "image")} | {"filled_cells": len(filled), "comparison": cmp_}

    # 2. damaged input through the SAME input path and the SAME parent work directory (Codex round 3 same_path_stale):
    #    the valid workbook is converted first, then the file at that path is overwritten with damaged bytes
    same_path = root / "same_input.xlsx"
    shutil.copyfile(xlsx, same_path)
    rc_same_ok = X.recalculate_xlsx(str(same_path), str(root / "work_graded" / "same_path"))
    same_path.write_bytes(b"synthetic invalid workbook")
    rc2 = X.recalculate_xlsx(str(same_path), str(root / "work_graded" / "same_path"))
    check("same path: first conversion of the valid workbook ok", rc_same_ok["status"] == "ok", rc_same_ok.get("reason"))
    check("same path: scratch directories differ although input path and work directory are the same", rc_same_ok["scratch"] != rc2["scratch"] and os.path.dirname(rc_same_ok["scratch"]) == os.path.dirname(rc2["scratch"]))
    evidence["same_path"] = {"first": {k: rc_same_ok.get(k) for k in ("status", "scratch", "input_sha256", "output_sha256")}, "second": {k: rc2.get(k) for k in ("status", "reason", "scratch", "input_sha256", "soffice_rc", "produced")}}
    check("damaged input: status failed with a reason", rc2["status"] == "failed" and rc2.get("reason"), {k: rc2.get(k) for k in ("status", "reason", "soffice_rc", "produced", "soffice_stdout", "soffice_stderr")})
    check("damaged input: no values and no recalculated copy returned", "values" not in rc2 and "recalculated_copy" not in rc2)
    check("damaged input: fresh scratch directory, different from the first conversion", rc2["scratch"] != rc1["scratch"] and rc2["input_sha256"] != rc1["input_sha256"])
    check("damaged input: nothing produced or the product rejected", rc2.get("produced") in ([], None) or rc2["reason"].startswith(("recalculated workbook unreadable", "soffice")), rc2.get("produced"))
    evidence["damaged_recalc"] = {k: rc2.get(k) for k in ("status", "reason", "scratch", "input_sha256", "soffice_rc", "runner_rc", "produced", "soffice_stdout", "soffice_stderr")}

    # 3. a later valid conversion is unaffected
    rc3 = X.recalculate_xlsx(str(xlsx), str(root / "work_graded" / "recalc_again"))
    check("valid input again: status ok", rc3["status"] == "ok", rc3.get("reason"))
    check("valid input again: same recalculated flag values as the first conversion", rc3.get("values", {}).get("RawData") == rc1["values"].get("RawData"))
    evidence["valid_again"] = {k: rc3.get(k) for k in ("status", "scratch", "output_sha256", "soffice_rc")}

    hashes_after = {str(p): sha(p) for p in (xlsx, final / "PO_Audit_Summary.docx")}
    check("input files unchanged (hashes before == after)", hashes_after == hashes_before)
    evidence["hashes_after"] = hashes_after
    (root / "results.json").write_text(json.dumps({"checks": CHECKS, "evidence": evidence}, indent=1, default=str))
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== RECALC DOCKER {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {root / 'results.json'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
