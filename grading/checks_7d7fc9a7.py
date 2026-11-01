"""Deterministic checks for 7d7fc9a7-21a7-4b83-906f-416dea5ad04f (prepaid amortization), following
preregistration.md 2.7: D items 1-11, 13, 14, 19-30, 33, 34, 36-44, 47-50, 53; J items 12, 15-18, 31, 32, 35,
45, 46, 51, 52, 54, 55 (K1: "or an equivalent structure" governs 55); V item 56.

Thin task specification on the shared engine (grading/engine): the workbook gate, cell reading and classification,
header mapping, label and month helpers, money quantization. Task-specific here: the three sheets (summary, 1250,
1251), the schedule layout (one group of add / amortization / end-balance columns per month, in a two-row or a
one-row header), vendor lines, the bottom summary rows (totals, ending balance, variance, GL), invoice matching
against the independently parsed invoice lists, the reconciliation rule (prereg 2.7, approved 2026-10-30) and the
summary linkage. The reference is the independent recalculation (private/checks/recalc/<task>.json), never the
expert workbook. Every comparison with a GL or rubric figure is HALF_UP to cents on the Decimal of the delivered
value; identities on the deliverable's own values use a 0.005 tolerance (float noise), never a tolerance against the
GL.

Evidence states (version .2, Codex Review 1 B2): every cell an item needs is read as ok (a number), blank (a reliably
empty cell: zero in schedule arithmetic, exactly as the spreadsheet itself evaluates it; a missing figure where a
figure must be shown), unreliable (a formula without a cached value: grader side) or invalid (an error value or text
where a number is required: a confirmed invalid value). Ambiguous structure (two columns for one month and kind, two
bottom rows of one kind, an unmapped or ambiguous vendor column, rows with figures but no vendor) is kept as such. A
confirmed violation FAILs even when another input is unreliable; otherwise any unreliable or ambiguous required input
gives cannot_assess; only a complete, reliable comparison PASSes. Account identity on the summary is decided from
labels and headings before any value is compared (B3); the expected answer is never used to find a cell."""
import re
from decimal import Decimal

from .engine import headers as H
from .engine.cells import UNRELIABLE_KINDS, cell_coord, norm_text, numeric_cell, read_cell
from .engine.decision import Decision, Result
from .engine.money import cents, cents_equal, close, parse_money
from .engine.sheets import first_text, month_of, row_cells, sheet_names, text_in_rows
from .engine.workbook import workbook_gate

TASK = "7d7fc9a7-21a7-4b83-906f-416dea5ad04f"
VERSION = "7d7fc9a7-2026-11-01.2"  # .1 first gold-first version; .2 Codex Review 1 B1-B4 (item contract, evidence states, label-first summary identity, item 53 without allowance)
MONTHS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
D_ITEMS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 47, 48, 49, 50, 53]
J_ITEMS = [12, 15, 16, 17, 18, 31, 32, 35, 45, 46, 51, 52, 54, 55]
V_ITEMS = [56]
CRITICAL = {"C1": {"items": [13, 14, 33, 34], "name": "Completeness"},
            "C2": {"items": [21, 22, 23, 24, 25, 26, 30], "name": "1250 reconciliation"},
            "C3": {"items": [36, 37, 39, 40, 41, 42, 43, 44, 48], "name": "1251 reconciliation"},
            "C4": {"items": [7, 8, 9, 10, 11], "name": "Summary linkage"}}
WORKBOOK_ITEMS = [i for i in D_ITEMS if i != 1]
SUMMARY_ITEMS = [2, 5, 6, 7, 8, 9, 10, 11]
SCHED = {"1250": {"sheet_item": 3, "complete": 13, "amount": 14, "months": 19, "window": 20, "identity": 21, "totals": 22, "gl": {1: 23, 2: 24, 3: 25, 4: 26},
                  "bottom_adds": 27, "bottom_amort": 28, "bottom_end": 29, "variance": 30, "invoices": "expense_invoices", "schedule": "schedule_1250"},
         "1251": {"sheet_item": 4, "complete": 33, "amount": 34, "months": 38, "identity": 39, "totals": 40, "gl": {1: 41, 2: 42, 3: 43, 4: 44},
                  "bottom_all": 47, "variance": 48, "negative": 49, "monotone": 50, "invoices": "insurance_invoices"}}
SCHED_ITEMS = {"1250": [3, 13, 14, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30], "1251": [4, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 47, 48, 49, 50]}
# Inputs each item depends on (the production item contract, B1); "schedule_<acct>" covers that sheet's lines and bottom rows
ITEM_INPUTS = {1: ["workbook"], 2: ["summary_sheet"], 5: ["summary_sheet"], 6: ["summary_sheet"], 7: ["summary_cells", "schedule_1250", "schedule_1251"],
               8: ["summary_cells"], 9: ["summary_cells"], 10: ["summary_cells"], 11: ["summary_cells", "schedule_1250", "schedule_1251"], 53: ["schedule_1250", "schedule_1251", "summary_cells"],
               **{i: ["schedule_1250", "expense_invoices"] if i in (13, 14, 20) else ["schedule_1250"] for i in SCHED_ITEMS["1250"]},
               **{i: ["schedule_1251", "insurance_invoices"] if i in (33, 34) else ["schedule_1251"] for i in SCHED_ITEMS["1251"]}}

# Non-month columns of a schedule (header text = month-row text + sub-row text, normalised)
SCHEMA = {
    "vendor": {"required": True, "synonyms": ["vendor", "vendor name", "payee", "supplier", "name", "vendor / description", "vendor/description", "description"]},
    "beginning": {"required": False, "synonyms": ["beginning balance", "beg balance", "beg. balance", "opening balance", "beginning", "beg bal", "opening", "balance 1/1/2025"]},
    "amount": {"required": False, "synonyms": ["original amount", "invoice amount", "amount", "total amount", "prepaid amount", "original", "invoice total", "cost", "original invoice amount", "amount paid"]},
    "term": {"required": False, "synonyms": ["months", "amortization months", "term", "term (months)", "# months", "no. of months", "number of months", "period (months)", "amortization period", "months to amortize",
                                            "amortization", "amortization months", "term months", "months of service", "# of months"]},
    "start": {"required": False, "synonyms": ["start", "start date", "period start", "from", "begin date", "amortization start", "service start", "start month", "amortization period start"]},
    "end_date": {"required": False, "synonyms": ["end date", "period end", "to", "amortization end", "service end", "through", "end month", "amortization period end"]},
    "monthly": {"required": False, "synonyms": ["monthly expense", "monthly amortization", "monthly", "monthly amount", "per month", "monthly charge", "monthly exp"]},
    "invoice": {"required": False, "synonyms": ["invoice", "invoice #", "invoice number", "invoice no", "invoice no.", "inv #", "inv", "inv no"]},
    "date": {"required": False, "synonyms": ["date", "invoice date", "dated", "inv date"]},
    "comments": {"required": False, "synonyms": ["comments", "comment", "notes", "classification", "type", "nature", "category", "nature of prepaid"]},
    "account": {"required": False, "synonyms": ["acct#", "acct #", "acct", "account", "account #", "account number", "gl account", "coa", "expense account", "acct no", "coa #", "gl acct"]},
}
SUB_KINDS = (("end", ("end bal", "ending", "end balance", "balance", "remaining", "closing", "ending bal")),
             ("amort", ("amort", "credit", "w/o", "write", "expense", "recogni", "decrease", "reduction")),
             ("add", ("add", "debit", "purchase", "invoice", "increase", "new")))
BOTTOM = {"totals": r"^(month(ly)?\s+)?totals?\b|^totals?\b|^sum\b|^grand total", "ending": r"^(total\s+)?(ending|end|closing)\s+bal", "variance": r"^variance|^difference|^diff\b|^var\b",
          "gl": r"^g\.?\s?l\.?\b|^general ledger|^gl bal|^per gl|^balance per gl|^gl$", "adjust": r"adjust|rounding"}
NOT_A_LINE = r"^(month(ly)?\s+)?totals?\b|^totals?\b|^sum\b|^grand total|^(total\s+)?(ending|end|closing)\s+bal|^variance|^difference|^diff\b|^var\b|^g\.?\s?l\.?\b|^general ledger|^gl bal|^per gl|^balance per gl|^gl$|\btotal$|^subtotal|^note|^legend|^prepared|^source"
CURRENCY = re.compile(r"[$€£¥]|\[\$")


