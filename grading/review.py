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
import os
import sys

LABELS = ("pass", "fail", "cannot_tell")
LOCATION_KEYS = ("file", "files", "sheet", "sheets", "header_row", "header_rows", "column_mapping", "groups", "bottom_rows", "lines", "basis", "source", "cell", "coord",
                 "located_by", "label", "detail_sheet", "paragraphs", "slide", "slides", "shape", "table", "chart")
REFERENCE_SUMMARY = {
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
        if len(row) < 5 or not row[1].strip().isdigit():
            continue
        label = row[4].strip().lower().replace("cannot assess", "cannot_tell").replace("cannot_assess", "cannot_tell")
        out.append({"run_uuid": row[0], "item": int(row[1]), "weight": row[2], "label": label or None, "evidence": row[5] if len(row) > 5 else "", "judged_at": row[6] if len(row) > 6 else "", "reviewer": row[7] if len(row) > 7 else ""})
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
          "labelled_items": sorted(r["item"] for r in labelled), "counts": {k: sum(1 for r in labelled if r["label"] == k) for k in LABELS}, "rows": len(rows)}
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


def compare_labels(out_dir: str, run_uuid: str, grades: list[dict], checkpoint_path: str | None = None) -> dict:
    """Independent labels (from a saved checkpoint only) against the grader rows of one pass. Never modifies grades."""
    checkpoint_path = checkpoint_path or latest_checkpoint(out_dir, run_uuid)
    if not checkpoint_path or not os.path.isfile(checkpoint_path):
        raise RuntimeError(f"no saved label checkpoint for run {run_uuid}: labels must be saved (grading.review save-labels) before any automated verdict is compared or revealed")
    cp = json.load(open(checkpoint_path, encoding="utf-8"))
    if _sha(cp["copy"]) != cp["sha256"]:
        raise RuntimeError("the checkpointed label copy no longer matches its recorded SHA-256")
    labels = {r["item"]: r for r in read_labels(cp["copy"]) if r["label"]}
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
        host_dir = os.path.join(os.path.dirname(os.path.realpath(args.out_dir)), "runs", args.run_uuid)
        sel = authoritative_selection(cfg, host_dir, args.out_dir, args.run_uuid)
        if sel.get("blocked") or not sel.get("grades"):
            raise SystemExit(f"no authoritative pass to compare against: {sel.get('basis')}")
        grades = sel["grades"]
    else:
        with open(os.path.join(args.out_dir, "grades.jsonl"), encoding="utf-8") as f:
            grades = [json.loads(l) for l in f if l.strip()]
        grades = [g for g in grades if g.get("run_uuid") == args.run_uuid and g.get("grading_pass") == args.grading_pass]
    print(json.dumps({k: v for k, v in compare_labels(args.out_dir, args.run_uuid, grades, args.checkpoint).items() if k != "rows"}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
