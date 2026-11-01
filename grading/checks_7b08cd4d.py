"""Deterministic checks for 7b08cd4d-df60-41ae-9102-8aaa49306ba2 (tour profit and loss), following preregistration 2.6:
D items 1, 3, 6-24, 29-40, 49-58; J items 2, 4, 25-28, 41-48; V items 5, 59. Thin task specification on the shared
engine.

Reading. Every numeric cell of the workbook is read with its row label (the row's text cells left of it), its section
(the nearest label-only row above: Gross Revenue, Withholding, Expenses, a category, ...) and its column: the text of
the nearest header row above in that column gives a party (Tour Manager, Production Company, Total / Combined) and a
measure (gross, withholding, net, rate). Tour-stop rows are rows whose text names a stop city; the two Paris shows are
told apart by date or amount. Withholding by country comes from country rows of the withholding section, else from the
stop rows' withholding column summed by country. A category total is the row labelled as its total, else the category
row itself when it carries amounts, else the unlabelled amount row closing the category block.

Numbers (preregistration 2.6, APPROVED): a figure is compared with the recomputation after both are quantized half-up
to the precision the deliverable displays (whole dollars or cents; General shows cents for a non-integral value);
identities (16, 17, 56-58) on the deliverable's unrounded values (|difference| < 0.005). A-53: a net income one dollar
below the rounded figure passes when it is the deliverable's own difference of correctly rounded components. K1: a
failure of 32-34 or 38-40 whose Other Tour + Other Travel sum is right is tagged allocation ambiguity in the evidence.
A formula without a cached value is unreadable (cannot_assess).

Critical: C1 = 15-24; C2 = 49, 50, 51; C3 = 52-58."""
import re
from decimal import ROUND_HALF_UP, Decimal

from .engine.cells import cell_coord as _cell_coord
from .engine.decision import Decision, Result
from .engine.money import parse_money
from .engine.workbook import workbook_gate

TASK = "7b08cd4d-df60-41ae-9102-8aaa49306ba2"
VERSION = "7b08cd4d-2026-11-01.2"  # .2 (calibration on the dev output, 2026-11-01): cell-aware header rows; aggregate rows are no stops; revenue total row by measure
D_ITEMS = [1, 3] + list(range(6, 25)) + list(range(29, 41)) + list(range(49, 59))
J_ITEMS = [2, 4, 25, 26, 27, 28] + list(range(41, 49))
V_ITEMS = [5, 59]
CRITICAL = {"C1": {"items": list(range(15, 25)), "name": "Withholding and net revenue"}, "C2": {"items": [49, 50, 51], "name": "Expenses"},
            "C3": {"items": list(range(52, 59)), "name": "Net income"}}
COUNTRY_RX = {"UK": r"\buk\b|united\s*kingdom|england|britain|\bgb\b", "France": r"france|french", "Spain": r"spain|spanish", "Germany": r"germany|german"}
STOPS = [(1, "London", "UK", "2024-10-07"), (2, "Paris", "France", "2024-10-09"), (3, "Paris", "France", "2024-10-10"), (4, "Barcelona", "Spain", "2024-10-12"),
         (5, "Madrid", "Spain", "2024-10-14"), (6, "Munich", "Germany", "2024-10-16"), (7, "Berlin", "Germany", "2024-10-18")]
CATEGORIES = {"band": r"band|crew", "tour": r"other\s*tour", "hotel": r"hotel|restaurant", "travel": r"other\s*travel|\btravel\b"}
CAT_ITEMS = {"band": (29, 30, 31), "tour": (32, 33, 34), "hotel": (35, 36, 37), "travel": (38, 39, 40)}  # combined, TM, PC
PARTIES = ("total", "tm", "pc")


class _Unrecalc:
    def __repr__(self):
        return "<formula without a cached value>"


UNRECALC = _Unrecalc()


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace("\xa0", " ")).strip().lower()


def coord(r: int, c: int) -> str:
    return _cell_coord(r, c - 1)


def value(sh, r, c):
    x = sh["cells"].get(coord(r, c))
    if not x:
        return None
    if x.get("formula") and x.get("cached") is None:
        return UNRECALC
    return x.get("cached") if x.get("formula") else x.get("literal")


