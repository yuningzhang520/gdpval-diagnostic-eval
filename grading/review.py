"""Verdict-free human-review packets, saved-label checkpoints and the label/grader comparison.

Packet (written by every grading pass, never overwritten): for each rubric item the criterion and weight, where to
look in the deliverable (file, sheet, header rows, column map, located cells - locations only), the independent
source material a judge unit carries, and the deliverable excerpt; plus the task-level independent reference. No
grader verdict, judge verdict, suggested answer, diagnosis or wording that reveals an automated judgment appears in
the packet. The automated verdicts (deterministic and judge) of the pass go to a separate sealed file that is opened
only after the independent labels are saved. The labels CSV template is created once and never touched again.

Checkpoint: ``save_label_checkpoint`` copies the filled CSV, records its SHA-256, the timestamp, the labeller and the
label counts, and appends to an append-only checkpoint log. ``compare_labels`` refuses to run without a checkpoint
for the run and never modifies grades: it reports false PASS (human fail, grader pass), false FAIL (human pass,
grader fail), cannot-assess / coverage loss, and agreement with numerators and denominators, separately for
deterministic and judge items.

CLI: python -m grading.review save-labels --out-dir <grading out> --run-uuid <uuid> --csv <filled csv> --labeller '<name>'
     python -m grading.review compare --out-dir <grading out> --run-uuid <uuid> [--checkpoint <path>] [--grading-pass <id>]"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import os
import sys

LABELS = ("pass", "fail", "cannot_tell")
LOCATION_KEYS = ("file", "files", "sheet", "sheets", "header_row", "header_rows", "column_mapping", "groups", "bottom_rows", "lines", "basis", "source", "cell", "coord",
                 "located_by", "label", "detail_sheet", "paragraphs", "slide", "slides", "shape", "table", "chart")
def _ref_f841ddcf(ref: dict) -> str:
    j, sl, f = ref["june"], ref["slipped_rubric_rule"], ref["reference_figures_cents"]
    acc = lambda d: "; ".join(f"{k}: {v['n']} PO, order {v['order_cost']:,.2f}, shipped {v['shipped_cost']:,.3f}" for k, v in sorted(d["accounts"].items()))
    return (f"Independent recalculation from the input `PO Log.xlsx` ({ref['po_count']} POs, all Shipped, {ref['blank_actual']} blank actual ship dates). "
            f"June shipments (actual ship date 06/01-06/30/2025): {j['n']} POs {sorted(j['po_numbers'])}; order value at cost {f['june_order_value_at_cost']}, "
            f"shipped value at cost {f['june_shipped_value_at_cost']} (unrounded {j['total_shipped']}), short {f['june_short_shipped']}, % shipped {f['june_pct_shipped'] * 100:.4f} %; "
            f"per account: {acc(j)}. Slipped to July (start ship date >= 06/01/2025, cancel date <= 06/30/2025, shipped in July): {sl['n']} POs {sorted(sl['po_numbers'])}; "
            f"PO value at cost {f['slipped_po_value_at_cost']}, actual shipped value {f['slipped_actual_shipped_value']}; per account: {acc(sl)}.")


def _ref_47ef842d(ref: dict) -> str:
    rules = "; ".join(f"{k}: {v}" for k, v in ref["rules"].items())
    per = "; ".join(f"{u}: active stores {v['active_stores']}, current week inventory {v['current_inv_total']:,.0f}, daily sold (4 wk) {v['daily_sold_total']:.4f}, "
                    f"weekly rate {v['weekly_rate']:.4f}, WOS {v['wos']:.4f}, OOS stores {v['oos_count']}, % OOS {v['pct_oos'] * 100:.4f} %" for u, v in ref["per_upc"].items())
    return f"Independent recalculation from the input `Reference Inventory.xlsx` ({ref['rows']} rows). Rules: {rules}. Per UPC: {per}."


def _ref_c3525d4d(ref: dict) -> str:
    e, c = ref["email"], ref["comparison_original_vs_revised"]
    return (f"Independent recalculation from the inputs: production estimate base {e['base']}, side panel {e['side']} x 2, shelf strip {e['strip']} x 4 -> unit {ref['unit_cost_original']}; "
            f"revised strip +0.25 -> unit {ref['unit_cost_revised']}; overage {float(e['overage']) * 100:.0f} %, rounding: {ref['rounding_rule']}. "
            f"Original {ref['original_count']} stores -> {ref['original']['units_nearest_integer_adopted']} units, total {ref['original']['cost_adopted']}; "
            f"final {ref['final_count']} stores -> {ref['revised']['units_nearest_integer_adopted']} units, total {ref['revised']['cost_adopted']}; change {ref['delta_adopted']}. "
            f"Store lists compared after removing leading zeros: {c['normalised_common']} common, {len(c['added'])} added {c['added']}, removed {c['removed']}.")


def _ref_7b08cd4d(ref: dict) -> str:
    stops = "; ".join(f"{s['city']} ({s['country']}, {s['date']}): gross {s['gross']:,.0f}, rate {s['rate']}, withholding {s['withholding']:,.5f}, net {s['net']:,.5f}" for s in ref["stops"])
    wh = ", ".join(f"{k} {v:,.5f}" for k, v in ref["withholding_by_country"].items())
    return (f"Independent recalculation from the input `Fall Music Tour Ref File.xlsx`: stops {stops}. Gross {ref['gross']:,.2f}; withholding by country {wh}; total withholding "
            f"{ref['withholding']:,.5f}; net revenue {ref['net_revenue']:,.5f}. Expenses: tour manager {ref['tm_total']:,.2f} (by source category {ref['tm_by_category']}), production company "
            f"{ref['pc_total']:,.2f} (by source category {ref['pc_by_category']}), combined {ref['expenses_total']:,.2f}. Net income combined {ref['net_income']:,.5f}, tour manager "
            f"{ref['net_income_tm']:,.5f}, production company {ref['net_income_pc']:,.2f}.")


def _ref_b5d2e6f1(ref: dict) -> str:
    """Source sums only (the recalc file's gold comparisons are not used)."""
    h = ("WTD", "MTD", "YTD")
    brands = "; ".join(f"{name}: " + ", ".join(f"{p} qty {v[p + ' Qty']:,.0f}, sales ${v[p + ' $']:,.2f}, SOH {v[p + ' SOH']:,.0f}, ST% {v['ST%_ratio_of_sums'][p] * 100:.2f}%" for p in h)
                       for name, v in sorted(ref["by_brand"].items()))
    g = ref["grand_total"]
    return (f"Independent recalculation from the input `Weekly Sales Data.xlsx` ({ref['source_rows']} rows, {ref['stores']} stores, {ref['brands']} brands, {ref['pairs']} store-brand pairs). "
            f"ST% = Sales Quantity / Stock On Hand as a ratio of sums over the rows aggregated. By brand: {brands}. Grand total: "
            + ", ".join(f"{p} qty {g[p + ' Qty']:,.0f}, sales ${g[p + ' $']:,.2f}, SOH {g[p + ' SOH']:,.0f}" for p in h) + ".")


REFERENCE_SUMMARY = {
    "b5d2e6f1-62a2-433a-bcdd-95b260cdd860": _ref_b5d2e6f1,
    "f841ddcf-2a28-4f6d-bac3-61b607219d3e": _ref_f841ddcf,
    "47ef842d-8eac-4b90-bda8-dd934c228c96": _ref_47ef842d,
    "c3525d4d-2012-45df-853e-2d2a0e902991": _ref_c3525d4d,
    "7b08cd4d-df60-41ae-9102-8aaa49306ba2": _ref_7b08cd4d,
    "1137e2bb-bdf9-4876-b572-f29b7de5e595": lambda ref: (f"Independent recalculation from the input workbook: {ref['total_price_mismatch']} price-mismatch lines, {ref['total_case_pack']} case-pack lines, "
                                                         f"{ref['total_errors']} errors in total across {len(ref['lines'])} lines; per SKU " + ", ".join(f"{k}: {v['total']} ({v['price']} price, {v['case']} case)" for k, v in sorted(ref["by_sku"].items())) + "."),
    "7d7fc9a7-21a7-4b83-906f-416dea5ad04f": lambda ref: ("Independent recalculation: 41 services invoices (" + "; ".join(f"{i['vendor']} {i['invoice']} {i['date']} {i['amount_text']}" for i in ref["expense_invoices"]) + "). 25 insurance invoices ("
                                                         + "; ".join(f"{i['vendor']} {i['invoice']} {i['date']} {i['amount_text']}" for i in ref["insurance_invoices"]) + f"). GL balances from the prompt: 1250 {ref['gl_prompt']['1250']}, 1251 {ref['gl_prompt']['1251']}. "
                                                         f"YTD amortization 1250 {ref['ytd_amortization_1250_cents']}, 1251 {ref['ytd_amortization_1251_cents']}; total prepaid 4/30/2025 {ref['total_prepaid_2025_04_30']['path_ii_quantize_exact_sum_once']}."),
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d": lambda ref: (f"Independent recalculation from the source workbook: {ref['rows']} rows, {ref['total_hours']:.3f} hours; shares " + ", ".join(f"{k} {v:.2f}%" for k, v in sorted(ref["pct"].items()))
                                                         + "; margin " + ", ".join(f"{k} {v:.2f} h" for k, v in ref["margin"].items()) + "; time " + ", ".join(f"{k} {v:.2f} h" for k, v in ref["time"].items()) + "; strategic " + ", ".join(f"{k} {v:.2f} h" for k, v in ref["strategic"].items()) + "."),
}


