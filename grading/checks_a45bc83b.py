"""Deterministic checks for a45bc83b-22f9-4def-8d89-9c5661b2b86f (GCP migration design), following preregistration
2.10: D items 1, 2, 3, 5 (the deliverable set and its formats); J items 6-25 and 31-71 (presence, relationships and
consistency of the design, judged on extracted text with the requirement layers as source); V items 4, 26-30 and 72
(the diagram's icons and depictions, overall formatting), recorded for human review.

Item 70 ("Architecture diagram or summary annotates regions and/or zones"; decided by the human 2026-11-01): human
visual review is authoritative and the item is scored once, as a visual item; the judge also assesses it (summary text
and diagram labels as evidence) when a judge batch runs, and that verdict is used only for judge-human agreement.

Document identity (no content verdict): a .docx is the summary when its file name or opening text names the proposed
architecture summary, the POC when its file name or opening text names the POC, proof of concept or implementation
guide; with exactly two .docx files and one identified, the other takes the remaining role (by elimination). A file that
matches both roles, or several unidentified files, leaves the role unknown (cannot_assess), never a failure.
  1  a .docx identified as the summary          (fail: no .docx, or every .docx identified as the POC only)
  2  a readable .pdf with graphic content        (vector drawings or embedded images on a page; a text-only PDF fails)
  3  a .docx identified as the POC with ordered steps (at least three numbered list paragraphs, or three paragraphs
     opening with 'Step <n>'; bullets alone are not ordered steps)
  5  the summary is bulleted: at least three bullet paragraphs (Word bullet numbering, a 'List Bullet' style, or a typed
     bullet glyph) making up at least half of its non-empty, non-heading paragraphs
A confirmed violation FAILs; an unidentifiable or unreadable required input gives cannot_assess."""
import re

from .engine.decision import Decision, Result

TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
VERSION = "a45bc83b-2026-11-01.2"
D_ITEMS = [1, 2, 3, 5]
J_ITEMS = list(range(6, 26)) + list(range(31, 70)) + [71]  # scored by the judge
V_ITEMS = [4, 26, 27, 28, 29, 30, 70, 72]  # scored by human visual review
JUDGE_AGREEMENT_ONLY = [70]  # judged for judge-human agreement only; never a scored row
CRITICAL = {"C1": {"items": [1, 2, 3, 5], "name": "Deliverable set"},
            "C2": {"items": [], "judge_items": [6, 7, 8, 9, 10, 11, 12, 13, 49], "name": "Hard requirements met as an architecture, consistently"},
            "C3": {"items": [], "visual_items": [4, 26, 27, 28, 29, 30], "name": "Diagram"}}
SUMMARY_RX = re.compile(r"summary|proposed[\s_-]*architecture(?![\s_-]*(diagram|\.pdf))")
POC_RX = re.compile(r"\bpoc\b|proof[\s_-]*of[\s_-]*concept|implementation[\s_-]*guide|(^|[\s_-])poc([\s_-]|$)")
STEP_RX = re.compile(r"^\s*step\s*\d+\b", re.I)


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("_", " ")).strip().lower()


def role_of(name: str, doc: dict) -> dict:
    """Role evidence of one .docx from its file name, then its opening text (first three non-empty paragraphs)."""
    base = _norm(re.sub(r"\.docx$", "", name, flags=re.I))
    opening = " ".join(_norm(p["text"]) for p in [p for p in doc.get("paragraphs", []) if p["text"].strip()][:3])
    fn = {"summary": bool(SUMMARY_RX.search(base)) and not POC_RX.search(base), "poc": bool(POC_RX.search(base))}
    if fn["summary"] or fn["poc"]:
        return {"roles": {r for r, v in fn.items() if v}, "basis": "file name"}
    tx = {"summary": bool(re.search(r"architecture summary|summary of the proposed|proposed architecture", opening)) and not POC_RX.search(opening), "poc": bool(POC_RX.search(opening))}
    if tx["summary"] or tx["poc"]:
        return {"roles": {r for r, v in tx.items() if v}, "basis": "opening text"}
    return {"roles": set(), "basis": None}


