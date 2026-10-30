"""b5d2e6f1-62a2-433a-bcdd-95b260cdd860: brand and store-brand totals from the source
'Store Sales Report'; also measures how far the gold 'Data' sheet departs from the source and how
the gold computes ST%.

Reference for brand totals: sums over the SOURCE file (the prompt says "using the attached weekly
sales data sheet"). ST% reference: ratio of sums (sum of Sales Quantity / sum of Stock On Hand) per
brand or store-brand pair, as the rubric states; the mean of row-level ratios is computed only to
document the gold's method."""
import collections
import re
import zipfile
from common import inp, gold, ws_values, save

TID = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"
NUM = ["WTD Qty", "WTD $", "WTD SOH", "MTD Qty", "MTD $", "MTD SOH", "YTD Qty", "YTD $", "YTD SOH"]
GOLD_FILE = "Weekly Sales Analysis.xlsx"


def ratio(n, d):
    return n / d if d else None


def main():
    ws = ws_values(inp(TID, "Weekly Sales Data.xlsx"), "Store Sales Report")
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None]
    by_brand = collections.defaultdict(lambda: [0.0] * 9)
    by_pair = collections.defaultdict(lambda: [0.0] * 9)
    row_ratios = collections.defaultdict(lambda: {"WTD": [], "MTD": [], "YTD": []})
    stores = set()
    for r in rows:
        store, brand = str(r[0]).strip(), str(r[1]).strip()
        stores.add(store)
        vals = [float(x or 0) for x in r[5:14]]
        for i, v in enumerate(vals):
            by_brand[brand][i] += v
            by_pair[(store, brand)][i] += v
        for h, (qi, si) in {"WTD": (0, 2), "MTD": (3, 5), "YTD": (6, 8)}.items():
            if vals[si]:
                row_ratios[brand][h].append(vals[qi] / vals[si])
    grand = [sum(by_brand[b][i] for b in by_brand) for i in range(9)]

    def st(v):
        return {"WTD": ratio(v[0], v[2]), "MTD": ratio(v[3], v[5]), "YTD": ratio(v[6], v[8])}

    brand_table = {b: dict(zip(NUM, v)) | {"ST%_ratio_of_sums": st(v)} for b, v in sorted(by_brand.items())}
    mean_of_rows = {b: {h: (sum(x) / len(x) if x else None) for h, x in d.items()} for b, d in row_ratios.items()}
    print(f"source rows={len(rows)} stores={len(stores)} brands={len(by_brand)} store-brand pairs={len(by_pair)}")
    for b, v in brand_table.items():
        print(f"  {b:<18} WTDqty={v['WTD Qty']:.0f} WTD$={v['WTD $']:.2f} WTDsoh={v['WTD SOH']:.0f} MTDqty={v['MTD Qty']:.0f} YTDqty={v['YTD Qty']:.0f} YTD$={v['YTD $']:.2f}")
    print(f"  GRAND  WTDqty={grand[0]:.0f} WTD$={grand[1]:.2f} WTDsoh={grand[2]:.0f} MTDqty={grand[3]:.0f} MTD$={grand[4]:.2f} YTDqty={grand[6]:.0f} YTD$={grand[7]:.2f} YTDsoh={grand[8]:.0f}")

    # Gold comparison 1: gold 'Sales by Brand' totals versus source-derived totals.
    g = ws_values(gold(TID, GOLD_FILE), "Sales by Brand")
    gold_brand = {}
    for r in g.iter_rows(min_row=4, values_only=True):
        if r[0] and r[0] != "Grand Total":
            gold_brand[str(r[0])] = [float(x) for x in r[1:13] if x is not None]
    diffs, st_method = {}, {}
    for b, v in gold_brand.items():
        s = brand_table.get(b)
        if not s:
            diffs[b] = "brand missing in source"
            continue
        src = [s[k] for k in NUM]
        gv = [v[0], v[1], v[2], v[4], v[5], v[6], v[8], v[9], v[10]]  # skip ST% columns
        diffs[b] = [round(a - c, 2) for a, c in zip(gv, src)]
        st_method[b] = {h: {"gold": v[gi], "ratio_of_sums": s["ST%_ratio_of_sums"][h], "mean_of_row_ratios": mean_of_rows[b][h]}
                        for h, gi in (("WTD", 3), ("MTD", 7), ("YTD", 11))}
    print("gold 'Sales by Brand' minus source-derived totals (qty,$,SOH x WTD/MTD/YTD):")
    for b, d in diffs.items():
        print(f"  {b:<18} {d}")
    print("gold ST% versus ratio-of-sums and mean-of-row-ratios (WTD):")
    for b, d in st_method.items():
        w = d["WTD"]
        print(f"  {b:<18} gold={w['gold']:.5f} ratio_of_sums={w['ratio_of_sums']:.5f} mean_of_rows={w['mean_of_row_ratios']:.5f}")

    # Gold comparison 2: how the gold pivot aggregates each data field (from the package XML).
    with zipfile.ZipFile(gold(TID, GOLD_FILE)) as z:
        pivot_fields = {}
        for n in z.namelist():
            if n.startswith("xl/pivotTables/") and n.endswith(".xml"):
                x = z.read(n).decode("utf-8", "replace")
                pivot_fields[n] = [(re.search(r'name="([^"]+)"', f).group(1), (re.search(r'subtotal="([^"]+)"', f) or [None, "sum"])[1])
                                   for f in re.findall(r"<dataField [^>]*/>", x)]
    print("gold pivot data fields (name, aggregation):", pivot_fields)

    # Gold comparison 3: gold 'Data' tab versus the source, category changes separated from value changes.
    gd = ws_values(gold(TID, GOLD_FILE), "Data")
    gold_rows = [r for r in gd.iter_rows(min_row=2, values_only=True) if r[1] is not None]
    hdr = [c.value for c in ws[1]]
    col_diff = collections.Counter()
    for sr, gr in zip(rows, gold_rows):
        for j in range(18):
            sv, gv = sr[j], gr[j + 1]
            if j == 0:
                sv = str(sv).replace("Store", "").strip()
                gv = str(gv).strip()
            if (sv or "") != (gv or "") and not (isinstance(sv, (int, float)) and isinstance(gv, (int, float)) and abs(sv - gv) < 1e-9):
                col_diff[hdr[j]] += 1
    category_cols = {"Category"}
    diff_split = {"category_cells": {k: v for k, v in col_diff.items() if k in category_cols},
                  "value_cells": {k: v for k, v in col_diff.items() if k not in category_cols}}
    print(f"gold 'Data' vs source: rows compared={len(gold_rows)} (source {len(rows)}); differing cells: {diff_split}")
    save(TID, {"source_rows": len(rows), "stores": len(stores), "brands": len(by_brand), "pairs": len(by_pair),
               "by_brand": brand_table, "grand_total": dict(zip(NUM, grand)),
               "gold_minus_source_by_brand": diffs, "gold_st_pct_method": st_method, "gold_pivot_data_fields": pivot_fields,
               "gold_data_vs_source_diff_cells": diff_split})