def _d(x):
    return parse_money(x)


def vendor_key(s) -> str:
    t = norm_text(s)
    t = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|the)\b\.?", " ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def vendors_match(a: str, b: str) -> bool:
    ka, kb = vendor_key(a), vendor_key(b)
    return bool(ka) and bool(kb) and (ka == kb or ka in kb or kb in ka)


# ----------------------------------------------------------------------------- evidence states
def cell_state(cell) -> tuple[str, Decimal | None]:
    """('ok', number) | ('blank', 0) | ('unreliable', None) | ('invalid', raw value) | ('absent', None) for no cell."""
    if cell is None:
        return "absent", None
    if cell["status"] == "empty":
        return "blank", Decimal(0)
    if cell["status"] in UNRELIABLE_KINDS:
        return "unreliable", None
    st, v = numeric_cell(cell)
    if st == "ok":
        d = _d(v)
        return ("ok", d) if d is not None else ("invalid", cell["value"])
    return "invalid", cell["value"]


def register(d: Decision, field: str, cell, row=None, recalc=None) -> str:
    """Record what a cell implies for an item: unreliable -> unassessable (grader side), invalid -> confirmed violation.
    Returns the cell's state."""
    st, _ = cell_state(cell)
    if st == "unreliable":
        d.cell(field, cell["status"], cell["value"], cell["coord"], row, recalc)
    elif st == "invalid":
        nst, v = numeric_cell(cell)
        d.cell(field, nst if nst != "ok" else "non_numeric", v, cell["coord"], row, recalc)
    return st


# ----------------------------------------------------------------------------- schedule parsing
def sub_kind(text) -> str | None:
    t = norm_text(text)
    if not t:
        return None
    for kind, keys in SUB_KINDS:
        if any(k in t for k in keys):
            return kind
    return None


def month_header(sheet: dict, max_rows: int = 15) -> dict | None:
    """Locate the month-grouped header: the first row within max_rows with month tokens in at least three distinct
    columns. Returns {"month_row", "sub_row", "header_end", "groups": {month: {kind: col}} (first column of each month
    and kind), "ambiguous": {(month, kind): [cols]} (two or more columns for one month and kind: the evidence cannot be
    located uniquely), "unclassified": [(month, col)], "other": [(col, header text)]}."""
    rows = sheet["rows"]
    for r in range(1, min(max_rows, len(rows)) + 1):
        cells = row_cells(sheet, r)
        months = {}
        for c in cells:
            if c["status"] == "ok":
                m = month_of(c["value"]) if not (isinstance(c["value"], str) and sub_kind(c["value"]) and month_of(c["value"]) is None) else None
                if m is not None and isinstance(c["value"], str):  # month tokens are text headers; a lone datetime cell (e.g. 'Beginning Balance 1/1/2025') is not a month column
                    months[c["coord"]] = m
        if len(set(months.values())) < 3:
            continue
        sub_cells = row_cells(sheet, r + 1) if r < len(rows) else []
        groups: dict = {}
        ambiguous: dict = {}
        unclassified = []
        other = []
        for idx, c in enumerate(cells):
            col = idx
            text = c["value"] if c["status"] == "ok" else None
            m = months.get(c["coord"])
            sub = sub_cells[idx]["value"] if idx < len(sub_cells) and sub_cells[idx]["status"] == "ok" else None
            if m is not None:
                kind = sub_kind(sub) if sub is not None and not hasattr(sub, "year") else None
                if kind is None:
                    kind = sub_kind(text)
                if kind is None:
                    kind = "end" if sub is None else None
                if kind is None:
                    unclassified.append((m, col))
                    continue
                g = groups.setdefault(m, {})
                if kind in g:
                    ambiguous.setdefault((m, kind), [g[kind]]).append(col)
                else:
                    g[kind] = col
                continue
            label = " ".join(x for x in (norm_text(text) if text is not None and not hasattr(text, "year") else "", norm_text(sub) if sub is not None and not hasattr(sub, "year") else "") if x).strip()
            if label:
                other.append((col, label))
        two_row = any(sub_cells[i]["status"] == "ok" and sub_kind(sub_cells[i]["value"]) for i in range(len(sub_cells)) if not hasattr(sub_cells[i]["value"], "year"))
        return {"month_row": r, "sub_row": r + 1 if two_row else r, "header_end": r + 1 if two_row else r, "groups": {m: g for m, g in sorted(groups.items())},
                "ambiguous": ambiguous, "unclassified": unclassified, "other": other}
    return None


def parse_schedule(sheet: dict, name: str) -> dict:
    """Lines, bottom rows and the column map of one schedule sheet (every cell through read_cell). Rows with business
    figures but no vendor are kept as ``unidentified`` (never dropped as notes); duplicate bottom rows of one kind are
    kept in ``bottom_duplicates``."""
    hdr = month_header(sheet)
    if hdr is None:
        return {"sheet": name, "status": "no_month_header", "lines": [], "bottom": {}, "groups": {}}
    other_header = [""] * (max([c for c, _ in hdr["other"]] + [0]) + 1)
    for col, label in hdr["other"]:
        other_header[col] = label
    mapping = H.map_columns(other_header, SCHEMA)
    cols = mapping["cols"]
    month_cols = {c for g in hdr["groups"].values() for c in g.values()} | {c for cs in hdr["ambiguous"].values() for c in cs}
    if "vendor" in cols:
        vendor_col, vendor_basis = cols["vendor"], "mapped from its header"
    elif mapping["field_status"].get("vendor") == "ambiguous":
        return {"sheet": name, "status": "vendor_ambiguous", "lines": [], "bottom": {}, "groups": hdr["groups"], "header": hdr, "vendor_candidates": mapping["ambiguous"].get("vendor")}
    elif 0 not in month_cols and not other_header[0]:
        vendor_col, vendor_basis = 0, "first column without a header (fallback)"
    else:
        return {"sheet": name, "status": "vendor_unmapped", "lines": [], "bottom": {}, "groups": hdr["groups"], "header": hdr, "unmapped_headers": mapping["unmapped_headers"]}
    amb = set(hdr["ambiguous"])
    lines, bottom, bottom_dups, notes, unidentified = [], {}, {}, [], []
    stop = len(sheet["rows"])
    for r in range(hdr["header_end"] + 1, stop + 1):
        label = first_text(sheet, r, max_cols=max(3, vendor_col + 1))
        cells = row_cells(sheet, r)
        if not any(c["status"] != "empty" for c in cells):
            continue
        month_cells = {m: {k: read_cell(sheet, r, c) for k, c in g.items()} for m, g in hdr["groups"].items()}
        if label and re.search(NOT_A_LINE, norm_text(label), re.I):
            key = next((k for k, rx in BOTTOM.items() if re.search(rx, norm_text(label), re.I)), None)
            rec = {"row": r, "label": label, "months": month_cells, "other": {f: read_cell(sheet, r, c) for f, c in cols.items()}}
            if key and key not in bottom:
                bottom[key] = rec
            elif key:
                bottom_dups.setdefault(key, [bottom[key]["row"]]).append(r)
            else:
                notes.append({"row": r, "label": label})
            continue
        vendor = cells[vendor_col]["value"] if vendor_col < len(cells) and cells[vendor_col]["status"] == "ok" else None
        amount_cell = read_cell(sheet, r, cols["amount"]) if cols.get("amount") is not None else None
        figure_states = [cell_state(cc)[0] for mc in month_cells.values() for cc in mc.values()] + ([cell_state(amount_cell)[0]] if amount_cell else [])
        has_figures = any(s_ in ("ok", "unreliable", "invalid") and not (s_ == "ok" and False) for s_ in figure_states)
        if not has_figures:
            if label:
                notes.append({"row": r, "label": label})
            continue
        if not (isinstance(vendor, str) and vendor.strip()):
            unidentified.append({"row": r, "label": label, "reason": "business figures without a vendor"})
            continue
        line = {"row": r, "vendor": vendor.strip(), "months": month_cells, "other": {f: read_cell(sheet, r, c) for f, c in cols.items()}}
        add_state, adds = {}, {}
        for m in hdr["groups"]:
            if (m, "add") in amb:
                add_state[m], adds[m] = "ambiguous", None
            elif "add" not in month_cells[m]:
                add_state[m], adds[m] = "unmapped", None
            else:
                st, v = cell_state(month_cells[m]["add"])
                add_state[m], adds[m] = st, (v if st in ("ok", "blank") else None)
        line["add_state"], line["adds"] = add_state, adds
        if amount_cell is not None and cell_state(amount_cell)[0] != "blank":
            st, v = cell_state(amount_cell)
            line["amount"], line["amount_state"], line["amount_source"] = (v if st == "ok" else None), st, "amount column"
        else:
            states = set(add_state.values())
            if not adds:
                line["amount"], line["amount_state"] = None, "unmapped"
            elif states & {"unreliable", "ambiguous", "invalid", "unmapped"}:
                bad = next(s_ for s_ in ("unreliable", "ambiguous", "invalid", "unmapped") if s_ in states)
                line["amount"], line["amount_state"] = None, bad
            else:
                line["amount"], line["amount_state"] = sum(adds.values(), Decimal(0)), "ok"
            line["amount_source"] = "sum of monthly adds"
        start = None
        sc = line["other"].get("start")
        if sc and sc["status"] == "ok":
            start = month_of(sc["value"])
        if start is None:
            dc = line["other"].get("date")
            if dc and dc["status"] == "ok":
                start = month_of(dc["value"])
        if start is None:
            firsts = [m for m, v in sorted(adds.items()) if v is not None and v > 0]
            start = firsts[0] if firsts else None
        line["start"] = start
        tc = line["other"].get("term")
        term = numeric_cell(tc)[1] if tc and numeric_cell(tc)[0] == "ok" else None
        line["term"] = int(term) if term is not None and float(term).is_integer() else term
        lines.append(line)
    return {"sheet": name, "status": "ok", "header": hdr, "mapping": {k: v for k, v in mapping.items() if k in ("cols", "field_status", "unmapped_headers", "ambiguous")},
            "groups": hdr["groups"], "ambiguous_columns": amb, "unclassified_columns": hdr["unclassified"], "lines": lines, "bottom": bottom, "bottom_duplicates": bottom_dups,
            "notes": notes, "unidentified": unidentified, "vendor_col": vendor_col, "vendor_basis": vendor_basis}


