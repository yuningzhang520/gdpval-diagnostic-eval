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
GL. No comparison is ever skipped into a PASS: a confirmed violation FAILs, an unreliable required input gives
cannot_assess, everything else PASSes."""
import re
from decimal import Decimal

from .engine import headers as H
from .engine.cells import UNRELIABLE_KINDS, cell_coord, norm_text, numeric_cell, read_cell
from .engine.decision import Decision, Result
from .engine.money import cents, cents_equal, close, parse_money
from .engine.sheets import find_label_rows, first_text, month_of, row_cells, sheet_names, text_in_rows
from .engine.workbook import workbook_gate

TASK = "7d7fc9a7-21a7-4b83-906f-416dea5ad04f"
VERSION = "7d7fc9a7-2026-11-01.1"
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


def _d(x):
    return parse_money(x)


def vendor_key(s) -> str:
    t = norm_text(s)
    t = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|the)\b\.?", " ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def vendors_match(a: str, b: str) -> bool:
    ka, kb = vendor_key(a), vendor_key(b)
    return bool(ka) and bool(kb) and (ka == kb or ka in kb or kb in ka)


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
    columns. Returns {"month_row", "sub_row" (row holding the add/amort/end kinds, may equal month_row), "header_end",
    "groups": {month: {"add": col, "amort": col, "end": col}}, "other": [(col, header text)]}."""
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
                if kind and kind not in groups.setdefault(m, {}):
                    groups[m][kind] = col
                continue
            label = " ".join(x for x in (norm_text(text) if text is not None and not hasattr(text, "year") else "", norm_text(sub) if sub is not None and not hasattr(sub, "year") else "") if x).strip()
            if label:
                other.append((col, label))
        two_row = any(sub_cells[i]["status"] == "ok" and sub_kind(sub_cells[i]["value"]) for i in range(len(sub_cells)) if not hasattr(sub_cells[i]["value"], "year"))
        return {"month_row": r, "sub_row": r + 1 if two_row else r, "header_end": r + 1 if two_row else r, "groups": {m: g for m, g in sorted(groups.items())}, "other": other}
    return None


def parse_schedule(sheet: dict, name: str) -> dict:
    """Lines, bottom rows and the column map of one schedule sheet (every cell through read_cell)."""
    hdr = month_header(sheet)
    if hdr is None:
        return {"sheet": name, "status": "no_month_header", "lines": [], "bottom": {}, "groups": {}}
    other_header = [""] * (max([c for c, _ in hdr["other"]] + [0]) + 1)
    for col, label in hdr["other"]:
        other_header[col] = label
    mapping = H.map_columns(other_header, SCHEMA)
    cols = mapping["cols"]
    vendor_col = cols.get("vendor", 0 if 0 not in {c for g in hdr["groups"].values() for c in g.values()} else None)
    lines, bottom, notes = [], {}, []
    stop = len(sheet["rows"])
    for r in range(hdr["header_end"] + 1, stop + 1):
        label = first_text(sheet, r, max_cols=max(3, (vendor_col or 0) + 1))
        cells = row_cells(sheet, r)
        if not any(c["status"] != "empty" for c in cells):
            continue
        if label and re.search(NOT_A_LINE, norm_text(label), re.I):
            key = next((k for k, rx in BOTTOM.items() if re.search(rx, norm_text(label), re.I)), None)
            if key and key not in bottom:
                bottom[key] = {"row": r, "label": label, "months": {m: {k: read_cell(sheet, r, c) for k, c in g.items()} for m, g in hdr["groups"].items()},
                               "other": {f: read_cell(sheet, r, c) for f, c in cols.items()}}
            else:
                notes.append({"row": r, "label": label})
            continue
        vendor = cells[vendor_col]["value"] if vendor_col is not None and vendor_col < len(cells) and cells[vendor_col]["status"] == "ok" else None
        month_cells = {m: {k: read_cell(sheet, r, c) for k, c in g.items()} for m, g in hdr["groups"].items()}
        has_numbers = any(numeric_cell(cc)[0] == "ok" for mc in month_cells.values() for cc in mc.values()) or (cols.get("amount") is not None and numeric_cell(read_cell(sheet, r, cols["amount"]))[0] == "ok")
        if not (isinstance(vendor, str) and vendor.strip()) or not has_numbers:
            if label:
                notes.append({"row": r, "label": label})
            continue
        line = {"row": r, "vendor": vendor.strip(), "months": month_cells, "other": {f: read_cell(sheet, r, c) for f, c in cols.items()}}
        adds = {m: numeric_cell(mc["add"])[1] if "add" in mc and numeric_cell(mc["add"])[0] == "ok" else None for m, mc in month_cells.items()}
        line["adds"] = adds
        amt_cell = line["other"].get("amount")
        amt = numeric_cell(amt_cell)[1] if amt_cell and numeric_cell(amt_cell)[0] == "ok" else None
        line["amount"] = _d(amt) if amt is not None else (sum((_d(v) for v in adds.values() if v is not None), Decimal(0)) if any(v is not None for v in adds.values()) else None)
        line["amount_source"] = "amount column" if amt is not None else "sum of monthly adds"
        start = None
        sc = line["other"].get("start")
        if sc and sc["status"] == "ok":
            start = month_of(sc["value"])
        if start is None:
            dc = line["other"].get("date")
            if dc and dc["status"] == "ok":
                start = month_of(dc["value"])
        if start is None:
            firsts = [m for m, v in sorted(adds.items()) if v is not None and _d(v) and _d(v) > 0]
            start = firsts[0] if firsts else None
        line["start"] = start
        tc = line["other"].get("term")
        term = numeric_cell(tc)[1] if tc and numeric_cell(tc)[0] == "ok" else None
        line["term"] = int(term) if term is not None and float(term).is_integer() else term
        lines.append(line)
    return {"sheet": name, "status": "ok", "header": hdr, "mapping": {k: v for k, v in mapping.items() if k in ("cols", "field_status", "unmapped_headers", "ambiguous")},
            "groups": hdr["groups"], "lines": lines, "bottom": bottom, "notes": notes, "vendor_col": vendor_col}