def _versioned(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base}_v{n}{ext}"):
        n += 1
    return f"{base}_v{n}{ext}"


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _locations(evidence) -> dict:
    """Locations only: a whitelist of evidence keys; never violations, cell lists, notes or values."""
    if not isinstance(evidence, dict):
        return {}
    out = {}
    for k in LOCATION_KEYS:
        if k in evidence and evidence[k] not in (None, "", [], {}):
            v = evidence[k]
            out[k] = v if not isinstance(v, (dict, list)) else json.loads(json.dumps(v, default=str))[: 40] if isinstance(v, list) else {kk: vv for kk, vv in list(v.items())[:40]}
    return out


def write_review_materials(out_dir: str, run_uuid: str, rubric: list[dict], checks: dict, judge_units: list[dict], judge_verdicts: list[dict], extraction: dict,
                           reference: dict | None = None, task_id: str | None = None, grading_pass: str | None = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    items_md = _versioned(os.path.join(out_dir, f"review_{run_uuid}_items.md"))
    sealed_json = _versioned(os.path.join(out_dir, f"review_{run_uuid}_judge_verdicts.json"))
    template = os.path.join(out_dir, f"review_{run_uuid}_independent_judgments.csv")
    units_by_item = {u["item"]: u for u in judge_units}
    task_id = task_id or checks.get("task")
    ref_summary = REFERENCE_SUMMARY.get(task_id, lambda r: "")(reference) if reference is not None and task_id in REFERENCE_SUMMARY else ""
    with open(items_md, "x", encoding="utf-8") as f:
        f.write(f"# Review packet — run {run_uuid}\n\nDeliverables: " + ", ".join(i["path"] for i in extraction["inventory"]) + "\n\n")
        f.write("This packet carries no automated verdict. Write your independent judgment for each criterion in the CSV before any grader or judge output is revealed; "
                "label pass, fail or cannot_tell and name the evidence location (file, sheet, cell / page / slide / paragraph).\n\n")
        if ref_summary:
            f.write("## Independent reference (computed from the task's source materials, not from any deliverable)\n\n" + ref_summary + "\n\n")
        for i, r in enumerate(rubric, 1):
            f.write(f"## Item {i} (weight {r['score']})\n\n**Criterion:** {r['criterion']}\n\n")
            d = checks["items"].get(i)
            if d:
                loc = _locations(d.get("evidence"))
                if loc:
                    f.write(f"**Where to look:** {json.dumps(loc, default=str)[:800]}\n\n")
            u = units_by_item.get(i)
            if u:
                f.write("**Source material / independent reference:** " + u["source_material"][:1500] + "\n\n")
                f.write("**Deliverable excerpt:**\n\n```\n" + u["deliverable_excerpt"][:4000] + "\n```\n\n")
            if not d and not u:
                f.write("_No automated check and no judge unit for this item (visual or unassigned): review the rendered deliverable._\n\n")
    with open(sealed_json, "x", encoding="utf-8") as f:
        json.dump({"run_uuid": run_uuid, "grading_pass": grading_pass, "note": "SEALED: open only after the independent judgments are saved as a checkpoint (grading.review save-labels)",
                   "deterministic": {str(i): {k: d.get(k) for k in ("verdict", "note", "attribution", "deliverable_value", "reference_value")} for i, d in checks["items"].items()},
                   "verdicts": judge_verdicts}, f, indent=1, default=str)
    preserved = os.path.exists(template)
    if not preserved:
        with open(template, "x", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["run_uuid", "item", "weight", "criterion", "independent_judgment (pass/fail/cannot_tell)", "evidence (file, location)", "judged_at_utc", "reviewer"])
            for i, r in enumerate(rubric, 1):
                w.writerow([run_uuid, i, r["score"], r["criterion"], "", "", "", ""])
    return {"items": items_md, "judge_verdicts": sealed_json, "independent_template": template, "independent_template_preserved": preserved,
            "independent_template_sha256": _sha(template)}


def read_labels(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    out = []
    for row in rows[1:]:
        key = row[1].strip() if len(row) > 1 else ""
        if len(row) < 5 or not (key.isdigit() or re.fullmatch(r"C\d+", key)):  # an item number, or a critical criterion id (criterion-level label, policy v2)
            continue
        label = row[4].strip().lower().replace("cannot assess", "cannot_tell").replace("cannot_assess", "cannot_tell")
        out.append({"run_uuid": row[0], "item": int(key) if key.isdigit() else key, "weight": row[2], "label": label or None, "evidence": row[5] if len(row) > 5 else "", "judged_at": row[6] if len(row) > 6 else "", "reviewer": row[7] if len(row) > 7 else ""})
    return out


def save_label_checkpoint(out_dir: str, run_uuid: str, csv_path: str, labeller: str) -> dict:
    """Checkpoint the filled labels: a copy under labels/<run>/, SHA-256, timestamp, counts; append-only log. Fails on an
    unknown label value or a row of another run; blank labels are allowed (unlabelled items are reported as such)."""
    rows = read_labels(csv_path)
    bad = [r for r in rows if r["label"] not in (None,) + LABELS]
    if bad:
        raise ValueError(f"unknown label value(s): {[(r['item'], r['label']) for r in bad][:5]}; allowed: {LABELS}")
    foreign = [r for r in rows if r["run_uuid"] != run_uuid]
    if foreign:
        raise ValueError(f"{len(foreign)} row(s) belong to another run ({foreign[0]['run_uuid']!r})")
    labelled = [r for r in rows if r["label"]]
    if not labelled:
        raise ValueError("no labelled rows: nothing to checkpoint")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ldir = os.path.join(out_dir, "labels", run_uuid)
    os.makedirs(ldir, exist_ok=True)
    copy = os.path.join(ldir, f"labels_{stamp}.csv")
    with open(csv_path, "rb") as src, open(copy, "xb") as dst:
        dst.write(src.read())
    cp = {"run_uuid": run_uuid, "saved_at": _now(), "labeller": labeller, "source_csv": os.path.realpath(csv_path), "copy": copy, "sha256": _sha(copy),
          "labelled_items": sorted((r["item"] for r in labelled), key=lambda x: (isinstance(x, str), str(x).zfill(4))), "counts": {k: sum(1 for r in labelled if r["label"] == k) for k in LABELS}, "rows": len(rows)}
    path = os.path.join(ldir, f"checkpoint_{stamp}.json")
    with open(path, "x", encoding="utf-8") as f:
        json.dump(cp, f, indent=1)
    with open(os.path.join(out_dir, "labels", "checkpoints.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({**cp, "checkpoint": path}) + "\n")
    return {**cp, "checkpoint": path}


def latest_checkpoint(out_dir: str, run_uuid: str) -> str | None:
    ldir = os.path.join(out_dir, "labels", run_uuid)
    if not os.path.isdir(ldir):
        return None
    cps = sorted(f for f in os.listdir(ldir) if f.startswith("checkpoint_") and f.endswith(".json"))
    return os.path.join(ldir, cps[-1]) if cps else None


def compare_criteria(criterion_labels: dict, item_labels: dict, critical_status: dict, sensitivity: dict) -> dict:
    """Criterion-level agreement (policy v2): the human's criterion label against the pass's critical status (revised /
    current definition), reported apart from item-level agreement. ``sensitivity`` maps a criterion id to its
    preregistered-definition status and the differing items; the human status under the preregistered definition is
    derived from the criterion label and the differing items' labels (fail if any fails, pass if all pass)."""
    rows = []
    for cid in sorted(set(criterion_labels) | set(critical_status), key=lambda c: int(str(c)[1:]) if str(c)[1:].isdigit() else 0):
        h = (criterion_labels.get(cid) or {}).get("label")
        g = critical_status.get(cid)
        cls = None if h is None or g is None else ("agree" if h == g else "human_cannot" if h == "cannot_tell" else "grader_not_confirmed" if g not in ("pass", "fail") else "disagree")
        row = {"criterion": cid, "human": h, "grader": g, "class": cls}
        if cid in sensitivity:
            parts = [h] + [(item_labels.get(i) or {}).get("label") for i in sensitivity[cid]["differing_items"]]
            hp = "fail" if "fail" in parts else "pass" if parts and all(p == "pass" for p in parts) else "cannot_tell"
            gp = sensitivity[cid]["preregistered_status"]
            row["preregistered"] = {"human_derived": hp, "grader": gp, "class": "agree" if hp == gp else "human_cannot" if hp == "cannot_tell" else "grader_not_confirmed" if gp not in ("pass", "fail") else "disagree"}
        rows.append(row)
    decided = [r for r in rows if r["class"] in ("agree", "disagree")]
    return {"rows": rows, "agreement": f"{sum(1 for r in decided if r['class'] == 'agree')}/{len(decided)}", "unlabelled": sorted(c for c in critical_status if c not in criterion_labels)}


def compare_labels(out_dir: str, run_uuid: str, grades: list[dict], checkpoint_path: str | None = None, queue_items: list[int] | None = None,
                   critical_status: dict | None = None, sensitivity: dict | None = None) -> dict:
    """Independent labels (from a saved checkpoint only) against the grader rows of one pass. Never modifies grades.
    With ``queue_items`` (the frozen review queue, approved 2026-11-01) only queued items enter the agreement sample;
    queued items without a label are reported, labels outside the queue are ignored and counted."""
    checkpoint_path = checkpoint_path or latest_checkpoint(out_dir, run_uuid)
    if not checkpoint_path or not os.path.isfile(checkpoint_path):
        raise RuntimeError(f"no saved label checkpoint for run {run_uuid}: labels must be saved (grading.review save-labels) before any automated verdict is compared or revealed")
    cp = json.load(open(checkpoint_path, encoding="utf-8"))
    if _sha(cp["copy"]) != cp["sha256"]:
        raise RuntimeError("the checkpointed label copy no longer matches its recorded SHA-256")
    all_labels = {r["item"]: r for r in read_labels(cp["copy"]) if r["label"]}
    criterion_labels = {k: v for k, v in all_labels.items() if isinstance(k, str)}
    labels = {k: v for k, v in all_labels.items() if not isinstance(k, str)}
    outside = []
    if queue_items is not None:
        outside = sorted(i for i in labels if i not in set(queue_items))
        labels = {i: r for i, r in labels.items() if i in set(queue_items)}
    by_item = {g["item"]: g for g in grades}
    rows, agg = [], {"D": {"n": 0, "agree": 0, "false_pass": 0, "false_fail": 0, "grader_cannot": 0, "human_cannot": 0}, "J": {"n": 0, "agree": 0, "false_pass": 0, "false_fail": 0, "grader_cannot": 0, "human_cannot": 0}, "V": {"n": 0, "agree": 0, "false_pass": 0, "false_fail": 0, "grader_cannot": 0, "human_cannot": 0}}
    for item, lab in sorted(labels.items()):
        g = by_item.get(item)
        verdict = g["verdict"] if g else None
        src = (g or {}).get("source", "?")
        cls = ("false_pass" if lab["label"] == "fail" and verdict == "pass" else "false_fail" if lab["label"] == "pass" and verdict == "fail" else
               "agree" if lab["label"] == verdict else "human_cannot" if lab["label"] == "cannot_tell" else "grader_cannot" if verdict not in ("pass", "fail") else "disagree")
        rows.append({"item": item, "source": src, "weight": (g or {}).get("weight"), "human": lab["label"], "grader": verdict, "class": cls, "human_evidence": lab["evidence"]})
        a = agg.setdefault(src, {"n": 0, "agree": 0, "false_pass": 0, "false_fail": 0, "grader_cannot": 0, "human_cannot": 0})
        a["n"] += 1
        if cls in a:
            a[cls] += 1
    for a in agg.values():
        decided = a["n"] - a["grader_cannot"] - a["human_cannot"]
        a["agreement"] = f"{a['agree']}/{decided}" if decided else "0/0"
        a["agreement_rate"] = (a["agree"] / decided) if decided else None
        a["coverage_loss"] = a["grader_cannot"]
    out = {"run_uuid": run_uuid, "checkpoint": checkpoint_path, "checkpoint_sha256": cp["sha256"], "compared_at": _now(), "grading_pass": (grades[0].get("grading_pass") if grades else None),
           "labelled_items": len(labels), "rows": rows, "summary": agg,
           **({"queue_items": sorted(queue_items), "queue_unlabelled": sorted(set(queue_items) - set(labels)), "labels_outside_queue_ignored": outside} if queue_items is not None else {}),
           **({"criteria": compare_criteria(criterion_labels, labels, critical_status or {}, sensitivity or {})} if criterion_labels or critical_status else {}),
           "false_pass_items": [r["item"] for r in rows if r["class"] == "false_pass"], "false_fail_items": [r["item"] for r in rows if r["class"] == "false_fail"]}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(out_dir, "labels", run_uuid, f"comparison_{stamp}.json")
    with open(path, "x", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    out["path"] = path
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="verdict-free review packets: label checkpoints and comparison")
    p.add_argument("command", choices=("save-labels", "compare"))
    p.add_argument("--out-dir", required=True)
    p.add_argument("--run-uuid", required=True)
    p.add_argument("--csv", default=None)
    p.add_argument("--labeller", default=None)
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--grading-pass", default=None, help="compare against this pass (default: the authoritative selection)")
    p.add_argument("--queue", default=None, help="frozen review queue: the agreement sample is the run task's queued items")
    p.add_argument("--phase", default="dev", choices=("dev", "validation", "formal"), help="phase plan of a v2 queue")
    args = p.parse_args(argv)
    if args.command == "save-labels":
        if not (args.csv and args.labeller):
            raise SystemExit("save-labels needs --csv and --labeller")
        print(json.dumps(save_label_checkpoint(args.out_dir, args.run_uuid, args.csv, args.labeller), indent=1))
        return 0
    from .grade import grading_passes
    passes = grading_passes(args.out_dir, args.run_uuid)
    chosen = next((x for x in passes if x.get("grading_pass") == args.grading_pass), None) if args.grading_pass else None
    if chosen is None:
        from .run_grading import authoritative_selection
        import json as _j
        cfg = _j.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"), encoding="utf-8"))
        # the grading-run records name the run's host directory; the layout guesses (a per-run out dir or the phase's
        # grading root, beside 'runs') are fallbacks
        import glob as _glob
        recs = [_j.load(open(f, encoding="utf-8")) for f in sorted(_glob.glob(os.path.join(args.out_dir, f"grading_run_{args.run_uuid}_*.json")))]
        root = os.path.realpath(args.out_dir)
        guesses = [os.path.join(os.path.dirname(os.path.dirname(root)), "runs", args.run_uuid), os.path.join(os.path.dirname(root), "runs", args.run_uuid)]
        host_dir = next((r_.get("host_dir") for r_ in reversed(recs) if r_.get("host_dir")), None) or next((g for g in guesses if os.path.isdir(g)), guesses[-1])
        sel = authoritative_selection(cfg, host_dir, args.out_dir, args.run_uuid)
        if sel.get("blocked") or not sel.get("grades"):
            raise SystemExit(f"no authoritative pass to compare against: {sel.get('basis')}")
        grades = sel["grades"]
    else:
        with open(os.path.join(args.out_dir, "grades.jsonl"), encoding="utf-8") as f:
            grades = [json.loads(l) for l in f if l.strip()]
        grades = [g for g in grades if g.get("run_uuid") == args.run_uuid and g.get("grading_pass") == args.grading_pass]
    queue_items, critical_status, sensitivity = None, None, None
    if args.queue:
        q = json.load(open(args.queue, encoding="utf-8"))
        task = (grades[0] or {}).get("task_id") if grades else None
        if "plans" in q:  # policy v2: phase plan with criterion-level labels
            plan = (q["plans"].get(task) or {}).get("phases", {}).get(args.phase)
            if plan is None:
                raise SystemExit(f"task {task!r} has no {args.phase} plan in {args.queue}")
            queue_items = [x["item"] for x in plan["items"]]
            gp = grades[0].get("grading_pass") if grades else None
            prec = next((x for x in passes if x.get("grading_pass") == gp), {})
            sc = prec.get("score") or {}
            critical_status = {c: (sc.get("critical") or {}).get(c, {}).get("status") for c in plan["criteria"]}
            pre = sc.get("critical_preregistered") or {}
            members = {c["id"]: c for c in q["plans"][task]["criteria"]}
            sensitivity = {c: {"preregistered_status": pre.get(c, {}).get("status"), "differing_items": sorted(set(members[c]["members"]) ^ set(members[c]["preregistered_members"]))}
                           for c in plan["criteria"] if "preregistered_members" in members.get(c, {})}
        else:
            if task not in q["queues"]:
                raise SystemExit(f"task {task!r} has no frozen queue in {args.queue}")
            queue_items = [x["item"] for x in q["queues"][task]["items"]]
    print(json.dumps({k: v for k, v in compare_labels(args.out_dir, args.run_uuid, grades, args.checkpoint, queue_items=queue_items, critical_status=critical_status,
                                                      sensitivity=sensitivity).items() if k != "rows"}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