def match_invoices(lines: list[dict], invoices: list[dict], unidentified: int = 0) -> dict:
    """Invoices against lines. Pass 1: vendor + month + exact amount on the month's add cell (a consolidated line may
    satisfy several invoices through different months). Pass 2: vendor + exact amount on the line's original amount.
    An unmatched invoice is ``uncertain`` when a line of its vendor has an unreadable or ambiguous figure that could hold
    it; otherwise a line of its vendor with a reliably read different amount makes it a wrong amount; otherwise it is
    missing. Rows with figures but no vendor bound the confirmed missing count: max(0, missing - unidentified)."""
    used_adds: set = set()
    used_lines: set = set()
    matched, wrong_amount, missing, uncertain = [], [], [], []
    inv_amount = lambda inv: Decimal(inv["amount_text"].replace(",", ""))
    keep = lambda inv: {k: inv[k] for k in ("vendor", "invoice", "month", "amount_text", "file", "page")}
    for inv in invoices:
        amt, m = inv_amount(inv), inv["month"]
        hit = None
        for i, ln in enumerate(lines):
            if not vendors_match(ln["vendor"], inv["vendor"]):
                continue
            if ln["add_state"].get(m) == "ok" and (i, m) not in used_adds and cents_equal(ln["adds"][m], amt):
                hit = {"line": i, "row": ln["row"], "via": f"{MONTHS.get(m, m)} add"}
                used_adds.add((i, m))
                break
        if hit is None:
            for i, ln in enumerate(lines):
                if i in used_lines or not vendors_match(ln["vendor"], inv["vendor"]):
                    continue
                if ln["amount_state"] == "ok" and cents_equal(ln["amount"], amt) and not any((i, mm) in used_adds for mm in ln["adds"]):
                    hit = {"line": i, "row": ln["row"], "via": ln["amount_source"]}
                    used_lines.add(i)
                    break
        if hit:
            matched.append({**keep(inv), **hit})
        else:
            missing.append(inv)
    still_missing = []
    for inv in missing:
        amt, m = inv_amount(inv), inv["month"]
        vendor_lines = [(i, ln) for i, ln in enumerate(lines) if vendors_match(ln["vendor"], inv["vendor"])]
        doubt = [(i, ln) for i, ln in vendor_lines if ln["add_state"].get(m) in ("unreliable", "ambiguous") or ln["amount_state"] in ("unreliable", "ambiguous")]
        if doubt:
            i, ln = doubt[0]
            uncertain.append({**keep(inv), "line": i, "row": ln["row"], "reason": f"{MONTHS.get(m, m)} add {ln['add_state'].get(m)}, amount {ln['amount_state']}"})
            continue
        cand = next((i for i, ln in vendor_lines if i not in used_lines and ln["amount_state"] == "ok" and (ln["start"] in (None, m)) and not any((i, mm) in used_adds for mm in ln["adds"])), None)
        if cand is not None:
            ln = lines[cand]
            used_lines.add(cand)
            wrong_amount.append({**keep(inv), "line": cand, "row": ln["row"], "delivered_amount": str(ln["amount"])})
        else:
            still_missing.append(inv)
    consumed = used_lines | {i for i, _ in used_adds} | {u["line"] for u in uncertain}
    extra = [{"line": i, "row": ln["row"], "vendor": ln["vendor"], "amount": str(ln["amount"]) if ln["amount"] is not None else None} for i, ln in enumerate(lines) if i not in consumed]
    return {"matched": matched, "wrong_amount": wrong_amount, "missing": still_missing, "uncertain": uncertain, "extra_lines": extra, "invoices": len(invoices), "lines": len(lines),
            "unidentified_rows": unidentified, "confirmed_missing_lower_bound": max(0, len(still_missing) - unidentified)}


def line_cell(line: dict, m: int, kind: str):
    return line["months"].get(m, {}).get(kind)


def column_sum(lines: list[dict], m: int, kind: str) -> dict:
    """Sum of one month/kind over the lines with the cells that keep it from being known (unreliable) or valid (invalid)."""
    total, unknown, invalid = Decimal(0), [], []
    for ln in lines:
        c = line_cell(ln, m, kind)
        st, v = cell_state(c)
        if st in ("ok", "blank"):
            total += v
        elif st == "unreliable":
            unknown.append(c["coord"])
        elif st == "invalid":
            invalid.append(c["coord"])
    return {"sum": total, "unknown": unknown, "invalid": invalid}


def bottom_cell(rowrec, m: int, prefer=("end", "amort", "add")):
    """(state, value, cell) of a bottom row's figure for month m: the first non-blank cell among the preferred kinds."""
    if not rowrec or m not in rowrec["months"]:
        return "absent", None, None
    for k in prefer:
        c = rowrec["months"][m].get(k)
        st, v = cell_state(c)
        if st in ("ok", "unreliable", "invalid"):
            return st, v, c
    return "blank", None, None


