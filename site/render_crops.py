"""Render the evidence crops of the three example cards into site/img/.

  card A  weekly sales: both candidates' "Sales by Store" cells (store boundary and grand total)
  card B  weeks of supply: both candidates' out-of-stock chart on "Summary", category axis visible
  card C  PO entry audit: each candidate's Word summary, the paragraph that defines the checks

Steps, all on copies (raw model outputs are never opened for writing):
1. Locate each candidate's deliverable in the formal run store and check its SHA-256 against the run's artifact manifest.
2. Copy it and prepare the copy for display only: card A removes the sheet's PivotTable relationship, so LibreOffice
   shows the saved cells instead of rebuilding the PivotTable (a rebuild shifts rows and relabels "Store 1 Total" as
   "Store 1 Result"). Cell values, cell styles and charts are untouched; Word documents are copied unchanged.
3. Export each range to PDF with LibreOffice inside the frozen sandbox image (no network; site/render_crops_uno.py).
   Cell crops print the grid and the row / column headers, with the column-name row as the title row; chart crops
   print the cell range the chart is anchored in; a Word document is exported whole.
4. Check the rendering against the saved file: every cell token shown (A), every category label the chart references
   and none of the five UPCs (B), or every word of the heading and paragraph shown (C, read from the document). Render
   each PDF at 2x of 100% scale, trim the margin (C: crop to the heading and its paragraph), add the card A marks (a
   box on Opus 5.5's "Store 1 Total" row, a dashed line where GPT-6.1-sol goes from Store 1 to Store 2), and write PNGs
   plus site/img/crops.json (sources, hashes, ranges or paragraphs, the cell values, chart labels or text shown, marks,
   and for C how often the whole document uses "multiple" and "divisib-").

Usage: .venv/bin/python site/render_crops.py   (needs Docker and the sandbox image of config.json)"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pymupdf
from openpyxl import load_workbook
from PIL import Image, ImageChops, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.expanduser("~/turing-eval-runs")
OUT = os.path.join(REPO, "site", "img")
ZOOM = 2 * 96 / 72  # 2x of 100% sheet scale (96 css px per inch)
MODEL = {"opus": "anthropic/claude-opus-5-5", "gpt": "openai/gpt-6.1-sol"}
SALES = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"
WOS = "47ef842d-8eac-4b90-bda8-dd934c228c96"
PO = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
JOBS = [
    {"card": "A", "cand": "opus", "task": SALES, "file": "Weekly Sales Data - Beauty Sales Analysis.xlsx", "sheet": "Sales by Store", "prep": "strip_pivot",
     "crops": [{"kind": "store_boundary", "range": "A11:C15", "header_row": 4, "cols": 3, "mark": "box_row"},
               {"kind": "grand_total", "range": "A354:C356", "header_row": 4, "cols": 3}]},
    {"card": "A", "cand": "gpt", "task": SALES, "file": "Weekly Sales Analysis.xlsx", "sheet": "Sales by Store", "prep": "strip_pivot",
     "crops": [{"kind": "store_boundary", "range": "A13:C16", "header_row": 6, "cols": 3, "mark": "line_before"},
               {"kind": "grand_total", "range": "A317:C319", "header_row": 6, "cols": 3}]},
    {"card": "B", "cand": "opus", "task": WOS, "file": "Top5_UPC_Inventory_Position_Wk28_2025.xlsx", "sheet": "Summary",
     "crops": [{"kind": "chart", "range": "A19:F35", "chart_part": "xl/charts/chart1.xml", "upc_range": "B48:B52"}]},
    {"card": "B", "cand": "gpt", "task": WOS, "file": "Inventory_Health_Top_5_2025_W28.xlsx", "sheet": "Summary",
     "crops": [{"kind": "chart", "range": "A18:E32", "chart_part": "xl/charts/chart1.xml", "upc_range": "B11:B15", "cut_at_row": 32}]},
    {"card": "C", "cand": "opus", "task": PO, "file": "PO_Audit_Error_Summary.docx", "heading": "1. Summary"},
    {"card": "C", "cand": "gpt", "task": PO, "file": "Wholesale_Order_Audit_Summary.docx", "heading": "Method & workbook use"},
]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def run_of(model, task):
    for root in ("runs", "opus/runs", "gpt/runs"):
        for line in open(os.path.join(B, "formal", root, "run_inventory.jsonl"), encoding="utf-8"):
            x = json.loads(line) if line.strip() else {}
            if x.get("kind") == "sample" and x.get("model") == model and x.get("task_id") == task:
                return os.path.join(B, "formal", root, x["run_uuid"]), x["run_uuid"]
    raise SystemExit(f"no formal run for {model} {task}")


def sheet_part(z, sheet):
    wb, rels = z.read("xl/workbook.xml").decode(), z.read("xl/_rels/workbook.xml.rels").decode()
    rid = re.search(r'<sheet [^>]*name="%s"[^>]*r:id="([^"]+)"' % re.escape(sheet), wb) or re.search(r'<sheet [^>]*r:id="([^"]+)"[^>]*name="%s"' % re.escape(sheet), wb)
    target = re.search(r'Target="([^"]+)"', re.search(r'<Relationship [^>]*Id="%s"[^>]*>' % rid.group(1), rels).group(0)).group(1)
    return "xl/" + target.split("xl/")[-1].lstrip("/")


def rewrite(src, dst, part, fn):
    """Copy the workbook zip, passing one part through fn(text) -> (text, count); returns the count."""
    z, count = zipfile.ZipFile(src), None
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
        for info in z.infolist():
            data = z.read(info.filename)
            if info.filename == part:
                text, count = fn(data.decode())
                data = text.encode()
            out.writestr(info, data)
    return count


def strip_pivot(src, dst, sheet):
    part = sheet_part(zipfile.ZipFile(src), sheet)
    rels = part.replace("worksheets/", "worksheets/_rels/") + ".rels"
    pat = r"<Relationship [^>]*pivotTable[^>]*/>"
    return rewrite(src, dst, rels, lambda t: (re.sub(pat, "", t), len(re.findall(pat, t))))


def doc_text(path, heading):
    """The heading paragraph and the next non-empty paragraph of a Word document, and how often the whole document
    (paragraphs and tables) uses "multiple" and "divisib-"."""
    import docx
    d = docx.Document(path)
    paras = [p.text.strip() for p in d.paragraphs]
    i = paras.index(heading)
    body = next(t for t in paras[i + 1:] if t)
    full = " ".join(paras + [c.text for t in d.tables for r in t.rows for c in r.cells]).lower()
    return {"heading": heading, "paragraph": body, "document_terms": {"multiple": len(re.findall(r"\bmultiple", full)), "divisib": len(re.findall(r"divisib", full))}}


def fmt(v):
    return "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v).strip())


def cells(path, sheet, rng, header_row, ncols):
    ws = load_workbook(path, data_only=True)[sheet]
    m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
    r0, r1 = int(m.group(2)), int(m.group(4))
    cols = range(1, ncols + 1)
    return {"header": [fmt(ws.cell(header_row, c).value) for c in cols], "rows": [[r] + [fmt(ws.cell(r, c).value) for c in cols] for r in range(r0, r1 + 1)]}


def chart_labels(path, sheet, part, upc_range):
    """The category labels the chart references (read from the saved cells) and the UPCs that must not be among them."""
    xml = zipfile.ZipFile(path).read(part).decode()
    cat = re.search(r"<(?:c:)?cat>.*?<(?:c:)?f>([^<]+)</(?:c:)?f>", xml, flags=re.S).group(1)
    title = " ".join(re.findall(r"<a:t>([^<]*)</a:t>", re.search(r"<(?:c:)?title>.*?</(?:c:)?title>", xml, flags=re.S).group(0))) if re.search(r"<(?:c:)?chart>\s*<(?:c:)?title>", xml) else None
    ws = load_workbook(path, data_only=True)[sheet]
    rng = cat.split("!")[1].replace("$", "")
    labels = [fmt(c.value) for row in ws[rng] for c in row]
    upcs = [fmt(c.value) for row in ws[upc_range] for c in row]
    return {"category_ref": cat, "categories": labels, "chart_title": title, "upc_cells": upc_range, "upcs": upcs}


def save(c, crop, png):
    crop.save(os.path.join(OUT, png), optimize=True)
    c.update({"png": png, "png_px": list(crop.size), "png_sha256": sha(os.path.join(OUT, png))})
    del c["name"]


def crop_paragraph(c, doc):
    """Crop the page region of the heading and its paragraph: the text blocks from the heading's block through the block
    that ends the paragraph, all of whose words belong to the heading or the paragraph; every word of both must show."""
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    want = norm(c["text"]["heading"] + " " + c["text"]["paragraph"])
    full = " ".join(p.get_text() for p in doc).lower()  # the rendering also covers text boxes, headers and footers
    c["text"]["rendered_terms"] = {"multiple": len(re.findall(r"\bmultiple", full)), "divisib": len(re.findall(r"divisib", full))}
    for page in doc:
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        start = next((i for i, b in enumerate(blocks) if norm(b[4]).startswith(c["text"]["heading"])), None)
        if start is None:
            continue
        rect, i = pymupdf.Rect(blocks[start][:4]), start + 1
        while not norm(page.get_text("text", clip=rect)).endswith(norm(c["text"]["paragraph"])[-40:]):
            if i >= len(blocks) or norm(blocks[i][4]) not in want:
                raise SystemExit(f"{c['file']}: the paragraph after {c['text']['heading']!r} is not a contiguous run of blocks")
            rect |= pymupdf.Rect(blocks[i][:4]); i += 1
        shown = norm(page.get_text("text", clip=rect + (-1, -1, 1, 1)))
        missing = [w for w in want.split() if w not in shown]
        if missing:
            raise SystemExit(f"{c['file']}: words not in the rendering: {missing[:5]}")
        pad = 6 / ZOOM
        pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=rect + (-pad, -pad, pad, pad), alpha=False, annots=False)
        c.update({"page": page.number + 1, "clip_pt": [round(v, 1) for v in rect]})
        save(c, Image.frombytes("RGB", (pix.width, pix.height), pix.samples), f"{c['card'].lower()}_{c['cand']}_summary.png")
        return
    raise SystemExit(f"{c['file']}: heading {c['text']['heading']!r} not found in the rendering")


def main():
    cfg = json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))
    image = cfg["sandbox"]["image_id"]
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="crops-")
    in_dir, pdf_dir = os.path.join(tmp, "in"), os.path.join(tmp, "out")
    os.makedirs(in_dir); os.makedirs(pdf_dir)
    for d in (tmp, in_dir, pdf_dir):
        os.chmod(d, 0o777)
    meta = {"rendered_with": "LibreOffice in the frozen sandbox image " + image[:19] + "…, no network; display-only preparation of copies (card A: PivotTable relationship removed so the saved cells are shown; card C: Word documents unchanged)",
            "crops": []}
    uno_jobs = {}
    for job in JOBS:
        run_dir, run_uuid = run_of(MODEL[job["cand"]], job["task"])
        raw = os.path.join(run_dir, "final", job["file"])
        manifest = json.load(open(os.path.join(run_dir, "artifact_manifest.json"), encoding="utf-8"))
        listed = {os.path.basename(f.get("path") or f.get("relpath") or ""): f.get("sha256") for f in manifest.get("files", [])}
        digest = sha(raw)
        if listed.get(job["file"]) != digest:
            raise SystemExit(f"{job['card']} {job['cand']}: deliverable missing from, or hash different from, the artifact manifest")
        ext = os.path.splitext(job["file"])[1]
        copy = os.path.join(tmp, f"{job['card']}_{job['cand']}{ext}")
        shutil.copyfile(raw, copy)
        shown = os.path.join(in_dir, f"{job['card']}_{job['cand']}_shown{ext}")
        if ext == ".docx":  # the whole document is exported; the heading and its paragraph are cropped below
            shutil.copyfile(copy, shown)
            name = f"{job['card']}_{job['cand']}_doc"
            uno_jobs[os.path.basename(shown)] = [{"out": name + ".pdf"}]
            meta["crops"].append({"card": job["card"], "cand": job["cand"], "task_id": job["task"], "run_uuid": run_uuid, "file": job["file"], "sha256": digest,
                                  "manifest_sha256_checked": True, "sheet": None, "range": None, "header_row": None, "kind": "doc_paragraph", "mark": None,
                                  "hidden_columns": None, "text": doc_text(copy, job["heading"]), "name": name})
            continue
        if job.get("prep") == "strip_pivot":
            if strip_pivot(copy, shown, job["sheet"]) != 1:
                raise SystemExit(f"{job['cand']}: expected exactly one PivotTable relationship on {job['sheet']}")
        else:
            shutil.copyfile(copy, shown)
        exports = uno_jobs.setdefault(os.path.basename(shown), [])
        for c in job["crops"]:
            name = f"{job['card']}_{job['cand']}_{c['range'].replace(':', '-')}"
            exports.append({"sheet": job["sheet"], "range": c["range"], "out": name + ".pdf", "grid": c["kind"] != "chart", "title_row": c.get("header_row")})
            entry = {"card": job["card"], "cand": job["cand"], "task_id": job["task"], "run_uuid": run_uuid, "file": job["file"], "sha256": digest,
                     "manifest_sha256_checked": True, "sheet": job["sheet"], "range": c["range"], "header_row": c.get("header_row"), "kind": c["kind"],
                     "mark": c.get("mark"), "hidden_columns": None, "name": name}
            if c["kind"] == "chart":
                entry["chart"] = chart_labels(copy, job["sheet"], c["chart_part"], c["upc_range"])
                entry["cut_at_row"] = c.get("cut_at_row")
            else:
                entry["cells"] = cells(copy, job["sheet"], c["range"], c["header_row"], c["cols"])
            meta["crops"].append(entry)
    json.dump(uno_jobs, open(os.path.join(in_dir, "jobs.json"), "w", encoding="utf-8"))
    shutil.copyfile(os.path.join(REPO, "site", "render_crops_uno.py"), os.path.join(in_dir, "render_crops_uno.py"))
    subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{in_dir}:/in:ro", "-v", f"{pdf_dir}:/out", image,
                    "/usr/bin/python3", "-I", "/in/render_crops_uno.py", "/in/jobs.json", "/in", "/out"], check=True)
    for c in meta["crops"]:
        pdf = os.path.join(pdf_dir, c["name"] + ".pdf")
        doc = pymupdf.open(pdf)
        if c["kind"] == "doc_paragraph":
            crop_paragraph(c, doc)
            continue
        if len(doc) != 1:
            raise SystemExit(f"{pdf}: expected one page, got {len(doc)}")
        page = doc[0]
        words = page.get_text("words")
        text = " ".join(w[4] for w in words)
        if c["kind"] == "chart":  # the chart shows the labels it references, and no UPC
            for label in c["chart"]["categories"]:
                for token in label.split():
                    if token not in text:
                        raise SystemExit(f"{pdf}: category label token {token!r} not in the rendering")
            if any(u in text for u in c["chart"]["upcs"]):
                raise SystemExit(f"{pdf}: a UPC appears in the chart rendering")
        else:  # the rendered crop shows the saved cells
            for row in [c["cells"]["header"]] + [r[1:] for r in c["cells"]["rows"]]:
                for v in row:
                    for token in str(v).split():
                        if token and token not in text:
                            raise SystemExit(f"{pdf}: cell text {token!r} not in the rendering")
        pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False, annots=False)  # no comment-marker icons
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 12 else 0)
        x0, y0, x1, y1 = diff.getbbox()
        if c.get("cut_at_row"):  # stop above the first text line of the given row (a note under the chart)
            below = [w for w in words if w[4].startswith("¹")]
            if len(below) != 1:
                raise SystemExit(f"{pdf}: expected one note marker in row {c['cut_at_row']}")
            line = [w for w in words if abs(w[3] - below[0][3]) < 4 or abs(w[1] - below[0][1]) < 4]
            cut = int(min(w[1] for w in line) * ZOOM) - 3
            x0, y0, x1, y1 = diff.crop((0, 0, im.width, cut)).getbbox()
        else:
            cut = im.height
        x0, y0, x1, y1 = max(x0 - 6, 0), max(y0 - 6, 0), min(x1 + 6, im.width), min(y1 + 6, cut)
        draw = ImageDraw.Draw(im)
        if c["mark"] == "box_row":
            total = next(w for w in words if w[4] == "Total" and any(v[4] == "Store" and abs(v[1] - w[1]) < 2 for v in words))
            draw.rectangle([x0 + 4, (total[1] - 3) * ZOOM, x1 - 4, (total[3] + 3) * ZOOM], outline=(31, 95, 168), width=5)
        if c["mark"] == "line_before":
            store2 = next(w for w in words if w[4] == "Store" and any(v[4] == "2" and abs(v[1] - w[1]) < 2 for v in words))
            above = max((w for w in words if w[3] <= store2[1] + 1 and w[4] not in ("A", "B", "C")), key=lambda w: w[3])
            y = (above[3] + store2[1]) / 2 * ZOOM
            for xs in range(int(x0 + 4), int(x1 - 4), 22):
                draw.line([xs, y, min(xs + 12, x1 - 4), y], fill=(179, 38, 30), width=5)
        crop = im.crop((x0, y0, x1, y1))
        save(c, crop, ("" if c["card"] == "A" else c["card"].lower() + "_") + f"{c['cand']}_{c['range'].replace(':', '-')}.png")
    json.dump(meta, open(os.path.join(OUT, "crops.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    shutil.rmtree(tmp)
    print(json.dumps([{k: c.get(k) for k in ("png", "png_px", "range", "page", "clip_pt")} for c in meta["crops"]]))


if __name__ == "__main__":
    sys.exit(main())
