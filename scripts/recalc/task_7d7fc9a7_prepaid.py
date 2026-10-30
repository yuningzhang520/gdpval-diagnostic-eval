"""7d7fc9a7-21a7-4b83-906f-416dea5ad04f: parse every invoice from the PDFs, build the amortization
schedules under the prompt's rules, and reconcile to the GL balances stated in the prompt.

Numeric policy for this task:
- Amounts are exact rationals (fractions.Fraction) built from the decimal text printed on the
  invoices. A float read from a workbook would be converted through Decimal(str(x)) first, with the
  raw cell value kept beside it; that conversion is not claimed lossless for arbitrary Excel floats.
- The monthly charge is amount / term as an exact fraction; balances accumulate exactly.
- Quantization HALF_UP to cents is done on the exact rational (q_cents) only where a figure is
  compared with a GL balance or a rubric figure. The Decimal context is set to ROUND_HALF_UP
  explicitly for the quantized figures.
- The total prepaid balance is computed along two paths, both kept: (i) each account's balance
  quantized to cents, then summed; (ii) the exact balances summed, then quantized once.
- Rounding each invoice's monthly charge to cents before accumulating is not allowed for this task;
  that variant is computed only to document its drift from the GL.
- Precision settings and tolerances are never adjusted to absorb a boundary case; see
  test_7d7fc9a7_quantization.py for the asserted values."""
import collections
import re
from decimal import Decimal, ROUND_HALF_UP, getcontext
from fractions import Fraction

import pymupdf

from common import inp, save, ws_values

getcontext().rounding = ROUND_HALF_UP
TID = "7d7fc9a7-21a7-4b83-906f-416dea5ad04f"
AMT = re.compile(r"^\$\s*([\d,]+\.\d{2})\s*$")
MONTHS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
GL_PROMPT = {  # decimal text from the prompt
    "1250": {1: "518934.86", 2: "426673.13", 3: "473655.55", 4: "559377.61"},
    "1251": {1: "506657.98", 2: "461097.55", 3: "415537.13", 4: "369976.70"},
}
EXPENSE_FILES = ["Aurisic_Prepaid_Expenses_Jan25.pdf", "Aurisic_Prepaid_Expenses_Feb25.pdf",
                 "Aurisic_Prepaid_Expenses_Mar25.pdf", "Aurisic_Prepaid_Expenses_Apr25.pdf"]