def locate_sheets(x: dict) -> dict:
    """Summary and schedule sheets by name (rubric 2-4), with content-based fallbacks recorded as such."""
    names = sheet_names(x)
    out = {"summary": None, "1250": None, "1251": None, "basis": {}}
    for n in names:
        t = norm_text(n)
        if "1250" in t and out["1250"] is None:
            out["1250"], out["basis"]["1250"] = n, "sheet name contains 1250"
        elif "1251" in t and out["1251"] is None:
            out["1251"], out["basis"]["1251"] = n, "sheet name contains 1251"
        elif "summary" in t and "prepaid" in t and out["summary"] is None:
            out["summary"], out["basis"]["summary"] = n, "sheet name contains 'prepaid' and 'summary'"
    for n in names:  # fallbacks by name words, then by content
        t = norm_text(n)
        if n in out.values():
            continue
        if out["summary"] is None and "summary" in t:
            out["summary"], out["basis"]["summary"] = n, "sheet name contains 'summary' (not 'prepaid')"
        elif out["1250"] is None and ("expense" in t or "exp" in t.split()) and "insur" not in t:
            out["1250"], out["basis"]["1250"] = n, "sheet name names the expenses schedule (no account number)"
        elif out["1251"] is None and "insur" in t:
            out["1251"], out["basis"]["1251"] = n, "sheet name names the insurance schedule (no account number)"
    for n in names:
        if n in out.values():
            continue
        s = x["sheets"][n]
        vendors = " ".join(str(c["value"]) for r in range(1, min(len(s["rows"]), 80) + 1) for c in row_cells(s, r)[:2] if c["status"] == "ok" and isinstance(c["value"], str)).lower()
        if out["1251"] is None and ("bcbs" in vendors or "good insurance" in vendors) and month_header(s):
            out["1251"], out["basis"]["1251"] = n, "content: insurance vendors on a month-grouped sheet (sheet name lacks 1251)"
        elif out["1250"] is None and month_header(s) and not ("bcbs" in vendors or "good insurance" in vendors):
            out["1250"], out["basis"]["1250"] = n, "content: month-grouped schedule without insurance vendors (sheet name lacks 1250)"
    if out["summary"] is None:
        rest = [n for n in names if n not in out.values()]
        if rest:
            out["summary"], out["basis"]["summary"] = rest[0], "fallback: the remaining sheet"
    return out


# ----------------------------------------------------------------------------- summary sheet (identity before value, B3)
def account_of(text) -> str | None:
    t = norm_text(text)
    a = "1250" in t or re.search(r"\bexpenses?\b|\bexp\b", t) is not None
    b = "1251" in t or "insur" in t
    return "both" if a and b else "1250" if a else "1251" if b else None


def kind_of(label) -> str | None:
    t = norm_text(label)
    if re.search(r"amorti[sz]", t):
        return "ytd"
    if re.search(r"\bbalance\b|\bending\b|\bg\.?\s?l\b|end of period", t):
        return "balance"
    if re.search(r"\btotal\b|addition|prepaid|invoice|\bytd\b|year-to-date|purchas", t):
        return "additions"
    return None


def summary_cells(sheet: dict, max_rows: int = 60) -> list[dict]:
    """Every figure cell of the summary sheet - numbers, formulas without a cached value, error values - with its state,
    the row label, the sub-heading above the block, its formula and its number format."""
    out, heading = [], ""
    for r in range(1, min(max_rows, len(sheet["rows"])) + 1):
        cells = row_cells(sheet, r)
        texts = [c["value"] for c in cells if c["status"] == "ok" and isinstance(c["value"], str) and c["value"].strip() and numeric_cell(c)[0] != "ok"]
        figures = []
        for c in cells:
            raw = sheet["cells"].get(c["coord"], {})
            st, v = cell_state(c)
            if st == "ok" and not isinstance(c["value"], bool) and not (isinstance(c["value"], str) and not raw.get("formula")):
                figures.append((c, st, v))
            elif st == "unreliable" or (st == "invalid" and c["status"] == "error_value"):
                figures.append((c, st, v))
        if texts and not figures:
            heading = texts[0]
        for c, st, v in figures:
            raw = sheet["cells"].get(c["coord"], {})
            label = " ".join(texts)
            kind, acct = kind_of(label), account_of(label)
            if kind == "balance" and (acct == "both" or (acct is None and re.search(r"\btotal\b|combined|overall|grand|all accounts", norm_text(label)))):
                cls = ("total", None)
            else:
                a = acct if acct not in (None, "both") else (account_of(heading) if acct is None else None)
                cls = (kind, a if a != "both" else None)
            out.append({"coord": c["coord"], "row": r, "state": st, "value": v, "label": label, "heading": heading, "formula": raw.get("formula"),
                        "number_format": raw.get("number_format"), "class": cls, "cell": c})
    return out


def resolve_target(cells: list[dict], kind: str, acct: str | None) -> dict:
    """The summary cell(s) whose labels identify the target; values are never used to find them."""
    cands = [c for c in cells if c["class"] == (kind, acct)]
    unknown = [c for c in cells if c["class"][0] is None or (c["class"][0] in ("balance", "ytd", "additions") and c["class"][1] is None)]
    if not cands:
        return {"status": "none_with_unknowns" if unknown else "none", "cells": [], "unknown": [c["coord"] for c in unknown]}
    if len(cands) == 1:
        return {"status": "unique", "cells": cands, "unknown": []}
    if all(c["state"] == "ok" for c in cands) and len({cents(c["value"]) for c in cands}) == 1:
        return {"status": "unique_value", "cells": cands, "unknown": []}
    return {"status": "ambiguous", "cells": cands, "unknown": []}


def references_sheet(formula: str | None, sheet_name: str) -> bool:
    if not formula:
        return False
    f = formula.replace("$", "")
    return f"'{sheet_name}'!" in f or re.search(rf"(?<![A-Za-z0-9_']){re.escape(sheet_name)}!", f) is not None


def money_format_ok(nf: str | None) -> bool:
    """Preregistration 2.7, rubric 53 (operational definition): a currency symbol, or exactly two decimals with thousands
    separators (accounting or number format)."""
    nf = nf or "General"
    return bool(CURRENCY.search(nf)) or "#,##0.00" in nf


