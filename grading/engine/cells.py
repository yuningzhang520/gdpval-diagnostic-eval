"""Shared cell reading and classification (engine). Moved verbatim from the 1137e2bb grader on 2026-11-01 when
the second task (7d7fc9a7) needed the same reading interface; behaviour unchanged (the 1137 gold catalog is the
regression net). Every cell is read through ``read_value`` and classified by ``numeric_cell``; the status vocabulary
is: ok / empty / formula_unrecalculated / error_value / non_numeric / non_finite (and non_binary for flags)."""
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..extract import ERROR_PREFIXES

INVALID_KINDS = ("error_value", "empty", "non_numeric", "non_finite", "non_binary")
UNRELIABLE_KINDS = ("formula_unrecalculated",)


def norm_text(s) -> str:
    t = re.sub(r"\s+", " ", str(s or "")).strip().lower()
    return t.rstrip(":?").strip()


def num_value(v):
    """Finite number or None: NaN, Infinity, booleans and strings that are not numbers are not values."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v.strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def qty(v) -> str | None:
    """Exact decimal normalisation of a quantity (no truncation): 60 -> '60', 60.5 -> '60.5', '60.0' -> '60'."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return format(d.normalize(), "f")


def q2(x) -> Decimal | None:
    try:
        d = Decimal(str(x))
        if not d.is_finite():
            return None
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def numeric_cell(cell: dict) -> tuple[str, object]:
    """A cell read through read_value, required to hold a finite number: ok (value) / empty /
    formula_unrecalculated / error_value / non_numeric / non_finite."""
    st, v = cell["status"], cell["value"]
    if st != "ok":
        return st, v
    if isinstance(v, bool):
        return "non_numeric", v
    try:
        f = float(v.strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return "non_numeric", v
    if not math.isfinite(f):
        return "non_finite", v
    return "ok", f


def describe_cell(kind: str, value) -> str:
    return {"empty": "blank", "error_value": f"an Excel error value {value!r}", "non_numeric": f"not a number ({value!r})", "non_finite": f"not a finite number ({value!r})",
            "non_binary": f"not a 0/1 flag ({value!r})", "formula_unrecalculated": "a formula without a cached value (not recalculated)"}.get(kind, kind)


def cell_coord(excel_row: int, col_index: int) -> str:
    import openpyxl.utils.cell as oc
    return f"{oc.get_column_letter(col_index + 1)}{excel_row}"


def read_value(sheet: dict, excel_row: int, col: int) -> tuple[str, object]:
    """The one cell-reading interface: (status, value) with status ok / empty / formula_unrecalculated
    (a formula without a cached value: recalculation failed or did not run) / error_value (an Excel
    error value, literal or produced by a recalculated formula: kept apart from the unrecalculated case)."""
    coord = cell_coord(excel_row, col)
    c = sheet["cells"].get(coord)
    if c is None:
        return "empty", None
    if c.get("formula") and c.get("cached") is None:
        return "formula_unrecalculated", None
    v = c.get("cached") if c.get("formula") else c.get("literal")
    if isinstance(v, str) and v.strip().upper().startswith(ERROR_PREFIXES):
        return "error_value", v
    return "ok", v


def read_cell(sheet: dict, excel_row: int, col: int) -> dict:
    st, v = read_value(sheet, excel_row, col)
    return {"status": st, "value": v, "coord": cell_coord(excel_row, col)}