def match_invoices(lines: list[dict], invoices: list[dict]) -> dict:
    """Invoices against lines. Pass 1: vendor + month + exact amount on the month's add cell (a consolidated line may
    satisfy several invoices through different months). Pass 2: vendor + exact amount on the line's original amount.
    Pass 3: vendor + month with a different amount (present, wrong amount). Leftover invoices are missing; leftover
    lines are extra."""
    used_adds: set = set()
    used_lines: set = set()
    matched, wrong_amount, missing = [], [], []
    inv_amount = lambda inv: Decimal(inv["amount_text"].replace(",", ""))
    for inv in invoices:
        amt, m = inv_amount(inv), inv["month"]
        hit = None
        for i, ln in enumerate(lines):
            if not vendors_match(ln["vendor"], inv["vendor"]):
                continue
            v = ln["adds"].get(m)
            if v is not None and (i, m) not in used_adds and cents_equal(v, amt):
                hit = {"line": i, "row": ln["row"], "via": f"{MONTHS.get(m, m)} add"}
                used_adds.add((i, m))
                break
        if hit is None:
            for i, ln in enumerate(lines):
                if i in used_lines or not vendors_match(ln["vendor"], inv["vendor"]):
                    continue
                if ln["amount"] is not None and cents_equal(ln["amount"], amt) and not any((i, mm) in used_adds for mm in ln["adds"]):
                    hit = {"line": i, "row": ln["row"], "via": ln["amount_source"]}
                    used_lines.add(i)
                    break
        if hit:
            matched.append({**{k: inv[k] for k in ("vendor", "invoice", "month", "amount_text", "file", "page")}, **hit})
        else:
            missing.append(inv)
    still_missing = []
    for inv in missing:
        amt, m = inv_amount(inv), inv["month"]
        cand = next((i for i, ln in enumerate(lines) if i not in used_lines and vendors_match(ln["vendor"], inv["vendor"]) and (ln["start"] in (None, m)) and not any((i, mm) in used_adds for mm in ln["adds"])), None)
        if cand is not None:
            ln = lines[cand]
            used_lines.add(cand)
            wrong_amount.append({**{k: inv[k] for k in ("vendor", "invoice", "month", "amount_text", "file", "page")}, "line": cand, "row": ln["row"], "delivered_amount": str(ln["amount"]) if ln["amount"] is not None else None})
        else:
            still_missing.append(inv)
    consumed = used_lines | {i for i, _ in used_adds}
    extra = [{"line": i, "row": ln["vendor"] and ln["row"], "vendor": ln["vendor"], "amount": str(ln["amount"]) if ln["amount"] is not None else None} for i, ln in enumerate(lines) if i not in consumed]
    return {"matched": matched, "wrong_amount": wrong_amount, "missing": still_missing, "extra_lines": extra, "invoices": len(invoices), "lines": len(lines)}


def _num(cell):
    """Decimal of an ok numeric cell, Decimal(0) for an empty cell (blank = zero in a schedule), None otherwise."""
    if cell is None:
        return None
    if cell["status"] == "empty":
        return Decimal(0)
    st, v = numeric_cell(cell)
    return _d(v) if st == "ok" else None


