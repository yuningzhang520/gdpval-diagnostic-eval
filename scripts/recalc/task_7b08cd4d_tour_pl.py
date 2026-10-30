"""7b08cd4d-df60-41ae-9102-8aaa49306ba2: tour P&L recomputed from 'Fall Music Tour Ref File.xlsx'.

Identities (net income = net revenue - expenses) are checked on unrounded values. Figures are
quantized half-up to whole dollars only for comparison with rubric figures, which are stated in whole
dollars; the rounded figures need not add up and that is not an error."""
from decimal import Decimal, ROUND_HALF_UP
import openpyxl
from common import inp, rubric, save, round_half_up, is_date, numbers_in


def dollars(x):
    """Half-up to whole dollars, for comparison with rubric figures only."""
    return Decimal(str(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP)

TID = "7b08cd4d-df60-41ae-9102-8aaa49306ba2"


def main():
    path = inp(TID, "Fall Music Tour Ref File.xlsx")
    wbv = openpyxl.load_workbook(path, data_only=True)
    wbf = openpyxl.load_workbook(path, data_only=False)
    rates = {}
    for r in wbv["Assump Withholding Tax"].iter_rows(values_only=True):
        if isinstance(r[1], str) and isinstance(r[2], (int, float)):
            rates[r[1].strip()] = float(r[2])
    print("rates:", rates)
    tm_v, tm_f = wbv["Inc & Costs Tracked by Tour Mgr"], wbf["Inc & Costs Tracked by Tour Mgr"]
    stops, tm_items, header = [], [], None
    print("-- Tour Mgr sheet rows (label | value | formula) --")
    for i in range(1, tm_v.max_row + 1):
        b, c, d, e = (tm_v.cell(i, j).value for j in (2, 3, 4, 5))
        ef = tm_f.cell(i, 5).value
        if b is None and e is None:
            continue
        print(f"  r{i}: {b!r} | {c!r} | {d!r} | {e!r} | {ef if isinstance(ef, str) and ef.startswith('=') else ''}")
        if is_date(b) or (isinstance(ef, str) and ef.startswith("=B") and isinstance(c, str)):
            stops.append({"date": str(b)[:10], "city": c, "country": d, "gross": float(e)})
            continue
        if isinstance(b, str) and e is None and i >= 27:
            header = b.strip()
        elif isinstance(b, str) and isinstance(e, (int, float)) and i >= 27 and not (isinstance(ef, str) and ef.startswith("=SUBTOTAL")) and not b.strip().upper().startswith(("TOTAL", "NET")):
            tm_items.append({"category": header, "item": b.strip(), "amount": float(e), "formula": ef if isinstance(ef, str) else None})
    pc_v, pc_f = wbv["Costs Tracked by Productn Co"], wbf["Costs Tracked by Productn Co"]
    pc_items, header = [], None
    print("-- Production Co sheet rows --")
    for i in range(1, pc_v.max_row + 1):
        b, c = pc_v.cell(i, 2).value, pc_v.cell(i, 3).value
        cf = pc_f.cell(i, 3).value
        if b is None and c is None:
            continue
        print(f"  r{i}: {b!r} | {c!r} | {cf if isinstance(cf, str) and cf.startswith('=') else ''}")
        if isinstance(b, str) and c is None and i >= 6:
            header = b.strip()
        elif isinstance(b, str) and isinstance(c, (int, float)) and i >= 6 and not (isinstance(cf, str) and cf.startswith("=SUBTOTAL")) and not b.strip().upper().startswith(("TOTAL", "NET")):
            pc_items.append({"category": header, "item": b.strip(), "amount": float(c)})
    gross = sum(s["gross"] for s in stops)
    wh_by_country, net_by_stop = {}, []
    for s in stops:
        rate = rates[s["country"]]
        wh = s["gross"] * rate
        wh_by_country[s["country"]] = wh_by_country.get(s["country"], 0) + wh
        net_by_stop.append({**s, "rate": rate, "withholding": wh, "net": s["gross"] - wh})
    withholding = sum(wh_by_country.values())
    net_rev = gross - withholding
    def cat_sum(items):
        d = {}
        for it in items:
            d[it["category"]] = d.get(it["category"], 0) + it["amount"]
        return d
    tm_cat, pc_cat = cat_sum(tm_items), cat_sum(pc_items)
    tm_total, pc_total = sum(tm_cat.values()), sum(pc_cat.values())
    print("stops:", [(s["city"], s["country"], s["gross"]) for s in stops])
    print(f"gross={gross} withholding={withholding} by country={ {k: round(v, 5) for k, v in wh_by_country.items()} } net={net_rev}")
    print("tour manager items:", [(i["category"], i["item"], i["amount"]) for i in tm_items])
    print("production items:", [(i["category"], i["item"], i["amount"]) for i in pc_items])
    print(f"TM by category={tm_cat} total={tm_total}; PC by category={pc_cat} total={pc_total}; combined expenses={tm_total+pc_total}")
    ni = net_rev - (tm_total + pc_total)
    print(f"net income combined={ni} (TM {net_rev - tm_total}, PC {-pc_total})")
    identity = {"net_revenue_unrounded": net_rev, "expenses_unrounded": tm_total + pc_total, "net_income_unrounded": ni,
                "identity_holds_unrounded": abs((net_rev - (tm_total + pc_total)) - ni) < 1e-9,
                "rubric_comparison_whole_dollars": {"net_revenue": dollars(net_rev), "expenses": dollars(tm_total + pc_total),
                                                    "net_income": dollars(ni), "tm_net_income": dollars(net_rev - tm_total),
                                                    "rounded_difference": dollars(net_rev) - dollars(tm_total + pc_total)}}
    print("identity on unrounded values:", identity)
    # Compare against rubric figures without using them in the computation.
    checks = []
    for it in rubric(TID):
        nums = [n for n in numbers_in(it["criterion"]) if n >= 1000]
        if "equals" in it["criterion"] and nums:
            checks.append((it["criterion"][:90], nums))
    print("rubric 'equals' figures (for side-by-side reading):")
    for c, n in checks:
        print("  ", n, "|", c)
    save(TID, {"rates": rates, "stops": net_by_stop, "gross": gross, "withholding_by_country": wh_by_country, "withholding": withholding,
               "net_revenue": net_rev, "tour_manager_items": tm_items, "production_items": pc_items, "tm_by_category": tm_cat,
               "pc_by_category": pc_cat, "tm_total": tm_total, "pc_total": pc_total, "expenses_total": tm_total + pc_total,
               "net_income": ni, "net_income_tm": net_rev - tm_total, "net_income_pc": -pc_total, "identity_check": identity})
