"""Human-review materials. For every criterion the reviewer first sees the deliverable excerpt and
the criterion (plus the deterministic result where one exists); judge verdicts go to a separate
file that is opened only after the independent judgment has been written down. The independent
judgment record (criterion id, judgment, evidence, time) is a CSV template. Model identity is not
shown; the run is identified by its execution uuid.

Nothing here overwrites an existing record: the items file and the judge-verdict file are written
as new versions (``_v2``, ``_v3``, …) when a previous version exists, and an existing independent
judgments CSV is left untouched (a reviewer may already have filled it in)."""
import csv
import hashlib
import json
import os


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


def write_review_materials(out_dir: str, run_uuid: str, rubric: list[dict], checks: dict, judge_units: list[dict], judge_verdicts: list[dict], extraction: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    items_md = _versioned(os.path.join(out_dir, f"review_{run_uuid}_items.md"))
    judge_json = _versioned(os.path.join(out_dir, f"review_{run_uuid}_judge_verdicts.json"))
    template = os.path.join(out_dir, f"review_{run_uuid}_independent_judgments.csv")
    units_by_item = {u["item"]: u for u in judge_units}
    with open(items_md, "x", encoding="utf-8") as f:
        f.write(f"# Review materials — run {run_uuid}\n\nDeliverables: " + ", ".join(i["path"] for i in extraction["inventory"]) + "\n\n")
        f.write("Write your independent judgment for each criterion in the CSV before opening the judge file.\n\n")
        for i, r in enumerate(rubric, 1):
            f.write(f"## Item {i} (weight {r['score']})\n\n**Criterion:** {r['criterion']}\n\n")
            d = checks["items"].get(i)
            if d:
                f.write(f"**Deterministic check:** {d['verdict']} — compared deliverable `{d['deliverable_value']}` with reference `{d['reference_value']}`; evidence {json.dumps(d['evidence'], default=str)[:400]}; {d['note']}\n\n")
            u = units_by_item.get(i)
            if u:
                f.write("**Source material / reference:** " + u["source_material"][:1500] + "\n\n")
                f.write("**Deliverable excerpt:**\n\n```\n" + u["deliverable_excerpt"][:4000] + "\n```\n\n")
            if not d and not u:
                f.write("_No deterministic result and no judge unit for this item (visual or unassigned)._\n\n")
    with open(judge_json, "x", encoding="utf-8") as f:
        json.dump({"run_uuid": run_uuid, "note": "open only after the independent judgments are recorded", "verdicts": judge_verdicts}, f, indent=1)
    preserved = os.path.exists(template)
    if not preserved:
        with open(template, "x", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["run_uuid", "item", "weight", "criterion", "independent_judgment (pass/fail/cannot_assess)", "evidence (file, location)", "judged_at_utc", "reviewer"])
            for i, r in enumerate(rubric, 1):
                w.writerow([run_uuid, i, r["score"], r["criterion"], "", "", "", ""])
    return {"items": items_md, "judge_verdicts": judge_json, "independent_template": template, "independent_template_preserved": preserved,
            "independent_template_sha256": _sha(template)}