def line_values(line: dict, m: int, kind: str):
    mc = line["months"].get(m, {})
    return mc.get(kind)


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


# ----------------------------------------------------------------------------- summary sheet
SUMMARY_TARGETS = {"balance_1250": (r"1250|expense", r"balance|ending|gl", None), "balance_1251": (r"1251|insur", r"balance|ending|gl", None),
                   "total": (r"total", r"prepaid|balance", r"1250|1251|expense|insur|amort|addition|invoice"),  # the grand total, never one account's figure
                   "ytd_1250": (r"1250|expense", r"amort", None), "ytd_1251": (r"1251|insur", r"amort", None)}


def summary_cells(sheet: dict, max_rows: int = 60) -> list[dict]:
    """Numeric cells of the summary sheet with their row label (and the sub-heading above the block) and formula."""
    out, heading = [], ""
    for r in range(1, min(max_rows, len(sheet["rows"])) + 1):
        cells = row_cells(sheet, r)
        texts = [c["value"] for c in cells if c["status"] == "ok" and isinstance(c["value"], str) and c["value"].strip()]
        nums = [(c, numeric_cell(c)[1]) for c in cells if numeric_cell(c)[0] == "ok" and not isinstance(c["value"], bool)]
        if texts and not nums:
            heading = texts[0]
        for c, v in nums:
            raw = sheet["cells"].get(c["coord"], {})
            out.append({"coord": c["coord"], "row": r, "value": _d(v), "label": " ".join(texts), "heading": heading, "formula": raw.get("formula"), "cell": c})
    return out


def find_summary_value(cells: list[dict], expected: Decimal | None, label_rx: tuple, exclude: set) -> tuple[dict | None, str]:
    """A summary cell for a target: by value (cents equal to the expected figure), else by its label keywords (with an
    exclusion pattern so a single account's figure never stands in for the grand total)."""
    if expected is not None:
        for c in cells:
            if c["coord"] not in exclude and c["value"] is not None and cents(c["value"]) == cents(expected):
                return c, "value"
    acct_rx, kind_rx, not_rx = label_rx
    for c in cells:
        lab = norm_text(c["label"] + " " + c["heading"])
        if c["coord"] not in exclude and re.search(acct_rx, lab) and re.search(kind_rx, lab) and not (not_rx and re.search(not_rx, lab)):
            return c, "label"
    return None, "absent"