def to_fraction(value):
    """Exact rational from decimal text, an int, or a Decimal. A float goes through Decimal(str(x)),
    the shortest round-trip text of the float; callers keep the raw value beside the result and the
    conversion is not claimed lossless for arbitrary Excel floats."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(Decimal(str(value)))
    return Fraction(Decimal(str(value).replace(",", "").replace("$", "").strip()))


def q_cents(fr):
    """HALF_UP quantization of an exact rational to cents, performed on the rational itself (ties
    round away from zero). Returns a two-place Decimal built from the integer number of cents."""
    fr = Fraction(fr)
    sign = -1 if fr < 0 else 1
    scaled = abs(fr) * 100
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    if Fraction(rem, scaled.denominator) >= Fraction(1, 2):
        whole += 1
    return Decimal(sign * whole).scaleb(-2)


def gl(account, month):
    return Decimal(GL_PROMPT[account][month]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_pdf(path):
    inv = []
    for pno, page in enumerate(pymupdf.open(path), 1):
        lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
        joined = " ".join(lines)
        vendor = next(l for l in lines if l != "INVOICE")
        num = re.search(r"Invoice #:\s*(\d+)", joined).group(1)
        date = re.search(r"Date:\s*(\d{1,2}/\d{1,2}/\d{4})", joined).group(1)
        amt_idx = next(i for i, l in enumerate(lines) if AMT.match(l))
        amount_text = AMT.match(lines[amt_idx]).group(1)
        inv.append({"file": path.split("/")[-1], "page": pno, "vendor": vendor, "invoice": num, "date": date,
                    "month": int(date.split("/")[0]), "description": lines[amt_idx - 1],
                    "amount_text": amount_text, "amount": to_fraction(amount_text)})
    return inv


def schedule(invoices, term_fn, start_fn, round_monthly=False):
    """Per-month adds, amortization and ending balance for Jan..Apr plus per-line detail, all exact.
    round_monthly=True is the disallowed variant (per-invoice cents rounding before accumulation),
    computed only to document its drift from the GL."""
    adds = collections.defaultdict(Fraction)
    amort = collections.defaultdict(Fraction)
    detail = []
    for inv in invoices:
        term, start = term_fn(inv), start_fn(inv)
        monthly = inv["amount"] / term
        if round_monthly:
            monthly = Fraction(q_cents(monthly))
        line = {"vendor": inv["vendor"], "invoice": inv["invoice"], "amount": inv["amount_text"], "term": term,
                "start": start, "monthly_exact": str(monthly), "monthly_cents": str(q_cents(monthly)), "balance": {}}
        bal = Fraction(0)
        for m in range(1, 5):
            if m == inv["month"]:
                adds[m] += inv["amount"]
                bal += inv["amount"]
            if start <= m < start + term:
                amort[m] += monthly
                bal -= monthly
            line["balance"][MONTHS[m]] = str(q_cents(bal))
        detail.append(line)
    bal, ending = Fraction(0), {}
    for m in range(1, 5):
        bal += adds[m] - amort[m]
        ending[m] = bal
    return {"adds": dict(adds), "amortization": dict(amort), "ending": ending, "lines": detail}


def reconcile(ending, account):
    """Compare exact ending balances with the GL after HALF_UP quantization to cents."""
    out = {}
    for m, v in ending.items():
        c = q_cents(v)
        out[MONTHS[m]] = {"ending_exact": str(v), "ending_cents": str(c), "gl": str(gl(account, m)),
                          "variance_cents": str(c - gl(account, m))}
    return out


def combine(a, b):
    return {m: a["ending"][m] + b["ending"][m] for m in range(1, 5)}


def compute():
    exp = []
    for f in EXPENSE_FILES:
        exp += parse_pdf(inp(TID, f))
    ins = parse_pdf(inp(TID, "Aurisic_Prepaid_Insurance.pdf"))
    # 1250: six months starting in the invoice month (the prompt's default; no invoice states a period).
    s1250 = schedule(exp, lambda i: 6, lambda i: i["month"])
    s1250_rounded = schedule(exp, lambda i: 6, lambda i: i["month"], round_monthly=True)
    # 1251: Good Insurance over the 12-month policy period from January.
    good = [i for i in ins if i["vendor"].startswith("Good")]
    bcbs = [i for i in ins if i["vendor"].startswith("BCBS")]
    s_good = schedule(good, lambda i: 12, lambda i: 1)
    s_good_rounded = schedule(good, lambda i: 12, lambda i: 1, round_monthly=True)
    # BCBS, adopted rule: each monthly payment is amortized in the following month (coverage 2/1/2025
    # onward, first payment due 1/15/2025); the April payment stays in the balance at 4/30.
    s_bcbs = schedule(bcbs, lambda i: 1, lambda i: i["month"] + 1)
    # BCBS, alternative documented for the record: each payment amortized in its own month except the
    # January payment, which covers February.
    s_bcbs_own = schedule(bcbs, lambda i: 1, lambda i: 2 if i["month"] == 1 else i["month"])
    e1251 = combine(s_good, s_bcbs)
    e1250 = s1250["ending"]
    total_exact = e1250[4] + e1251[4]
    totals = {"path_i_sum_of_quantized_balances": q_cents(e1250[4]) + q_cents(e1251[4]),
              "path_ii_quantize_exact_sum_once": q_cents(total_exact),
              "exact_total": total_exact}
    return {"expense_invoices": exp, "insurance_invoices": ins,
            "s1250": s1250, "s1250_rounded": s1250_rounded, "s_good": s_good, "s_good_rounded": s_good_rounded,
            "s_bcbs": s_bcbs, "s_bcbs_own": s_bcbs_own, "ending_1250": e1250, "ending_1251": e1251,
            "ending_1251_rounded": combine(s_good_rounded, s_bcbs), "ending_1251_own": combine(s_good, s_bcbs_own),
            "totals": totals,
            "ytd_amortization_1250": sum(s1250["amortization"].values(), Fraction(0)),
            "ytd_amortization_1251": sum(s_good["amortization"].values(), Fraction(0)) + sum(s_bcbs["amortization"].values(), Fraction(0))}


def main():
    r = compute()
    exp, ins = r["expense_invoices"], r["insurance_invoices"]
    print(f"expense invoices={len(exp)} by month={dict(collections.Counter(i['month'] for i in exp))} total={q_cents(sum((i['amount'] for i in exp), Fraction(0)))}")
    print(f"insurance invoices={len(ins)} vendors={dict(collections.Counter(i['vendor'] for i in ins))} total={q_cents(sum((i['amount'] for i in ins), Fraction(0)))}")
    print("expense descriptions:", dict(collections.Counter(i["description"] for i in exp)))
    dup = [k for k, v in collections.Counter((i["vendor"], i["invoice"]) for i in exp + ins).items() if v > 1]
    print("duplicate (vendor, invoice#):", dup)
    recon = {"1250 (exact accumulation, adopted)": reconcile(r["ending_1250"], "1250"),
             "1250 (per-line rounding, disallowed)": reconcile(r["s1250_rounded"]["ending"], "1250"),
             "1251 (BCBS following month, adopted)": reconcile(r["ending_1251"], "1251"),
             "1251 (per-line rounding, disallowed)": reconcile(r["ending_1251_rounded"], "1251"),
             "1251 (BCBS own month, alternative)": reconcile(r["ending_1251_own"], "1251")}
    for label, rec in recon.items():
        print(label)
        for m, v in rec.items():
            print(f"   {m}: exact={v['ending_exact']} -> {v['ending_cents']} GL={v['gl']} variance={v['variance_cents']}")
    t = r["totals"]
    print(f"total prepaid 4/30: exact={t['exact_total']} (= {float(t['exact_total']):.6f}); path (i) sum of quantized balances={t['path_i_sum_of_quantized_balances']}; path (ii) quantize exact sum once={t['path_ii_quantize_exact_sum_once']}")
    print(f"YTD amortization 1250={q_cents(r['ytd_amortization_1250'])} 1251={q_cents(r['ytd_amortization_1251'])}")
    coa = ws_values(inp(TID, "COA.xlsx"), "COA")
    accounts = [(c[0], c[1]) for c in coa.iter_rows(min_row=3, values_only=True) if c[0] is not None]
    print("COA accounts:", accounts)

    def sched_out(s):
        return {"adds": {MONTHS[m]: str(q_cents(v)) for m, v in s["adds"].items()},
                "amortization_exact": {MONTHS[m]: str(v) for m, v in s["amortization"].items()},
                "amortization_cents": {MONTHS[m]: str(q_cents(v)) for m, v in s["amortization"].items()},
                "ending_exact": {MONTHS[m]: str(v) for m, v in s["ending"].items()},
                "ending_cents": {MONTHS[m]: str(q_cents(v)) for m, v in s["ending"].items()}}

    save(TID, {
        "numeric_policy": "exact rationals from invoice decimal text; monthly = amount/term exact; balances exact; "
                          "HALF_UP to cents on the rational only at GL/rubric comparison; total kept along two paths; "
                          "per-line rounding before accumulation not allowed (variant documented only).",
        "expense_invoices": [{k: v for k, v in i.items() if k != "amount"} for i in exp],
        "insurance_invoices": [{k: v for k, v in i.items() if k != "amount"} for i in ins],
        "schedule_1250": sched_out(r["s1250"]), "schedule_1250_lines": r["s1250"]["lines"],
        "schedule_good": sched_out(r["s_good"]), "bcbs_following_month_adopted": sched_out(r["s_bcbs"]),
        "bcbs_own_month_alternative": sched_out(r["s_bcbs_own"]),
        "reconciliation": recon,
        "total_prepaid_2025_04_30": {"exact": str(t["exact_total"]), "path_i_sum_of_quantized_balances": str(t["path_i_sum_of_quantized_balances"]),
                                     "path_ii_quantize_exact_sum_once": str(t["path_ii_quantize_exact_sum_once"])},
        "ytd_amortization_1250_cents": str(q_cents(r["ytd_amortization_1250"])),
        "ytd_amortization_1251_cents": str(q_cents(r["ytd_amortization_1251"])),
        "gl_prompt": GL_PROMPT, "coa": accounts})
