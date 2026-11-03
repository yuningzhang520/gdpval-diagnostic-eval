"""Build the submission page (site/index.html) from the canonical sources, site v5.

The page implements the approved preview of the author's spec v5 (sections: findings, results, failures, data
opportunity, method and limits). Every displayed number is read from its canonical source at build time, written to
site/data/metrics.json with a descriptive provenance and verification status, and rendered from there; nothing numeric
is typed into the page. Reader copy comes from site/content.json ({{token}} placeholders filled from the metrics) and is
gated by block status ('approved' or 'draft'). The default build is a DRAFT with a visible banner. `--final` refuses
while any block is not approved or any check below fails. `--preview PATH` writes a banner-free rendering to PATH
outside site/ for local review; it never touches index.html or metrics.json.

Checks that refuse the final build (warnings): a taxonomy item without a confirmed adjudication record; a display
category grouping that does not cover every failure type exactly once; a not-re-graded review item outside a critical
requirement that already fails on a confirmed item; a failing task cell without a label, or a label whose failure
types differ from the confirmed items in the failing critical requirements; rubric-item totals that disagree between
the item bundle and the critical-requirement membership; a card item that is not in its failure type; formal run
settings that differ between the frozen config and the Inspect logs; the crops' metadata disagreeing with the
deliverables; the judge verdicts still provisional; a forbidden term on the page (report-only terms and the retired
names of the page vocabulary); requirement-source tags that do not cover exactly the confirmed items, whose prompt
quotes are not verbatim in the task prompt, or that the author has not approved; card C's grader record, quotes or
term counts moving; the expert-file audit values not recomputing from the input; a review count flow that does not
reconcile.

Chart (inline SVG, CSS tokens only, labelled values, role="img" with an aria-label stating the values): critical
requirements per model, before and after author review (Results), with a wide and a narrow variant; below 52rem the
narrow one is shown. The author-review result of the hand-reviewed rubric items is a sentence plus its count flow
(Method). The task-verdict grid (with each failed task's failure source) and the category table are HTML tables with
text labels; cards A-C carry crops rendered by site/render_crops.py.

Inputs are read from the repository and from the local run store (not in the repository); metrics.json names the
latter descriptively and carries no path outside the repository.

Usage: .venv/bin/python site/build.py [--final] [--preview PATH]"""
import collections
import csv
import datetime as dt
import glob
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "site")
B = os.path.expanduser("~/turing-eval-runs")
CAND = {"anthropic/claude-opus-5-5": "opus", "openai/gpt-6.1-sol": "gpt"}
MODEL_OF = {v: k for k, v in CAND.items()}
NAME = {"opus": "Claude Opus 5.5", "gpt": "GPT-6.1-sol"}
SHORT = {"opus": "Opus 5.5", "gpt": "GPT-6.1-sol"}
TASK_NAME = {"b5d2e6f1": "Weekly sales analysis", "f841ddcf": "June shipment recap", "47ef842d": "Weeks of supply", "1137e2bb": "PO entry audit",
             "c3525d4d": "Holiday floor-stand budget", "7b08cd4d": "Tour profit and loss", "7d7fc9a7": "Prepaid amortization", "2ea2e5b5": "Work-time study deck",
             "c357f0e2": "UAT test plan", "a45bc83b": "GCP migration design"}
CONFIRMED = ("confirmed_fail", "verified_fail", "grader_false_pass")
STATUS_WORD = {"pass": "pass", "fail": "fail", "not_confirmed": "undecided"}
SEV_ORDER = {"high": 3, "medium": 2, "low": 1}
WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
NUM_WORDS = {v: k for k, v in WORDS.items()}
SALES_TASK = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"
SALES_FILES = {"opus": "Weekly Sales Data - Beauty Sales Analysis.xlsx", "gpt": "Weekly Sales Analysis.xlsx"}
SECTIONS = ("findings", "results", "failures", "data", "method")
FORBIDDEN = ("R-2.7-21", "as graded", "adjudicated", "unresolved", "re-checked", "criteria", "code check",
             # one name per concept on the page (vocabulary of the 2026-11-03 clarity round)
             "not confirmed", "grader couldn't read", "added rule", "requirement source", "prompt-stated", "stated in the prompt",
             # internal process terms
             "deadline exception", "evidence pack", "source-only", "formal")
