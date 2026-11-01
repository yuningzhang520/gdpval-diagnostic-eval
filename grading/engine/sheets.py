"""Shared sheet helpers (engine): sheet selection by name or content, label rows, row text, and month-column detection
for schedules laid out by period (one group of columns per month, or one column per month and measure). Introduced for
7d7fc9a7 (2026-11-01)."""
import re

from .cells import norm_text, read_cell

MONTH_TOKENS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
                "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}
_NUMERIC_MONTH = re.compile(r"^(?:(\d{1,2})[/-](?:20)?\d{2}|(?:20)?\d{2}-(\d{1,2}))$")


def month_of(text) -> int | None:
    """Month number named by a header cell: 'Jan', 'January 2025', 'Jan-25', '1/2025', '2025-01', a datetime (its month); None otherwise."""
    if text is None:
        return None
    if hasattr(text, "month") and hasattr(text, "year"):
        return int(text.month)
    s = norm_text(text)
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):  # isoformat date text from extraction
        return int(s[5:7])
    m = _NUMERIC_MONTH.match(s.replace(" ", ""))
    if m:
        return int(m.group(1) or m.group(2))
    for tok in re.split(r"[\s\-_/.,']+", s):
        if tok in MONTH_TOKENS:
            return MONTH_TOKENS[tok]
    return None


def sheet_names(x: dict) -> list[str]:
    return list(x.get("sheet_order") or x["sheets"].keys())


def find_sheets(x: dict, name_predicate) -> list[str]:
    return [n for n in sheet_names(x) if name_predicate(norm_text(n))]


def row_cells(sheet: dict, r: int) -> list[dict]:
    """Every cell of Excel row r (1-based) through read_cell, left to right."""
    width = len(sheet["rows"][r - 1]) if r - 1 < len(sheet["rows"]) else 0
    return [read_cell(sheet, r, c) for c in range(width)]


def row_text(sheet: dict, r: int, max_cols: int | None = None) -> str:
    cells = row_cells(sheet, r)[: max_cols or None]
    return " | ".join(str(c["value"]) for c in cells if c["status"] == "ok" and c["value"] not in (None, ""))


def first_text(sheet: dict, r: int, max_cols: int = 4) -> str | None:
    """The first textual cell of a row (its label), within the first ``max_cols`` columns."""
    for c in row_cells(sheet, r)[:max_cols]:
        if c["status"] == "ok" and isinstance(c["value"], str) and c["value"].strip():
            return c["value"].strip()
    return None


def find_label_rows(sheet: dict, pattern: str, *, start: int = 1, end: int | None = None, max_cols: int = 4) -> list[int]:
    """Excel rows whose label (first text within max_cols) matches the regex (case-insensitive)."""
    rx = re.compile(pattern, re.I)
    end = end or len(sheet["rows"])
    out = []
    for r in range(start, end + 1):
        lab = first_text(sheet, r, max_cols)
        if lab and rx.search(lab):
            out.append(r)
    return out


def text_in_rows(sheet: dict, pattern: str, *, rows: int = 10) -> list[str]:
    """Cells (coordinates) in the first ``rows`` rows whose text matches the regex."""
    rx = re.compile(pattern, re.I)
    hits = []
    for r in range(1, min(rows, len(sheet["rows"])) + 1):
        for c in row_cells(sheet, r):
            if c["status"] == "ok" and c["value"] is not None and rx.search(str(c["value"])):
                hits.append(c["coord"])
    return hits
