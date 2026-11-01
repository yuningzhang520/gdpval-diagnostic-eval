#!/usr/bin/env python
"""Rubric-to-capability mapping (DRAFT, preregistration 1.17): every rubric item of the ten selected tasks gets one
primary capability from a fixed, ordered rule list applied to the criterion text, plus the rule that fired. Manual
overrides (item-level, with a reason) are applied after the rules and recorded as such. Deterministic: the same
rubric text gives the same map. The map is written to grading/capability_map.json; it carries item numbers, rubric
item ids, weights, the capability, the rule and a short criterion excerpt (the rubric text is public in GDPval).

Capabilities (PLAN.md section 5; failure taxonomy):
  requirements   - deliverable-spec compliance: required files, sheets, slides, sections, columns, titles, fields
  grounding      - reference grounding: figures, labels or items that must be taken from the attached sources
  rule_execution - business-rule execution: computed figures, flags, classifications, reconciliations by rule
  coverage       - coverage: every required element present, no omissions or extras
  consistency    - cross-file / cross-table consistency: one part of the deliverable agrees with another
  mechanics      - deliverable mechanics: formulas and links, pivot / chart objects, error-free cells, sortability
  presentation   - usability and presentation: formatting, readability, clarity, style
Usage: python scripts/capability_map.py [--check]  (--check: verify the committed map equals a fresh build)"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "grading", "capability_map.json")
VERSION = "capability-map-2026-11-01.1"

# ordered: the first matching rule decides; each rule is (name, capability, regex on the lower-cased criterion)
RULES = [
    ("overall_style", "presentation", r"overall formatting|formatting and style"),
    ("display_format", "presentation", r"\bformatted\b|\bformat\b|\bfont\b|\bbold\b|\bcolou?r\b|readab|legib|professional|visually"),
    ("deliverable_count", "requirements", r"\bexactly (\d+|one|two|three|four|five|six|seven|eight|nine|ten) (slides?|tabs?|sheets?|worksheets?|files?|tables?|workbooks?)\b|\bsingle (excel|word|powerpoint)?\s*(workbook|file|document|deck)"),
    ("coa_source", "grounding", r"chart[- ]of[- ]accounts|coa\.xlsx|\bcoa\b"),
    ("column_list", "requirements", r"(includes?|adds?) (the following|these|four|three|two) (functional )?columns|\bcolumns? (named|labeled|titled|for)\b|contains? an? .* column\b"),
    ("cross_artifact", "consistency", r"reconcil|consistent with|represented in the .* table|matches? the (workbook|excel|detail|summary|spreadsheet)|(word|document|memo|email|narrative)\b.*\bstates?\b.*\d|equal to the sum of .* (from|on) the (detail|respective)|equals? the .* (on|in) the (detail|summary|other) (tab|sheet|table)"),
    ("formula_link", "mechanics", r"(linked|driven|built|calculated|computed) (by|with|using) formulas?|\bformulas? (reference|link|pull)|hard-?coded|\blinked\b|pivot ?table|\bpivot\b|refresh"),
    ("error_free_sortable", "mechanics", r"error values?|#value|#div|#ref|\bsortable\b|\bfilter|\bbinary\b"),
    ("numeric_target", "rule_execution", r"±|\d+(\.\d+)?\s?%|\$\s?[\d,]+|equals? \$?[\d,]+(\.\d+)?\b|\bis \$?[\d,]+(\.\d+)?\b|=\s*\d|sums? to 100"),
    ("logic_rule", "rule_execution", r"\bflag(s|ged)?\b|\blogic\b|calculated|computed|straight-line|amorti[sz]|\bonly the following\b|\blabeled (cost|investment|high|medium|low)\b|classif|divisible|\bsum of\b|\btotals? (equal|equals)\b|\bbeginning balance\b.*\bending balance\b|\bwhen\b.*\b(is|are|equals?)\b.*\b(then|is|are)\b"),
    ("every_no_omission", "coverage", r"\bevery\b|no omissions?|\bno (categories|items|rows|lines) outside\b|\bincludes? (each|all)\b|\ball \d+\b|\bat least one\b|\bno duplicates?\b|\bexactly (\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b"),
    ("source_match", "grounding", r"matches? the (amount|value|source|invoice|input)|exactly matches|from the (source|attached|input|reference)|as (listed|shown) (in|on) the|chart[- ]of[- ]accounts|coa\.xlsx|\bsource (data|file|workbook)\b"),
    ("structure_required", "requirements", r"\.(xlsx|xls|docx|doc|pptx|pdf)\b|\bfile\b|workbook|worksheet|\btab\b|\bsheet\b|\bslides?\b|\bsection\b|\bcolumns?\b|\brows?\b|\bheader\b|\btitle\b|\btable\b|\bchart\b|\bincludes?\b|\bcontains?\b|\bprovides?\b|\bdelivers?\b|\bpresentation\b|\bdocument\b|\bdeck\b|\bmemo\b|\bemail\b|\bplan\b|\bsummary\b"),
]
OVERRIDES: dict = {}  # "task_id:item" -> {"capability": ..., "reason": ...}; filled only by recorded human or review decisions


def classify(criterion: str) -> tuple[str, str]:
    t = criterion.lower()
    for name, cap, rx in RULES:
        if re.search(rx, t):
            return cap, name
    return "requirements", "default"


def build() -> dict:
    sel = json.load(open(os.path.join(ROOT, "data", "selected_tasks.json"), encoding="utf-8"))["tasks"]
    tasks = {}
    for t in sel:
        tid = t["task_id"]
        rub = json.load(open(os.path.join(ROOT, "private", "rubric", f"{tid}.json"), encoding="utf-8"))
        items = []
        for i, r in enumerate(rub, 1):
            cap, rule = classify(r["criterion"])
            ov = OVERRIDES.get(f"{tid}:{i}")
            items.append({"item": i, "rubric_item_id": r.get("rubric_item_id"), "weight": r["score"], "capability": ov["capability"] if ov else cap,
                          "rule": "override" if ov else rule, "override_reason": ov["reason"] if ov else None, "criterion_excerpt": r["criterion"][:120]})
        tasks[tid] = {"group": t["group"], "occupation": t["occupation"], "items": items,
                      "by_capability": {c: {"items": sum(1 for x in items if x["capability"] == c), "weight": sum(x["weight"] for x in items if x["capability"] == c)} for c in sorted({x["capability"] for x in items})}}
    caps = sorted({x["capability"] for t in tasks.values() for x in t["items"]})
    return {"version": VERSION, "status": "DRAFT: rule-based proposal pending human review; preregistered at freeze-v1 with any recorded overrides",
            "rules": [{"name": n, "capability": c, "regex": rx} for n, c, rx in RULES], "overrides": OVERRIDES, "tasks": tasks,
            "totals": {c: {"items": sum(1 for t in tasks.values() for x in t["items"] if x["capability"] == c), "weight": sum(x["weight"] for t in tasks.values() for x in t["items"] if x["capability"] == c)} for c in caps},
            "item_count": sum(len(t["items"]) for t in tasks.values())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    m = build()
    if args.check:
        with open(OUT, encoding="utf-8") as f:
            ok = json.load(f) == m
        print("capability map matches a fresh build" if ok else "capability map differs from a fresh build")
        return 0 if ok else 1
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)
    print(json.dumps({"items": m["item_count"], "totals": m["totals"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