def identify_documents(docs: dict) -> dict:
    """{"summary": name | None, "poc": name | None, "status": {...}, "roles": {name: ...}}."""
    roles = {n: role_of(n, d) for n, d in docs.items()}
    out = {"roles": {n: {"roles": sorted(r["roles"]), "basis": r["basis"]} for n, r in roles.items()}, "summary": None, "poc": None, "status": {}}
    for role in ("summary", "poc"):
        hits = [n for n, r in roles.items() if r["roles"] == {role}]
        both = [n for n, r in roles.items() if r["roles"] == {"summary", "poc"}]
        if len(hits) == 1:
            out[role], out["status"][role] = hits[0], roles[hits[0]]["basis"]
        elif len(hits) > 1:
            out["status"][role] = f"ambiguous: {len(hits)} documents identified as the {role}"
        elif both:
            out["status"][role] = "ambiguous: a document is identified as both summary and POC"
    unknown = [n for n, r in roles.items() if not r["roles"]]
    if len(docs) == 2 and len(unknown) == 1:
        for role, other in (("summary", "poc"), ("poc", "summary")):
            if out[role] is None and out[other] is not None and role not in out["status"]:
                out[role], out["status"][role] = unknown[0], "by elimination (two documents, the other identified)"
    for role in ("summary", "poc"):
        if out[role] is None and role not in out["status"]:
            out["status"][role] = "unknown: unidentified documents present" if [n for n in unknown if n not in (out["summary"], out["poc"])] else "absent"
    return out


def ordered_steps(doc: dict) -> dict:
    body = [p for p in doc["paragraphs"] if p["text"].strip()]
    numbered = [p["index"] for p in body if p["list"]["numbered"]]
    steps = [p["index"] for p in body if STEP_RX.match(p["text"])]
    return {"numbered": len(numbered), "step_paragraphs": len(steps), "ok": len(numbered) >= 3 or len(steps) >= 3, "first": (numbered or steps)[:5]}


def bullet_share(doc: dict) -> dict:
    body = [p for p in doc["paragraphs"] if p["text"].strip() and not (p["style"] or "").lower().startswith(("heading", "title"))]
    bullets = [p["index"] for p in body if p["list"]["bullet"]]
    return {"paragraphs": len(body), "bullets": len(bullets), "share": round(len(bullets) / len(body), 4) if body else None, "ok": len(bullets) >= 3 and bool(body) and len(bullets) * 2 >= len(body)}


