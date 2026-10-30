#!/usr/bin/env python
"""Dump the structure and content of every task input and expert deliverable for
human review: sheets, dimensions, header rows, formulas, pivot caches, charts,
defined names (xlsx); paragraphs and tables (docx); slides, shapes, charts,
tables (pptx); pages and text (pdf). Output is one Markdown file per task under
a grader-only directory. Nothing here is model-visible.

Usage:
    python scripts/inspect_materials.py --tasks data/selected_tasks.json \
        --inputs-dir data/inputs --gold-dir private/gold --rubric-dir private/rubric \
        --prompts-dir data/prompts --out-dir private/checks/materials
"""
import argparse
import json
import os
import sys
import zipfile

import openpyxl
from docx import Document
from pptx import Presentation
from pptx.util import Emu
import fitz  # pymupdf

MAX_ROWS = 40
MAX_COLS = 20


def fmt(v):
    if v is None:
        return ""
    s = str(v)
    return s.replace("|", "\\|").replace("\n", " ")[:60]


def dump_xlsx(path, out, max_rows=MAX_ROWS):
    out.append(f"\n### XLSX: {os.path.basename(path)}\n")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    pivots = [n for n in names if "pivotCache" in n or "pivotTable" in n]
    charts = [n for n in names if n.startswith("xl/charts/chart")]
    drawings = [n for n in names if n.startswith("xl/drawings/") and n.endswith(".xml")]
    out.append(f"- zip parts: pivotCache/pivotTable={len(pivots)}, charts={len(charts)}, drawings={len(drawings)}, media={sum(1 for n in names if n.startswith('xl/media/'))}")
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    if wb_f.defined_names:
        out.append(f"- defined names: {list(wb_f.defined_names.keys())[:20]}")
    for ws in wb_f.worksheets:
        wv = wb_v[ws.title]
        n_formula = 0
        n_cells = 0
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    n_cells += 1
                    if isinstance(c.value, str) and c.value.startswith("="):
                        n_formula += 1
        out.append(f"\n#### sheet '{ws.title}' dims={ws.dimensions} max_row={ws.max_row} max_col={ws.max_column} nonempty={n_cells} formulas={n_formula} merged={len(ws.merged_cells.ranges)} charts={len(getattr(ws, '_charts', []))} images={len(getattr(ws, '_images', []))} tables={list(ws.tables.keys())} state={ws.sheet_state}")
        if ws.sheet_state != "visible":
            out.append("  (hidden sheet)")
        cols = min(ws.max_column, MAX_COLS)
        shown = 0
        for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_rows), max_col=cols), start=1):
            vals = []
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    cached = wv[c.coordinate].value
                    vals.append(f"{fmt(v)} ⇒ {fmt(cached)}")
                else:
                    vals.append(fmt(v))
            if any(vals):
                out.append(f"| {r_idx} | " + " | ".join(vals) + " |")
                shown += 1
        if ws.max_row > max_rows:
            out.append(f"  ... ({ws.max_row - max_rows} more rows not shown)")
        # formulas sample beyond the shown rows
        extra = []
        for row in ws.iter_rows(min_row=max_rows + 1, max_row=ws.max_row):
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    extra.append(f"{c.coordinate}: {fmt(c.value)} ⇒ {fmt(wv[c.coordinate].value)}")
                    if len(extra) >= 15:
                        break
            if len(extra) >= 15:
                break
        if extra:
            out.append("  formula samples (later rows): " + "; ".join(extra))


def dump_docx(path, out):
    out.append(f"\n### DOCX: {os.path.basename(path)}\n")
    d = Document(path)
    paras = [p for p in d.paragraphs if p.text.strip()]
    out.append(f"- paragraphs(nonempty)={len(paras)} tables={len(d.tables)} inline_shapes={len(d.inline_shapes)} sections={len(d.sections)}")
    for p in paras:
        style = p.style.name if p.style is not None else ""
        out.append(f"- [{style}] {p.text.strip()}")
    for ti, t in enumerate(d.tables):
        out.append(f"\n  table {ti}: {len(t.rows)}x{len(t.columns)}")
        for r in t.rows[:MAX_ROWS]:
            out.append("  | " + " | ".join(fmt(c.text) for c in r.cells) + " |")


