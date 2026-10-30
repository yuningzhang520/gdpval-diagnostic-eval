"""47ef842d-8eac-4b90-bda8-dd934c228c96: weeks of supply and out-of-stock counts for the five UPCs
from 'Reference Inventory.xlsx'.

Operational definitions, fixed before any model output is seen. The prompt refers to an
"out-of-stock percentage" field that does not exist in the data, so these are this evaluation's
definitions, not the data dictionary's:
- Active store (per UPC): a distinct Store Number that has a row for that UPC in the snapshot (the
  file holds one week, 2025 week 28). The denominator of Percent OOS is the count of active stores.
- Out of stock: Current Week Inv == 0 on the store row (the data holds no negative inventory).
- Weekly unit rate of sale: 7 x sum of 'Daily Inv Sold In Last 4 Wks' over active stores, with the
  recorded values used as they are (a few are negative).
- WOS: sum of Current Week Inv over active stores / weekly unit rate; not computable when the weekly
  rate is 0 (reported as None, never as a finite number).
- 'Avg Days On Hand' holds '-' exactly on the rows whose daily sales are 0 (turnover days not
  computable). Those rows stay in every inventory and sales aggregate; '-' is kept as
  not-computable, never filled with 0 and never averaged."""
import collections
from common import inp, gold, ws_values, save

TID = "47ef842d-8eac-4b90-bda8-dd934c228c96"
UPCS = ["901153373247", "567219040266", "217313054556", "875218534223", "375301052429"]
RULES = {
    "active_store": "distinct Store Number with a row for the UPC in the single-week snapshot; denominator of Percent OOS",
    "oos": "Current Week Inv == 0",
    "weekly_rate": "7 * sum(Daily Inv Sold In Last 4 Wks) over active stores, recorded values as they are",
    "wos": "sum(Current Week Inv) over active stores / weekly_rate; None when weekly_rate == 0",
    "avg_days_on_hand_dash": "kept as not-computable; rows stay in all aggregates; never 0, never averaged",
}
COL = {"store": 4, "upc": 5, "desc": 6, "last_inv": 7, "cur_inv": 8, "inv_change": 9, "daily": 10, "avg_days": 11}


def num(v):
    """Float value, or None for blanks and non-numeric placeholders such as '-'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except ValueError:
        return None


def main():
    ws = ws_values(inp(TID, "Reference Inventory.xlsx"), "DATA")
    hdr = [c.value for c in ws[1]]
    print("columns:", hdr)
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[COL["upc"]] is not None]
    weeks = collections.Counter((r[0], r[1]) for r in rows)
    print(f"rows={len(rows)} year/week combos={dict(weeks)} distinct UPCs={len({str(r[COL['upc']]) for r in rows})}")
    nonnum = {}
    for j in range(COL["last_inv"], COL["avg_days"] + 1):
        c = collections.Counter(str(r[j]) for r in rows if num(r[j]) is None)
        nonnum[hdr[j]] = dict(c)
        print(f"  non-numeric values in '{hdr[j]}': {dict(c)}")
    dash = [r for r in rows if num(r[COL["avg_days"]]) is None]
    zero_daily = [r for r in rows if num(r[COL["daily"]]) == 0]
    dash_fact = {"dash_rows": len(dash), "zero_daily_rows": len(zero_daily),
                 "dash_rows_with_zero_daily": sum(1 for r in dash if num(r[COL["daily"]]) == 0),
                 "zero_daily_rows_with_dash": sum(1 for r in zero_daily if num(r[COL["avg_days"]]) is None)}
    dash_fact["dash_iff_zero_daily"] = (dash_fact["dash_rows_with_zero_daily"] == len(dash) == len(zero_daily) == dash_fact["zero_daily_rows_with_dash"])
    print("'-' vs zero daily sales:", dash_fact)
    out = {}
    for u in UPCS:
        sel = [r for r in rows if str(r[COL["upc"]]).strip() == u]
        stores = [str(r[COL["store"]]).strip() for r in sel]
        active = set(stores)
        cur = [num(r[COL["cur_inv"]]) for r in sel]
        daily = [num(r[COL["daily"]]) for r in sel]
        missing = {"cur_inv": sum(1 for v in cur if v is None), "daily": sum(1 for v in daily if v is None)}
        cur_inv = sum(v for v in cur if v is not None)
        daily_total = sum(v for v in daily if v is not None)
        weekly = 7 * daily_total
        wos = cur_inv / weekly if weekly != 0 else None
        oos = sum(1 for v in cur if v == 0)
        pct = oos / len(active) if active else None
        avg_days_numeric = [num(r[COL["avg_days"]]) for r in sel if num(r[COL["avg_days"]]) is not None]
        alt = {  # alternative definitions considered, not adopted
            "current_inv_le_0": sum(1 for v in cur if v is not None and v <= 0),
            "avg_days_on_hand_dash": sum(1 for r in sel if num(r[COL["avg_days"]]) is None),
            "current_inv_eq_0_and_daily_gt_0": sum(1 for r in sel if num(r[COL["cur_inv"]]) == 0 and (num(r[COL["daily"]]) or 0) > 0),
        }
        out[u] = {"rows": len(sel), "active_stores": len(active), "duplicate_store_rows": len(stores) - len(active),
                  "missing_numeric": missing, "negative_inventory_rows": sum(1 for v in cur if v is not None and v < 0),
                  "negative_daily_rows": sum(1 for v in daily if v is not None and v < 0),
                  "current_inv_total": cur_inv, "daily_sold_total": daily_total, "weekly_rate": weekly,
                  "wos": wos, "wos_computable": weekly != 0, "oos_count": oos, "pct_oos": pct,
                  "avg_days_on_hand": {"numeric_rows": len(avg_days_numeric), "dash_rows": alt["avg_days_on_hand_dash"],
                                       "mean_over_numeric_rows_only": (sum(avg_days_numeric) / len(avg_days_numeric)) if avg_days_numeric else None},
                  "alternative_oos_definitions_not_adopted": alt, "descriptions": sorted({str(r[COL["desc"]]) for r in sel})}
        print(f"UPC {u} {out[u]['descriptions']}: rows={len(sel)} active={len(active)} dup={out[u]['duplicate_store_rows']} "
              f"inv={cur_inv:.0f} daily={daily_total:.6f} (neg rows {out[u]['negative_daily_rows']}) weekly={weekly:.4f} "
              f"WOS={wos if wos is None else round(wos, 4)} OOS={oos} pct={pct:.4%} dash={alt['avg_days_on_hand_dash']}")
    g = ws_values(gold(TID, "Inventory final.xlsx"), "Summary")
    gold_rows = {str(r[1]): r[2:9] for r in g.iter_rows(min_row=5, max_row=9, values_only=True)}
    print("gold Summary (inv, daily, weekly, wos, stores, oos, pct):")
    for u, v in gold_rows.items():
        print(f"  {u}: {[round(x, 4) if isinstance(x, float) else x for x in v]}")
    save(TID, {"rules": RULES, "rows": len(rows), "weeks": {str(k): v for k, v in weeks.items()}, "non_numeric_by_column": nonnum,
               "dash_vs_zero_daily": dash_fact, "per_upc": out, "gold_summary": {u: list(v) for u, v in gold_rows.items()}})