def as_number(v):
    if v is UNRECALC:
        return UNRECALC
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    return parse_money(v) if isinstance(v, str) else None


def is_text(v) -> bool:
    return isinstance(v, str) and bool(v.strip()) and parse_money(v) is None


def places(fmt: str, x: Decimal) -> int:
    """Displayed precision, whole dollars or cents: the format's decimals (capped at 2); General: cents unless integral."""
    f = (fmt or "General").split(";")[0]
    if f.lower() == "general":
        return 0 if x == x.to_integral_value() else 2
    m = re.search(r"0\.(0+)", f)
    return min(len(m.group(1)), 2) if m else 0


def q(x: Decimal, p: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-p), rounding=ROUND_HALF_UP)


def party_of(h: str) -> str | None:
    t = norm(h)
    if re.search(r"tour\s*manager|\btm\b", t):
        return "tm"
    if re.search(r"production|\bpc\b|prod\.?\s*co", t):
        return "pc"
    if re.search(r"\btotal\b|combined|\ball\b", t):
        return "total"
    return None


def measure_of(h: str) -> str | None:
    t = norm(h)
    if re.search(r"\brate\b|%", t):
        return "rate"
    if re.search(r"withh|\btax", t):
        return "withholding"
    if re.search(r"\bnet\b", t):
        return "net"
    if re.search(r"gross|revenue|income|amount|usd|\$", t):
        return "gross"
    return None


# ----------------------------------------------------------------------------- reading
def read_sheet(sh: dict) -> dict:
    rows = sh["rows"]
    header_rows = {}
    for r, row in enumerate(rows, 1):
        hs = {c: v for c, v in enumerate(row, 1) if is_text(v) and (party_of(v) or measure_of(v) or re.search(r"\bcity\b|\bcountry\b|\bdate\b", norm(v)))}
        nums = [c for c in range(1, len(row) + 1) if as_number(value(sh, r, c)) is not None]  # cell-aware: a formula without a cached value is content, not a header
        if len(hs) >= 2 and not nums:
            header_rows[r] = hs
    out_rows, section = [], None
    for r, row in enumerate(rows, 1):
        cells = {c: value(sh, r, c) for c in range(1, len(row) + 1)}
        nums = {c: as_number(v) for c, v in cells.items() if as_number(v) is not None}
        texts = {c: str(v).strip() for c, v in cells.items() if is_text(v)}
        if r in header_rows:
            continue
        if texts and not nums:
            section = " ".join(texts.values())
            out_rows.append({"r": r, "label": section, "texts": texts, "nums": {}, "section": section, "label_only": True})
            continue
        if not nums:
            continue
        first_num = min(nums)
        label = " ".join(t for c, t in sorted(texts.items()) if c < first_num)
        hr = max((h for h in header_rows if h < r), default=None)
        cols = {}
        for c, n in nums.items():
            h = header_rows.get(hr, {}).get(c, "") if hr else ""
            cols[c] = {"value": n, "coord": coord(r, c), "fmt": (sh["cells"].get(coord(r, c)) or {}).get("number_format") or "General", "header": h,
                       "party": party_of(h), "measure": measure_of(h)}
        out_rows.append({"r": r, "label": label, "texts": texts, "nums": cols, "section": section, "label_only": False, "header_row": hr})
    return {"rows": out_rows, "header_rows": header_rows}


def party_cells(row: dict, measure: str | None = None) -> dict:
    """{party: cell} for one row: the party columns (with the given measure, or without one / any when unspecified)."""
    out = {}
    for c, x in sorted(row["nums"].items()):
        if x["party"] and (measure is None and x["measure"] in (None, "gross") or x["measure"] == measure):
            out.setdefault(x["party"], x)
    if measure is None and not out:  # no party header: a single amount column is the combined figure
        un = [x for c, x in sorted(row["nums"].items()) if x["measure"] in (None, "gross")]
        if len(un) == 1:
            out["total"] = un[0]
    return out