def run_checks(extraction: dict, reference: dict, rubric: list[dict], integrity: dict | None = None) -> dict:
    integrity = integrity or {}
    results: dict[int, Result] = {}
    inv = extraction["inventory"]
    docx_ok = {k: v for k, v in extraction.get("docx", {}).items() if "paragraphs" in v}
    docx_bad = {k: v for k, v in extraction.get("docx", {}).items() if "paragraphs" not in v}
    pdf_ok = {k: v for k, v in extraction.get("pdf", {}).items() if "pages" in v}
    pdf_bad = {k: v for k, v in extraction.get("pdf", {}).items() if "pages" not in v}
    ids = identify_documents(docx_ok)
    status = {"documents": ids, "unreadable": {k: v.get("error_class") for k, v in {**docx_bad, **pdf_bad}.items()}}
    ev0 = {"files": [i["path"] for i in inv], "kinds": {i["path"]: i["kind"] for i in inv}}

    def unreadable_note(bad: dict) -> tuple[str, str] | None:
        for name, info in bad.items():
            cls, intact = info.get("error_class"), integrity.get(name)
            if cls == "original_corrupt" and intact is True:
                return "model_caused_corrupt", f"{name}: structurally corrupt (transfer verified); treated as not delivered"
        return None

    # 1 and 5: the summary
    d1 = Decision(1, {**ev0, "identity": ids["roles"], "summary_status": ids["status"]["summary"]})
    summary = ids["summary"]
    if summary is None:
        if ids["status"]["summary"].startswith(("ambiguous", "unknown")) or docx_bad:
            d1.unreliable("unknown", "summary_identity", f"the summary document cannot be identified: {ids['status']['summary']}" + (f"; unreadable .docx {sorted(docx_bad)}" if docx_bad else ""))
        else:
            d1.violation("summary_absent", "no .docx is the proposed architecture summary (" + ("no .docx delivered" if not docx_ok else "every .docx is identified as the POC only") + ")")
    results[1] = d1.result(f"a .docx proposed architecture summary ({summary}: {ids['status']['summary']})" if summary else "a .docx proposed architecture summary")
    d5 = Decision(5, {**ev0, "summary": summary})
    if summary is None:
        if results[1].verdict == "fail":
            d5.violation("summary_absent", "no summary document, so no bulleted summary")
        else:
            d5.unreliable("unknown", "summary_identity", "the summary document cannot be identified")
    else:
        bs = bullet_share(docx_ok[summary])
        d5.evidence["bullets"] = bs
        d5.deliverable, d5.reference = bs["share"], ">= 0.5 and >= 3 bullets"
        if not bs["ok"]:
            d5.violation("not_bulleted", f"{summary}: {bs['bullets']} bullet paragraph(s) of {bs['paragraphs']}")
    results[5] = d5.result("the summary uses a bulleted format")
    # 2: the PDF diagram
    d2 = Decision(2, {**ev0, "pdfs": {k: {"pages": v["page_count"], "drawings": sum(p["drawings"] for p in v["pages"]), "images": sum(p["images"] for p in v["pages"])} for k, v in pdf_ok.items()}})
    graphic = [k for k, v in pdf_ok.items() if any(p["drawings"] > 0 or p["images"] > 0 for p in v["pages"])]
    if not graphic:
        bad = unreadable_note(pdf_bad)
        if pdf_bad and not bad:
            d2.unreliable("unknown", "pdf", f"PDF unreadable by the grader: {sorted(pdf_bad)}")
        elif not pdf_ok and not pdf_bad:
            d2.violation("pdf_absent", "no .pdf delivered")
        elif bad:
            d2.violation(bad[0], bad[1])
        else:
            d2.violation("no_graphic", f"the PDF(s) {sorted(pdf_ok)} contain no drawing or image (text only): not a diagram")
    results[2] = d2.result(f"a .pdf diagram ({', '.join(graphic)})" if graphic else "a .pdf diagram")
    # 3: the POC with ordered steps
    poc = ids["poc"]
    d3 = Decision(3, {**ev0, "identity": ids["roles"], "poc_status": ids["status"]["poc"]})
    if poc is None:
        if ids["status"]["poc"].startswith(("ambiguous", "unknown")) or docx_bad:
            d3.unreliable("unknown", "poc_identity", f"the POC document cannot be identified: {ids['status']['poc']}")
        else:
            d3.violation("poc_absent", "no .docx is the POC (" + ("no .docx delivered" if not docx_ok else "every .docx is identified as the summary only") + ")")
    else:
        st = ordered_steps(docx_ok[poc])
        d3.evidence["steps"] = st
        d3.deliverable, d3.reference = st["numbered"] or st["step_paragraphs"], ">= 3 ordered steps"
        if not st["ok"]:
            d3.violation("no_ordered_steps", f"{poc}: {st['numbered']} numbered paragraph(s), {st['step_paragraphs']} 'Step n' paragraph(s)")
    results[3] = d3.result(f"a .docx POC with ordered steps ({poc})" if poc else "a .docx POC with ordered steps")
    items = {i: results[i].as_dict() for i in D_ITEMS}
    deps = {1: ["docx"], 2: ["pdf"], 3: ["docx"], 5: ["docx"]}
    for i, r in items.items():
        r["weight"] = rubric[i - 1]["score"]
        r["criterion"] = rubric[i - 1]["criterion"]
        r["dependencies"] = deps[i]
        r["fail_on_own"] = {"missing": deps[i], "invalid": deps[i], "row_set": False, "row_scoped": False, "invalid_kinds": []}
    return {"task": TASK, "version": VERSION, "items": items, "critical": critical_status(items), "extraction_status": status, "judge_items": J_ITEMS, "documents": ids}


def critical_status(items: dict) -> dict:
    out = {}
    for cid, spec in CRITICAL.items():
        verdicts = [items[i]["verdict"] for i in spec["items"] if i in items]
        pending = bool(spec.get("judge_items") or spec.get("visual_items"))
        st = "fail" if "fail" in verdicts else "not_confirmed" if ("cannot_assess" in verdicts or pending or not verdicts) else "pass"
        out[cid] = {"name": spec["name"], "deterministic_items": spec["items"], "judge_items": spec.get("judge_items", []), "visual_items": spec.get("visual_items", []),
                    "status_from_deterministic": st, "note": "judge or human items pending" if pending and st != "fail" else ""}
    return out