def dump_pptx(path, out):
    out.append(f"\n### PPTX: {os.path.basename(path)}\n")
    prs = Presentation(path)
    out.append(f"- slides={len(prs.slides)} size={Emu(prs.slide_width).inches:.2f}x{Emu(prs.slide_height).inches:.2f} in")
    for si, s in enumerate(prs.slides, 1):
        out.append(f"\n#### slide {si} layout='{s.slide_layout.name}' shapes={len(s.shapes)}")
        for sh in s.shapes:
            kind = sh.shape_type
            line = f"- shape '{sh.name}' type={kind}"
            if sh.has_text_frame and sh.text_frame.text.strip():
                line += f" text={fmt(sh.text_frame.text)!r}"
            if getattr(sh, "has_chart", False) and sh.has_chart:
                ch = sh.chart
                line += f" CHART type={ch.chart_type} series={len(list(ch.plots[0].series)) if ch.plots else 0}"
                try:
                    cats = list(ch.plots[0].categories)
                    vals = list(ch.plots[0].series[0].values)
                    line += f" cats={cats[:14]} vals={[round(v, 4) if isinstance(v, float) else v for v in vals[:14]]}"
                except Exception as exc:  # noqa: BLE001
                    line += f" (chart data not readable: {exc})"
            if getattr(sh, "has_table", False) and sh.has_table:
                tbl = sh.table
                line += f" TABLE {len(tbl.rows)}x{len(tbl.columns)}"
                out.append(line)
                for r in tbl.rows:
                    out.append("  | " + " | ".join(fmt(c.text) for c in r.cells) + " |")
                continue
            if kind is not None and "PICTURE" in str(kind):
                line += " (picture)"
            out.append(line)


def dump_pdf(path, out, max_chars=6000):
    out.append(f"\n### PDF: {os.path.basename(path)}\n")
    doc = fitz.open(path)
    out.append(f"- pages={doc.page_count} metadata={ {k: v for k, v in doc.metadata.items() if v} }")
    for i, page in enumerate(doc, 1):
        text = page.get_text("text")
        imgs = page.get_images(full=True)
        draws = page.get_drawings()
        out.append(f"\n#### page {i} size={page.rect.width:.0f}x{page.rect.height:.0f} chars={len(text)} images={len(imgs)} vector_paths={len(draws)}")
        out.append(text[:max_chars].rstrip())
        if len(text) > max_chars:
            out.append(f"... ({len(text) - max_chars} more chars)")


def dump_file(path, out):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            dump_xlsx(path, out)
        elif ext == ".docx":
            dump_docx(path, out)
        elif ext == ".pptx":
            dump_pptx(path, out)
        elif ext == ".pdf":
            dump_pdf(path, out)
        else:
            out.append(f"\n### OTHER: {os.path.basename(path)} ({os.path.getsize(path)} bytes)\n")
    except Exception as exc:  # noqa: BLE001
        out.append(f"\n### ERROR reading {os.path.basename(path)}: {type(exc).__name__}: {exc}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--inputs-dir", default="data/inputs")
    ap.add_argument("--gold-dir", default="private/gold")
    ap.add_argument("--rubric-dir", default="private/rubric")
    ap.add_argument("--prompts-dir", default="data/prompts")
    ap.add_argument("--out-dir", default="private/checks/materials")
    ap.add_argument("--only", nargs="*", help="task id prefixes to limit to")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    tasks = json.load(open(args.tasks))["tasks"]
    for t in tasks:
        tid = t["task_id"]
        if args.only and not any(tid.startswith(p) for p in args.only):
            continue
        out = [f"# {tid}\n", f"occupation: {t['occupation']} | group: {t['group']}\n"]
        out.append("## PROMPT\n")
        out.append(open(os.path.join(args.prompts_dir, f"{tid}.txt"), encoding="utf-8").read())
        out.append("\n## INPUT FILES\n")
        idir = os.path.join(args.inputs_dir, tid)
        for name in sorted(os.listdir(idir)) if os.path.isdir(idir) else []:
            dump_file(os.path.join(idir, name), out)
        out.append("\n## EXPERT DELIVERABLES (gold)\n")
        gdir = os.path.join(args.gold_dir, tid)
        for name in sorted(os.listdir(gdir)) if os.path.isdir(gdir) else []:
            dump_file(os.path.join(gdir, name), out)
        out.append("\n## RUBRIC\n")
        items = json.load(open(os.path.join(args.rubric_dir, f"{tid}.json"), encoding="utf-8"))
        out.append(f"items={len(items)} weight_sum={sum(i['score'] for i in items)}\n")
        for i, it in enumerate(items, 1):
            out.append(f"{i}. [+{it['score']}] {it['criterion']}")
        path = os.path.join(args.out_dir, f"{tid}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        print(f"wrote {path} ({sum(len(x) for x in out)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