def stop_rows(model: dict) -> dict:
    """{stop number: [rows]} for rows naming a stop city (outside expense sections)."""
    out = {}
    for row in model["rows"]:
        if row["label_only"] or re.search(r"hotel|restaurant|expens|cost", norm(row["section"] or "")):
            continue
        t = norm(" ".join(row["texts"].values()))
        cities = {c.lower() for _, c, _, _ in STOPS if re.search(rf"\b{c.lower()}\b", t)}
        if len(cities) >= 2 or re.search(r"\b\d+\s*shows?\b", t):
            continue  # an aggregate row (a country or multi-stop summary), not a tour stop
        for n, city, country, date in STOPS:
            if re.search(rf"\b{city.lower()}\b", t):
                if city == "Paris":
                    m = re.search(r"show\s*(\d)|#\s*(\d)", t)
                    num = int(m.group(1) or m.group(2)) if m else None
                    day = "10/09" in t or "10-09" in t or "oct 9" in t or "2024-10-09" in t
                    day2 = "10/10" in t or "10-10" in t or "oct 10" in t or "2024-10-10" in t
                    if num in (2, 3) and n != num:
                        continue
                    if num is None and ((day and n == 3) or (day2 and n == 2)):
                        continue
                out.setdefault(n, []).append(row)
    return out


def combined_gross(row: dict):
    pc = party_cells(row)
    if "total" in pc:
        return pc["total"]
    gross = [x for c, x in sorted(row["nums"].items()) if x["measure"] == "gross" and x["party"] in (None, "total")]
    if gross:
        return gross[0]
    return pc.get("tm")


def find_label_row(model: dict, rx: str, *, exclude: str | None = None, section_rx: str | None = None):
    for row in model["rows"]:
        if row["label_only"]:
            continue
        lb = norm(row["label"])
        if re.search(rx, lb) and not (exclude and re.search(exclude, lb)) and (not section_rx or re.search(section_rx, norm(row["section"] or ""))):
            return row
    return None


def section_block(model: dict, rx: str) -> list[dict]:
    """The rows from the first label-only row matching ``rx`` that heads a non-empty block, down to the next label-only row."""
    out, inside = [], False
    for row in model["rows"]:
        if row["label_only"]:
            if inside and out:
                break
            inside = bool(re.search(rx, norm(row["label"])))
            out = [] if inside else out
            continue
        if inside:
            out.append(row)
    return out


def category_total(model: dict, cat: str):
    rx = CATEGORIES[cat]
    row = find_label_row(model, rf"(total.*({rx}))|(({rx}).*total)", exclude=r"total\s*expens" if cat != "travel" else r"total\s*expens|total\s*tour")
    if row:
        return row, "labelled total row"
    row = next((r for r in model["rows"] if not r["label_only"] and re.fullmatch(rf".*({rx}).*", norm(r["label"])) and party_cells(r)
                and not re.search(r"\(|:", norm(r["label"])) or False), None)
    block = section_block(model, rx)
    if block:
        unl = [r for r in block if not norm(r["label"]) and party_cells(r)]
        if unl:
            return unl[-1], "unlabelled row closing the category block"
    if row and not block:
        return row, "category row with amounts"
    return None, "no category total"


# ----------------------------------------------------------------------------- comparisons
def _num(d: Decision, x, what: str):
    if x is None:
        d.violation("missing", f"no {what} shown")
        return None
    if x["value"] is UNRECALC:
        d.unreliable("grader_error", what, {"cell": x["coord"]})
        return None
    return x["value"]


def compare(d: Decision, x, ref, what: str, *, blank_is_zero=False):
    """Quantized comparison at the deliverable's displayed precision; registers the outcome on ``d``."""
    if x is None and blank_is_zero and ref == 0:
        return
    v = _num(d, x, what)
    if v is None:
        return
    p = places(x["fmt"], v)
    refd = Decimal(str(ref))
    d.deliverable, d.reference = str(v), str(q(refd, p))
    if q(v, p) != q(refd, p):
        d.violation("wrong_value", f"{what} {v} at {x['coord']} (shown {q(v, p)}) != {q(refd, p)}")


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
        best = None
        for sn in wb["sheet_order"]:
            m = read_sheet(wb["sheets"][sn])
            score = len(stop_rows(m)) + sum(1 for r in m["rows"] if re.search(r"net\s*income|total\s*expens", norm(r["label"])))
            if best is None or score > best[0]:
                best = (score, sn, m)
        _, sheet, model = best
        status["sheet"] = sheet
        status["header_rows"] = {r: {c: h for c, h in hs.items()} for r, hs in model["header_rows"].items()}
        check_pl(results, model, {"file": name, "sheet": sheet}, reference, status)
    for i in D_ITEMS:
        results.setdefault(i, Result(i, "cannot_assess", {"note": "no result produced"}, None, None, "extraction_failed: item not reached", "grader_extraction"))
    items = {i: results[i].as_dict() for i in D_ITEMS}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = ["workbook"]
        r["fail_on_own"] = {"missing": ["workbook"], "invalid": ["workbook"], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS}


