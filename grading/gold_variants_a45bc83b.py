"""Gold-derived variants for a45bc83b (GCP migration design): the three expert deliverables as the anchor and as the base
of every variant (python-docx edits of the two documents, PyMuPDF rebuilds of the diagram, file removals and renames),
each with its declared deterministic verdict map for items 1, 2, 3, 5. Judge items (6-25, 31-71) and visual items (4,
26-30, 72) are not asserted here.

Gold baseline (grader a45bc83b-2026-11-01.1): 1, 2, 3, 5 pass (first pass kept in
grading/validation/<task>/gold_first_pass.json). Usage: python -m grading.gold_variants_a45bc83b <out_dir>. Grader side
only; never model-visible."""
import hashlib
import json
import os
import shutil
import sys

from docx import Document
from docx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
SUMMARY, PDF, POC = "Proposed Architecture Summary.docx", "Proposed_Architecture.pdf", "POC_Implementation_Guide.docx"
D_ITEMS = [1, 2, 3, 5]
GOLD_BASELINE = {i: "pass" for i in D_ITEMS}


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


def _strip_numbering(path: str, *, prefix=None) -> None:
    doc = Document(path)
    n = 0
    for p in doc.paragraphs:
        ppr = p._p.pPr
        numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        if numpr is not None:
            ppr.remove(numpr)
            if prefix and p.runs:
                n += 1
                p.runs[0].text = prefix(n) + p.runs[0].text
    doc.save(path)


# ----------------------------------------------------------------------------- mutators (operate on the variant's final dir)
def m_summary_deleted(d):
    os.remove(os.path.join(d, SUMMARY))


def m_pdf_deleted(d):
    os.remove(os.path.join(d, PDF))


def m_poc_deleted(d):
    os.remove(os.path.join(d, POC))


def m_summary_not_bulleted(d):
    _strip_numbering(os.path.join(d, SUMMARY))


def m_poc_without_ordered_steps(d):
    _strip_numbering(os.path.join(d, POC))


def m_pdf_text_only(d):
    import pymupdf
    src = pymupdf.open(os.path.join(d, PDF)); labels = src[0].get_text("text"); src.close()
    out = pymupdf.open(); pg = out.new_page(width=612, height=792); pg.insert_text((72, 72), labels[:1500], fontsize=9)
    os.remove(os.path.join(d, PDF)); out.save(os.path.join(d, PDF)); out.close()


def m_summary_identity_unknown(d):
    os.rename(os.path.join(d, SUMMARY), os.path.join(d, "Document.docx"))
    doc = Document(); doc.add_paragraph("Meeting notes"); doc.save(os.path.join(d, "notes.docx"))


def n_summary_renamed(d):
    os.rename(os.path.join(d, SUMMARY), os.path.join(d, "Deliverable A.docx"))


def n_summary_typed_bullets(d):
    _strip_numbering(os.path.join(d, SUMMARY), prefix=lambda n: "• ")


def n_poc_step_text(d):
    _strip_numbering(os.path.join(d, POC), prefix=lambda n: f"Step {n}: ")


def n_extra_readme(d):
    open(os.path.join(d, "README.txt"), "w").write("Deliverables: summary, diagram, POC guide.\n")


def n_pdf_rasterised(d):
    import pymupdf
    src = pymupdf.open(os.path.join(d, PDF)); pix = src[0].get_pixmap(dpi=100); src.close()
    out = pymupdf.open(); pg = out.new_page(width=612, height=792); pg.insert_image(pg.rect, pixmap=pix)
    os.remove(os.path.join(d, PDF)); out.save(os.path.join(d, PDF)); out.close()


def n_poc_renamed(d):
    os.rename(os.path.join(d, POC), os.path.join(d, "Guide.docx"))  # identified by its opening text ('POC Idea: ...')


CATALOG = {
    "R01_summary_deleted": {"kind": "rubric_relevant", "mutate": m_summary_deleted, "expected": F(1, 5), "basis": "no summary document: 1 fails as not delivered, and with it the bulleted format (5)"},
    "R02_pdf_deleted": {"kind": "rubric_relevant", "mutate": m_pdf_deleted, "expected": F(2), "basis": "no PDF diagram (2)"},
    "R03_poc_deleted": {"kind": "rubric_relevant", "mutate": m_poc_deleted, "expected": F(3), "basis": "no POC document (3); the summary is still identified by its file name"},
    "R04_summary_not_bulleted": {"kind": "rubric_relevant", "mutate": m_summary_not_bulleted, "expected": F(5), "basis": "the summary's Word bullet numbering removed: plain paragraphs, not a bulleted format (5)"},
    "R05_poc_without_ordered_steps": {"kind": "rubric_relevant", "mutate": m_poc_without_ordered_steps, "expected": F(3),
        "basis": "the POC's numbered lists removed (typed bullets remain): no ordered steps (3)"},
    "R06_pdf_text_only": {"kind": "rubric_relevant", "mutate": m_pdf_text_only, "expected": F(2), "basis": "the PDF replaced by a text-only page (no drawing, no image): not a diagram (2)"},
    "R07_summary_identity_unknown": {"kind": "rubric_relevant", "mutate": m_summary_identity_unknown, "expected": CA(1, 5),
        "basis": "the summary renamed 'Document.docx' beside an extra unidentified 'notes.docx': which file is the summary cannot be determined (1, 5 cannot_assess, never fail)"},
    "N01_summary_renamed": {"kind": "neutral", "mutate": n_summary_renamed, "basis": "the summary under a neutral file name: identified by elimination (two documents, the POC identified)"},
    "N02_summary_typed_bullets": {"kind": "neutral", "mutate": n_summary_typed_bullets, "basis": "bullets typed as '• ' glyphs instead of Word numbering"},
    "N03_poc_step_text": {"kind": "neutral", "mutate": n_poc_step_text, "basis": "ordered steps written as 'Step n:' paragraphs instead of a numbered list"},
    "N04_extra_readme": {"kind": "neutral", "mutate": n_extra_readme, "basis": "an extra README.txt"},
    "N05_pdf_rasterised": {"kind": "neutral", "mutate": n_pdf_rasterised, "basis": "the diagram exported as an image inside the PDF (embedded image, no vector drawing)"},
    "N06_poc_renamed": {"kind": "neutral", "mutate": n_poc_renamed, "basis": "the POC under a neutral file name: identified by its opening text"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    CATALOG[name]["mutate"](final)
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items 1, 2, 3, 5 only; 'neutral' means deterministic-neutral; judge and visual items are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