def references_sheet(formula: str | None, sheet_name: str) -> bool:
    if not formula:
        return False
    f = formula.replace("$", "")
    return f"'{sheet_name}'!" in f or re.search(rf"(?<![A-Za-z0-9_']){re.escape(sheet_name)}!", f) is not None


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
                fill([i for i in SCHED_ITEMS[acct] if i != spec["sheet_item"]], "cannot_assess", f"extraction_failed: no month-grouped header found on sheet {name!r} (rows with Jan-Apr column groups)", "grader_extraction", ev_base)
                continue
            groups = sch["groups"]
            months_present = sorted(m for m in (1, 2, 3, 4) if m in groups)
            ev = {**ev_base, "header_rows": (sch["header"]["month_row"], sch["header"]["header_end"]), "groups": {MONTHS.get(m, m): {k: cell_coord(sch["header"]["month_row"], c) for k, c in g.items()} for m, g in groups.items()},
                  "lines": len(sch["lines"]), "bottom_rows": {k: v["row"] for k, v in sch["bottom"].items()}, "column_mapping": sch["mapping"]["cols"]}
            # months displayed
            results[spec["months"]] = Result(spec["months"], "pass" if months_present == [1, 2, 3, 4] else "fail", ev, [MONTHS[m] for m in months_present], "Jan, Feb, Mar, Apr",
                                             "" if months_present == [1, 2, 3, 4] else f"month groups found: {[MONTHS[m] for m in months_present]}", None if months_present == [1, 2, 3, 4] else "model_caused")
            # invoice completeness and amounts
            mt = match_invoices(sch["lines"], reference[spec["invoices"]])
            sch["match"] = mt
            d = Decision(spec["complete"], ev)
            if mt["missing"]:
                d.violation("missing_invoices", f"{len(mt['missing'])} of {mt['invoices']} invoices absent: " + "; ".join(f"{i['vendor']} {i['invoice']} {i['amount_text']} ({i['file']} p{i['page']})" for i in mt["missing"][:6]),
                            missing=[{k: i[k] for k in ("vendor", "invoice", "month", "amount_text", "file", "page")} for i in mt["missing"]])
            d.deliverable, d.reference = {"matched": len(mt["matched"]), "wrong_amount": len(mt["wrong_amount"]), "missing": len(mt["missing"]), "extra_lines": len(mt["extra_lines"])}, mt["invoices"]
            results[spec["complete"]] = d.result(f"every one of the {mt['invoices']} invoices is present (matched by vendor, month and exact amount)")
            d = Decision(spec["amount"], ev)
            if mt["wrong_amount"]:
                d.violation("amount_mismatch", "; ".join(f"{w['vendor']} {w['invoice']} {w['amount_text']} delivered as {w['delivered_amount']} (row {w['row']})" for w in mt["wrong_amount"][:6]), rows=[w["row"] for w in mt["wrong_amount"]])
            d.deliverable, d.reference = len(mt["wrong_amount"]), 0  # absent invoices are item 13's finding; 14 judges the delivered lines
            results[spec["amount"]] = d.result("every delivered invoice amount equals its source invoice")
            # per-line identity and window
            lines = sch["lines"]
            need = [m for m in (1, 2, 3, 4) if m in groups]
            d = Decision(spec["identity"], ev)
            missing_kind = [(MONTHS[m], k) for m in need for k in ("end",) if k not in groups[m]]
            if missing_kind:
                d.unreliable("unmapped", "month_columns", f"end-balance column not identified for {missing_kind}")
            bad = []
            prev_cells = {}
            for ln in lines:
                beg_cell = ln["other"].get("beginning")
                prev = _num(beg_cell) if beg_cell else Decimal(0)
                if beg_cell and prev is None:
                    d.cell("beginning", beg_cell["status"], beg_cell["value"], beg_cell["coord"], ln["row"], recalc_status)
                    prev = Decimal(0)
                for m in need:
                    if "end" not in groups[m]:
                        continue
                    add, amort, end = (_num(line_values(ln, m, "add")) if "add" in groups[m] else Decimal(0)), (_num(line_values(ln, m, "amort")) if "amort" in groups[m] else Decimal(0)), _num(line_values(ln, m, "end"))
                    cells_ = [line_values(ln, m, k) for k in ("add", "amort", "end") if k in groups[m]]
                    for cc in cells_:
                        if cc["status"] in UNRELIABLE_KINDS:
                            d.cell("schedule", cc["status"], cc["value"], cc["coord"], ln["row"], recalc_status)
                    if None in (add, amort, end):
                        bad_cell = next((cc for cc in cells_ if _num(cc) is None), None)
                        if bad_cell and bad_cell["status"] not in UNRELIABLE_KINDS:
                            d.violation("invalid_value", f"row {ln['row']} {MONTHS[m]}: {bad_cell['coord']} is not a number ({bad_cell['value']!r})", cell=bad_cell["coord"], row=ln["row"])
                        prev = end if end is not None else prev
                        continue
                    if not close(prev + add - amort, end):
                        bad.append({"row": ln["row"], "month": MONTHS[m], "beginning": str(prev), "add": str(add), "amort": str(amort), "end": str(end), "expected_end": str(prev + add - amort)})
                    prev = end
            if bad:
                d.violation("identity", f"{len(bad)} line-month(s) where beginning + adds - amortization != ending, e.g. {bad[:3]}", rows=sorted({b['row'] for b in bad})[:20])
            d.deliverable = len(bad)
            results[spec["identity"]] = d.result("beginning + adds - amortization = ending on every line and month")
            if "window" in spec:
                d = Decision(spec["window"], ev)
                outside = []
                for mm in mt["matched"]:
                    ln = lines[mm["line"]]
                    for m in need:
                        if m < mm["month"] and "amort" in groups[m]:
                            v = _num(line_values(ln, m, "amort"))
                            if v is not None and v != 0:
                                outside.append({"row": ln["row"], "month": MONTHS[m], "amortization": str(v), "invoice_month": MONTHS[mm["month"]]})
                if outside:
                    d.violation("amortization_outside_period", f"{len(outside)} line-month(s) with amortization before the invoice month, e.g. {outside[:3]}", rows=sorted({o['row'] for o in outside})[:20])
                d.deliverable = len(outside)
                results[spec["window"]] = d.result("no amortization recorded before a line's start month (Jan-Apr)")
            # totals, ending balances, GL, variance
            bottom = sch["bottom"]
            sums = {m: {k: sum((_num(line_values(ln, m, k)) or Decimal(0)) for ln in lines) for k in ("add", "amort", "end") if k in groups[m]} for m in need}
            totals_row, ending_row, var_row, gl_row = bottom.get("totals"), bottom.get("ending"), bottom.get("variance"), bottom.get("gl")

            def bottom_value(rowrec, m, prefer=("end", "amort", "add")):
                if not rowrec or m not in rowrec["months"]:
                    return None, None
                for k in prefer:
                    c = rowrec["months"][m].get(k)
                    if c and numeric_cell(c)[0] == "ok":
                        return _d(numeric_cell(c)[1]), c["coord"]
                return None, None
            d = Decision(spec["totals"], ev)
            if not totals_row:
                d.violation("no_totals_row", "no monthly totals row below the lines")
            else:
                for m in need:
                    for k in ("amort", "end"):
                        if k not in groups[m]:
                            continue
                        c = totals_row["months"][m].get(k)
                        v = _d(numeric_cell(c)[1]) if c and numeric_cell(c)[0] == "ok" else None
                        if k == "end" and v is None and ending_row:
                            v, _ = bottom_value(ending_row, m, ("end",))
                        if v is None:
                            d.violation("total_missing", f"{MONTHS[m]} {k} total absent", month=MONTHS[m])
                        elif not close(v, sums[m][k]):
                            d.violation("total_not_sum", f"{MONTHS[m]} {k} total {v} != sum of lines {sums[m][k]}", month=MONTHS[m])
            results[spec["totals"]] = d.result("monthly totals equal the sums of the lines")
            for m, item in spec["gl"].items():
                d = Decision(item, ev)
                if m not in groups or "end" not in groups[m]:
                    d.unreliable("unmapped", "month_columns", f"no {MONTHS[m]} end-balance column")
                    results[item] = d.result("")
                    continue
                v, coord = bottom_value(ending_row, m, ("end",)) if ending_row else (None, None)
                src = "ending-balance row"
                if v is None:
                    v, coord = bottom_value(totals_row, m, ("end",)) if totals_row else (None, None)
                    src = "totals row"
                if v is None:
                    v, coord, src = sums[m].get("end"), None, "sum of the line ending balances (no totals row)"
                adj = None
                if v is not None and cents(v) != cents(gl[acct][m]) and bottom.get("adjust"):
                    a, _ = bottom_value(bottom["adjust"], m)
                    if a is not None and cents(v + a) == cents(gl[acct][m]):
                        adj = a
                shown = v if adj is None else v + adj
                d.deliverable, d.reference = str(cents(shown)) if shown is not None else None, str(gl[acct][m])
                d.evidence = {**ev, "source": src, "cell": coord, "exact": str(shown) if shown is not None else None, "adjustment": str(adj) if adj is not None else None}
                if shown is None:
                    d.violation("no_ending_balance", f"no {MONTHS[m]} ending balance on the schedule")
                elif cents(shown) != cents(gl[acct][m]):
                    d.violation("gl_mismatch", f"{MONTHS[m]} ending balance {cents(shown)} != GL {gl[acct][m]} (difference {cents(shown) - gl[acct][m]})")
                results[item] = d.result(f"{MONTHS[m]} ending balance equals the GL balance at cents (HALF_UP)" + (" after the quantified adjustment" if adj is not None else ""))
            for key, kinds, item in (("bottom_adds", ("add",), spec.get("bottom_adds")), ("bottom_amort", ("amort",), spec.get("bottom_amort")), ("bottom_end", ("end",), spec.get("bottom_end")), ("bottom_all", ("add", "amort", "end"), spec.get("bottom_all"))):
                if item is None:
                    continue
                d = Decision(item, ev)
                for m in need:
                    for k in kinds:
                        v, _ = bottom_value(totals_row, m, (k,)) if totals_row else (None, None)
                        if v is None and k == "end" and ending_row:
                            v, _ = bottom_value(ending_row, m, ("end",))
                        if v is None:
                            d.violation("bottom_summary_missing", f"no {MONTHS[m]} {k} figure in a bottom summary row", month=MONTHS[m], kind=k)
                results[item] = d.result("bottom summary section present for Jan-Apr")
            d = Decision(spec["variance"], ev)
            if not gl_row:
                d.violation("no_gl_row", "no GL balance row")
            if not var_row:
                d.violation("no_variance_row", "no variance row")
            if gl_row and var_row:
                for m in need:
                    g_, _ = bottom_value(gl_row, m)
                    vv, vc = bottom_value(var_row, m)
                    if g_ is None:
                        d.violation("gl_missing_month", f"{MONTHS[m]}: no GL balance figure", month=MONTHS[m])
                    if vv is None:
                        d.violation("variance_missing_month", f"{MONTHS[m]}: no variance figure", month=MONTHS[m])
                    elif cents(vv) != Decimal("0.00"):
                        d.violation("variance_nonzero", f"{MONTHS[m]}: variance {cents(vv)} at {vc}", month=MONTHS[m], cell=vc)
            results[spec["variance"]] = d.result("GL balance and variance present for every month, variance 0.00")
            if acct == "1251":
                good = [ln for ln in lines if vendors_match(ln["vendor"], "Good Insurance")]
                bcbs = [ln for ln in lines if vendors_match(ln["vendor"], "BCBS")]
                d = Decision(36, ev)
                if not good:
                    d.violation("no_good_insurance_lines", "no Good Insurance line on the 1251 schedule")
                for ln in good:
                    if ln["amount"] is None:
                        continue
                    monthly = ln["amount"] / 12
                    for m in need:
                        if "amort" in groups[m]:
                            v = _num(line_values(ln, m, "amort"))
                            if v is None or abs(v - monthly) > Decimal("0.01"):
                                d.violation("not_straight_line_12", f"row {ln['row']} {MONTHS[m]}: amortization {v} != amount/12 = {cents(monthly)}", row=ln["row"], month=MONTHS[m])
                    if ln["term"] is not None and ln["term"] != 12:
                        d.violation("term_not_12", f"row {ln['row']}: term {ln['term']} months, policy period is 12", row=ln["row"])
                d.deliverable = len(good)
                results[36] = d.result("Good Insurance lines amortize straight-line over 12 months from January")
                d = Decision(37, ev)
                if not bcbs:
                    d.violation("no_bcbs_lines", "no BCBS line on the 1251 schedule")
                else:
                    jan = sum((_num(line_values(ln, 1, "amort")) or Decimal(0)) for ln in bcbs if 1 in groups and "amort" in groups[1])
                    feb = sum((_num(line_values(ln, 2, "amort")) or Decimal(0)) for ln in bcbs if 2 in groups and "amort" in groups[2])
                    if jan != 0:
                        d.violation("bcbs_january_amortization", f"BCBS amortization in January is {jan}, coverage starts 2/1/2025")
                    if feb <= 0:
                        d.violation("bcbs_no_february_amortization", f"BCBS amortization in February is {feb}; it must begin in February 2025")
                    d.deliverable = {"jan": str(jan), "feb": str(feb)}
                results[37] = d.result("BCBS amortization begins in February 2025 (none in January)")
                d = Decision(49, ev)
                neg = [(ln["row"], MONTHS[m], str(_num(line_values(ln, m, "amort")))) for ln in lines for m in need if "amort" in groups[m] and (_num(line_values(ln, m, "amort")) or Decimal(0)) < 0]
                if neg:
                    d.violation("negative_amortization", f"{len(neg)} negative amortization entr(ies), e.g. {neg[:3]}", rows=[n[0] for n in neg][:20])
                results[49] = d.result("no negative amortization entries")
                d = Decision(50, ev)
                ups = []
                for ln in lines:
                    prev = _num(ln["other"]["beginning"]) if ln["other"].get("beginning") else Decimal(0)
                    for m in need:
                        if "end" not in groups[m]:
                            continue
                        end = _num(line_values(ln, m, "end")); add = _num(line_values(ln, m, "add")) if "add" in groups[m] else Decimal(0)
                        if end is None or prev is None:
                            prev = end
                            continue
                        if end > prev + Decimal("0.005") and not (add and add > 0):
                            ups.append({"row": ln["row"], "month": MONTHS[m], "from": str(prev), "to": str(end)})
                        prev = end
                if ups:
                    d.violation("balance_increase_without_addition", f"{len(ups)} line-month(s) where the balance rises without an addition, e.g. {ups[:3]}", rows=sorted({u['row'] for u in ups})[:20])
                results[50] = d.result("no balance increases without a documented addition")
        # ---- summary sheet
        sname = located["summary"]
        if sname is None:
            fill(SUMMARY_ITEMS, "fail", "no summary worksheet (no sheet named or recognisable as the Prepaid Summary)", "model_caused_missing", {"file": xlsx_name, "sheets": sheet_names(x)})
        else:
            s = x["sheets"][sname]
            ev = {"file": xlsx_name, "sheet": sname, "basis": located["basis"].get("summary")}
            ok2 = "prepaid" in norm_text(sname) and "summary" in norm_text(sname)
            results[2] = Result(2, "pass" if ok2 else "fail", ev, sname, "sheet title includes 'Prepaid' and 'Summary'", "" if ok2 else f"sheet named {sname!r}", None if ok2 else "model_caused")
            # the header block: the rows above the first row that carries an amount (title, company, period, column captions)
            header_rows = next((r - 1 for r in range(1, min(len(s["rows"]), 40) + 1) if any(numeric_cell(c)[0] == "ok" and not isinstance(c["value"], bool) for c in row_cells(s, r))), min(len(s["rows"]), 12))
            header_rows = max(header_rows, 1)
            hits = text_in_rows(s, r"aurisic", rows=header_rows)
            results[5] = Result(5, "pass" if hits else "fail", {**ev, "cells": hits[:5], "header_rows": header_rows}, bool(hits), "Aurisic in the header", "" if hits else f"company name not found in the header block (rows 1-{header_rows})", None if hits else "model_caused")
            period = text_in_rows(s, r"(4\s*/\s*30\s*/\s*(20)?25)|(04\s*/\s*30\s*/\s*2025)|(2025-04-30)|(apr(il)?\.?\s*30,?\s*2025)|(30\s*apr(il)?\.?,?\s*2025)|(april\s*2025)|(apr\.?\s*2025)|(through\s*april)", rows=header_rows)
            results[6] = Result(6, "pass" if period else "fail", {**ev, "cells": period[:5], "header_rows": header_rows}, bool(period), "reporting period up to April 30, 2025 in the header", "" if period else f"no reporting period through April 30, 2025 in the header block (rows 1-{header_rows})", None if period else "model_caused")
            cells_ = summary_cells(s)
            summary_info = {"sheet": sname, "cells": [{k: (str(v) if k == "value" else v) for k, v in c.items() if k != "cell"} for c in cells_]}
            # delivered detail totals for item 11 (YTD amortization = sum of the schedule's monthly amortization totals)
            ytd_detail = {}
            for acct in ("1250", "1251"):
                sch = schedules.get(acct)
                if sch and sch.get("status") == "ok" and sch["bottom"].get("totals"):
                    vals = []
                    for m in (1, 2, 3, 4):
                        c = sch["bottom"]["totals"]["months"].get(m, {}).get("amort")
                        vals.append(_d(numeric_cell(c)[1]) if c and numeric_cell(c)[0] == "ok" else None)
                    ytd_detail[acct] = sum(vals) if all(v is not None for v in vals) else None
                else:
                    ytd_detail[acct] = None
            ref_ytd = {"1250": Decimal(reference["ytd_amortization_1250_cents"]), "1251": Decimal(reference["ytd_amortization_1251_cents"])}
            ref_bal = {"1250": gl["1250"][4], "1251": gl["1251"][4]}
            total_ref = Decimal(reference["total_prepaid_2025_04_30"]["path_ii_quantize_exact_sum_once"])
            found: dict = {}
            used: set = set()
            for key, expected in (("balance_1250", ref_bal["1250"]), ("balance_1251", ref_bal["1251"]), ("total", total_ref), ("ytd_1250", ytd_detail["1250"] if ytd_detail["1250"] is not None else ref_ytd["1250"]), ("ytd_1251", ytd_detail["1251"] if ytd_detail["1251"] is not None else ref_ytd["1251"])):
                c, how = find_summary_value(cells_, expected, SUMMARY_TARGETS[key], used)
                found[key] = {"cell": c, "how": how, "expected": expected}
                if c:
                    used.add(c["coord"])
            summary_info["found"] = {k: {"coord": v["cell"]["coord"] if v["cell"] else None, "how": v["how"], "value": str(v["cell"]["value"]) if v["cell"] else None, "expected": str(v["expected"]), "formula": v["cell"]["formula"] if v["cell"] else None} for k, v in found.items()}
            for item, key, label in ((8, "balance_1250", "April 2025 GL balance for 1250"), (9, "balance_1251", "April 2025 GL balance for 1251"), (10, "total", "total prepaid balance as of 4/30/2025")):
                f_ = found[key]
                d = Decision(item, {**ev, "cell": f_["cell"]["coord"] if f_["cell"] else None, "located_by": f_["how"], "label": f_["cell"]["label"] if f_["cell"] else None})
                d.reference = str(cents(f_["expected"]))
                if f_["cell"] is None:
                    d.violation("absent", f"no cell on the summary shows the {label} ({cents(f_['expected'])}) and no labelled candidate was found")
                else:
                    d.deliverable = str(cents(f_["cell"]["value"]))
                    if cents(f_["cell"]["value"]) != cents(f_["expected"]):
                        d.violation("wrong_value", f"{label}: {cents(f_['cell']['value'])} at {f_['cell']['coord']} != {cents(f_['expected'])}", cell=f_["cell"]["coord"])
                results[item] = d.result(f"{label} shown as {cents(f_['expected'])} (HALF_UP to cents)")
            d = Decision(11, {**ev, "cells": {k: found[k]["cell"]["coord"] if found[k]["cell"] else None for k in ("ytd_1250", "ytd_1251")}, "detail_totals": {k: str(v) if v is not None else None for k, v in ytd_detail.items()}})
            for acct, key in (("1250", "ytd_1250"), ("1251", "ytd_1251")):
                f_ = found[key]
                if f_["cell"] is None:
                    d.violation("absent", f"no YTD amortization figure for {acct} on the summary")
                    continue
                if ytd_detail[acct] is None:
                    d.unreliable("unknown", "detail_totals", f"no monthly amortization totals on the {acct} schedule to compare with")
                elif cents(f_["cell"]["value"]) != cents(ytd_detail[acct]):
                    d.violation("ytd_mismatch", f"{acct} YTD amortization {cents(f_['cell']['value'])} at {f_['cell']['coord']} != sum of the schedule's monthly totals {cents(ytd_detail[acct])}", cell=f_["cell"]["coord"])
            d.deliverable = {k: str(cents(found[k]["cell"]["value"])) if found[k]["cell"] else None for k in ("ytd_1250", "ytd_1251")}
            d.reference = {k: str(cents(v)) for k, v in ref_ytd.items()}
            results[11] = d.result("YTD amortization per account equals the sum of the schedule's Jan-Apr totals")
            d = Decision(7, {**ev, "cells": {k: (found[k]["cell"]["coord"], found[k]["cell"]["formula"]) if found[k]["cell"] else None for k in ("ytd_1250", "ytd_1251", "balance_1250", "balance_1251")}})
            for key, acct in (("ytd_1250", "1250"), ("balance_1250", "1250"), ("ytd_1251", "1251"), ("balance_1251", "1251")):
                f_ = found[key]
                target = located[acct]
                if f_["cell"] is None:
                    d.violation("absent", f"{key}: no figure on the summary to link")
                elif not f_["cell"]["formula"]:
                    d.violation("hard_coded", f"{key} at {f_['cell']['coord']} is a literal value, not a formula", cell=f_["cell"]["coord"])
                elif target and not references_sheet(f_["cell"]["formula"], target):
                    d.violation("not_linked_to_detail", f"{key} at {f_['cell']['coord']} is a formula that does not reference the {acct} sheet {target!r}: {f_['cell']['formula'][:80]}", cell=f_["cell"]["coord"])
            results[7] = d.result("YTD amortization and ending balances are formulas referencing the 1250 and 1251 sheets")
        # ---- formats (53): amount cells on the schedules carry a currency / two-decimal format; date cells a date format
        fmts, bad_fmt, date_bad = 0, [], []
        for acct, sch in schedules.items():
            if sch.get("status") != "ok":
                continue
            sheet = x["sheets"][sch["sheet"]]
            for ln in sch["lines"]:
                for mc in ln["months"].values():
                    for c in mc.values():
                        if numeric_cell(c)[0] == "ok":
                            nf = (sheet["cells"].get(c["coord"]) or {}).get("number_format") or "General"
                            fmts += 1
                            if not ("$" in nf or "#,##0.00" in nf or re.search(r"0\.00", nf)):
                                bad_fmt.append((c["coord"], nf))
            for coord, c in sheet["cells"].items():
                v = c.get("cached") if c.get("formula") else c.get("literal")
                if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", v):
                    nf = c.get("number_format") or "General"
                    if not re.search(r"[dmy]", nf, re.I) or nf == "General":
                        date_bad.append((coord, nf))
        d = Decision(53, {"amount_cells": fmts, "unformatted_examples": bad_fmt[:10], "date_cells_without_date_format": date_bad[:10]})
        if fmts and len(bad_fmt) > fmts * 0.1:
            d.violation("amounts_not_currency_formatted", f"{len(bad_fmt)} of {fmts} schedule amount cells lack a currency / two-decimal number format, e.g. {bad_fmt[:3]}")
        if date_bad:
            d.violation("dates_without_date_format", f"{len(date_bad)} date cell(s) without a date format, e.g. {date_bad[:3]}")
        if not fmts and schedules:
            d.unreliable("unknown", "formats", "no schedule amount cells located")
        results[53] = d.result("amounts carry a currency / two-decimal format and dates a date format")
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status,
            "schedules": {acct: {k: v for k, v in sch.items() if k in ("sheet", "status", "groups", "bottom", "match", "vendor_col")} | {"lines": len(sch.get("lines", []))} for acct, sch in schedules.items()},
            "summary": summary_info, "schedule_lines": {acct: sch.get("lines", []) for acct, sch in schedules.items()}}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        verdicts = [items[i]["verdict"] for i in spec["items"] if i in items]
        status = "fail" if "fail" in verdicts else "not_confirmed" if ("cannot_assess" in verdicts or spec.get("judge_items")) else "pass"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "judge_items": spec.get("judge_items", []), "status_from_deterministic": status,
                    "note": "judge items pending" if spec.get("judge_items") and status != "fail" else ""}
    return out