def check_pl(results, model, ev0, reference, status):
    ref_stops = {i + 1: s for i, s in enumerate(reference["stops"])}
    rates = {k: Decimal(str(v)) for k, v in reference["rates"].items()}
    stops = stop_rows(model)
    status["stops"] = {n: [r["r"] for r in rs] for n, rs in stops.items()}
    # 3, 6: city and country for each stop, no duplicates
    d3, d6 = Decision(3, ev0), Decision(6, ev0)
    for n, city, country, _ in STOPS:
        rs = stops.get(n) or []
        if not rs:
            d3.violation("missing_stop", f"no revenue row for show {n} ({city})"); continue
        t = norm(" ".join(rs[0]["texts"].values()))
        if not re.search(COUNTRY_RX[country], t):
            d3.violation("no_country", f"show {n} ({city}) row {rs[0]['r']} names no country")
        if len(rs) > 1:
            d6.violation("duplicate", f"show {n} ({city}) appears in rows {[r['r'] for r in rs]}")
    stop_row_count = len({r["r"] for rs in stops.values() for r in rs})
    if stop_row_count > len(STOPS):
        d6.violation("extra_rows", f"{stop_row_count} stop rows for 7 shows")
    results[3] = d3.result("city and country for each tour stop")
    results[6] = d6.result("each tour stop exactly once")
    # 7-13: combined gross per stop; 14: no production-company revenue
    d14 = Decision(14, ev0)
    gross_cells = {}
    for n, city, country, _ in STOPS:
        d = Decision(6 + n, {**ev0, "show": n, "city": city})
        rs = stops.get(n) or []
        if not rs:
            d.violation("missing_stop", f"no row for show {n} ({city})")
        else:
            x = combined_gross(rs[0])
            gross_cells[n] = x
            compare(d, x, ref_stops[n]["gross"], f"show {n} combined gross")
            pc = party_cells(rs[0]).get("pc")
            if pc is not None:
                if pc["value"] is UNRECALC:
                    d14.unreliable("grader_error", f"show {n} PC", {"cell": pc["coord"]})
                elif pc["value"] != 0:
                    d14.violation("pc_revenue", f"show {n}: production company revenue {pc['value']} at {pc['coord']}")
        results[6 + n] = d.result(f"show {n} {city}: combined gross {ref_stops[n]['gross']:,.0f}")
    results[14] = d14.result("no revenue attributed to the production company")
    # per-stop withholding / net columns
    wh_cells = {n: next((x for c, x in sorted(rs[0]["nums"].items()) if x["measure"] == "withholding" and x["party"] in (None, "total")), None)
                or next((x for c, x in sorted(rs[0]["nums"].items()) if x["measure"] == "withholding"), None) for n, rs in stops.items() if rs}
    net_cells = {n: next((x for c, x in sorted(rs[0]["nums"].items()) if x["measure"] == "net" and x["party"] in (None, "total")), None)
                 or next((x for c, x in sorted(rs[0]["nums"].items()) if x["measure"] == "net"), None) for n, rs in stops.items() if rs}
    rate_cells = {n: next((x for c, x in sorted(rs[0]["nums"].items()) if x["measure"] == "rate"), None) for n, rs in stops.items() if rs}
    # withholding by country
    wsec = section_block(model, r"withh|\btax")
    country_rows = {}
    for row in wsec:
        lb = norm(row["label"])
        for k, rx in COUNTRY_RX.items():
            if re.search(rx, lb) and not any(re.search(rf"\b{c.lower()}\b", lb) for _, c, _, _ in STOPS):
                country_rows.setdefault(k, row)
    by_country = {}
    for k in COUNTRY_RX:
        if k in country_rows:
            by_country[k] = party_cells(country_rows[k]).get("total") or party_cells(country_rows[k]).get("tm")
    status["withholding_by_country"] = {k: (v["coord"] if v else None) for k, v in by_country.items()}
    # 15: rates applied as specified
    d15 = Decision(15, ev0)
    for n, city, country, _ in STOPS:
        rc = rate_cells.get(n)
        if rc is not None and rc["value"] is not UNRECALC:
            rv = rc["value"] / 100 if rc["value"] > 1 else rc["value"]
            if rv != rates[country]:
                d15.violation("wrong_rate", f"show {n} rate {rc['value']} != {rates[country]}")
    for k in COUNTRY_RX:
        gross_k = sum((Decimal(str(s["gross"])) for s in reference["stops"] if s["country"] == k), Decimal(0))
        exp = gross_k * rates[k]
        x = by_country.get(k)
        if x is not None:
            if x["value"] is UNRECALC:
                d15.unreliable("grader_error", f"{k} withholding", {"cell": x["coord"]})
            elif q(x["value"], places(x["fmt"], x["value"])) != q(exp, places(x["fmt"], x["value"])):
                d15.violation("rate_not_applied", f"{k} withholding {x['value']} != {rates[k]} x {gross_k} = {exp}")
        else:
            per = [wh_cells.get(n) for n, _, c, _ in STOPS if c == k]
            if not per or any(p is None for p in per):
                d15.violation("no_withholding", f"no withholding shown for {k}")
            for (n, _, c, _), p in zip([s for s in STOPS if s[2] == k], per):
                if p is None or p["value"] is UNRECALC or gross_cells.get(n) is None or gross_cells[n]["value"] is UNRECALC:
                    continue
                if abs(p["value"] - gross_cells[n]["value"] * rates[k]) >= Decimal("0.005") and q(p["value"], places(p["fmt"], p["value"])) != q(Decimal(str(ref_stops[n]["withholding"])), places(p["fmt"], p["value"])):
                    d15.violation("rate_not_applied", f"show {n} withholding {p['value']} != {rates[k]} x gross")
    results[15] = d15.result("withholding rates applied as specified")
    # 16, 17: per-stop identities on the deliverable's values
    for item, cells, what in ((16, wh_cells, "withholding"), (17, net_cells, "net revenue")):
        d = Decision(item, ev0)
        for n, city, country, _ in STOPS:
            x, g = cells.get(n), gross_cells.get(n)
            if x is None:
                d.violation("missing", f"show {n} ({city}): no per-stop {what} amount"); continue
            if x["value"] is UNRECALC or g is None or g["value"] is UNRECALC:
                d.unreliable("grader_error", f"show {n} {what}", {"cell": x["coord"]}); continue
            if item == 16:
                exp = g["value"] * rates[country]
            else:
                w = wh_cells.get(n)
                if w is None or w["value"] is UNRECALC:
                    d.unreliable("grader_error", f"show {n} withholding", None); continue
                exp = g["value"] - w["value"]
            if abs(x["value"] - exp) >= Decimal("0.005"):
                d.violation("identity", f"show {n} {what} {x['value']} != {exp}")
        results[item] = d.result(f"per-stop {what} identity")
    # 18-20: totals (a labelled total row; otherwise the revenue table's own 'Total' row, read by its measure columns)
    last_stop = max((r["r"] for rs in stops.values() for r in rs), default=0)
    tot_row = next((r for r in model["rows"] if r["r"] > last_stop and not r["label_only"] and re.match(r"(grand\s*)?totals?\b", norm(r["label"]))
                    and any(v["measure"] in ("gross", "withholding", "net") for v in r["nums"].values())), None)

    def from_total_row(meas):
        if tot_row is None:
            return None
        return next((v for c, v in sorted(tot_row["nums"].items()) if v["measure"] == meas), None)
    gt = find_label_row(model, r"total\s*gross|gross.*total", exclude=r"net")
    wt = find_label_row(model, r"total\s*(withh|tax)|(withh|tax).*total")
    if wt is None and wsec:
        unl = [r for r in wsec if not norm(r["label"]) and party_cells(r)]
        wt = unl[-1] if unl else None
    nt = find_label_row(model, r"net\s*(tour\s*)?revenue|net\s*income\s*from\s*shows|revenue.*net", exclude=r"withh")
    status["totals_rows"] = {"gross": gt and gt["r"], "withholding": wt and wt["r"], "net_revenue": nt and nt["r"]}
    for item, row, refv, what, meas in ((18, gt, reference["gross"], "total gross revenue", "gross"), (19, wt, reference["withholding"], "total withholding", "withholding"),
                                        (20, nt, reference["net_revenue"], "total net revenue", "net")):
        d = Decision(item, {**ev0, "row": row and row["r"]})
        x = None
        if row:
            pc = party_cells(row)
            x = pc.get("total") or next((v for c, v in sorted(row["nums"].items()) if v["measure"] == meas), None) or pc.get("tm")
        else:
            x = from_total_row(meas)
            d.evidence["row"] = tot_row and tot_row["r"]
        compare(d, x, refv, what)
        results[item] = d.result(f"{what} {refv:,.2f}")
    # 21-24: withholding by country
    for item, k in ((21, "UK"), (22, "France"), (23, "Spain"), (24, "Germany")):
        d = Decision(item, {**ev0, "country": k})
        x = by_country.get(k)
        if x is None:
            per = [wh_cells.get(n) for n, _, c, _ in STOPS if c == k]
            if per and all(p is not None for p in per):
                if any(p["value"] is UNRECALC for p in per):
                    d.unreliable("grader_error", f"{k} withholding", None)
                else:
                    total = sum((p["value"] for p in per), Decimal(0))
                    pl = places(per[0]["fmt"], total)
                    d.deliverable, d.reference = str(total), str(q(Decimal(str(reference["withholding_by_country"][k])), pl))
                    if q(total, pl) != q(Decimal(str(reference["withholding_by_country"][k])), pl):
                        d.violation("wrong_value", f"{k} withholding (sum of stops) {total} != {reference['withholding_by_country'][k]}")
            else:
                d.violation("missing", f"no withholding shown for {k}")
        else:
            compare(d, x, reference["withholding_by_country"][k], f"{k} withholding")
        results[item] = d.result(f"{k} withholding {reference['withholding_by_country'][k]:,.2f}")
    # 29-40: category totals
    cat_ref = {"band": (reference["tm_by_category"]["Band & Crew"] + reference["pc_by_category"]["Band & Crew (Fees & Per Diem)"], reference["tm_by_category"]["Band & Crew"],
                        reference["pc_by_category"]["Band & Crew (Fees & Per Diem)"]),
               "tour": (136836.5, 136836.5, 0), "hotel": (reference["tm_by_category"]["Hotel & Restaurants"] + reference["pc_by_category"]["Hotel & Restaurants"],
                                                          reference["tm_by_category"]["Hotel & Restaurants"], reference["pc_by_category"]["Hotel & Restaurants"]),
               "travel": (362711, 350056, 12655)}  # tour / travel: the rubric's split (K1, graded as written)
    status["categories"] = {}
    cat_rows = {}
    for cat, items in CAT_ITEMS.items():
        row, how = category_total(model, cat)
        cat_rows[cat] = row
        status["categories"][cat] = {"row": row and row["r"], "how": how}
        pcs = party_cells(row) if row else {}
        for item, party, refv in zip(items, PARTIES, cat_ref[cat]):
            d = Decision(item, {**ev0, "category": cat, "party": party, "row": row and row["r"], "how": how})
            if row is None:
                d.violation("missing", f"no {cat} category total")
            else:
                compare(d, pcs.get(party), refv, f"{cat} {party} total", blank_is_zero=True)
            results[item] = d.result(f"{cat} {party} total {refv:,.2f}")
    # K1 tag: Other Tour + Other Travel right in sum, split different
    for party, idx in (("total", 0), ("tm", 1), ("pc", 2)):
        a, b = (party_cells(cat_rows["tour"]) if cat_rows["tour"] else {}).get(party), (party_cells(cat_rows["travel"]) if cat_rows["travel"] else {}).get(party)
        if a and b and a["value"] is not UNRECALC and b["value"] is not UNRECALC:
            s = a["value"] + b["value"]
            if q(s, 0) == q(Decimal(str(cat_ref["tour"][idx] + cat_ref["travel"][idx])), 0):
                for item in (CAT_ITEMS["tour"][idx], CAT_ITEMS["travel"][idx]):
                    if results[item].verdict == "fail":
                        results[item].evidence["tag"] = "allocation ambiguity (task material): Other Tour + Other Travel equals the recomputation; the split differs (K1)"
    # 49-51: total expenses
    te = find_label_row(model, r"total\s*(expens|cost)", exclude=r"other|band|hotel|travel|tour\s*cost")
    tep = party_cells(te) if te else {}
    for item, party, refv in ((49, "total", reference["expenses_total"]), (50, "tm", reference["tm_total"]), (51, "pc", reference["pc_total"])):
        d = Decision(item, {**ev0, "row": te and te["r"]})
        if te is None:
            d.violation("missing", "no total expenses row")
        else:
            compare(d, tep.get(party), refv, f"total expenses {party}")
        results[item] = d.result(f"total expenses {party} {refv:,.2f}")
    # 52-58: net income
    ni = find_label_row(model, r"net\s*(income|profit|loss)|profit\s*/\s*loss|\bp\s*&\s*l\b")
    nip = party_cells(ni) if ni else {}
    d = Decision(52, {**ev0, "row": ni and ni["r"]})
    if ni is None:
        d.violation("missing", "no net income row")
    else:
        for party in PARTIES:
            if party not in nip:
                d.violation("missing_party", f"net income without a {party} value")
    results[52] = d.result("net income for tour manager, production company and combined")
    nrp = party_cells(nt) if nt else {}
    for item, party, refv, comp in ((53, "total", reference["net_income"], ("total",)), (54, "tm", reference["net_income_tm"], ("tm",)), (55, "pc", reference["net_income_pc"], ("pc",))):
        d = Decision(item, {**ev0, "row": ni and ni["r"]})
        x = nip.get(party)
        if ni is None:
            d.violation("missing", "no net income row")
        else:
            compare(d, x, refv, f"net income {party}")
            if d.violations and x is not None and x["value"] is not UNRECALC:  # A-53: the deliverable's own rounded difference of correctly rounded components
                nr, ex_ = nrp.get(party), tep.get(party)
                refs = {"total": (reference["net_revenue"], reference["expenses_total"]), "tm": (reference["net_revenue"], reference["tm_total"]), "pc": (0, reference["pc_total"])}[party]
                ok = False
                if nr is not None and ex_ is not None and nr["value"] is not UNRECALC and ex_["value"] is not UNRECALC:
                    p = places(x["fmt"], x["value"])
                    ok = (q(nr["value"], p) == q(Decimal(str(refs[0])), p) and q(ex_["value"], p) == q(Decimal(str(refs[1])), p)
                          and abs(x["value"] - (nr["value"] - ex_["value"])) < Decimal("0.005") and x["value"] == q(x["value"], p))
                elif party == "pc" and nr is None and ex_ is not None and ex_["value"] is not UNRECALC:
                    ok = abs(x["value"] + ex_["value"]) < Decimal("0.005")
                if ok:
                    d.violations.clear()
                    d.evidence["a53"] = "net income is the deliverable's own difference of correctly rounded components (A-53)"
        results[item] = d.result(f"net income {party} {refv:,.2f}")
    for item, party in ((56, "total"), (57, "tm"), (58, "pc")):
        d = Decision(item, {**ev0, "rows": [ni and ni["r"], nt and nt["r"], te and te["r"]]})
        x, nr, ex_ = nip.get(party), nrp.get(party), tep.get(party)
        if x is None:
            d.violation("missing", f"no {party} net income")
        elif ex_ is None:
            d.violation("missing", f"no {party} total expenses")
        elif nr is None and party != "pc":
            d.violation("missing", f"no {party} net revenue")
        elif any(v is not None and v["value"] is UNRECALC for v in (x, nr, ex_)):
            d.unreliable("grader_error", f"{party} net income identity", None)
        else:
            nrv = nr["value"] if nr is not None else Decimal(0)
            if abs(x["value"] - (nrv - ex_["value"])) >= Decimal("0.005"):
                d.violation("identity", f"{party} net income {x['value']} != net revenue {nrv} - expenses {ex_['value']}")
        results[item] = d.result(f"{party} net income = net revenue - expenses")


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        vs = [items[i]["verdict"] for i in spec["items"] if i in items]
        st = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "status_from_deterministic": st}
    return out
