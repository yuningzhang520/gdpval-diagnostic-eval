"""1137e2bb-bdf9-4876-b572-f29b7de5e595: price-mismatch and case-pack flags from 'Reference_PO Data.xlsx'."""
import collections
from common import inp, ws_values, save

TID = "1137e2bb-bdf9-4876-b572-f29b7de5e595"


def main():
    ws = ws_values(inp(TID, "Reference_PO Data.xlsx"), "RawData")
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None]
    lines = []
    for r in rows:
        po, sku, units, entered, expected, uom, case, loc = r[:8]
        pm = 1 if abs(float(entered) - float(expected)) > 1e-9 else 0
        pm_cents = 1 if round(float(entered), 2) != round(float(expected), 2) else 0
        cp = 1 if (str(uom).strip().upper() == "CASE" and case and float(units) % float(case) != 0) else 0
        cp_missing = 1 if (str(uom).strip().upper() == "CASE" and (not case or float(case) <= 0)) else 0
        lines.append({"po": po, "sku": sku, "units": units, "entered": entered, "expected": expected, "uom": uom, "case": case,
                      "price_mismatch": pm, "price_mismatch_2dp": pm_cents, "case_pack": cp, "case_pack_missing": cp_missing, "total": pm + cp})
    tot_pm = sum(l["price_mismatch"] for l in lines)
    tot_cp = sum(l["case_pack"] for l in lines)
    by_sku = collections.defaultdict(lambda: [0, 0])
    for l in lines:
        by_sku[l["sku"]][0] += l["price_mismatch"]
        by_sku[l["sku"]][1] += l["case_pack"]
    print(f"lines={len(lines)} price_mismatch={tot_pm} (2dp variant {sum(l['price_mismatch_2dp'] for l in lines)}) case_pack={tot_cp} total={tot_pm+tot_cp} case_pack_missing_rows={sum(l['case_pack_missing'] for l in lines)}")
    print("UOM values:", collections.Counter(str(l["uom"]) for l in lines), "blank case packs:", sum(1 for l in lines if not l["case"]))
    for sku, (a, b) in sorted(by_sku.items()):
        if a + b:
            print(f"  {sku}: price={a} case={b} total={a+b}")
    print("flagged lines:", [(l["po"], l["sku"], l["units"], l["price_mismatch"], l["case_pack"]) for l in lines if l["total"]])
    save(TID, {"lines": lines, "total_price_mismatch": tot_pm, "total_case_pack": tot_cp, "total_errors": tot_pm + tot_cp,
               "by_sku": {k: {"price": v[0], "case": v[1], "total": v[0] + v[1]} for k, v in by_sku.items() if v[0] + v[1]}})