# ----------------------------------------------------------------------------- checks
def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {"workbooks": {}, "pipeline": {}}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=WORKBOOK_ITEMS, file_item=1, single_file=True)
    schedules: dict = {}
    summary_info = None
    if readable:
        xlsx_name = sorted(readable)[0]
        x = readable[xlsx_name]
        recalc_status = x.get("recalc", {}).get("status")
        located = locate_sheets(x)
        status["pipeline"]["sheets"] = located
        gl = {acct: {int(m): Decimal(v) for m, v in reference["gl_prompt"][acct].items()} for acct in ("1250", "1251")}
        for acct, spec in SCHED.items():
            name = located[acct]
            ev_base = {"file": xlsx_name, "sheet": name, "basis": located["basis"].get(acct)}
            if name is None:
                results[spec["sheet_item"]] = Result(spec["sheet_item"], "fail", {"file": xlsx_name, "sheets": sheet_names(x)}, None, acct, f"no worksheet whose name includes {acct} and no schedule located by content", "model_caused")
                fill([i for i in SCHED_ITEMS[acct] if i != spec["sheet_item"]], "fail", f"the {acct} schedule was not delivered (no sheet named or recognisable as it)", "model_caused_missing", {"file": xlsx_name, "sheets": sheet_names(x)})
                continue
            results[spec["sheet_item"]] = Result(spec["sheet_item"], "pass" if acct in norm_text(name) else "fail", {**ev_base}, name, f"sheet name includes {acct}",
                                                 "" if acct in norm_text(name) else f"the schedule sheet is named {name!r}: the account number {acct} is not in the name", None if acct in norm_text(name) else "model_caused")
            sch = parse_schedule(x["sheets"][name], name)
            schedules[acct] = sch
            if sch["status"] != "ok":
                reason = {"no_month_header": "no month-grouped header found (rows with Jan-Apr column groups)", "vendor_ambiguous": f"vendor column ambiguous ({sch.get('vendor_candidates')})",
                          "vendor_unmapped": f"no vendor column identified (unrecognised headers {sch.get('unmapped_headers')})"}[sch["status"]]
                fill([i for i in SCHED_ITEMS[acct] if i != spec["sheet_item"]], "cannot_assess", f"extraction_failed: sheet {name!r}: {reason}", "grader_extraction", ev_base)
                continue
            groups, amb = sch["groups"], sch["ambiguous_columns"]
            months_present = sorted(m for m in (1, 2, 3, 4) if m in groups)
            ev = {**ev_base, "header_rows": (sch["header"]["month_row"], sch["header"]["header_end"]), "groups": {MONTHS.get(m, m): {k: cell_coord(sch["header"]["month_row"], c) for k, c in g.items()} for m, g in groups.items()},
                  "lines": len(sch["lines"]), "bottom_rows": {k: v["row"] for k, v in sch["bottom"].items()}, "column_mapping": sch["mapping"]["cols"], "vendor_basis": sch["vendor_basis"]}
            if amb:
                ev["ambiguous_columns"] = {f"{MONTHS.get(m, m)}:{k}": [cell_coord(sch["header"]["month_row"], c) for c in cs] for (m, k), cs in sch["header"]["ambiguous"].items()}
            if sch["unidentified"]:
                ev["unidentified_rows"] = [u["row"] for u in sch["unidentified"]][:20]
            U = len(sch["unidentified"])
            # months displayed
            results[spec["months"]] = Result(spec["months"], "pass" if months_present == [1, 2, 3, 4] else "fail", ev, [MONTHS[m] for m in months_present], "Jan, Feb, Mar, Apr",
                                             "" if months_present == [1, 2, 3, 4] else f"month groups found: {[MONTHS[m] for m in months_present]}", None if months_present == [1, 2, 3, 4] else "model_caused")
            # invoice completeness and amounts
            mt = match_invoices(sch["lines"], reference[spec["invoices"]], unidentified=U)
            sch["match"] = mt
            d = Decision(spec["complete"], ev)
            if mt["confirmed_missing_lower_bound"] > 0:
                d.violation("missing_invoices", f"at least {mt['confirmed_missing_lower_bound']} of {mt['invoices']} invoices absent: " + "; ".join(f"{i['vendor']} {i['invoice']} {i['amount_text']} ({i['file']} p{i['page']})" for i in mt["missing"][:6]),
                            missing=[{k: i[k] for k in ("vendor", "invoice", "month", "amount_text", "file", "page")} for i in mt["missing"]])
            elif mt["missing"]:
                d.unreliable("unidentified", "invoice_lines", f"{len(mt['missing'])} invoice(s) not found on a vendor line; {U} row(s) with figures but no vendor could hold them")
            if mt["uncertain"]:
                d.unreliable("grader_error" if any("unreliable" in u["reason"] for u in mt["uncertain"]) else "ambiguous", "invoice_lines",
                             f"{len(mt['uncertain'])} invoice(s) whose vendor line has an unreadable or ambiguous figure: {mt['uncertain'][:3]}")
            d.deliverable, d.reference = {"matched": len(mt["matched"]), "wrong_amount": len(mt["wrong_amount"]), "missing": len(mt["missing"]), "uncertain": len(mt["uncertain"]), "extra_lines": len(mt["extra_lines"])}, mt["invoices"]
            results[spec["complete"]] = d.result(f"every one of the {mt['invoices']} invoices is present (matched by vendor, month and exact amount)")
            d = Decision(spec["amount"], ev)
            if mt["wrong_amount"]:
                d.violation("amount_mismatch", "; ".join(f"{w['vendor']} {w['invoice']} {w['amount_text']} delivered as {w['delivered_amount']} (row {w['row']})" for w in mt["wrong_amount"][:6]), rows=[w["row"] for w in mt["wrong_amount"]])
            if mt["uncertain"]:
                d.unreliable("grader_error" if any("unreliable" in u["reason"] for u in mt["uncertain"]) else "ambiguous", "invoice_lines", f"{len(mt['uncertain'])} invoice amount(s) unreadable on their line")
            if mt["missing"] and U:
                d.unreliable("unidentified", "invoice_lines", f"{len(mt['missing'])} invoice(s) not on a vendor line; {U} row(s) with figures but no vendor may carry them with any amount")
            d.deliverable, d.reference = len(mt["wrong_amount"]), 0  # confirmed absent invoices are item 13's finding; 14 judges the delivered lines
            results[spec["amount"]] = d.result("every delivered invoice amount equals its source invoice")
            lines = sch["lines"]
            need = [m for m in (1, 2, 3, 4) if m in groups]

            def month_usable(d_, m, kinds):
                """Register ambiguity or unmapped columns for (m, kind); True when every kind is uniquely located."""
                ok = True
                for k in kinds:
                    if (m, k) in amb:
                        d_.unreliable("ambiguous", "month_columns", f"{MONTHS[m]} {k}: {len(sch['header']['ambiguous'][(m, k)])} candidate columns")
                        ok = False
                    elif k not in groups.get(m, {}):
                        d_.unreliable("unmapped", "month_columns", f"{MONTHS[m]} {k} column not identified")
                        ok = False
                return ok
            # per-line identity (21 / 39)
            d = Decision(spec["identity"], ev)
            bad = []
            for ln in lines:
                beg = ln["other"].get("beginning")
                if beg is None:
                    prev = Decimal(0)  # no beginning-balance column: operations began in January (prompt)
                else:
                    st = register(d, "beginning", beg, ln["row"], recalc_status)
                    prev = cell_state(beg)[1] if st in ("ok", "blank") else None
                for m in need:
                    if not month_usable(d, m, ("add", "amort", "end")):
                        prev = None
                        continue
                    cs = {k: line_cell(ln, m, k) for k in ("add", "amort", "end")}
                    states = {k: register(d, "schedule", c, ln["row"], recalc_status) for k, c in cs.items()}
                    vals = {k: cell_state(c)[1] for k, c in cs.items()}
                    known = all(states[k] in ("ok", "blank") for k in cs)
                    if known and prev is not None and not close(prev + vals["add"] - vals["amort"], vals["end"]):
                        bad.append({"row": ln["row"], "month": MONTHS[m], "beginning": str(prev), "add": str(vals["add"]), "amort": str(vals["amort"]), "end": str(vals["end"]), "expected_end": str(prev + vals["add"] - vals["amort"])})
                    if prev is None and known:
                        d.unreliable("unknown", "schedule", f"row {ln['row']} {MONTHS[m]}: the opening figure is unknown (previous month unreadable or ambiguous)")
                    prev = vals["end"] if states["end"] in ("ok", "blank") else None
            if bad:
                d.violation("identity", f"{len(bad)} line-month(s) where beginning + adds - amortization != ending, e.g. {bad[:3]}", rows=sorted({b['row'] for b in bad})[:20])
            d.deliverable = len(bad)
            results[spec["identity"]] = d.result("beginning + adds - amortization = ending on every line and month")
            if "window" in spec:
                d = Decision(spec["window"], ev)
                outside = []
                first_month = {}
                for mm in mt["matched"]:
                    first_month[mm["line"]] = min(first_month.get(mm["line"], 99), mm["month"])
                for li, start_m in sorted(first_month.items()):
                    ln = lines[li]
                    for m in need:
                        if m >= start_m:
                            continue
                        if not month_usable(d, m, ("amort",)):
                            continue
                        c = line_cell(ln, m, "amort")
                        st, v = cell_state(c)
                        if st == "unreliable":
                            register(d, "amortization", c, ln["row"], recalc_status)
                        elif st == "invalid" or (st == "ok" and v != 0):
                            outside.append({"row": ln["row"], "month": MONTHS[m], "amortization": str(v if st == "ok" else c["value"]), "invoice_month": MONTHS[start_m]})
                if outside:
                    d.violation("amortization_outside_period", f"{len(outside)} line-month(s) with amortization before the invoice month, e.g. {outside[:3]}", rows=sorted({o['row'] for o in outside})[:20])
                d.deliverable = len(outside)
                results[spec["window"]] = d.result("no amortization recorded before a line's start month (Jan-Apr)")
            # totals, ending balances, GL, variance
            bottom, dups = sch["bottom"], sch["bottom_duplicates"]
            totals_row, ending_row, var_row, gl_row = bottom.get("totals"), bottom.get("ending"), bottom.get("variance"), bottom.get("gl")

            def bottom_dup(d_, *keys):
                for k in keys:
                    if k in dups:
                        d_.unreliable("ambiguous", "bottom_rows", f"{len(dups[k])} '{k}' rows ({dups[k]}): the figure cannot be located uniquely")
                        return True
                return False
            d = Decision(spec["totals"], ev)
            bottom_dup(d, "totals", "ending")
            if not totals_row:
                d.violation("no_totals_row", "no monthly totals row below the lines")
            else:
                for m in need:
                    for k in ("amort", "end"):
                        if not month_usable(d, m, (k,)):
                            continue
                        st, v, c = bottom_cell(totals_row, m, (k,))
                        if st in ("blank", "absent") and k == "end" and ending_row:
                            st, v, c = bottom_cell(ending_row, m, ("end",))
                        if st == "unreliable":
                            register(d, "totals", c, totals_row["row"], recalc_status)
                            continue
                        if st == "invalid":
                            register(d, "totals", c, totals_row["row"], recalc_status)
                            continue
                        if st in ("blank", "absent"):
                            d.violation("total_missing", f"{MONTHS[m]} {k} total absent", month=MONTHS[m])
                            continue
                        cs_ = column_sum(lines, m, k)
                        if cs_["invalid"]:
                            d.violation("invalid_value", f"{MONTHS[m]} {k}: line cell(s) {cs_['invalid'][:5]} are not numbers; the per-line sum is undefined", cells=cs_["invalid"][:10])
                        elif cs_["unknown"]:
                            d.unreliable("grader_error", "schedule", {"month": MONTHS[m], "kind": k, "cells": cs_["unknown"][:10]})
                        elif not close(v, cs_["sum"]):
                            if U:
                                d.unreliable("unidentified", "schedule", f"{MONTHS[m]} {k} total {v} != sum of vendor lines {cs_['sum']}; {U} row(s) with figures but no vendor")
                            else:
                                d.violation("total_not_sum", f"{MONTHS[m]} {k} total {v} != sum of lines {cs_['sum']}", month=MONTHS[m])
            results[spec["totals"]] = d.result("monthly totals equal the sums of the lines")
            for m, item in spec["gl"].items():
                d = Decision(item, ev)
                if m not in groups or not month_usable(d, m, ("end",)):
                    if m not in groups:
                        d.unreliable("unmapped", "month_columns", f"no {MONTHS[m]} column group")
                    results[item] = d.result("")
                    continue
                if bottom_dup(d, "ending", "totals"):
                    results[item] = d.result("")
                    continue
                st, v, c, src = "absent", None, None, None
                for rowrec, label in ((ending_row, "ending-balance row"), (totals_row, "totals row")):
                    st, v, c = bottom_cell(rowrec, m, ("end",))
                    src = label
                    if st not in ("blank", "absent"):
                        break
                shown = None
                if st == "ok":
                    shown = v
                elif st in ("unreliable", "invalid"):
                    register(d, "ending_balance", c, None, recalc_status)
                else:
                    cs_ = column_sum(lines, m, "end")
                    src = "sum of the line ending balances (no ending or totals row figure)"
                    if cs_["invalid"]:
                        d.violation("invalid_value", f"{MONTHS[m]}: line ending balance cell(s) {cs_['invalid'][:5]} are not numbers", cells=cs_["invalid"][:10])
                    elif cs_["unknown"]:
                        d.unreliable("grader_error", "schedule", {"month": MONTHS[m], "cells": cs_["unknown"][:10]})
                    else:
                        shown = cs_["sum"]
                adj = None
                if shown is not None and cents(shown) != cents(gl[acct][m]) and bottom.get("adjust"):
                    sa, a, ca = bottom_cell(bottom["adjust"], m)
                    if sa == "ok" and cents(shown + a) == cents(gl[acct][m]):
                        adj = a
                    elif sa == "unreliable":
                        register(d, "adjustment", ca, bottom["adjust"]["row"], recalc_status)
                        shown = None
                d.evidence = {**ev, "source": src, "cell": c["coord"] if c else None, "exact": str(shown) if shown is not None else None, "adjustment": str(adj) if adj is not None else None}
                d.reference = str(gl[acct][m])
                if shown is not None:
                    total_shown = shown if adj is None else shown + adj
                    d.deliverable = str(cents(total_shown))
                    if cents(total_shown) != cents(gl[acct][m]):
                        d.violation("gl_mismatch", f"{MONTHS[m]} ending balance {cents(total_shown)} != GL {gl[acct][m]} (difference {cents(total_shown) - gl[acct][m]})")
                results[item] = d.result(f"{MONTHS[m]} ending balance equals the GL balance at cents (HALF_UP)" + (" after the quantified adjustment" if adj is not None else ""))
            for key, kinds, item in (("bottom_adds", ("add",), spec.get("bottom_adds")), ("bottom_amort", ("amort",), spec.get("bottom_amort")), ("bottom_end", ("end",), spec.get("bottom_end")), ("bottom_all", ("add", "amort", "end"), spec.get("bottom_all"))):
                if item is None:
                    continue
                d = Decision(item, ev)
                bottom_dup(d, "totals")
                for m in need:
                    for k in kinds:
                        if not month_usable(d, m, (k,)):
                            continue
                        st, v, c = bottom_cell(totals_row, m, (k,)) if totals_row else ("absent", None, None)
                        if st in ("blank", "absent") and k == "end" and ending_row:
                            st, v, c = bottom_cell(ending_row, m, ("end",))
                        if st in ("unreliable", "invalid"):
                            register(d, "bottom_summary", c, None, recalc_status)
                        elif st in ("blank", "absent"):
                            d.violation("bottom_summary_missing", f"no {MONTHS[m]} {k} figure in a bottom summary row", month=MONTHS[m], kind=k)
                results[item] = d.result("bottom summary section present for Jan-Apr")
            d = Decision(spec["variance"], ev)
            bottom_dup(d, "gl", "variance")
            if not gl_row:
                d.violation("no_gl_row", "no GL balance row")
            if not var_row:
                d.violation("no_variance_row", "no variance row")
            if gl_row and var_row:
                for m in need:
                    if any((m, k) in amb for k in ("end", "amort", "add")):
                        d.unreliable("ambiguous", "month_columns", f"{MONTHS[m]}: the month's figure column is ambiguous")
                        continue
                    sg, g_, cg = bottom_cell(gl_row, m)
                    sv, vv, cv = bottom_cell(var_row, m)
                    if sg in ("blank", "absent"):
                        d.violation("gl_missing_month", f"{MONTHS[m]}: no GL balance figure", month=MONTHS[m])
                    elif sg in ("unreliable", "invalid"):
                        register(d, "gl_balance", cg, gl_row["row"], recalc_status)
                    if sv in ("blank", "absent"):
                        d.violation("variance_missing_month", f"{MONTHS[m]}: no variance figure", month=MONTHS[m])
                    elif sv in ("unreliable", "invalid"):
                        register(d, "variance", cv, var_row["row"], recalc_status)
                    elif cents(vv) != Decimal("0.00"):
                        d.violation("variance_nonzero", f"{MONTHS[m]}: variance {cents(vv)} at {cv['coord']}", month=MONTHS[m], cell=cv["coord"])
            results[spec["variance"]] = d.result("GL balance and variance present for every month, variance 0.00")
            if acct == "1251":
                good = [ln for ln in lines if vendors_match(ln["vendor"], "Good Insurance")]
                bcbs = [ln for ln in lines if vendors_match(ln["vendor"], "BCBS")]
                d = Decision(36, ev)
                if not good:
                    d.violation("no_good_insurance_lines", "no Good Insurance line on the 1251 schedule")
                for ln in good:
                    if ln["term"] is not None and ln["term"] != 12:
                        d.violation("term_not_12", f"row {ln['row']}: term {ln['term']} months, policy period is 12", row=ln["row"])
                    if ln["amount_state"] != "ok":
                        d.unreliable("grader_error" if ln["amount_state"] == "unreliable" else "unknown", "amount", f"row {ln['row']}: original amount {ln['amount_state']}")
                        continue
                    monthly = ln["amount"] / 12
                    for m in need:
                        if not month_usable(d, m, ("amort",)):
                            continue
                        c = line_cell(ln, m, "amort")
                        st, v = cell_state(c)
                        if st == "unreliable":
                            register(d, "amortization", c, ln["row"], recalc_status)
                        elif st == "invalid" or abs(v - monthly) > Decimal("0.01"):
                            d.violation("not_straight_line_12", f"row {ln['row']} {MONTHS[m]}: amortization {v if st != 'invalid' else c['value']!r} != amount/12 = {cents(monthly)}", row=ln["row"], month=MONTHS[m])
                d.deliverable = len(good)
                results[36] = d.result("Good Insurance lines amortize straight-line over 12 months from January")
                d = Decision(37, ev)
                if not bcbs:
                    d.violation("no_bcbs_lines", "no BCBS line on the 1251 schedule")
                else:
                    sums37 = {}
                    for m in (1, 2):
                        if m not in groups or not month_usable(d, m, ("amort",)):
                            sums37[m] = None
                            continue
                        cs_ = column_sum(bcbs, m, "amort")
                        for coord in cs_["unknown"]:
                            d.unreliable("grader_error", "amortization", {"month": MONTHS[m], "cell": coord})
                        if cs_["invalid"]:
                            d.violation("invalid_value", f"BCBS {MONTHS[m]} amortization cell(s) {cs_['invalid'][:3]} are not numbers")
                        sums37[m] = None if (cs_["unknown"] or cs_["invalid"]) else cs_["sum"]
                    if sums37.get(1) is not None and sums37[1] != 0:
                        d.violation("bcbs_january_amortization", f"BCBS amortization in January is {sums37[1]}, coverage starts 2/1/2025")
                    if sums37.get(2) is not None and sums37[2] <= 0:
                        d.violation("bcbs_no_february_amortization", f"BCBS amortization in February is {sums37[2]}; it must begin in February 2025")
                    d.deliverable = {MONTHS[m]: (str(v) if v is not None else None) for m, v in sums37.items()}
                results[37] = d.result("BCBS amortization begins in February 2025 (none in January)")
                d = Decision(49, ev)
                neg = []
                for ln in lines:
                    for m in need:
                        if not month_usable(d, m, ("amort",)):
                            continue
                        c = line_cell(ln, m, "amort")
                        st, v = cell_state(c)
                        if st == "unreliable":
                            register(d, "amortization", c, ln["row"], recalc_status)
                        elif st == "ok" and v < 0:
                            neg.append((ln["row"], MONTHS[m], str(v)))
                if neg:
                    d.violation("negative_amortization", f"{len(neg)} negative amortization entr(ies), e.g. {neg[:3]}", rows=[n[0] for n in neg][:20])
                results[49] = d.result("no negative amortization entries")
                d = Decision(50, ev)
                ups = []
                for ln in lines:
                    beg = ln["other"].get("beginning")
                    prev = Decimal(0) if beg is None else (cell_state(beg)[1] if cell_state(beg)[0] in ("ok", "blank") else None)
                    if beg is not None and prev is None:
                        register(d, "beginning", beg, ln["row"], recalc_status)
                    for m in need:
                        if not month_usable(d, m, ("add", "end")):
                            prev = None
                            continue
                        se, end = cell_state(line_cell(ln, m, "end"))
                        sa, add = cell_state(line_cell(ln, m, "add"))
                        for c in (line_cell(ln, m, "end"), line_cell(ln, m, "add")):
                            if cell_state(c)[0] == "unreliable":
                                register(d, "schedule", c, ln["row"], recalc_status)
                        if se not in ("ok", "blank") or prev is None:
                            prev = end if se in ("ok", "blank") else None
                            continue
                        if end > prev + Decimal("0.005"):
                            if sa == "unreliable":
                                pass  # an unreadable addition could explain the increase: registered above
                            elif not (sa == "ok" and add > 0):
                                ups.append({"row": ln["row"], "month": MONTHS[m], "from": str(prev), "to": str(end)})
                        prev = end
                if ups:
                    d.violation("balance_increase_without_addition", f"{len(ups)} line-month(s) where the balance rises without an addition, e.g. {ups[:3]}", rows=sorted({u['row'] for u in ups})[:20])
                results[50] = d.result("no balance increases without a documented addition")
        # ---- summary sheet
        sname = located["summary"]
        cells_ = []
        if sname is None:
            fill(SUMMARY_ITEMS, "fail", "no summary worksheet (no sheet named or recognisable as the Prepaid Summary)", "model_caused_missing", {"file": xlsx_name, "sheets": sheet_names(x)})
        else:
            s = x["sheets"][sname]
            ev = {"file": xlsx_name, "sheet": sname, "basis": located["basis"].get("summary")}
            ok2 = "prepaid" in norm_text(sname) and "summary" in norm_text(sname)
            results[2] = Result(2, "pass" if ok2 else "fail", ev, sname, "sheet title includes 'Prepaid' and 'Summary'", "" if ok2 else f"sheet named {sname!r}", None if ok2 else "model_caused")
            cells_ = summary_cells(s)
            # the header block: the rows above the first row that carries a figure (title, company, period, column captions)
            first_fig = min((c["row"] for c in cells_), default=min(len(s["rows"]), 12) + 1)
            header_rows = max(first_fig - 1, 1)
            hits = text_in_rows(s, r"aurisic", rows=header_rows)
            results[5] = Result(5, "pass" if hits else "fail", {**ev, "cells": hits[:5], "header_rows": header_rows}, bool(hits), "Aurisic in the header", "" if hits else f"company name not found in the header block (rows 1-{header_rows})", None if hits else "model_caused")
            period = text_in_rows(s, r"(4\s*/\s*30\s*/\s*(20)?25)|(04\s*/\s*30\s*/\s*2025)|(2025-04-30)|(apr(il)?\.?\s*30,?\s*2025)|(30\s*apr(il)?\.?,?\s*2025)|(april\s*2025)|(apr\.?\s*2025)|(through\s*april)", rows=header_rows)
            results[6] = Result(6, "pass" if period else "fail", {**ev, "cells": period[:5], "header_rows": header_rows}, bool(period), "reporting period up to April 30, 2025 in the header", "" if period else f"no reporting period through April 30, 2025 in the header block (rows 1-{header_rows})", None if period else "model_caused")
            targets = {"balance_1250": ("balance", "1250"), "balance_1251": ("balance", "1251"), "total": ("total", None), "ytd_1250": ("ytd", "1250"), "ytd_1251": ("ytd", "1251")}
            found = {k: resolve_target(cells_, *t) for k, t in targets.items()}
            summary_info = {"sheet": sname, "cells": [{k: (str(v) if k == "value" else v) for k, v in c.items() if k != "cell"} for c in cells_],
                            "found": {k: {"status": f["status"], "cells": [c["coord"] for c in f["cells"]], "values": [str(c["value"]) if c["value"] is not None else None for c in f["cells"]],
                                          "formulas": [c["formula"] for c in f["cells"]], "unknown": f["unknown"]} for k, f in found.items()}}

            def compare_target(d_, f, expected, label):
                """Decide one summary figure located by its label: absent / unidentifiable / ambiguous / unreadable / value."""
                if f["status"] == "none":
                    d_.violation("absent", f"no summary cell is labelled as the {label}; every figure on the sheet is identified as another measure")
                    return
                if f["status"] == "none_with_unknowns":
                    d_.unreliable("unmapped", "summary_cells", f"no cell labelled as the {label}; figure(s) with unrecognised labels: {f['unknown'][:5]}")
                    return
                vals = [(c, c["state"], c["value"]) for c in f["cells"]]
                if f["status"] == "ambiguous":
                    if all(st == "ok" for _, st, _ in vals) and all(cents(v) != cents(expected) for _, _, v in vals):
                        d_.violation("wrong_value", f"{label}: every labelled candidate differs from {cents(expected)}: {[(c['coord'], str(cents(v))) for c, _, v in vals]}")
                    else:
                        d_.unreliable("ambiguous", "summary_cells", f"{label}: {len(vals)} labelled candidates with different values {[(c['coord'], str(v)) for c, _, v in vals]}")
                    return
                c, st, v = vals[0]
                d_.evidence = {**d_.evidence, "cell": c["coord"], "label": c["label"], "heading": c["heading"]}
                if st in ("unreliable", "invalid"):
                    register(d_, "summary_cells", c["cell"], c["row"], recalc_status)
                    return
                d_.deliverable = str(cents(v))
                if cents(v) != cents(expected):
                    d_.violation("wrong_value", f"{label}: {cents(v)} at {c['coord']} ({c['label']!r}) != {cents(expected)}", cell=c["coord"])
            for item, key, expected, label in ((8, "balance_1250", gl["1250"][4], "April 2025 GL balance for 1250"), (9, "balance_1251", gl["1251"][4], "April 2025 GL balance for 1251"),
                                               (10, "total", Decimal(reference["total_prepaid_2025_04_30"]["path_ii_quantize_exact_sum_once"]), "total prepaid balance as of 4/30/2025")):
                d = Decision(item, {**ev, "located_by": "label and heading", "candidates": [c["coord"] for c in found[key]["cells"]]})
                d.reference = str(cents(expected))
                compare_target(d, found[key], expected, label)
                results[item] = d.result(f"{label} shown as {cents(expected)} (HALF_UP to cents)")
            # item 11: the summary YTD amortization against the sum of the schedule's monthly amortization totals
            ytd_detail = {}
            d = Decision(11, {**ev, "candidates": {k: [c["coord"] for c in found[k]["cells"]] for k in ("ytd_1250", "ytd_1251")}})
            for acct in ("1250", "1251"):
                sch = schedules.get(acct)
                if not (sch and sch.get("status") == "ok" and sch["bottom"].get("totals")):
                    ytd_detail[acct] = None
                    d.unreliable("unknown", "detail_totals", f"no monthly amortization totals on the {acct} schedule to compare with")
                    continue
                tot, ok = Decimal(0), True
                for m in (1, 2, 3, 4):
                    st, v, c = bottom_cell(sch["bottom"]["totals"], m, ("amort",))
                    if st == "ok":
                        tot += v
                    else:
                        ok = False
                        if st == "unreliable":
                            register(d, "detail_totals", c, None, recalc_status)
                        else:
                            d.unreliable("unknown", "detail_totals", f"{acct} {MONTHS[m]} amortization total {st}")
                ytd_detail[acct] = tot if ok else None
                if ytd_detail[acct] is not None:
                    compare_target(d, found[f"ytd_{acct}"], ytd_detail[acct], f"{acct} YTD amortization (sum of the schedule's monthly totals)")
                elif found[f"ytd_{acct}"]["status"] == "none":
                    d.violation("absent", f"no summary cell is labelled as the {acct} YTD amortization")
            d.evidence = {**d.evidence, "detail_totals": {k: str(v) if v is not None else None for k, v in ytd_detail.items()}}
            d.reference = {"1250": str(reference["ytd_amortization_1250_cents"]), "1251": str(reference["ytd_amortization_1251_cents"])}
            results[11] = d.result("YTD amortization per account equals the sum of the schedule's Jan-Apr totals")
            # item 7: the located figures are formulas referencing the detail sheets (formula text is evidence even without a cached value)
            d = Decision(7, {**ev, "cells": {k: [(c["coord"], c["formula"]) for c in found[k]["cells"]] for k in ("ytd_1250", "ytd_1251", "balance_1250", "balance_1251")}})
            for key, acct in (("ytd_1250", "1250"), ("balance_1250", "1250"), ("ytd_1251", "1251"), ("balance_1251", "1251")):
                f, target = found[key], located[acct]
                if f["status"] == "none":
                    d.violation("absent", f"{key}: no summary figure labelled for it to link")
                    continue
                if f["status"] == "none_with_unknowns":
                    d.unreliable("unmapped", "summary_cells", f"{key}: no labelled figure; unrecognised labels at {f['unknown'][:5]}")
                    continue
                verdicts = []
                for c in f["cells"]:
                    if not c["formula"]:
                        verdicts.append(("hard_coded", c))
                    elif target and not references_sheet(c["formula"], target):
                        verdicts.append(("not_linked_to_detail", c))
                    else:
                        verdicts.append(("linked", c))
                if f["status"] == "ambiguous" and len({v for v, _ in verdicts}) > 1:
                    d.unreliable("ambiguous", "summary_cells", f"{key}: labelled candidates differ in linkage {[(c['coord'], v) for v, c in verdicts]}")
                    continue
                v, c = verdicts[0]
                if v == "hard_coded":
                    d.violation("hard_coded", f"{key} at {c['coord']} is a literal value, not a formula", cell=c["coord"])
                elif v == "not_linked_to_detail":
                    d.violation("not_linked_to_detail", f"{key} at {c['coord']} is a formula that does not reference the {acct} sheet {target!r}: {c['formula'][:80]}", cell=c["coord"])
            results[7] = d.result("YTD amortization and ending balances are formulas referencing the 1250 and 1251 sheets")
        # ---- formats (53, B4): every nonzero monetary cell carries a currency or two-decimal thousands format; date cells a date format
        monetary, bad_fmt, unknown_fmt, date_bad = 0, [], [], []

        def check_money(sheet, c):
            nonlocal monetary
            if c is None:
                return
            st, v = cell_state(c)
            nf = (sheet["cells"].get(c["coord"]) or {}).get("number_format") or "General"
            if st == "ok" and v != 0:
                monetary += 1
                if not money_format_ok(nf):
                    bad_fmt.append((f"{sheet_label}!{c['coord']}", nf, str(v)))
            elif st == "unreliable" and not money_format_ok(nf):
                unknown_fmt.append((f"{sheet_label}!{c['coord']}", nf))
        for acct, sch in schedules.items():
            if sch.get("status") != "ok":
                continue
            sheet = x["sheets"][sch["sheet"]]
            sheet_label = sch["sheet"]
            for ln in sch["lines"]:
                for mc in ln["months"].values():
                    for c in mc.values():
                        check_money(sheet, c)
                for f in ("beginning", "amount", "monthly"):
                    check_money(sheet, ln["other"].get(f))
            for rowrec in sch["bottom"].values():
                for mc in rowrec["months"].values():
                    for c in mc.values():
                        check_money(sheet, c)
            for coord, c in sheet["cells"].items():
                v = c.get("cached") if c.get("formula") else c.get("literal")
                if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", v):
                    nf = c.get("number_format") or "General"
                    if not re.search(r"[dmy]", nf, re.I) or nf == "General":
                        date_bad.append((f"{sheet_label}!{coord}", nf))
        if sname is not None:
            sheet = x["sheets"][sname]
            sheet_label = sname
            for c in cells_:
                if c["class"][0] is not None:
                    check_money(sheet, c["cell"])
        d = Decision(53, {"monetary_cells": monetary, "noncompliant": bad_fmt[:10], "noncompliant_count": len(bad_fmt), "unreadable_with_noncompliant_format": unknown_fmt[:10], "date_cells_without_date_format": date_bad[:10]})
        if bad_fmt:
            d.violation("amounts_not_currency_formatted", f"{len(bad_fmt)} nonzero monetary cell(s) lack a currency or two-decimal thousands format, e.g. {bad_fmt[:3]}")
        if date_bad:
            d.violation("dates_without_date_format", f"{len(date_bad)} date cell(s) without a date format, e.g. {date_bad[:3]}")
        if unknown_fmt:
            d.unreliable("grader_error", "formats", f"{len(unknown_fmt)} unreadable figure(s) with a non-currency format: whether they are nonzero amounts is unknown, e.g. {unknown_fmt[:3]}")
        if not monetary and not unknown_fmt and schedules:
            d.unreliable("unknown", "formats", "no monetary cells located")
        results[53] = d.result("every nonzero monetary cell carries a currency or two-decimal thousands format and dates a date format")
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():  # the production item contract (B1): grade_run reads weight and criterion for every row
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = list(ITEM_INPUTS.get(i, []))
        r["fail_on_own"] = {"missing": list(ITEM_INPUTS.get(i, [])), "invalid": list(ITEM_INPUTS.get(i, [])), "row_set": False, "row_scoped": False, "invalid_kinds": ["error_value", "non_numeric", "non_finite"]}
    sched_out = {}
    for acct, sch in schedules.items():
        o = {k: v for k, v in sch.items() if k in ("sheet", "status", "groups", "bottom", "match", "vendor_col", "vendor_basis", "notes", "unidentified", "bottom_duplicates", "unclassified_columns")}
        o["ambiguous_columns"] = {f"{MONTHS.get(m, m)}:{k}": cs for (m, k), cs in (sch.get("header") or {}).get("ambiguous", {}).items()}
        o["lines"] = len(sch.get("lines", []))
        sched_out[acct] = o
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status,
            "schedules": sched_out, "summary": summary_info, "schedule_lines": {acct: sch.get("lines", []) for acct, sch in schedules.items()}, "judge_items": J_ITEMS}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        verdicts = [items[i]["verdict"] for i in spec["items"] if i in items]
        status = "fail" if "fail" in verdicts else "not_confirmed" if ("cannot_assess" in verdicts or spec.get("judge_items")) else "pass"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "judge_items": spec.get("judge_items", []), "status_from_deterministic": status,
                    "note": "judge items pending" if spec.get("judge_items") and status != "fail" else ""}
    return out