LOCAL = "local run store, not in repo"
PROV = {
    "results": f"formal results summary, authoritative grading pass per run ({LOCAL}); see report §7.2",
    "human_layers": f"human-layer status recomputed with the frozen scoring on copies ({LOCAL}); see report §7.3",
    "adjudication": f"human adjudication records ({LOCAL}); see report §7.3 and §7.7",
    "worksheet": f"author adjudication worksheet ({LOCAL}); see report §7.7",
    "reveal": f"formal blind-label reveal ({LOCAL}); see report §7.6",
    "citations": f"citation check of the AI draft ({LOCAL}); see report §7.7",
    "ledgers": f"paid-workload ledgers ({LOCAL}); see report §8.1",
    "bundle": f"failure-analysis bundle: every graded item of the formal runs ({LOCAL}); see report §7.7",
    "workbooks": f"the candidates' deliverables and the task inputs ({LOCAL}); see report §6.5",
    "checks": f"defect-representative review records ({LOCAL}); see report §7.6",
    "visual": f"human visual-layer records ({LOCAL}); see report §7.3",
    "inventory": f"formal run inventories ({LOCAL}); see report §7.1",
    "logs": f"Inspect logs of the 20 formal runs ({LOCAL}); see report §2.3",
    "judge_registry": f"formal judge pass registry ({LOCAL}); see report §1",
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def esc(s):
    return html.escape(str(s), quote=True)


def load_json(p):
    return json.load(open(p, encoding="utf-8"))


def jsonl(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                out.append(json.loads(line))
    return out


def pct(n, d):
    return int((Decimal(n) * 100 / Decimal(d)).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if d else 0


WORD_RE = re.compile(r"\b\w[\w'’.\-/]*\b")


def words(text):
    return len(WORD_RE.findall(text))


def tw(text, size, bold=False):
    """Estimated rendered width of a label in the system sans at `size` px."""
    return len(text) * size * (0.6 if bold else 0.56)


def git_show(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, cwd=REPO, check=True).stdout


def rev(tag):
    return subprocess.run(["git", "rev-parse", "--short=7", f"{tag}^{{commit}}"], capture_output=True, text=True, cwd=REPO, check=True).stdout.strip()


def store_counts():
    """Store-total rows per candidate in the two Sales by Store sheets, and the input's data rows."""
    from openpyxl import load_workbook
    out = {}
    tdir = os.path.join(B, "analysis", "failures-v1", "tasks", SALES_TASK)
    for cand, fname in SALES_FILES.items():
        ws = load_workbook(os.path.join(tdir, cand, fname), data_only=True)["Sales by Store"]
        stores, totals = set(), 0
        for r in range(1, ws.max_row + 1):
            a = ws.cell(r, 1).value
            a = a.strip() if isinstance(a, str) else a
            if isinstance(a, str) and re.fullmatch(r"Store \d+ Total", a):
                totals += 1
            elif isinstance(a, str) and re.fullmatch(r"Store \d+", a):
                stores.add(a)
        out[cand] = {"stores": len(stores), "store_total_rows": totals}
    wb = load_workbook(os.path.join(tdir, "inputs", "Weekly Sales Data.xlsx"), read_only=True, data_only=True)
    out["source_rows"] = wb.worksheets[0].max_row - 1
    return out


# ------------------------------------------------------------------ SVG helpers
def stacked_bar(x0, y0, W, H, segs, total, size=12):
    """One stacked bar. segs: dicts with count, label, cls. A label goes inside its segment when it fits, otherwise
    outside below the bar on its own row with a short leader; outside labels are right-aligned to their anchor
    (left-aligned only when there is no room), in ascending anchor order, so no leader crosses another label. A zero
    segment gets an explicit outside label at the bar end. Returns (svg, height)."""
    out, outside, x = [], [], x0
    for s in segs:
        w = W * s["count"] / total if total else 0
        if s["count"] > 0:
            out.append(f'<rect class="{s["cls"]}" x="{x:.1f}" y="{y0}" width="{max(w - 2, 0.5):.1f}" height="{H}" rx="1.5"/>')
        if s["count"] > 0 and tw(s["label"], size, True) + 10 <= w:
            out.append(f'<text class="in {s["cls"]}-t" x="{x + w / 2:.1f}" y="{y0 + H/2 + size*0.36:.1f}" text-anchor="middle" font-size="{size}" font-weight="600">{esc(s["label"])}</text>')
        else:
            outside.append((x + w / 2 if s["count"] > 0 else x0 + W, s["label"]))
        x += w
    outside.sort(key=lambda t: t[0])
    for i, (anchor, label) in enumerate(outside):
        ly = y0 + H + 16 + i * 17
        out.append(f'<path class="leader" d="M{anchor:.1f} {y0 + H} V{ly - size*0.35:.1f}"/>')
        if anchor - 5 - tw(label, size) >= x0 - 1:
            out.append(f'<text class="lab" x="{anchor - 5:.1f}" y="{ly:.1f}" text-anchor="end" font-size="{size}">{esc(label)}</text>')
        else:
            out.append(f'<text class="lab" x="{anchor + 5:.1f}" y="{ly:.1f}" font-size="{size}">{esc(label)}</text>')
    return "".join(out), H + (16 + 17 * (len(outside) - 1) + 6 if outside else 0)


def svg(cls, w, h, label, body):
    return f'<svg class="chart-svg {cls}" viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="{esc(label)}">{body}</svg>'


def chart_review_change(A, row_labels, share_of, narrow):
    """Critical requirements per model, before and after author review, with the same three labels."""
    W = 358 if narrow else 896
    bar_x, bar_w = (0, W) if narrow else (150, 600)
    body, y = [], 0
    states = (("pass", "pass", "seg-pass"), ("fail", "fail", "seg-fail"), ("not_confirmed", "undecided", "seg-nc"))
    for m in ("opus", "gpt"):
        y += 16
        body.append(f'<text class="ttl" x="0" y="{y}" font-size="13.5" font-weight="600">{esc(NAME[m])}</text>')
        y += 8
        for key, rlabel in zip(("before", "after"), row_labels):
            counts = A[m][key]
            share = share_of(m) if key == "after" else ""
            segs = [{"count": counts[k], "label": f"{counts[k]} {word}", "cls": cls} for k, word, cls in states]
            if narrow:
                y += 15
                body.append(f'<text class="rl" x="0" y="{y}" font-size="12">{esc(rlabel)}</text>')
                if share:
                    body.append(f'<text class="share" x="{W}" y="{y}" text-anchor="end" font-size="12" font-weight="600">{esc(share)}</text>')
                y += 6
                s, h = stacked_bar(bar_x, y, bar_w, 22, segs, A["per_model"], 12)
            else:
                y += 4
                body.append(f'<text class="rl" x="0" y="{y + 15}" font-size="12.5">{esc(rlabel)}</text>')
                s, h = stacked_bar(bar_x, y, bar_w, 22, segs, A["per_model"], 12)
                if share:
                    body.append(f'<text class="share" x="{bar_x + bar_w + 12}" y="{y + 15}" font-size="12.5" font-weight="600">{esc(share)}</text>')
            body.append(s)
            y += h + 8
        y += 6
    aria = f'Critical requirements per model, {A["per_model"]} each. ' + " ".join(
        f'{NAME[m]}: ' + "; ".join(f'{lab.lower()} {A[m][k]["pass"]} pass, {A[m][k]["fail"]} fail, {A[m][k]["not_confirmed"]} undecided' for k, lab in zip(("before", "after"), row_labels))
        + f' ({share_of(m)} after review).' for m in ("opus", "gpt"))
    return svg("v-narrow" if narrow else "v-wide", W, y, aria, "".join(body))


# ------------------------------------------------------------------ visible-text counter
class Visible(HTMLParser):
    """Words shown by default, per section: closed <details> show only their <summary>; elements whose class is in
    `drop` (the other viewport's variants), the banner, <head>, <script> and <style> are not shown."""
    VOID = {"img", "br", "meta", "link", "input", "hr", "source", "wbr"}

    def __init__(self, drop):
        super().__init__(convert_charrefs=True)
        self.drop, self.stack, self.counts, self.text = set(drop), [], collections.Counter(), collections.defaultdict(list)

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        skip = tag in ("head", "script", "style") or bool(cls & (self.drop | {"banner"}))
        sec = a.get("id") if a.get("id") in SECTIONS else ("nav" if tag == "header" else "footer" if tag == "footer" else None)
        self.stack.append((tag, skip, sec))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for i, (tag, skip, _) in enumerate(self.stack):  # inside a closed <details>, only its own <summary> shows
            if skip or (tag == "details" and not (i + 1 < len(self.stack) and self.stack[i + 1][0] == "summary")):
                return
        if not data.strip():
            return
        sec = next((s for _, _, s in reversed(self.stack) if s), "other")
        self.counts[sec] += words(data)
        self.text[sec].append(data.strip())


def visible_counts(page, drop):
    v = Visible(drop)
    v.feed(page)
    return v


# ------------------------------------------------------------------ build
def main():
    final = "--final" in sys.argv
    preview = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    content = load_json(os.path.join(SITE, "content.json"))
    sel = load_json(os.path.join(REPO, "data", "selected_tasks.json"))
    tasks = sel["tasks"]
    order = [t["task_id"] for t in tasks]
    results = load_json(os.path.join(B, "formal", "results_summary.json"))
    hl = load_json(os.path.join(B, "formal", "human_layers_summary.json"))
    adj = jsonl(os.path.join(B, "formal", "human_review", "adjudication_*.jsonl"))
    vis = jsonl(os.path.join(B, "formal", "human_review", "visual_*.jsonl"))
    diag = list(csv.DictReader(open(os.path.join(REPO, "analysis", "codex_failure_review", "diagnosis.csv"), encoding="utf-8")))
    taxonomy = load_json(os.path.join(REPO, "analysis", "human_taxonomy.json"))
    reveal_path = sorted(glob.glob(os.path.join(B, "labeling", "formal-v4-reveal", "reveal_*.json")))[-1]
    reveal = load_json(reveal_path)
    csum = load_json(os.path.join(B, "analysis", "citations_summary.json"))
    status_md = open(os.path.join(REPO, "docs", "status.md"), encoding="utf-8").read()
    analysis_md = open(os.path.join(REPO, "analysis", "codex_failure_review", "analysis.md"), encoding="utf-8").read()
    ws_path = os.path.join(B, "analysis", "critical_adjudication.csv")
    items_path = os.path.join(B, "analysis", "failures-v1", "all_items.csv")
    crops_meta = load_json(os.path.join(SITE, "img", "crops.json"))
    registry_path = os.path.join(B, "judge_formal", "registry.jsonl")
    sources = [{"source": "repository: config.json", "sha256": sha(os.path.join(REPO, "config.json"))},
               {"source": "repository: data/selected_tasks.json", "sha256": sha(os.path.join(REPO, "data", "selected_tasks.json"))},
               {"source": "repository: docs/status.md", "sha256": sha(os.path.join(REPO, "docs", "status.md"))},
               {"source": "repository: preregistration.md", "sha256": sha(os.path.join(REPO, "preregistration.md"))},
               {"source": "repository: analysis/codex_failure_review/diagnosis.csv", "sha256": sha(os.path.join(REPO, "analysis", "codex_failure_review", "diagnosis.csv"))},
               {"source": "repository: analysis/human_taxonomy.json", "sha256": sha(os.path.join(REPO, "analysis", "human_taxonomy.json"))},
               {"source": "repository: analysis/requirement_source.json", "sha256": sha(os.path.join(REPO, "analysis", "requirement_source.json"))},
               {"source": "repository: docs/expert_gold_fail_audit.md", "sha256": sha(os.path.join(REPO, "docs", "expert_gold_fail_audit.md"))},
               {"source": "repository: site/img/crops.json (site/render_crops.py)", "sha256": sha(os.path.join(SITE, "img", "crops.json"))},
               {"source": PROV["results"], "sha256": sha(os.path.join(B, "formal", "results_summary.json"))},
               {"source": PROV["human_layers"], "sha256": sha(os.path.join(B, "formal", "human_layers_summary.json"))},
               {"source": PROV["worksheet"], "sha256": sha(ws_path)},
               {"source": PROV["bundle"], "sha256": sha(items_path)},
               {"source": PROV["reveal"], "sha256": sha(reveal_path)},
               {"source": PROV["citations"], "sha256": sha(os.path.join(B, "analysis", "citations_summary.json"))},
               {"source": PROV["judge_registry"], "sha256": sha(registry_path)}]
    for p in sorted(glob.glob(os.path.join(B, "formal", "human_review", "*.jsonl"))):
        sources.append({"source": (PROV["adjudication"] if "adjudication_" in p else PROV["visual"]) + f" · batch {os.path.basename(p)[:-6]}", "sha256": sha(p)})
    for c in crops_meta["crops"]:
        sources.append({"source": f"repository: site/img/{c['png']}", "sha256": sha(os.path.join(SITE, "img", c["png"]))})
    M, warnings = {}, []

    def metric(name, value, source, verification):
        M[name] = {"value": value, "source": source, "verification": verification}
        return value

    # ---- tasks, models, costs
    groups = collections.Counter(t["group"] for t in tasks)
    occupations = sorted({t["occupation"] for t in tasks})
    metric("tasks", len(order), "repository: data/selected_tasks.json", "fixed before generation")
    tg = metric("task_groups", {"order_clerks": groups["deep"], "accounting_and_it": groups["supplementary"], "occupations": len(occupations)}, "repository: data/selected_tasks.json (group, occupation)", "fixed before generation")
    model_ids = sorted({r["model"] for r in results["runs"]})
    metric("models", len(model_ids), PROV["results"], "fixed before generation")
    metric("runs_total", len(results["runs"]), PROV["results"], "one run per task and model")
    LEDGERS = (("dev", "Dev generation"), ("validation", "Validation generation"), ("compat", "Compatibility"), ("judge_dev", "Judge Dev"), ("judge_validation", "Judge Validation"),
               ("formal", "Formal generation, shared ledger (units 1-2)"), ("formal/opus", "Formal generation, Opus worker"), ("formal/gpt", "Formal generation, GPT worker"), ("judge_formal", "Formal judge"))
    per_ledger, all_paid = {}, Decimal("0")
    for lg, label in LEDGERS:
        st = json.loads(subprocess.run([sys.executable, "-m", "harness.ledger_admin", "status", "--ledger", os.path.join(B, lg, "ledger.json")], capture_output=True, text=True, cwd=REPO, check=True).stdout)
        per_ledger[label] = st["settled_usd"]; all_paid += Decimal(st["settled_usd"])
    formal_total = sum(Decimal(v) for k, v in per_ledger.items() if k.startswith("Formal"))
    metric("cost_formal_total_usd", str(formal_total), PROV["ledgers"] + " · the four formal ledgers", "ledger settlement (harness accounting from provider-reported usage, not an invoice)")
    gen_model = collections.defaultdict(Decimal)  # formal generation per model: every settlement of the three formal generation ledgers, by the unit's model
    for lg in ("formal", "formal/opus", "formal/gpt"):
        for e in load_json(os.path.join(B, lg, "ledger.json"))["entries"]:
            if e["type"] == "settlement":
                gen_model[CAND[e["unit_id"].split(":")[1]]] += Decimal(e["cost_usd"])
    if sum(gen_model.values()) != sum(Decimal(v) for k, v in per_ledger.items() if k.startswith("Formal generation")) or set(gen_model) != {"opus", "gpt"}:
        warnings.append("formal generation settlements by model do not add up to the generation ledgers' settled totals")
    metric("cost_formal_generation_per_model_usd", {m: str(v) for m, v in gen_model.items()}, PROV["ledgers"] + " · settlement entries of the three formal generation ledgers (shared units 1-2, Opus worker, GPT worker), by the unit's model",
           "ledger settlements; the per-model sums equal the three ledgers' settled totals; generation only, judge excluded")
    metric("cost_all_workloads_usd", {"total": str(all_paid), "per_ledger": per_ledger}, PROV["ledgers"] + " · harness ledger_admin status on every paid-workload ledger",
           "ledger settlements after manual resolutions, inferred portions included; equals report §8.1 recorded subtotal")
    # ---- adjudication layer and worksheet
    latest = {}
    for a in adj:
        latest[(a["model"], a["task_id"], a["item"])] = a
    adj_by = collections.Counter(a["adjudication"] for a in latest.values())
    metric("adjudication_layer", {"items": len(latest), "records": len(adj), "by_class": dict(adj_by),
                                  "last_recorded_at": max(a["recorded_at"] for a in adj)}, PROV["adjudication"] + " · latest record per item key",
           "human decisions; 'leave' marks an unresolved item-level coverage gap, not a verdict; later records supersede earlier ones")
    ws_rows = [r for r in csv.DictReader(open(ws_path, encoding="utf-8")) if r["section"] in ("1", "2")]
    wkey = lambda r: (MODEL_OF["opus"] if r["candidate"].startswith("Claude") else MODEL_OF["gpt"], r["task_id"], int(r["item"]))
    ws_keys = {wkey(r) for r in ws_rows}
    ws_by = collections.Counter(latest[k]["adjudication"] for k in ws_keys if k in latest)
    ws_conf = sum(ws_by.get(c, 0) for c in CONFIRMED)
    metric("worksheet_breakdown", {"rows": len(ws_keys), "by_class": dict(ws_by), "confirmed_failing": ws_conf}, PROV["worksheet"] + " joined with the latest adjudication records",
           "human decisions on the reviewed items (kept separate from the adjudication layer); confirmed failure = confirmed_fail + verified_fail + grader_false_pass")
    ws_crit = sum(1 for r in ws_rows if r["section"] == "1" and r["is_critical"] == "True" and r["graded_verdict"] in ("fail", "cannot_assess"))
    ws_draft_model = sum(1 for r in ws_rows if r["section"] == "2" and r["graded_verdict"] != "pass" and r["codex_class"] in ("model_error", "model_format_deviation"))
    ws_false_pass = sum(1 for r in ws_rows if r["section"] == "2" and r["graded_verdict"] == "pass" and latest[wkey(r)]["adjudication"] == "grader_false_pass")
    if ws_crit + ws_draft_model + ws_false_pass != len(ws_keys):
        warnings.append("the reviewed items do not split into critical members, draft model failures and the false pass")
    draft_cls = {c: dict(collections.Counter(r["codex_class"] for r in ws_rows if latest[wkey(r)]["adjudication"] == c)) for c in ("verified_pass", "leave")}
    if any(set(v) != {"grader_read_failure"} for v in draft_cls.values()):
        warnings.append("not every verified-pass or unresolved reviewed item carries the AI-draft class grader_read_failure")
    # unresolved items: each must sit in a criterion that already fails on a confirmed member
    members = {}
    hl_by = {(r["model"], r["task_id"]): r for r in hl["runs"]}
    for r in hl["runs"]:
        for cid, mem in r["members"].items():
            for i in mem["items"]:
                members[(r["model"], r["task_id"], i)] = cid
    leave_keys = [k for k, a in latest.items() if a["adjudication"] == "leave"]
    leave_where, leave_ok = collections.Counter(), True
    for k in leave_keys:
        cid = members.get(k)
        crit_status = hl_by[(k[0], k[1])]["adjudicated"].get(cid) if cid else None
        confirmed_member = cid and any(latest.get((k[0], k[1], i), {}).get("adjudication") in CONFIRMED for i in hl_by[(k[0], k[1])]["members"][cid]["items"])
        leave_ok &= bool(cid and crit_status == "fail" and confirmed_member)
        leave_where[f"{CAND[k[0]]}|{k[1][:8]}|{cid}"] += 1
    if not leave_ok:
        warnings.append("an unresolved item sits outside a criterion that already fails on a confirmed item")
    c1_verified = sorted(k[2] for k, a in latest.items() if a["adjudication"] == "verified_pass" and k[0] == MODEL_OF["opus"] and k[1].startswith("7d7fc9a7") and members.get(k) == "C1")
    leave_hits = []
    for (m, t, i), a in latest.items():
        if a["adjudication"] == "leave":
            other = MODEL_OF["gpt"] if m == MODEL_OF["opus"] else MODEL_OF["opus"]
            o = latest.get((other, t, i))
            if o and o["adjudication"] in CONFIRMED:
                leave_hits.append([CAND[m], t[:8], i])
    metric("leave_comparison", {"leave_items": adj_by.get("leave", 0), "with_confirmed_counterpart_on_other_candidate": leave_hits, "by_criterion": dict(leave_where),
                                "all_in_criteria_failing_on_a_confirmed_item": leave_ok}, PROV["adjudication"] + " joined with " + PROV["human_layers"], "computed")
    # ---- non-pass items: reviewed and not reviewed
    all_items = list(csv.DictReader(open(items_path, encoding="utf-8")))
    ikey = lambda r: (MODEL_OF[r["candidate"]], r["task_id"], int(r["item_id"]))
    diag_cls = {r["item_key"]: r["class"] for r in diag}
    nonpass = [r for r in all_items if r["verdict"] != "pass"]
    not_rev = [r for r in nonpass if ikey(r) not in ws_keys]
    nr_fail = [r for r in not_rev if r["verdict"] == "fail"]
    nr = {"total": len(not_rev), "critical": sum(1 for r in not_rev if r["is_critical"] == "True"), "fail": len(nr_fail),
          "fail_draft_classes": dict(collections.Counter(diag_cls.get(f'{r["candidate"]}|{r["task_id"]}|{r["item_id"]}', "none") for r in nr_fail)),
          "cannot_assess": sum(1 for r in not_rev if r["verdict"] == "cannot_assess"), "pending_visual": sum(1 for r in not_rev if r["verdict"] == "pending_human"),
          "invalid_judge_output": sum(1 for r in not_rev if r["verdict"] == "invalid_judge_output")}
    if nr["critical"] or set(nr["fail_draft_classes"]) - {"grader_false_fail", "rubric_ambiguous"}:
        warnings.append("an item not reviewed by hand is critical, or the AI draft attributed one of its fails to the model")
    metric("review_scope", {"reviewed": len(ws_keys), "critical_members": ws_crit, "draft_suspected_model_failures": ws_draft_model, "false_pass_from_blind_audit": ws_false_pass,
                            "reviewed_nonpass": sum(1 for r in nonpass if ikey(r) in ws_keys), "draft_class_of_verified_pass_and_unresolved": draft_cls,
                            "opus_7d7fc9a7_C1_verified_pass_items": c1_verified, "not_reviewed": nr},
           PROV["worksheet"] + "; " + PROV["bundle"] + "; " + PROV["adjudication"], "computed from the reviewed item keys, the graded verdicts and the AI-draft classes")
    # ---- runs and critical status
    runs = []
    judge_with_verdict = judge_total = invalid = 0
    overall = lambda d: "pass" if all(v == "pass" for v in d.values()) else ("fail" if any(v == "fail" for v in d.values()) else "not_confirmed")
    for r in sorted(results["runs"], key=lambda r: (order.index(r["task_id"]), r["model"])):
        h = hl_by[(r["model"], r["task_id"])]
        jv = r["judge_verdicts"]
        judge_total += r["judge_items"]; invalid += jv.get("invalid_judge_output", 0)
        judge_with_verdict += sum(n for k, n in jv.items() if k not in ("invalid_judge_output", "provider_error", "not_run"))
        sens = h.get("adds_policy_not_binding") or h["adjudicated"]
        runs.append({"task_id": r["task_id"], "task": TASK_NAME[r["task_id"][:8]], "occupation": next(t["occupation"] for t in tasks if t["task_id"] == r["task_id"]),
                     "model": NAME[CAND[r["model"]]], "cand": CAND[r["model"]], "run_uuid": r["run_uuid"], "pass": r["pass"], "P": r["P"], "E": r["E"], "W": r["W"], "P_over_E": r["P_over_E"], "E_over_W": r["E_over_W"],
                     "critical": {"pure_automated": overall(h["graded"]), "as_graded": overall(h["with_visual"]), "adjudicated": overall(h["adjudicated"]), "sensitivity": overall(sens)}})
    metric("runs", runs, PROV["results"] + " + " + PROV["human_layers"], "item scores as graded (frozen); critical status on four bases computed with the frozen scoring on copies")
    per_task = collections.Counter()
    for h in hl["runs"]:
        if h["model"] == MODEL_OF["opus"]:
            per_task[h["task_id"]] = len(h["adjudicated"])
    crit = collections.Counter()
    for h in hl["runs"]:
        for key, label in (("graded", "pure_automated"), ("with_visual", "as_graded"), ("adjudicated", "adjudicated"), ("adds_policy_not_binding", "sensitivity")):
            d = h.get(key) or h["adjudicated"]
            for st in d.values():
                crit[(CAND[h["model"]], label, st)] += 1
    cc = {f"{c}|{b}|{s}": crit.get((c, b, s), 0) for c in ("opus", "gpt") for b in ("pure_automated", "as_graded", "adjudicated", "sensitivity") for s in ("pass", "fail", "not_confirmed")}
    metric("critical_counts", cc, PROV["human_layers"],
           "automated only = frozen verdicts; as graded = + preregistered visual layer; adjudicated = + human records (final); sensitivity = adjudicated with R-2.7-21 not binding (both models)")
    crit_total = sum(v for k, v in cc.items() if k.startswith("opus|adjudicated|"))
    prereg = open(os.path.join(REPO, "preregistration.md"), encoding="utf-8").read()
    approved = re.search(r"Critical criteria: closed\. .*?APPROVED on\s+(\d{4}-\d{2}-\d{2})", prereg, flags=re.S).group(1)
    revised = re.search(r"C2 Activity shares \(revised (\d{4}-\d{2}-\d{2}), R-2\.8-1", open(os.path.join(REPO, "report", "REPORT.md"), encoding="utf-8").read()).group(1)
    prereg_same = all(h["preregistered_adjudicated"] is None or overall(h["preregistered_adjudicated"]) == overall(h["adjudicated"]) for h in hl["runs"])
    if not prereg_same:
        warnings.append("a revised critical definition changes a task's status against the preregistered one")
    metric("critical_criteria", {"per_model": crit_total, "per_task_min": min(per_task.values()), "per_task_max": max(per_task.values()), "approved": approved, "revised_one": revised,
                                 "revised_definition_same_status": prereg_same}, "repository: preregistration.md (closing list, item 1) and grading task definitions via " + PROV["human_layers"],
           "counted from the frozen task definitions; approval date as recorded in the preregistration")
    fail_by_rule = {m: cc[f"{m}|adjudicated|fail"] - cc[f"{m}|sensitivity|fail"] for m in ("opus", "gpt")}
    metric("rule_dependence", fail_by_rule, PROV["human_layers"], "adjudicated fails minus sensitivity fails per model (R-2.7-21)")
    # ---- grader reliability
    metric("judge_coverage", {"with_verdict": judge_with_verdict, "items": judge_total, "invalid_judge_output": invalid}, PROV["results"], "automated count")
    rs = reveal["summary"]
    ag = metric("agreement", {"deterministic": [rs["deterministic_items"]["agree"], rs["deterministic_items"]["n"]], "judge": [rs["judge_items"]["agree"], rs["judge_items"]["n"]], "all": [rs["agree"], rs["comparable"]]},
                PROV["reveal"], "human blind labels vs frozen graders on the sampled formal items")
    fp = {}
    for layer, name in (("D", "deterministic"), ("J", "judge")):
        gp = [p for p in reveal["packets"] if p["item_source"] == layer and p["grader_verdict_compared"] == "pass"]
        fp[name] = [sum(1 for p in gp if p["human_label"] == "fail"), len(gp)]
    fp["overall"] = [fp["deterministic"][0] + fp["judge"][0], fp["deterministic"][1] + fp["judge"][1]]
    metric("false_pass_search", fp, PROV["reveal"] + " · packets of the formal-v4 checkpoint sample", "human blind labels on the sampled items originally graded pass, per layer; counts only")
    sec = status_md[status_md.index("## Judge Validation complete; judge-human agreement"):]
    sec = sec[:sec.index("\n## ", 10)]
    mjv = re.search(r"- (\d+)/(\d+) counted:", sec)
    jv_agree = metric("judge_validation_agreement", [int(mjv.group(1)), int(mjv.group(2))], "repository: docs/status.md, 'Judge Validation complete; judge-human agreement' (report §4.2, §4.4)",
                      "human blind labels vs the frozen judge on the held-out Validation judge-only items; the debug-set item excluded")
    recheck = "## Codex recheck 2 of V1.9 closed as known limitations" in status_md
    js = metric("judge_status", {"provisional": not (bool(mjv) and recheck), "condition_agreement_recorded": bool(mjv), "condition_recheck_v1_9_recorded": recheck,
                                 "recheck_outcome": "BLOCKED (B1-B3, N1), closed by the author as known limitations (stop / pause control)" if recheck else None},
                "repository: preregistration.md 1.25; docs/status.md 'Judge Validation complete; judge-human agreement' and 'Codex recheck 2 of V1.9 closed as known limitations'",
                "preregistration 1.25: formal judge verdicts are provisional until both the Judge Validation agreement and the independent recheck of V1.9 exist; the label is lifted when both are recorded (site spec v3.1)")
    # ---- AI draft, citations, defect review
    cls = collections.Counter(r["class"] for r in diag)
    cnt = load_json(os.path.join(B, "analysis", "failures-v1", "_counts.json"))
    T = metric("triage", {"reviewed": len(diag), "nonpass_total": cnt["failures_rows"], "pending_visual": len(cnt["visual_pending"]), "invalid_judge": len(cnt["invalid_judge"]), "classes": dict(cls)},
               "repository: analysis/codex_failure_review/diagnosis.csv; " + PROV["bundle"], "AI-assisted draft (OpenAI Codex static review), not human-adjudicated")
    if len(nonpass) != T["nonpass_total"]:
        warnings.append("non-pass count of the bundle differs from the triage count")
    md08 = re.search(r"### D08\..*?\*\*Affected:\*\*(.*?)\n", analysis_md, flags=re.S)
    d08 = sum(len([i for i in g.split(",") if i.strip()]) for g in re.findall(r"\{([^}]*)\}", md08.group(1)))
    metric("d08_items", d08, "repository: analysis/codex_failure_review/analysis.md, D08 affected keys", "AI-draft defect diagnosis; author-verified (report §7.6); the items are adjudicated grader false fails")
    metric("citations", {"checked": csum["citations"], "by_status": csum["by_status"], "rows": csum["rows"]}, PROV["citations"], "mechanical checks of the draft's citations; 'verified' = the check passed, not that a value or conclusion is confirmed")
    reps = [r for r in csv.DictReader(open(os.path.join(B, "analysis", "critical_adjudication_checks.csv"), encoding="utf-8")) if r["record_type"] == "representative"]
    blind = collections.Counter(json.loads(line)["verdict"] for p in glob.glob(os.path.join(B, "analysis", "blind_review", "verdicts_*.jsonl")) for line in open(p, encoding="utf-8") if line.strip())
    verified = [r for r in reps if r["author_verification"].strip() == "human verified"]
    br = metric("blind_review", {"representatives": len(reps), "satisfied": blind.get("satisfied", 0), "rubric_ambiguous": blind.get("rubric ambiguous", 0), "author_verified": len(verified),
                                 "author_verified_ids": sorted(r["defect"] for r in verified), "others": len(reps) - len(verified)}, PROV["checks"], "second-model blind review; author verification recorded per representative")
    metric("visual_verdicts", len({(v["run_uuid"], v["item"]) for v in vis}), PROV["visual"], "human-authoritative (preregistered)")
    metric("human_review_time", "about 3 hours", "author estimate; report §8.1", "author-reported, not measured")
    # ---- taxonomy, categories
    adj_conf = {(CAND[a["model"]], a["task_id"], a["item"]) for a in latest.values() if a["adjudication"] in CONFIRMED}
    clusters = []
    for cl in taxonomy["clusters"]:
        items = [it for it in cl["items"] if (it["candidate"], it["task_id"], it["item"]) in adj_conf]
        if len(items) != len(cl["items"]):
            warnings.append(f"failure type {cl['id']} has items without a confirmed adjudication record")
        clusters.append({**cl, "items": items})
    tax_total = sum(len(c["items"]) for c in clusters)
    if tax_total != len(adj_conf):
        warnings.append(f"taxonomy holds {tax_total} items but the layer holds {len(adj_conf)} confirmed items")
    is_crit = lambda it: (MODEL_OF[it["candidate"]], it["task_id"], it["item"]) in members
    fc = taxonomy["failed_critical_criteria"]
    by_id = {c["id"]: c for c in clusters}
    # ---- requirement source of each confirmed failure: the prompt, only the rubric, or the pre-registered additions rule
    rs_doc = load_json(os.path.join(REPO, "analysis", "requirement_source.json"))
    cl_of = {(it["candidate"], it["task_id"], it["item"]): c["id"] for c in clusters for it in c["items"]}
    src_of = {(it["candidate"], it["task_id"], it["item"]): it["source"] for it in rs_doc["items"]}
    prompts = {t: open(os.path.join(B, "analysis", "failures-v1", "tasks", t, "task_prompt.txt"), encoding="utf-8").read() for t in order}
    norm_ws = lambda x: re.sub(r"\s+", " ", x)
    if (set(src_of) != adj_conf or len(src_of) != len(rs_doc["items"]) or any(v not in ("prompt", "rubric", "rule") for v in src_of.values())
            or any(it["failure_type"] != cl_of.get((it["candidate"], it["task_id"], it["item"])) for it in rs_doc["items"])
            or any((v == "rule") != (cl_of[k] == "ADDS") for k, v in src_of.items())
            or any((it["source"] == "prompt") != bool(it["prompt_fragments"]) or any(norm_ws(f) not in norm_ws(prompts[it["task_id"]]) for f in it["prompt_fragments"]) for it in rs_doc["items"])):
        warnings.append("the requirement-source tags do not cover exactly the confirmed items, or a tag, failure type or prompt quote does not check")
    if rs_doc["status"] != "approved" or any(it["debatable"] and not it.get("author_decision") for it in rs_doc["items"]):
        warnings.append("the requirement-source tags are not approved by the author, or a judgment call lacks the author's decision")
    src_n = {m: {s: sum(1 for k, v in src_of.items() if k[0] == m and v == s) for s in ("prompt", "rubric", "rule")} for m in ("opus", "gpt")}
    src_tasks = {m: len({k[1] for k, v in src_of.items() if k[0] == m and v == "prompt"}) for m in ("opus", "gpt")}
    metric("requirement_source", {"status": rs_doc["status"], "rule": rs_doc["rule"], "per_model": src_n, "prompt_tasks": src_tasks,
                                  "debatable": ["%s|%s|%s" % (it["candidate"], it["task_id"][:8], it["item"]) for it in rs_doc["items"] if it["debatable"]],
                                  "items": {"%s|%s|%s" % (it["candidate"], it["task_id"][:8], it["item"]): it["source"] for it in rs_doc["items"]}},
           "repository: analysis/requirement_source.json; task prompts of the formal task inputs (" + LOCAL + ")",
           "tagged after the runs from the task prompts (Claude's draft); status and the author's decision on each judgment call as recorded in the file; "
           "every prompt quote checked verbatim against the task prompt; display only, no verdict changes")
    sev_of = lambda its: max((by_id[cl_of[(it["candidate"], it["task_id"], it["item"])]]["severity"] for it in its), key=lambda s: SEV_ORDER[s], default=None)
    cat_rows, seen = [], []
    for row in content["failures"]["categories"]:
        its = [it for t in row["types"] for it in by_id[t]["items"]]
        seen += row["types"]
        per = {m: {"items": sum(1 for it in its if it["candidate"] == m), "tasks": len({it["task_id"] for it in its if it["candidate"] == m}),
                   "critical": sum(1 for it in its if it["candidate"] == m and is_crit(it)),
                   "prompt": sum(1 for it in its if it["candidate"] == m and src_of.get((it["candidate"], it["task_id"], it["item"])) == "prompt"),
                   "severity": sev_of([it for it in its if it["candidate"] == m])} for m in ("opus", "gpt")}
        sev = max((by_id[t]["severity"] for t in row["types"]), key=lambda s: SEV_ORDER[s])
        cat_rows.append({"id": row["id"], "types": row["types"], "per_model": per, "highest_severity": sev})
    if sorted(seen) != sorted(by_id) or len(seen) != len(set(seen)):
        warnings.append("the display categories do not cover every failure type exactly once")
    cat_tot = {m: {k: sum(r["per_model"][m][k] for r in cat_rows) for k in ("items", "critical", "prompt")} for m in ("opus", "gpt")}
    if any(cat_tot[m]["prompt"] != src_n[m]["prompt"] for m in ("opus", "gpt")):
        warnings.append("the categories' prompt counts differ from the requirement-source tags")
    if any(cat_tot[m]["items"] != sum(1 for c in adj_conf if c[0] == m) for m in ("opus", "gpt")):
        warnings.append("category totals differ from the confirmed items per model")
    metric("categories", {"rows": cat_rows, "totals": cat_tot, "scale_max": max(r["per_model"][m]["items"] for r in cat_rows for m in ("opus", "gpt"))},
           "repository: analysis/human_taxonomy.json grouped by site/content.json categories; critical membership from " + PROV["human_layers"],
           "display grouping of the existing failure types; no item changes type and no decision changes; counts are rubric items")
    metric("taxonomy_types", [{"id": c["id"], "name": c["name"], "definition": c["definition"], "severity": c.get("severity"), "per_model": c["per_model"], "critical_rubric_items": c["critical_rubric_items"],
                               "flagged_by": c["flagged_by"], "item_keys": ["%s|%s|%s" % (i["candidate"], i["task_id"][:8], i["item"]) for i in c["items"]], "note": c.get("note")} for c in clusters],
           "repository: analysis/human_taxonomy.json", "human-confirmed items only; severity is the author's rating")
    metric("failed_critical_criteria", {m: fc[m]["count"] for m in fc}, "repository: analysis/human_taxonomy.json", "adjudicated")
    metric("m2_leverage", taxonomy["m2_counts"], "repository: analysis/human_taxonomy.json (failed critical criteria by failure type)", "human-verified")
    m1 = by_id["M1"]
    metric("m1", {"gpt_items": m1["per_model"]["gpt"]["items"], "gpt_tasks": m1["per_model"]["gpt"]["tasks"], "critical": m1["critical_rubric_items"], "opus_items": m1["per_model"]["opus"]["items"]},
           "repository: analysis/human_taxonomy.json", "human-verified")
    opus_keys = [(MODEL_OF["opus"], t, i) for t, items_ in ((SALES_TASK, (12, 16, 25, 26)), ("7b08cd4d-df60-41ae-9102-8aaa49306ba2", (16, 17)), ("47ef842d-8eac-4b90-bda8-dd934c228c96", (28, 35, 42, 49, 56, 57))) for i in items_]
    backed = {f"{k[1][:8]}|{k[2]}": latest[k]["adjudication"] for k in opus_keys if k in latest and latest[k]["adjudication"] in ("confirmed_pass", "grader_false_fail")}
    if len(backed) != len(opus_keys):
        warnings.append("the 'Opus 5.5 includes them' claim lacks an author record for some Opus items")
    metric("opus_levels_verified", backed, PROV["adjudication"] + " (confirmed_pass / grader_false_fail with the author's evidence)", "author-verified; backs 'Opus 5.5 includes them'")
    # ---- cards
    ck = content["cards"]["card_keys"]
    rubric_of = {ikey(r): r["rubric_text"] for r in all_items}
    a_items = sorted(it["item"] for it in by_id[ck["A"]["cluster"]]["items"] if it["candidate"] == ck["A"]["cand"] and it["task_id"].startswith(ck["A"]["task"]))
    b_keys = [it for it in by_id[ck["B"]["cluster"]]["items"] if it["task_id"].startswith(ck["B"]["task"]) and it["item"] == ck["B"]["item"]]
    b_task = b_keys[0]["task_id"] if b_keys else None
    upcs = re.search(r"exactly the (\w+) UPCs", rubric_of.get((MODEL_OF["gpt"], b_task, ck["B"]["item"]), "")) if b_task else None
    # card C: GPT-6.1-sol's item only; the LLM judge passed it, the blind audit caught it, and it alone fails the task
    c_gpt = next((it for it in by_id[ck["C"]["cluster"]]["items"] if it["candidate"] == "gpt" and it["item"] == ck["C"]["item"] and it["task_id"].startswith(ck["C"]["task"])), None)
    c_task = c_gpt["task_id"] if c_gpt else None
    c_rows = {r["candidate"]: r for r in all_items if r["task_id"] == c_task and r["item_id"] == str(ck["C"]["item"])}
    c_h = hl_by.get((MODEL_OF["gpt"], c_task), {"adjudicated": {}, "members": {}})
    c_failed = [cid for cid, v in c_h["adjudicated"].items() if v == "fail"]
    c_alone = len(c_failed) == 1 and [i for i in c_h["members"][c_failed[0]]["items"] if latest.get((MODEL_OF["gpt"], c_task, i), {}).get("adjudication") in CONFIRMED] == [ck["C"]["item"]]
    c_terms = {c["cand"]: c["text"] for c in crops_meta["crops"] if c["card"] == "C"}
    c_ok = bool(c_gpt and is_crit(c_gpt) and c_alone and latest[(MODEL_OF["gpt"], c_task, ck["C"]["item"])]["adjudication"] == "grader_false_pass"
                and {m: (r["layer"], r["verdict"]) for m, r in c_rows.items()} == {"opus": ("judge", "pass"), "gpt": ("judge", "pass")} and ("opus", c_task, ck["C"]["item"]) not in adj_conf
                and set(c_terms) == {"opus", "gpt"} and c_terms["gpt"]["document_terms"]["multiple"] == 0 and c_terms["gpt"]["rendered_terms"]["multiple"] == 0
                and c_terms["opus"]["document_terms"]["multiple"] > 0 and "whole multiple of the case pack" in c_terms["opus"]["paragraph"]
                and all(q in c_terms["gpt"]["paragraph"] for q in content["cards"]["card_c_quotes"]["gpt"]) and all(q in c_terms["opus"]["paragraph"] for q in content["cards"]["card_c_quotes"]["opus"]) and c_terms["gpt"]["document_terms"]["divisib"] == c_terms["gpt"]["rendered_terms"]["divisib"])
    if not (a_items and all(is_crit({"candidate": "gpt", "task_id": SALES_TASK, "item": i}) for i in a_items) and len({it["candidate"] for it in b_keys}) == 2 and upcs
            and all(is_crit(it) for it in b_keys) and c_ok):
        warnings.append("a card item is not in its failure type, has the wrong critical membership or grader record, or its evidence moved")
    sc = store_counts()
    stores = sc["opus"]["stores"] if sc["opus"]["stores"] == sc["gpt"]["stores"] else None
    if stores is None:
        warnings.append("the two Sales by Store sheets list different store counts")
    gpt17 = next(r for r in all_items if r["candidate"] == "gpt" and r["task_id"] == SALES_TASK and r["item_id"] == "17")["verdict"]
    grand = {c["cand"]: c["cells"]["rows"][-1][3] for c in crops_meta["crops"] if c["kind"] == "grand_total"}
    if len(set(grand.values())) != 1 or gpt17 != "pass":
        warnings.append("the crops' grand totals differ, or GPT's grand-total item is not a frozen pass")
    for c in crops_meta["crops"]:
        raw = os.path.join(B, "analysis", "failures-v1", "tasks", c["task_id"], c["cand"], c["file"])
        if sha(raw) != c["sha256"] or sha(os.path.join(SITE, "img", c["png"])) != c["png_sha256"]:
            warnings.append(f"crop {c['png']}: deliverable or image hash differs from crops.json")
    cards = metric("cards", {"A": {"gpt_items": a_items, "gpt_store_subtotal_rows": sc["gpt"]["store_total_rows"], "opus_store_total_rows": sc["opus"]["store_total_rows"], "stores": stores,
                                   "grand_total_wtd_qty": grand, "gpt_grand_total_item17_frozen_verdict": gpt17},
                             "B": {"item": ck["B"]["item"], "task": b_task, "both_confirmed": len({it["candidate"] for it in b_keys}) == 2, "required_upcs": NUM_WORDS.get(upcs.group(1)) if upcs else None,
                                   "opus_failed_critical": fc["opus"]["count"], "m2_sole_cause_opus": taxonomy["m2_counts"]["m2_opus_sole"]},
                             "C": {"item": ck["C"]["item"], "task": c_task, "gpt_decision": latest[(MODEL_OF["gpt"], c_task, ck["C"]["item"])]["adjudication"] if c_gpt else None,
                                   "frozen_verdicts": {m: [r["layer"], r["verdict"]] for m, r in c_rows.items()}, "decides_gpt_task_alone": c_alone,
                                   "document_terms": {m: {"document": t["document_terms"], "rendered": t["rendered_terms"]} for m, t in c_terms.items()}},
                             "source_rows": sc["source_rows"]},
                   "repository: analysis/human_taxonomy.json; " + PROV["adjudication"] + "; " + PROV["workbooks"] + "; " + PROV["bundle"] + " (rubric text, frozen verdicts)",
                   "card items are human-confirmed failures; store and total rows read from the deliverables; card C term counts read from the Word documents and their renderings")
    metric("crops", [{k: c.get(k) for k in ("card", "cand", "task_id", "run_uuid", "file", "sha256", "sheet", "range", "header_row", "kind", "mark", "cells", "chart", "text", "page", "clip_pt", "png", "png_px")}
                     for c in crops_meta["crops"]],
           "repository: site/img/crops.json, written by site/render_crops.py from " + PROV["workbooks"],
           crops_meta["rendered_with"] + "; every shown cell token (card A), every referenced category label and no UPC (card B), or every word of the heading and paragraph (card C) checked in the rendering")
    # ---- configuration and run record
    gen_cfg = json.loads(git_show("freeze-v1-generation", "config.json"))
    grd_cfg = json.loads(git_show("freeze-v1-grading", "config.json"))
    freeze_rec = json.loads(git_show("freeze-v1-generation", "harness/freeze/freeze-v1-generation.json"))
    cfg_sha = hashlib.sha256(git_show("freeze-v1-generation", "config.json").encode()).hexdigest()
    if cfg_sha != freeze_rec["config_sha256"]:
        warnings.append("the config at freeze-v1-generation does not match the freeze record's hash")
    from inspect_ai.log import read_eval_log
    inv = []
    for root in ("runs", "opus/runs", "gpt/runs"):
        for line in open(os.path.join(B, "formal", root, "run_inventory.jsonl"), encoding="utf-8"):
            x = json.loads(line) if line.strip() else {}
            if x.get("kind") == "sample":
                inv.append(x)
    applied = collections.defaultdict(set)
    for x in inv:
        h = read_eval_log(x["log_file"], header_only=True)
        g, ec = h.eval.model_generate_config, h.eval.config
        applied[CAND[x["model"]]].add((g.reasoning_effort, g.max_tokens, g.max_retries, g.timeout, g.attempt_timeout, ec.time_limit, ec.working_limit, ec.message_limit, ec.epochs))
    rr = gen_cfg["retries"]["layer_1_inspect_model_request"]
    gc = gen_cfg["generation"]
    expect = {(None, None, rr["max_retries"], rr["timeout_s"], rr["attempt_timeout_s"], gc["time_limit_s"], gc["working_limit_s"], gc["message_limit"], gc["epochs"])}
    flat = {m: next(iter(v)) for m, v in applied.items() if len(v) == 1}
    if len(flat) != 2 or any(v[2:] != next(iter(expect))[2:] for v in flat.values()) or len({v[:2] for v in flat.values()}) != 1:
        warnings.append("formal run settings differ between runs, models or the frozen config")
    eff, mt = next(iter(flat.values()))[:2] if flat else (None, None)
    reg = jsonl(registry_path)
    first = lambda kind: next(e["at"] for e in reg if e.get("kind") == kind)
    jc = gen_cfg["judge"]
    jg = grd_cfg["judge"]
    if any(jc[k] != jg[k] for k in ("model", "temperature", "max_tokens", "reasoning_effort", "prompt_sha256")):
        warnings.append("judge settings differ between the two freezes")
    run_cfg = metric("run_configuration", {
        "models": {m: MODEL_OF[m] for m in ("opus", "gpt")}, "reasoning_effort": eff, "max_output_tokens": mt, "max_retries": rr["max_retries"], "request_timeout_s": rr["timeout_s"],
        "attempt_timeout_s": rr["attempt_timeout_s"], "provider_sdk_retries": gen_cfg["retries"]["layer_2_provider_sdk"]["max_retries"], "time_limit_s": gc["time_limit_s"],
        "working_limit_s": gc["working_limit_s"], "message_limit": gc["message_limit"], "attempts": gc["attempts"],
        "generation_start": min(x["started_at"] for x in inv), "generation_end": max(x["finished_at"] for x in inv),
        "judge_pass_start": first("pass_start"), "judge_pass_end": first("pass_end"), "labels_saved": reveal["checkpoint_saved_at"],
        "freeze_generation_commit": rev("freeze-v1-generation"), "freeze_grading_commit": rev("freeze-v1-grading"),
        "config_sha256": cfg_sha, "judge": {"model": jg["model"], "temperature": jg["temperature"], "max_tokens": jg["max_tokens"], "reasoning_effort": jg["reasoning_effort"], "prompt_sha256": jg["prompt_sha256"]}},
        "repository: config.json at freeze-v1-generation and freeze-v1-grading, harness/freeze/freeze-v1-generation.json; " + PROV["logs"] + "; " + PROV["inventory"] + "; " + PROV["judge_registry"] + "; " + PROV["reveal"],
        "frozen config cross-checked against the generate config and limits recorded in all 20 formal Inspect logs")
    # ---- limits actually reached by the formal runs (full logs: sample limits, stop reasons, output tokens, retries)
    lim = {"runs": 0, "sample_limit_hits": [], "max_tokens_stops": 0, "model_requests": 0, "largest_output_tokens_one_request": 0,
           "longest_run_s": 0, "most_messages": 0, "request_retries": 0, "inventory_recovered_attempts": sum(1 for x in inv if x.get("recovered_attempts"))}
    for x in inv:
        for s in read_eval_log(x["log_file"]).samples:
            lim["runs"] += 1
            if s.limit:
                lim["sample_limit_hits"].append([CAND[x["model"]], x["task_id"][:8], s.limit.type])
            lim["longest_run_s"] = max(lim["longest_run_s"], round(s.total_time or 0))
            lim["most_messages"] = max(lim["most_messages"], len(s.messages))
            for e in s.events:
                if e.event == "model":
                    lim["model_requests"] += 1
                    lim["request_retries"] += e.retries or 0
                    o = e.output
                    if o and o.choices and o.choices[0].stop_reason == "max_tokens":
                        lim["max_tokens_stops"] += 1
                    if o and o.usage:
                        lim["largest_output_tokens_one_request"] = max(lim["largest_output_tokens_one_request"], o.usage.output_tokens or 0)
    metric("run_limits_reached", lim, PROV["logs"] + "; " + PROV["inventory"],
           f"read from every model event of the 20 formal samples; limits: {mt} output tokens per request, {gc['time_limit_s']} s per run, {gc['message_limit']} messages per run")
    # ---- rubric items and critical requirements
    rubric_n = {m: sum(1 for r in all_items if r["candidate"] == m) for m in ("opus", "gpt")}
    crit_n = {m: sum(1 for r in all_items if r["candidate"] == m and r["is_critical"] == "True") for m in ("opus", "gpt")}
    member_n = {m: sum(len(mem["items"]) for h in hl["runs"] if h["model"] == MODEL_OF[m] for mem in h["members"].values()) for m in ("opus", "gpt")}
    if len(set(rubric_n.values())) != 1 or len(set(crit_n.values())) != 1 or crit_n != member_n:
        warnings.append("rubric-item totals differ between the models, or the critical members differ between the item bundle and the human layers")
    metric("rubric_items", {"per_model": rubric_n["opus"], "inside_critical_requirements": crit_n["opus"], "critical_requirements": crit_total,
                            "critical_requirements_per_task": {t[:8]: per_task[t] for t in order}},
           PROV["bundle"] + "; critical membership from " + PROV["human_layers"], "counted per model from the item bundle; the two models face the same rubric items")
    # ---- task verdicts after review, with the failure label of each failing cell
    occ_of = {t["task_id"]: t["occupation"] for t in tasks}
    type_of = {(it["candidate"], it["task_id"], it["item"]): c["id"] for c in clusters for it in c["items"]}
    labels = content["results"]["fail_labels"]
    tv, tv_n, tv_sens, tv_before = [], {m: collections.Counter() for m in CAND.values()}, {m: collections.Counter() for m in CAND.values()}, {m: collections.Counter() for m in CAND.values()}
    label_only = collections.Counter()
    src_cells, fp_alone = {m: collections.Counter() for m in ("opus", "gpt")}, 0
    for t in order:
        row = {"task_id": t, "task": TASK_NAME[t[:8]], "occupation": occ_of[t]}
        for m in ("opus", "gpt"):
            h = hl_by[(MODEL_OF[m], t)]
            st, sens, before = overall(h["adjudicated"]), overall(h.get("adds_policy_not_binding") or h["adjudicated"]), overall(h["with_visual"])
            failed = sorted(cid for cid, v in h["adjudicated"].items() if v == "fail")
            conf = [{"requirement": cid, "item": i, "failure_type": type_of.get((m, t, i)), "decision": latest[(MODEL_OF[m], t, i)]["adjudication"]}
                    for cid in failed for i in h["members"][cid]["items"] if latest.get((MODEL_OF[m], t, i), {}).get("adjudication") in CONFIRMED]
            types = sorted({c["failure_type"] for c in conf})
            lab = labels.get(f"{t[:8]}|{m}")
            if st == "fail" and (not lab or sorted(lab["types"]) != types or any(not any(c["requirement"] == cid for c in conf) for cid in failed)):
                warnings.append(f"task {t[:8]} {m}: failing cell without a label, a label whose failure types differ from the confirmed items, or a failing requirement without a confirmed item")
            if st != "fail" and lab:
                warnings.append(f"task {t[:8]} {m}: a label on a cell that does not fail")
            srcs = {src_of.get((m, t, c["item"])) for c in conf}
            source = next((s for s in ("prompt", "rubric", "rule") if s in srcs), None) if st == "fail" else None
            row[m] = {"after_review": st, "before_review": before, "without_additions_rule": sens, "failed_requirements": failed,
                      "confirmed_items_in_failed_requirements": conf, "label": lab["label"] if lab and st == "fail" else None, "requirement_source": source}
            tv_n[m][st] += 1; tv_sens[m][sens] += 1; tv_before[m][before] += 1
            if source:
                src_cells[m][source] += 1
            fp_alone += bool(st == "fail" and conf and all(c["decision"] == "grader_false_pass" for c in conf))
            if st == "fail" and types == ["M2"]:
                label_only[m] += 1
        tv.append(row)
    cnt3 = lambda c: {s: c.get(s, 0) for s in ("pass", "fail", "not_confirmed")}
    metric("task_verdicts", {"rows": tv, "after_review": {m: cnt3(tv_n[m]) for m in ("opus", "gpt")}, "before_review": {m: cnt3(tv_before[m]) for m in ("opus", "gpt")},
                             "failures_only_an_exact_label": dict(label_only),
                             "failed_tasks_by_requirement_source": {m: {s: src_cells[m].get(s, 0) for s in ("prompt", "rubric", "rule")} for m in ("opus", "gpt")},
                             "failed_tasks_decided_by_a_grader_false_pass_alone": fp_alone},
           PROV["human_layers"] + "; " + PROV["adjudication"] + "; failure types from repository: analysis/human_taxonomy.json; requirement sources from repository: analysis/requirement_source.json; labels from site/content.json",
           "a task passes when all its critical requirements pass (after review); each failing cell's label is checked against the failure types of the confirmed items in its failing requirements; "
           "a failed task's source is 'prompt' if any confirmed item in its failing requirements is stated in the prompt, else 'rubric', else 'rule'")
    deb = {(it["candidate"], it["task_id"], it["item"]) for it in rs_doc["items"] if it["debatable"]}

    def tally(flip_to):  # requirement-source tally with every judgment call set to flip_to (None = as tagged)
        src = {k: (flip_to if flip_to and k in deb else v) for k, v in src_of.items()}
        items = {m: sum(1 for k, v in src.items() if k[0] == m and v == "prompt") for m in ("opus", "gpt")}
        cells = {m: sum(1 for r in tv if r[m]["after_review"] == "fail" and any(src.get((m, r["task_id"], c["item"])) == "prompt" for c in r[m]["confirmed_items_in_failed_requirements"]))
                 for m in ("opus", "gpt")}
        return {"prompt_items": items, "failed_tasks_on_prompt": cells}
    sens_src = {"as_tagged": tally(None), "judgment_calls_as_rubric": tally("rubric"), "judgment_calls_as_prompt": tally("prompt")}
    if sens_src["as_tagged"]["failed_tasks_on_prompt"] != {m: src_cells[m]["prompt"] for m in ("opus", "gpt")}:
        warnings.append("the requirement-source sensitivity does not reproduce the tagged tally")
    if {k[0] for k in deb} != {"gpt"}:
        warnings.append("a borderline case is not a GPT-6.1-sol failure; the results note says all are")
    metric("requirement_source_sensitivity", sens_src, "derived from repository: analysis/requirement_source.json and the task verdicts",
           "the tally recomputed with every judgment call (debatable tag) read as rubric, and as prompt")
    m2_keys = {(it["candidate"], it["task_id"], it["item"]) for it in by_id["M2"]["items"]}
    opus_split = {"rubric_detail": sum(1 for k, v in src_of.items() if k[0] == "opus" and v == "rubric" and k not in m2_keys),
                  "exact_wording": sum(1 for k, v in src_of.items() if k[0] == "opus" and v == "rubric" and k in m2_keys),
                  "added_rule": src_n["opus"]["rule"]}
    if sum(opus_split.values()) != src_n["opus"]["prompt"] + src_n["opus"]["rubric"] + src_n["opus"]["rule"] or src_n["opus"]["prompt"]:
        warnings.append("Opus 5.5's failures do not split into rubric detail, exact wording and the added rule")
    metric("opus_failure_split", opus_split, "derived from repository: analysis/requirement_source.json (source) and analysis/human_taxonomy.json (M2 = exact wording)",
           "rubric-tagged items in M2 count as exact wording, the other rubric-tagged items as detail the rubric adds")
    wos = next(r for r in tv if r["task_id"].startswith("47ef842d"))
    if any(wos[m]["failed_requirements"] != ["C4"] for m in ("opus", "gpt")):
        warnings.append("weeks of supply no longer fails only on the chart requirement for both models")
    metric("task_verdicts_without_additions_rule", {m: cnt3(tv_sens[m]) for m in ("opus", "gpt")}, PROV["human_layers"],
           "after review, with the per-line additions rubric items set to cannot assess (the pre-registered additions rule not binding)")
    # ---- the weekly sales example (key terms and step 1)
    ex_h = hl_by[(MODEL_OF["gpt"], SALES_TASK)]
    ex_req = next(cid for cid, mem in ex_h["members"].items() if set(a_items) <= set(mem["items"]))
    name_of = {r["criterion_id"]: r["criterion_name"] for r in all_items if r["task_id"] == SALES_TASK and r["criterion_id"]}
    rubric = load_json(os.path.join(REPO, "private", "rubric", SALES_TASK + ".json"))
    layer_of = {int(r["item_id"]): r["layer"] for r in all_items if r["task_id"] == SALES_TASK and r["candidate"] == "gpt"}
    ex16 = rubric[16 - 1]
    if ex16["criterion"] != rubric_of[(MODEL_OF["gpt"], SALES_TASK, 16)] or any(layer_of[i] != "deterministic" for i in a_items):
        warnings.append("the weekly sales example's rubric item 16 or the grader of its subtotal items moved")
    ex = metric("weekly_sales_example", {"critical_requirements": len(ex_h["members"]), "names_recorded": {cid: name_of.get(cid) for cid in sorted(ex_h["members"])},
                                         "store_requirement": ex_req, "store_requirement_items": len(ex_h["members"][ex_req]["items"]), "failed_subtotal_items_gpt": a_items,
                                         "item_16_points": ex16["score"], "subtotal_items_grader": sorted({layer_of[i] for i in a_items})},
                "repository: private/rubric (the task's GDPval rubric, not published) and " + PROV["bundle"] + "; membership from " + PROV["human_layers"],
                "counted from the records; the page's names of the requirements and the quoted rubric items are descriptive paraphrases, the recorded names are listed here")
    # ---- GDPval's expert file for the weekly sales task (worked example), from the pre-run material audit
    audit = open(os.path.join(REPO, "docs", "expert_gold_fail_audit.md"), encoding="utf-8").read().splitlines()
    st_row = next(l for l in audit if l.startswith("| `b5d2e6f1` · 7, 8, 9"))
    data_row = next(l for l in audit if l.startswith("| `b5d2e6f1` · `c2_source_totals`"))
    m_st, m_cells = re.search(r"Clinique WTD (0\.\d+) vs (0\.\d+)", st_row), re.search(r"differs from the source in (\d+) cells", data_row)
    from openpyxl import load_workbook
    src_rows = list(load_workbook(os.path.join(B, "analysis", "failures-v1", "tasks", SALES_TASK, "inputs", "Weekly Sales Data.xlsx"), read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True))
    hdr = src_rows[0]
    qi, si, bi = hdr.index("Week to Date Sales Quantity"), hdr.index("Week to Date Stock on Hand"), hdr.index("Brand Name")
    cl = [r for r in src_rows[1:] if str(r[bi] or "").strip().lower() == "clinique"]
    st_sums = sum(r[qi] or 0 for r in cl) / sum(r[si] or 0 for r in cl)
    st_avg = sum((r[qi] or 0) / r[si] for r in cl if r[si]) / sum(1 for r in cl if r[si])
    if not (m_st and m_cells and "**Expert error**" in st_row and "**Unresolved**" in data_row
            and f"{st_avg:.4f}" == m_st.group(1) and f"{st_sums:.4f}" == m_st.group(2)):
        warnings.append("the expert-file audit rows of the weekly sales task moved, or its ST% example does not recompute from the input")
    gold = metric("expert_file_weekly_sales", {"st_pct_method": "average of row ratios (expert error in the audit)", "clinique_wtd_st_expert": m_st.group(1) if m_st else None,
                                               "clinique_wtd_st_ratio_of_sums": m_st.group(2) if m_st else None, "data_tab_cells_differing_from_source": int(m_cells.group(1)) if m_cells else None,
                                               "data_tab_difference": "unexplained in the audit: an undocumented expert edit or another input version"},
                  "repository: docs/expert_gold_fail_audit.md (weekly sales rows); the task input (" + LOCAL + ") for the ST% recomputation",
                  "pre-run material audit; the Clinique WTD values recomputed from the input at build time")
    # ---- pilot size and cost of the proposed dataset (estimate, not measured)
    pp = content["data"]["pilot_plan"]
    pilot = metric("pilot_estimate", {**{k: v for k, v in pp.items() if not k.startswith("_")}, "samples": len(pp["families"]) * pp["tasks_per_family"],
                                      "hours_per_sample": pp["gdpval_hours_per_task"] + pp["extra_hours_per_sample"],
                                      "hours_total": len(pp["families"]) * pp["tasks_per_family"] * (pp["gdpval_hours_per_task"] + pp["extra_hours_per_sample"])},
                   "repository: site/content.json (data.pilot_plan, the proposal's parameters); " + pp["gdpval_source"],
                   "estimate for a proposal, not a measured result; the expert time per task is GDPval's reported average, the extra hours are this proposal's estimate")
    # ---- chart data
    A = {"per_model": crit_total}
    for m in ("opus", "gpt"):
        A[m] = {b: {s: cc[f"{m}|{key}|{s}"] for s in ("pass", "fail", "not_confirmed")} for b, key in (("before", "as_graded"), ("after", "adjudicated"))}
        A[m]["after_pass_pct"] = pct(A[m]["after"]["pass"], crit_total)
    D = {"n": len(ws_keys), "segments": [
        {"key": "confirmed_fail+verified_fail+grader_false_pass", "name": "confirmed failure", "count": ws_conf, "cls": "seg-accent"},
        {"key": "grader_false_fail", "name": "grader false fail", "count": ws_by.get("grader_false_fail", 0), "cls": "seg-g1"},
        {"key": "verified_pass", "name": "cannot assess, then pass", "count": ws_by.get("verified_pass", 0), "cls": "seg-g2"},
        {"key": "leave", "name": "cannot assess, left", "count": ws_by.get("leave", 0), "cls": "seg-g3"}]}
    if sum(s["count"] for s in D["segments"]) != D["n"]:
        warnings.append("the author-review bar does not sum to the reviewed items")
    for s in D["segments"]:
        s["pct"] = pct(s["count"], D["n"])
    ws_graded = collections.Counter((latest[wkey(r)]["adjudication"], r["graded_verdict"]) for r in ws_rows)
    if any(v != "cannot_assess" for (a, v) in ws_graded if a in ("verified_pass", "leave")):
        warnings.append("a 'cannot assess → pass / left' item was not graded cannot assess")
    metric("charts", {"review_change": A, "review_result": D, "review_result_graded_verdicts": {f"{a}|{v}": n for (a, v), n in ws_graded.items()}},
           "derived at build time from critical_counts (before review = as graded, after review = adjudicated) and worksheet_breakdown",
           "before review = frozen verdicts plus the pre-registered visual review; after review = plus the author's review decisions (final)")
    # ---- categories as shown (Seen here, inside critical requirements)
    cat_v = M["categories"]["value"]
    for r in cat_v["rows"]:
        r["seen_here"] = {m: r["per_model"][m]["items"] for m in ("opus", "gpt")}
        r["inside_critical_requirements"] = {m: r["per_model"][m]["critical"] for m in ("opus", "gpt")}
        r["total_items"] = r["per_model"]["opus"]["items"] + r["per_model"]["gpt"]["items"]
    cat_v["types_per_category"] = {r["id"]: len(r["types"]) for r in cat_v["rows"]}
    m4_tasks = len({it["task_id"] for t in ("M4",) for it in by_id[t]["items"]})
    # ---- page-level checks
    quote = next(t[2] for t in content["findings"]["terms"] if t[0] == "Rubric item")
    qtext = re.search(r":\s*(.+?)…", quote).group(1)
    norm = lambda x: re.sub(r"[\"“”'‘’]", "", x)
    if not norm(ex16["criterion"]).startswith(norm(qtext)):
        warnings.append("the quoted rubric item of the key terms is not item 16's wording")
    cat_a = next(r for r in cat_v["rows"] if r["id"] == "A")
    graded_nonpass = sum(1 for r in nonpass if r["verdict"] in ("fail", "cannot_assess"))
    if graded_nonpass != T["reviewed"]:
        warnings.append("the AI draft's items are not exactly the rubric items graded fail or cannot assess")
    b_opus_crit = [it for t in ("M2", "M6") for it in by_id[t]["items"] if it["candidate"] == "opus" and is_crit(it)]
    if any(type_of[(it["candidate"], it["task_id"], it["item"])] != "M2" for it in b_opus_crit):
        warnings.append("an Opus 5.5 critical item in category B is not an exact-label (M2) item")
    if js["provisional"]:
        warnings.append("judge verdicts are still provisional; the page states no provisional label")
    if "gemini-3.1-pro" not in jg["model"]:
        warnings.append("the page names the judge Gemini 3.1 Pro but the frozen judge is another model")
    if lim["sample_limit_hits"] or lim["max_tokens_stops"]:
        warnings.append("a formal run reached a limit; the page describes the limits as caps only")
    # ---- gating
    blocks = ("findings", "results", "failures", "taxonomy_fill", "cards", "cards_fill", "data", "worked_fill", "method", "footer")
    pending = [k for k in blocks if content[k]["status"] != "approved"]
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    hm = lambda s: s[11:16]
    fpd = M["false_pass_search"]["value"]
    nrv_tot = M["review_scope"]["value"]
    nrv = nrv_tot["not_reviewed"]
    gen_start = dt.datetime.fromisoformat(str(run_cfg["generation_start"]))
    tl_h = run_cfg["time_limit_s"] / 3600
    runs_each = len(results["runs"]) // (len(order) * len(model_ids))
    if runs_each * len(order) * len(model_ids) != len(results["runs"]) or gc["attempts"] != 1:
        warnings.append("runs per task and model is not one, or attempts differ from one")
    tsens = M["task_verdicts_without_additions_rule"]["value"]
    tafter = M["task_verdicts"]["value"]["after_review"]
    rule_tasks = {m: tafter[m]["fail"] - tsens[m]["fail"] for m in ("opus", "gpt")}
    rv_fail = sum(n for (a, v), n in ws_graded.items() if v == "fail")
    rv_fail_crit = sum(1 for r in ws_rows if r["section"] == "1" and r["graded_verdict"] == "fail")  # reviewed because a verdict could change
    rv_fail_draft = sum(1 for r in ws_rows if r["section"] == "2" and r["graded_verdict"] == "fail")  # reviewed because the AI draft suspected a model failure
    if rv_fail_crit + rv_fail_draft != rv_fail:
        warnings.append("the reviewed graded fails do not split into critical members and draft-suspected items")
    rv_ca = sum(n for (a, v), n in ws_graded.items() if v == "cannot_assess")
    flow = {"graded_fail_or_cannot_assess": T["reviewed"], "reviewed_of_those": nrv_tot["reviewed_nonpass"], "critical_members": ws_crit, "draft_suspected": ws_draft_model,
            "graded_pass_from_blind_audit": ws_false_pass, "reviewed": len(ws_keys), "reviewed_graded_fail": rv_fail, "reviewed_graded_fail_critical": rv_fail_crit, "reviewed_graded_fail_draft_suspected": rv_fail_draft, "reviewed_cannot_assess": rv_ca,
            "not_reviewed": nrv["total"], "not_reviewed_fail": nrv["fail"], "not_reviewed_cannot_assess": nrv["cannot_assess"], "no_verdict": nrv["pending_visual"] + nrv["invalid_judge_output"]}
    if (flow["reviewed_of_those"] + flow["not_reviewed_fail"] + flow["not_reviewed_cannot_assess"] != flow["graded_fail_or_cannot_assess"]
            or flow["critical_members"] + flow["draft_suspected"] != flow["reviewed_of_those"] or flow["reviewed_of_those"] + flow["graded_pass_from_blind_audit"] != flow["reviewed"]
            or rv_fail + rv_ca + flow["graded_pass_from_blind_audit"] != flow["reviewed"] or flow["not_reviewed_fail"] + flow["not_reviewed_cannot_assess"] + flow["no_verdict"] != flow["not_reviewed"]):
        warnings.append("the review count flow does not reconcile")
    metric("review_count_flow", flow, PROV["worksheet"] + "; " + PROV["bundle"], "reconciled at build time: graded fail or cannot assess = reviewed + not reviewed; reviewed = those + the blind-audit pass")  # failed tasks that fail only under the additions rule
    if any(tafter[m]["pass"] != tsens[m]["pass"] or tafter[m]["fail"] + tafter[m]["not_confirmed"] != tsens[m]["fail"] + tsens[m]["not_confirmed"] for m in ("opus", "gpt")):
        warnings.append("without the additions rule a task changes other than from fail to not confirmed")
    metric("rule_dependence_tasks", rule_tasks, PROV["human_layers"], "failed tasks after review minus failed tasks without the additions rule, per model")
    sub = {"tasks": len(order), "models": len(model_ids), "runs": len(results["runs"]), "runs_each": runs_each, "runs_each_word": WORDS[runs_each],
           "oc_tasks": tg["order_clerks"], "other_tasks": tg["accounting_and_it"], "occupations": tg["occupations"], "occupations_word": WORDS[tg["occupations"]],
           "m1_gpt_tasks": m1["per_model"]["gpt"]["tasks"], "crit_total": crit_total, "crit_items": crit_n["opus"], "rubric_items": rubric_n["opus"],
           "crit_min": M["critical_criteria"]["value"]["per_task_min"], "crit_max": M["critical_criteria"]["value"]["per_task_max"],
           "opus_tasks_pass": tafter["opus"]["pass"], "gpt_tasks_pass": tafter["gpt"]["pass"], "opus_tasks_fail": tafter["opus"]["fail"],
           "opus_label_only": label_only["opus"],
           "sens_opus_pass": tsens["opus"]["pass"], "sens_opus_fail": tsens["opus"]["fail"], "sens_opus_nc": tsens["opus"]["not_confirmed"],
           "sens_gpt_pass": tsens["gpt"]["pass"], "sens_gpt_fail": tsens["gpt"]["fail"], "sens_gpt_nc": tsens["gpt"]["not_confirmed"],
           "ws_rows": len(ws_keys), "ws_confirmed": ws_conf, "ws_leave": ws_by.get("leave", 0), "reviewed": T["reviewed"],
           "seg0": D["segments"][0]["count"], "pct0": D["segments"][0]["pct"], "seg1": D["segments"][1]["count"], "pct1": D["segments"][1]["pct"],
           "seg2": D["segments"][2]["count"], "pct2": D["segments"][2]["pct"], "seg3": D["segments"][3]["count"], "pct3": D["segments"][3]["pct"],
           "d08_items_word": WORDS.get(d08, d08), "sample_n": ag["all"][1], "fp_all_n": fpd["overall"][0], "fp_all_d": fpd["overall"][1],
           "notrev_total": nrv["total"], "confirmed_items": tax_total, "categories": len(cat_rows), "types": len(clusters),
           "types_split": ", ".join(f"{r['id']}: {len(r['types'])}" for r in cat_rows), "d_tasks_word": WORDS[m4_tasks],
           "stores": stores, "opus_store_total_rows": cards["A"]["opus_store_total_rows"], "card_a_items": " / ".join(str(i) for i in a_items),
           "card_b_upcs_word": WORDS.get(cards["B"]["required_upcs"], ""), "m2_opus_sole": taxonomy["m2_counts"]["m2_opus_sole"], "opus_failed_crit": fc["opus"]["count"],
           "source_rows": sc["source_rows"], "c_item": ck["C"]["item"],
           "c_divisib_word": {1: "once", 2: "twice"}.get(c_terms.get("gpt", {}).get("document_terms", {}).get("divisib"), "more than twice"),
           "opus_items": cat_v["totals"]["opus"]["items"], "gpt_items": cat_v["totals"]["gpt"]["items"],
           "opus_prompt_items": src_n["opus"]["prompt"], "gpt_prompt_items": src_n["gpt"]["prompt"], "gpt_prompt_tasks": src_tasks["gpt"],
           "omit_items": sum(r["total_items"] for r in cat_v["rows"] if r["id"] in ("A", "C")), "form_items": sum(r["total_items"] for r in cat_v["rows"] if r["id"] == "B"),
           "rule_items": sum(r["total_items"] for r in cat_v["rows"] if r["id"] == "D"),
           "opus_prompt_task_fails": src_cells["opus"]["prompt"], "gpt_prompt_task_fails": src_cells["gpt"]["prompt"],
           "fail_cells": tafter["opus"]["fail"] + tafter["gpt"]["fail"], "prompt_fail_cells": src_cells["opus"]["prompt"] + src_cells["gpt"]["prompt"],
           "rubric_fail_cells": tafter["opus"]["fail"] + tafter["gpt"]["fail"] - src_cells["opus"]["prompt"] - src_cells["gpt"]["prompt"],
           "fp_alone_word": WORDS[fp_alone], "src_debatable": len(M["requirement_source"]["value"]["debatable"]),
           "gpt_prompt_items_min": sens_src["judgment_calls_as_rubric"]["prompt_items"]["gpt"], "gpt_prompt_items_max": sens_src["judgment_calls_as_prompt"]["prompt_items"]["gpt"],
           "gpt_prompt_tasks_min": sens_src["judgment_calls_as_rubric"]["failed_tasks_on_prompt"]["gpt"], "gpt_prompt_tasks_max": sens_src["judgment_calls_as_prompt"]["failed_tasks_on_prompt"]["gpt"],
           "opus_prompt_max": max(sens_src[k]["prompt_items"]["opus"] for k in sens_src),
           "opus_detail_items": opus_split["rubric_detail"], "opus_wording_items": opus_split["exact_wording"], "opus_rule_items": opus_split["added_rule"],
           "rv_fail_crit": rv_fail_crit, "rv_fail_draft": rv_fail_draft, "gpt_tasks_fail": tafter["gpt"]["fail"], "rv_crit": flow["critical_members"], "rv_draft": flow["draft_suspected"], "rv_fp": flow["graded_pass_from_blind_audit"], "rv_fail": rv_fail, "rv_ca": rv_ca,
           "rv_conf_fail": ws_graded.get(("confirmed_fail", "fail"), 0), "rv_vfail": ws_by.get("verified_fail", 0), "gff_pct": pct(ws_by.get("grader_false_fail", 0), rv_fail),
           "nr_fail": nrv["fail"], "nr_ca": nrv["cannot_assess"], "nr_visual": nrv["pending_visual"], "nr_invalid": nrv["invalid_judge_output"],
           "nr_fail_ffail": nrv["fail_draft_classes"].get("grader_false_fail", 0), "nr_fail_amb": nrv["fail_draft_classes"].get("rubric_ambiguous", 0),
           "pilot_train": pp["train_per_family"], "pilot_heldout": pp["heldout_per_family"],
           "gold_cells": gold["data_tab_cells_differing_from_source"], "gold_st_expert": gold["clinique_wtd_st_expert"], "gold_st_sums": gold["clinique_wtd_st_ratio_of_sums"],
           "pilot_families_n": len(pp["families"]), "pilot_families": ", ".join(pp["families"]), "pilot_tasks": pp["tasks_per_family"], "pilot_samples": pilot["samples"],
           "gdpval_hours": pp["gdpval_hours_per_task"], "pilot_extra_hours": pp["extra_hours_per_sample"], "pilot_hours_per": pilot["hours_per_sample"],
           "pilot_hours_total": pilot["hours_total"], "pilot_runs": pp["runs_per_task"], "pilot_rise": pp["accept_rise_points"], "pilot_hold": pp["hold_within_points"],
           "a_gpt_items": cat_a["per_model"]["gpt"]["items"], "a_gpt_tasks": cat_a["per_model"]["gpt"]["tasks"],
           "b_opus_crit": len(b_opus_crit), "opus_crit_items": cat_v["totals"]["opus"]["critical"],
           "ex_item_points": ex["item_16_points"], "ex_crit_items": ex["store_requirement_items"], "ex_failed_items": len(a_items), "ex_crit_count": ex["critical_requirements"],
           "cost_formal": f"{formal_total:.2f}", "cost_all": f"{all_paid:.2f}", "review_time": M["human_review_time"]["value"],
           "cost_gen_opus": f"{gen_model['opus'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}", "cost_gen_gpt": f"{gen_model['gpt'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}",
           "rule_task_fail_per_model": rule_tasks["opus"] if rule_tasks["opus"] == rule_tasks["gpt"] else f"{rule_tasks['opus']} / {rule_tasks['gpt']}",
           "rule_task_word": "task" if rule_tasks["opus"] == rule_tasks["gpt"] == 1 else "tasks",
           "rule_fail_per_model": fail_by_rule["opus"] if fail_by_rule["opus"] == fail_by_rule["gpt"] else f"{fail_by_rule['opus']} / {fail_by_rule['gpt']}",
           "ag_det_n": ag["deterministic"][0], "ag_det_d": ag["deterministic"][1], "ag_judge_n": ag["judge"][0], "ag_judge_d": ag["judge"][1],
           "jv_agree": f"{jv_agree[0]}/{jv_agree[1]}", "jv_d": jv_agree[1],
           "opus_id": MODEL_OF["opus"], "gpt_id": MODEL_OF["gpt"], "effort": run_cfg["reasoning_effort"], "max_tokens": f"{run_cfg['max_output_tokens']:,}",
           "time_limit_words": f"{WORDS[int(tl_h)]}-hour" if tl_h == int(tl_h) else f"{run_cfg['time_limit_s']:,}-second", "attempts_word": WORDS[gc["attempts"]],
           "max_retries": run_cfg["max_retries"], "gen_date_long": f"{gen_start.day} {gen_start.strftime('%b %Y')}",
           "gen_start": hm(str(run_cfg["generation_start"])), "gen_end": hm(str(run_cfg["generation_end"])),
           "judge_start": hm(run_cfg["judge_pass_start"]), "judge_end": hm(run_cfg["judge_pass_end"]), "labels_saved": hm(run_cfg["labels_saved"]),
           "opus_run": next(c["run_uuid"] for c in crops_meta["crops"] if c["card"] == "A" and c["cand"] == "opus"),
           "gpt_run": next(c["run_uuid"] for c in crops_meta["crops"] if c["card"] == "A" and c["cand"] == "gpt"),
           "built": generated[:10]}

    def fill(text, extra=None):
        d = {**sub, **(extra or {})}
        out = re.sub(r"\{\{(\w+)\}\}", lambda m: esc(d[m.group(1)]), esc(text or ""))
        out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
        out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
        out = re.sub(r"\[(pass|fail|nc)\|([^\]]+)\]", r'<span class="c-\1">\2</span>', out)
        out = re.sub(r"\[([^\]|]+)\]\((https://[^)\s]+)\)", r'<a href="\2">\1</a>', out)
        return out.replace("\n", "<br>")

    def lead(pair):
        return f"<strong>{fill(pair[0])}</strong> {fill(pair[1])}"

    def table(head, rows_html, cls="cat"):
        return f'<div class="tw"><table class="{cls}"><thead><tr>' + "".join(f"<th>{fill(h)}</th>" for h in head) + f"</tr></thead><tbody>{rows_html}</tbody></table></div>"

    co = content
    repo = co["repo_url"]
    report_url = f"{repo}/blob/main/{co['report_path']}"
    fi, re_, fa, tf, cd, cdf, da, wf, me = (co[k] for k in ("findings", "results", "failures", "taxonomy_fill", "cards", "cards_fill", "data", "worked_fill", "method"))
    # ---- findings
    tiles = "".join(f'<div class="tile"><div class="v">{fill(v)}</div><div class="l">{fill(l)}</div><div class="s">{fill(s)}</div></div>' for v, l, s in fi["tiles"])
    terms = table(fi["terms_head"], "".join(f"<tr><td><strong>{fill(a)}</strong></td><td>{fill(b)}</td><td>{fill(c)}</td></tr>" for a, b, c in fi["terms"]))
    findings_html = (f'<section id="findings"><h1>{fill(fi["title"])}</h1><p class="deck">{fill(fi["deck"])}</p>'
                     f'<ul class="bul">{"".join(f"<li>{lead(b)}</li>" for b in fi["bullets"])}</ul><div class="tiles t4">{tiles}</div>'
                     f'<p class="note">{fill(fi["note"])}</p>' + (f'<p class="note setup">{lead(fi["measured"])}</p>' if fi.get("measured") else "") +
                     f'<details><summary>{fill(fi["terms_title"])}</summary>{terms}</details></section>')
    # ---- results
    pill = lambda st: f'<span class="pill pill-{st}">{esc(STATUS_WORD[st])}</span>'
    grid_rows, occ_seen = [], None
    for r in tv:
        if r["occupation"] != occ_seen:
            occ_seen = r["occupation"]
            grid_rows.append(f'<tr class="occ"><td colspan="3">{esc(occ_seen)}</td></tr>')
        cells = "".join(f'<td>{pill(r[m]["after_review"])}' + (f' <em class="fl">{esc(r[m]["label"])}</em>' if r[m]["label"] else "")
                        + (f' <span class="src src-{r[m]["requirement_source"]}">{esc(re_["source_words"][r[m]["requirement_source"]])}</span>' if r[m]["requirement_source"] else "") + "</td>" for m in ("opus", "gpt"))
        grid_rows.append(f'<tr><td>{esc(r["task"])}</td>{cells}</tr>')
    gt = re_["grid_total"]
    grid_rows.append(f'<tr class="tot"><td><strong>{fill(gt[0])}</strong></td><td><strong>{fill(gt[1])}</strong></td><td><strong>{fill(gt[2])}</strong></td></tr>')
    gt2 = re_["grid_total2"]
    grid_rows.append(f'<tr class="tot2"><td>{fill(gt2[0])}</td><td>{fill(gt2[1])}</td><td>{fill(gt2[2])}</td></tr>')
    share_of = lambda m: re.sub(r"\{\{(\w+)\}\}", lambda x: str({"n": A[m]["after"]["pass"], "crit_total": crit_total, "pct": A[m]["after_pass_pct"]}[x.group(1)]), re_["share"])
    results_html = (f'<section id="results"><h2>{fill(re_["heading"])}</h2><h3>{fill(re_["grid_title"])}</h3><p class="note">{fill(re_["grid_sub"])}</p>'
                    + table(re_["grid_head"], "".join(grid_rows), "cat vgrid")
                    + f'<details><summary>{fill(re_["notes_title"])}</summary>' + "".join(f"<p>{fill(n)}</p>" for n in re_["notes"]) + "</details>"
                    f'<h3>{fill(re_["chart_title"])}</h3><p class="note">{fill(re_["chart_sub"])}</p>'
                    f'<figure class="fig">{chart_review_change(A, re_["row_labels"], share_of, False)}{chart_review_change(A, re_["row_labels"], share_of, True)}</figure>'
                    f'<details><summary>{fill(re_["chosen_title"])}</summary><p>{lead(re_["chosen"])}</p><ul class="bul">'
                    + "".join(f"<li>{lead(b)}</li>" for b in re_["bases"]) + "</ul></details></section>")
    # ---- failures
    sev_badge = lambda s: f"<span class='sev sev-{esc(s)}'>{esc(s)}</span>"

    def sev_cell(p):  # always Opus / GPT, like the other columns; a dash where a model has no failure in the category
        return " / ".join(sev_badge(p[m]["severity"]) if p[m]["severity"] else "—" for m in ("opus", "gpt"))
    tasks_txt = lambda n, t: f"{n} · {t} task{'s' if t != 1 else ''}" if n else "0"
    cat_rows_html = ""
    for row, data in zip(fa["categories"], cat_v["rows"]):
        p = data["per_model"]
        cat_rows_html += (f"<tr><td><strong>{esc(row['id'])}. {esc(row['name'])}</strong><br><span class='small'>{esc(row['meaning'])}</span></td><td class='num'>{tasks_txt(p['opus']['items'], p['opus']['tasks'])}</td>"
                          f"<td class='num'>{tasks_txt(p['gpt']['items'], p['gpt']['tasks'])}</td><td class='num'><strong>{data['total_items']}</strong></td>"
                          f"<td class='num'>{p['opus']['prompt']} / {p['gpt']['prompt']}</td><td class='num'>{sev_cell(p)}</td></tr>")
    ct = cat_v["totals"]
    cat_rows_html += (f"<tr class='tot'><td><strong>{fill(fa['cat_total'])}</strong></td><td class='num'><strong>{ct['opus']['items']}</strong></td><td class='num'><strong>{ct['gpt']['items']}</strong></td>"
                      f"<td class='num'><strong>{ct['opus']['items'] + ct['gpt']['items']}</strong></td><td class='num'><strong>{ct['opus']['prompt']} / {ct['gpt']['prompt']}</strong></td><td></td></tr>")
    if [r["id"] for r in fa["categories"]] != [r["id"] for r in cat_v["rows"]]:
        warnings.append("the category rows of the page and of the metrics differ")
    tt = {t["id"]: t for t in M["taxonomy_types"]["value"]}
    tax_rows = ""
    for row in fa["categories"]:
        tax_rows += f"<tr class='occ'><td colspan='{len(tf['head'])}'>{esc(row['id'])}. {esc(row['name'])}</td></tr>"
        for tid in row["types"]:
            t, (tname, tdef) = tt[tid], tf["types"][tid]
            groups = collections.OrderedDict()
            for k in t["item_keys"]:
                cand, task8, item = k.split("|")
                groups.setdefault(cand, collections.OrderedDict()).setdefault(TASK_NAME[task8], []).append(int(item))
            keys = "<br>".join(f"{esc(SHORT[c_])}: " + "; ".join(f"{esc(tn)} {', '.join(str(i) for i in sorted(its))}" for tn, its in groups[c_].items())
                               for c_ in ("opus", "gpt") if c_ in groups)
            crit = " / ".join(str(sum(1 for it in by_id[tid]["items"] if it["candidate"] == m and is_crit(it))) for m in ("opus", "gpt"))
            prm = " / ".join(str(sum(1 for it in by_id[tid]["items"] if it["candidate"] == m and src_of.get((m, it["task_id"], it["item"])) == "prompt")) for m in ("opus", "gpt"))
            tax_rows += (f"<tr><td><strong>{esc(tname)}</strong><br><span class='small'>{esc(tdef)}</span></td><td>{sev_badge(t['severity'])}</td>"
                         f"<td class='num'>{tasks_txt(t['per_model']['opus']['items'], t['per_model']['opus']['tasks'])}</td><td class='num'>{tasks_txt(t['per_model']['gpt']['items'], t['per_model']['gpt']['tasks'])}</td>"
                         f"<td class='num'>{prm}</td><td class='num'>{crit}</td><td class='small'>{keys}</td></tr>")
    if set(tf["types"]) != set(tt):
        warnings.append("the taxonomy display names do not cover every failure type exactly once")
    c_flag = collections.Counter()
    for tid in next(r for r in fa["categories"] if r["id"] == "C")["types"]:
        c_flag.update(tt[tid]["flagged_by"])
    if "deterministic" in c_flag:
        warnings.append("a category C failure was flagged by a code grader; the taxonomy note says none was")
    tax_html = (f"<details><summary>{fill(fa['types_title'])}</summary>" + table(tf["head"], tax_rows, "cat tax")
                + "".join(f"<p class='small'>{lead(n)}</p>" for n in tf["notes"]) + "</details>")
    crops = {(c["card"], c["cand"], c["kind"]): c for c in crops_meta["crops"]}

    def fig(c, caption):
        w, h = c["png_px"]
        cap_w = "" if c["card"] == "A" else f"style='max-width:{round(w / 2)}px' "  # B, C: no upscaling past 1x
        if c["kind"] == "chart":
            alt = f"{SHORT[c['cand']]}, {c['sheet']} chart" + (f" \"{c['chart']['chart_title']}\"" if c["chart"]["chart_title"] else "") + ": categories " + ", ".join(c["chart"]["categories"]) + "; no UPC on the chart."
        elif c["kind"] == "doc_paragraph":
            alt = f"{SHORT[c['cand']]}, {c['file']}, page {c['page']}, heading \"{c['text']['heading']}\": {c['text']['paragraph']}"
        else:
            alt = (f"{SHORT[c['cand']]}, {c['sheet']} {c['range']}, columns " + ", ".join(c["cells"]["header"]) + ": "
                   + "; ".join(f"row {r[0]} " + ", ".join(v for v in r[1:] if v) for r in c["cells"]["rows"])
                   + (". The Store 1 Total row is boxed." if c["mark"] == "box_row" else ". A dashed line marks Store 2 following Shiseido with no Store 1 subtotal." if c["mark"] == "line_before" else "."))
        return (f"<figure class='crop'><div class='paper'><a href='img/{esc(c['png'])}'><img src='img/{esc(c['png'])}' width='{round(w / 2)}' height='{round(h / 2)}' {cap_w}alt='{esc(alt)}' loading='lazy'></a></div>"
                f"<figcaption>{esc(caption)}</figcaption></figure>")
    cap = lambda tpl, c, **kw: re.sub(r"\{\{(\w+)\}\}", lambda m: str({"cand": SHORT[c["cand"]], "sheet": c["sheet"], "range": c["range"], **kw}[m.group(1)]), tpl)
    a_items_txt = " / ".join(str(i) for i in a_items)
    crops_a = (f"<div class='crops'>{fig(crops[('A', 'opus', 'store_boundary')], cap(cdf['crop_caption'], crops[('A', 'opus', 'store_boundary')]))}"
               f"{fig(crops[('A', 'gpt', 'store_boundary')], cap(cdf['crop_caption'] + cdf['crop_items'], crops[('A', 'gpt', 'store_boundary')], items=a_items_txt))}</div>"
               f"<p class='note'>{fill(cdf['mark_box'])} {fill(cdf['mark_line'])}</p><div class='divider'><span>{fill(cdf['grand_label'])}</span></div>"
               f"<div class='crops'>{fig(crops[('A', 'opus', 'grand_total')], cap(cdf['crop_caption'], crops[('A', 'opus', 'grand_total')]))}"
               f"{fig(crops[('A', 'gpt', 'grand_total')], cap(cdf['crop_caption'], crops[('A', 'gpt', 'grand_total')]))}</div><p class='note'>{fill(cdf['provenance'])}</p>")
    b_run = {c["cand"]: c["run_uuid"] for c in crops_meta["crops"] if c["card"] == "B"}
    crops_b = ("<div class='crops one'>" + "".join(fig(crops[("B", m, "chart")], cap(cdf["b_caption"], crops[("B", m, "chart")], item=ck["B"]["item"])) for m in ("opus", "gpt"))
               + f"</div><p class='note'>{fill(cdf['b_provenance'], {'opus_run': b_run['opus'], 'gpt_run': b_run['gpt']})}</p>")
    if any(c["chart"]["upcs"] and any(u in c["chart"]["categories"] for u in c["chart"]["upcs"]) for c in crops_meta["crops"] if c["kind"] == "chart"):
        warnings.append("a card B chart shows a UPC")
    cc_ = {m: crops[("C", m, "doc_paragraph")] for m in ("opus", "gpt")}
    crops_c = ("<div class='crops one'>" + "".join(fig(cc_[m], cap(cdf["c_caption"] + (cdf["c_item_cap"] if m == "gpt" else ""), cc_[m], file=cc_[m]["file"], page=cc_[m]["page"],
                                                                  heading=cc_[m]["text"]["heading"], item=ck["C"]["item"])) for m in ("opus", "gpt"))
               + f"</div><p class='note'>{fill(cdf['c_provenance'], {'opus_run': cc_['opus']['run_uuid'], 'gpt_run': cc_['gpt']['run_uuid']})}</p>")
    cards_html = ""
    for c in cd["items"]:
        body = "".join(f"<p>{lead(l)}</p>" for l in c["lines"])
        ev = {"A": crops_a, "B": crops_b, "C": crops_c}[c["id"]]
        body += ev if c["id"] == "A" else f"<details class='mini'><summary>{fill(c['details_title'])}</summary>{ev}</details>"
        cards_html += f"<article class='card'><h4>{fill(c['title'])}</h4>{body}</article>"
    failures_html = (f'<section id="failures"><h2>{fill(fa["heading"])}</h2>'
                     f'<h3>{fill(fa["cat_title"])}</h3><p class="note">{fill(fa["cat_sub"])}</p>' + table(fa["cat_head"], cat_rows_html, "cat cats")
                     + f'<p class="note">{fill(fa["severity_note"])}</p>{tax_html}'
                     f'<h3>{fill(fa["examples_title"])}</h3><p class="note">{fill(fa["examples_sub"])}</p><div class="cards">{cards_html}</div></section>')
    # ---- data opportunity
    gap_rows = "".join(f"<tr><td><strong>{esc(row['id'])}. {esc(row['name'])}</strong></td><td>"
                       + "<br>".join(f"{esc(SHORT[m])}: {fill(da['seen_fmt'], {'n': data['seen_here'][m], 'p': data['per_model'][m]['prompt']})}" for m in ("gpt", "opus"))
                       + f"</td><td>{fill(da['gaps'][row['id']][0])}</td><td>{fill(da['gaps'][row['id']][1])}</td></tr>" for row, data in zip(fa["categories"], cat_v["rows"]))
    data_html = (f'<section id="data"><h2>{fill(da["heading"])}</h2><p>{fill(da["thesis"])}</p>'
                 f'<p class="sub">{fill(da["why_title"])}</p><ul class="bul">{"".join(f"<li>{lead(x)}</li>" for x in da["why_points"])}</ul>'
                 f'<div class="card spec"><h4>{fill(da["card_title"])}</h4><p><strong>{fill(da["card_lead"])}</strong></p><ol>{"".join(f"<li>{fill(x)}</li>" for x in da["components"])}</ol>'
                 f'<p>{" ".join(lead(x) for x in da["seed"])}</p></div>'
                 f'<p class="note">{lead(da["per_model"])}</p><p class="note">{lead(da["pilot"])}</p><p class="note">{lead(da["cost"])}</p>'
                 f'<details><summary>{fill(da["more_title"])}</summary><p class="sub">{fill(da["gap_title"])}</p>' + table(da["gap_head"], gap_rows, "cat gaps")
                 + f'<p class="sub">{fill(da["uses_title"])}</p><ul class="bul">{"".join(f"<li>{lead(u)}</li>" for u in da["uses"])}</ul></details>'
                 f'<details><summary>{fill(da["details_title"])}</summary><dl class="we">{"".join(f"<dt>{esc(k)}</dt><dd>{fill(v)}</dd>" for k, v in wf["items"])}</dl></details></section>')
    # ---- method and limits
    steps = ""
    for n, text in me["steps"]:
        inner = f"<details class='inbox'><summary>{fill(me['example_title'])}</summary><p>{fill(me['example'])}</p></details>" if n == "1" else ""
        steps += f"<li><span class='num'>{esc(n)}</span><div><p>{fill(text)}</p>{inner}</div></li>"
    method_html = (f'<section id="method"><h2>{fill(me["heading"])}</h2><p class="deck2">{fill(me["sub"])}</p>'
                   f'<div class="strip">{"".join(f"<div><span>{fill(k)}</span>{fill(v)}</div>" for k, v in me["strip"])}</div><p class="note">{lead(me["tasks_line"])}</p><p class="note">{lead(me["tooling"])}</p>'
                   f'<details><summary>{fill(me["steps_title"])}</summary><ol class="steps">{steps}</ol></details>'
                   f'<details><summary>{fill(me["config_title"])}</summary><ol class="cfg">{"".join(f"<li>{fill(x)}</li>" for x in me["config"])}</ol></details>'
                   f'<details><summary>{fill(me["design_title"])}</summary><ul class="bul">{"".join(f"<li>{lead(x)}</li>" for x in me["design"])}</ul></details>'
                   f'<h3>{fill(me["reliability_title"])}</h3><p>{fill(me["review_title"])}</p>'
                   f'<details><summary>{fill(me["review_scope_title"])}</summary><ul class="bul">{"".join(f"<li>{lead(s)}</li>" for s in me["review_scope"])}</ul></details>'
                   f'<p class="sub">{fill(me["reliability_sub"])}</p>'
                   f'<div class="tiles t2">{"".join(f"<div class=tile><div class=v>{fill(v)}</div><div class=l>{fill(l)}</div></div>" for v, l in me["reliability_tiles"])}</div>'
                   f'<p class="note">{fill(me["selection_note"])}</p><p class="note">{fill(me["judge_note"])}</p>'
                   f'<h3>{fill(me["limits_title"])}</h3><ul class="bul">{"".join(f"<li>{lead(x)}</li>" for x in me["limits"])}</ul></section>')
    ft = co["footer"]["links"]
    footer_html = (f'<footer><a href="{esc(repo)}">{esc(ft[0])}</a> · <a href="{esc(report_url)}">{esc(ft[1])}</a> · <a href="data/metrics.json">{esc(ft[2])}</a> · '
                   f'{fill(co["footer"]["built"])}</footer>')
    nav = "".join(f'<a href="#{esc(i)}">{esc(t)}</a>' for i, t in co["nav"]) + f'<a href="{esc(repo)}">GitHub</a>'
    body_html = "\n".join((findings_html, results_html, failures_html, data_html, method_html, footer_html))
    # ---- term check on the page (text, alt and aria labels; URLs excluded)
    scan = re.sub(r'(href|src)="[^"]*"|(href|src)=\'[^\']*\'', "", body_html + nav)
    hits = sorted({t for t in FORBIDDEN if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", html.unescape(scan), flags=re.I)})
    if hits:
        warnings.append("forbidden terms on the page: " + ", ".join(hits))
    metric("term_check", {"forbidden": list(FORBIDDEN), "hits": hits}, "site/index.html (text, alt and aria labels; link targets excluded)", "computed at build time")
    if final and (pending or warnings):
        raise SystemExit("final build refused:\n- " + "\n- ".join([f"block {p} is {content[p]['status']}" for p in pending] + warnings))
    draft = not final
    banner = ("<div class='banner' role='status'><strong>Draft build, not for publication.</strong> Pending: " + esc("; ".join(pending + warnings)) + ".</div>") if draft and not preview else ""
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(fi['title'])}</title>
<meta name="description" content="A diagnostic evaluation of Claude Opus 5.5 and GPT-6.1-sol on {len(order)} GDPval tasks: task verdicts, author-reviewed failures and a dataset proposal.">
<style>
:root {{ --bg:#fbfaf7; --surface:#ffffff; --ink:#1b1b1a; --ink2:#4d4c48; --muted:#6f6e69; --rule:#e2e0d8; --row:#dcdad2; --accent:#1f5fa8; --accent-ink:#ffffff; --tag:#eef3fa;
  --g1:#76756f; --g2:#a4a39d; --g3:#d2d1cb; --g1-ink:#ffffff; --g2-ink:#1b1b1a; --g3-ink:#1b1b1a;
  --pass:#1f7a3a; --fail:#b3261e; --nc:#8a5a00; --on-pass:#ffffff; --on-fail:#ffffff; --on-nc:#ffffff; --sev-high:#b3261e; --sev-medium:#8a5a00; --sev-low:#5f6b78;
  --fs-0:.875rem; --fs-1:1.0625rem; --fs-2:1.1875rem; --fs-3:1.375rem; --fs-4:2.125rem; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#161614; --surface:#1f1f1d; --ink:#ecebe6; --ink2:#c4c3bb; --muted:#9a9993; --rule:#33332f; --row:#3d3d38; --accent:#7fb0ec; --accent-ink:#0f1a2b; --tag:#22303f;
  --g1:#7d7c76; --g2:#5f5e58; --g3:#4a4944; --g1-ink:#ffffff; --g2-ink:#ecebe6; --g3-ink:#ecebe6; --pass:#5fc27a; --fail:#f28b82; --nc:#e0b25c; --on-pass:#0d1f12; --on-fail:#2a0d0b; --on-nc:#2a1d03; --sev-high:#f28b82; --sev-medium:#e0b25c; --sev-low:#a6b3c2; }} }}
:root[data-theme="dark"] {{ --bg:#161614; --surface:#1f1f1d; --ink:#ecebe6; --ink2:#c4c3bb; --muted:#9a9993; --rule:#33332f; --row:#3d3d38; --accent:#7fb0ec; --accent-ink:#0f1a2b; --tag:#22303f;
  --g1:#7d7c76; --g2:#5f5e58; --g3:#4a4944; --g1-ink:#ffffff; --g2-ink:#ecebe6; --g3-ink:#ecebe6; --pass:#5fc27a; --fail:#f28b82; --nc:#e0b25c; --on-pass:#0d1f12; --on-fail:#2a0d0b; --on-nc:#2a1d03; --sev-high:#f28b82; --sev-medium:#e0b25c; --sev-low:#a6b3c2; }}
html {{ color-scheme: light dark; scroll-padding-top: 3.2rem; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size:var(--fs-1); line-height:1.55; }}
h1, h2, h3, h4 {{ font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, "Times New Roman", serif; font-weight:600; letter-spacing:-.005em; line-height:1.2; }}
main {{ max-width: 66rem; margin: 0 auto; padding: 0 16px 3.5rem; }}
header.top {{ position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--rule); }}
header.top .in {{ max-width:66rem; margin:0 auto; padding:.7rem 16px; font-size:var(--fs-0); }}
nav {{ display:flex; flex-wrap:nowrap; gap:.9rem; overflow-x:auto; white-space:nowrap; scrollbar-width:none; }} nav::-webkit-scrollbar {{ display:none; }}
nav a {{ color:var(--ink2); text-decoration:none; }} nav a:hover {{ color:var(--accent); text-decoration:underline; }}
h1 {{ font-size:var(--fs-4); margin:2rem 0 .6rem; }} h2 {{ font-size:var(--fs-3); margin:2.6rem 0 .8rem; padding-top:1.2rem; border-top:1px solid var(--rule); }} h3 {{ font-size:var(--fs-2); margin:1.6rem 0 .5rem; }} h4 {{ font-size:var(--fs-1); margin:0 0 .5rem; }}
p {{ margin:.6rem 0; }} a {{ color:var(--accent); }} .deck {{ color:var(--ink2); font-size:var(--fs-2); line-height:1.5; margin:0 0 1rem; }} .deck2 {{ color:var(--ink2); margin:0 0 .8rem; }}
.muted {{ color:var(--muted); }} .small {{ font-size:var(--fs-0); }} .mono, code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:.85em; }}
.num, .tile .v {{ font-variant-numeric: tabular-nums; }}
.c-pass {{ color:var(--pass); font-weight:700; }} .c-fail {{ color:var(--fail); font-weight:700; }} .c-nc {{ color:var(--nc); font-weight:700; }}
ul.bul {{ padding-left:1.2rem; margin:.6rem 0; }} ul.bul > li {{ margin:.35rem 0; }}
.tiles {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:.75rem; margin:1.1rem 0 .8rem; }} .tiles.t2 {{ grid-template-columns: repeat(2, 1fr); }}
.tile, .card, details {{ border:1px solid var(--rule); border-radius:4px; background:var(--surface); }}
.tile {{ padding:.75rem .9rem; }} .tile .v {{ font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; font-size:1.75rem; font-weight:600; line-height:1.1; }} .tile .l {{ color:var(--ink2); font-size:var(--fs-0); margin-top:.2rem; }} .tile .s {{ color:var(--muted); font-size:.8rem; margin-top:.15rem; }}
.note {{ font-size:var(--fs-0); color:var(--ink2); }} .note strong, .setup strong {{ color:var(--ink); }}
.fig {{ margin:.8rem 0 .4rem; }}
.sev {{ display:inline-block; font-size:.74rem; font-weight:700; letter-spacing:.02em; text-transform:uppercase; padding:0 .4rem; border-radius:3px; border:1px solid currentColor; }}
.sev-high {{ color:var(--sev-high); }} .sev-medium {{ color:var(--sev-medium); }} .sev-low {{ color:var(--sev-low); }}
details {{ padding:.45rem .9rem; margin:.7rem 0; }} summary {{ cursor:pointer; font-weight:600; font-size:var(--fs-0); color:var(--ink); }} summary::marker {{ color:var(--accent); }} details[open] > summary {{ margin-bottom:.4rem; }}
details > p, details li, details dd {{ font-size:var(--fs-0); }} details.mini {{ padding:.3rem .7rem; margin:.5rem 0 0; }}
table {{ border-collapse:collapse; width:100%; font-size:var(--fs-0); margin:.6rem 0; background:var(--surface); }} th, td {{ text-align:left; vertical-align:top; padding:.4rem .5rem; border-bottom:1px solid var(--rule); }} th {{ color:var(--ink2); font-weight:600; font-size:.8rem; }}
td.num {{ white-space:nowrap; }} .tw {{ overflow-x:auto; max-width:100%; }} tr.occ td {{ font-size:.78rem; font-weight:700; color:var(--ink2); background:var(--bg); padding:.25rem .5rem; }} tr.tot td {{ border-top:2px solid var(--ink); }}
.pill {{ display:inline-block; border-radius:3px; padding:0 .45rem; font-size:.78rem; font-weight:700; line-height:1.5; }} .pill-pass {{ background:var(--pass); color:var(--on-pass); }} .pill-fail {{ background:var(--fail); color:var(--on-fail); }} .pill-not_confirmed {{ background:var(--nc); color:var(--on-nc); }}
em.fl {{ font-style:normal; color:var(--ink2); margin-left:.3rem; }} .src {{ display:inline-block; font-size:.72rem; font-weight:600; padding:0 .35rem; margin-left:.3rem; border-radius:3px; border:1px solid var(--rule); color:var(--ink2); white-space:nowrap; }}
.src-prompt {{ border-color:var(--ink2); color:var(--ink); }} tr.tot2 td {{ color:var(--ink2); }} p.sub {{ font-weight:600; font-size:var(--fs-0); margin:1rem 0 .3rem; }}
ul.keyl {{ list-style:none; padding:0; margin:.5rem 0; font-size:var(--fs-0); }} ul.keyl li {{ margin:.3rem 0; }}
.sw {{ display:inline-block; width:.75rem; height:.75rem; margin-right:.5rem; vertical-align:-.05rem; border-radius:1px; }} .seg-accent-bg {{ background:var(--accent); }} .seg-g1-bg {{ background:var(--g1); }} .seg-g2-bg {{ background:var(--g2); }} .seg-g3-bg {{ background:var(--g3); }}
.cards {{ display:grid; grid-template-columns:1fr; gap:.9rem; margin-top:1rem; }} .card {{ padding:.9rem 1.1rem; overflow-wrap:anywhere; }} .card p {{ margin:.4rem 0; font-size:var(--fs-0); line-height:1.5; }}
.card.spec ol {{ margin:.4rem 0 .5rem; padding-left:1.3rem; font-size:var(--fs-0); }} .card.spec li {{ margin:.2rem 0; }}
.crops {{ display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:.9rem; margin:.7rem 0 .3rem; }} .crops.one {{ grid-template-columns:1fr; }} .crop {{ margin:0; }} .crop .paper {{ background:#ffffff; border:1px solid var(--rule); border-radius:3px; padding:4px; }}
.crop img {{ display:block; width:100%; height:auto; }} .crop figcaption {{ font-size:.8rem; color:var(--ink2); margin-top:.25rem; }}
.divider {{ display:flex; align-items:center; gap:.6rem; margin:.9rem 0 .2rem; font-size:.8rem; font-weight:600; color:var(--ink2); }} .divider::before, .divider::after {{ content:""; flex:1; border-top:1px dashed var(--muted); }}
.strip {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:.6rem; margin:.8rem 0 .4rem; }} .strip div {{ background:var(--surface); border:1px solid var(--rule); border-top:3px solid var(--accent); border-radius:4px; padding:.6rem .75rem; font-size:var(--fs-0); }}
.strip span {{ display:block; font-size:.72rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); margin-bottom:.2rem; }}
ol.steps {{ list-style:none; padding:0; margin:.6rem 0 .4rem; display:grid; grid-template-columns: repeat(4, 1fr); gap:.75rem; }} ol.steps li {{ border:1px solid var(--rule); border-radius:4px; background:var(--bg); padding:.7rem .8rem; display:flex; gap:.6rem; }} ol.steps li p {{ margin:0; }}
ol.steps .num {{ flex:none; width:1.6rem; height:1.6rem; border-radius:50%; background:var(--accent); color:var(--accent-ink); font-weight:700; display:flex; align-items:center; justify-content:center; font-size:var(--fs-0); }}
details.inbox {{ margin:.5rem 0 0; padding:.3rem .5rem; }} ol.cfg {{ padding-left:1.3rem; margin:.4rem 0; }} ol.cfg li {{ margin:.3rem 0; }}
dl.we dt {{ font-weight:600; margin-top:.5rem; font-size:var(--fs-0); }} dl.we dd {{ margin:.1rem 0 0; }}
.chart-svg {{ display:block; width:100%; height:auto; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-variant-numeric: tabular-nums; }}
.chart-svg text {{ fill:var(--ink); }} .chart-svg .rl {{ fill:var(--ink2); }} .chart-svg .leader {{ stroke:var(--ink2); stroke-width:1; fill:none; }}
.seg-pass {{ fill:var(--pass); }} .seg-fail {{ fill:var(--fail); }} .seg-nc {{ fill:var(--nc); }} .chart-svg .seg-pass-t {{ fill:var(--on-pass); }} .chart-svg .seg-fail-t {{ fill:var(--on-fail); }} .chart-svg .seg-nc-t {{ fill:var(--on-nc); }}
.seg-accent {{ fill:var(--accent); }} .seg-g1 {{ fill:var(--g1); }} .seg-g2 {{ fill:var(--g2); }} .seg-g3 {{ fill:var(--g3); }}
.chart-svg .seg-accent-t {{ fill:var(--accent-ink); }} .chart-svg .seg-g1-t {{ fill:var(--g1-ink); }} .chart-svg .seg-g2-t {{ fill:var(--g2-ink); }} .chart-svg .seg-g3-t {{ fill:var(--g3-ink); }}
.v-narrow {{ display:none; }} @media (max-width: 52rem) {{ .v-wide {{ display:none; }} .v-narrow {{ display:block; max-width:24rem; }} }}
.banner {{ background:#fff3cd; color:#5a4300; padding:.6rem 16px; font-size:var(--fs-0); }} a, .mono {{ overflow-wrap:anywhere; }}
footer {{ color:var(--muted); font-size:var(--fs-0); border-top:1px solid var(--rule); margin-top:2.5rem; padding-top:.9rem; }}
@media (max-width: 52rem) {{ ol.steps {{ grid-template-columns:1fr; }} .tiles {{ grid-template-columns: repeat(2, 1fr); }} .strip {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width: 40rem) {{ body {{ font-size:1rem; }} h1 {{ font-size:1.6rem; }} .deck {{ font-size:1.05rem; }} .crops {{ grid-template-columns:1fr; }} .strip, .tiles.t2 {{ grid-template-columns:1fr; }}
  table.cats, table.gaps, table.tax {{ min-width:34rem; }} table.cats td:first-child {{ min-width:11rem; }} table {{ font-size:.8rem; }} }}
@media (max-width: 30rem) {{ .tiles {{ grid-template-columns:1fr; gap:.5rem; }} .tile {{ display:grid; grid-template-columns:6.5rem 1fr; column-gap:.75rem; align-items:baseline; padding:.55rem .8rem; }} .tile .v {{ grid-row:span 2; font-size:1.5rem; }} .tile .l, .tile .s {{ margin-top:0; }} }}
</style>
</head>
<body>
{banner}
<header class="top"><div class="in"><nav aria-label="Sections">{nav}</nav></div></header>
<main>
{body_html}
</main>
</body>
</html>
"""
    if preview:
        with open(preview, "w", encoding="utf-8") as f:
            f.write(page)
    else:
        os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        doc = {"generated_at": generated, "build": "final" if final else "draft", "pending": pending, "warnings": warnings, "sources": sources, "metrics": M}
        text = json.dumps(doc, indent=1, default=str, ensure_ascii=False)
        if "/Users/" in text or "~/" in text or "turing-eval-runs" in text:
            raise SystemExit("metrics.json would name a path outside the repository")
        with open(os.path.join(SITE, "data", "metrics.json"), "w", encoding="utf-8") as f:
            f.write(text)
    wide, narrow = visible_counts(page, {"v-narrow"}), visible_counts(page, {"v-wide"})
    crop_words = {c["png"]: words(" ".join(c["cells"]["header"] + [v for r in c["cells"]["rows"] for v in r[1:]])) for c in crops_meta["crops"] if c["card"] == "A"}
    print(json.dumps({"build": "preview" if preview else ("final" if final else "draft"), "pending": pending, "warnings": warnings,
                      "visible_words_wide": dict(wide.counts, total=sum(wide.counts.values())), "visible_words_narrow": dict(narrow.counts, total=sum(narrow.counts.values())),
                      "card_a_crop_cell_words": dict(crop_words, total=sum(crop_words.values())), "out": preview or os.path.join(SITE, "index.html")}, indent=1))


if __name__ == "__main__":
    main()
