"""Extraction on copies. Originals under <host_dir>/final are read-only and never modified: every
step copies them into a work directory first. xlsx: formulas and cached values via openpyxl (two
loads), plus a LibreOffice headless recalculation of a copy inside the trusted sandbox image
(docker run, no network) whose values are recorded next to the cached ones; docx: paragraphs with
style names and tables; a file inventory with sizes and SHA-256 for everything."""
import hashlib
import json
import os
import re
import shutil
import subprocess

import openpyxl
import openpyxl.utils.cell
from docx import Document

from harness.image import sandbox_image_ref

IMAGE = sandbox_image_ref()  # full local image ID from config.json (sandbox.image_id); the tag is informational only
XLSX_EXT = (".xlsx", ".xlsm")
DOCX_EXT = (".docx",)
ERROR_PREFIXES = ("#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(final_dir: str) -> list[dict]:
    out = []
    for dp, _, fn in os.walk(final_dir):
        for name in sorted(fn):
            p = os.path.join(dp, name)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            out.append({"path": os.path.relpath(p, final_dir), "bytes": os.path.getsize(p), "sha256": sha256(p),
                        "kind": "xlsx" if name.lower().endswith(XLSX_EXT) else "docx" if name.lower().endswith(DOCX_EXT) else "other"})
    return out


def copy_originals(final_dir: str, work_dir: str) -> dict[str, dict]:
    """Working-copy lifecycle, step 1: copy every regular file to work_dir/copies (originals are
    only read) and verify the copy byte for byte against the original before anything else touches
    it. Returns rel -> {"copy", "original_sha256", "copy_sha256", "copy_verified"}."""
    copies = {}
    dst_root = os.path.join(work_dir, "copies")
    for item in inventory(final_dir):
        src = os.path.join(final_dir, item["path"])
        dst = os.path.join(dst_root, item["path"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o644)
        copy_sha = sha256(dst)
        copies[item["path"]] = {"copy": dst, "original_sha256": item["sha256"], "copy_sha256": copy_sha, "copy_verified": copy_sha == item["sha256"]}
    return copies


def _cell_value(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def extract_xlsx(path: str) -> dict:
    """Formulas (first load) and cached values (data_only load) for every non-empty cell, plus
    sheet-level structure: dimensions, pivot tables (name, cache source, row/data fields),
    tables, auto-filters."""
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    sheets = {}
    for ws in wb_f.worksheets:
        wv = wb_v[ws.title]
        cells = {}
        rows = []
        for row in ws.iter_rows():
            vals = []
            for c in row:
                v = c.value
                cached = wv[c.coordinate].value
                if v is None and cached is None:
                    vals.append(None)
                    continue
                formula = v if isinstance(v, str) and v.startswith("=") else None
                cells[c.coordinate] = {"formula": formula, "cached": _cell_value(cached), "literal": None if formula else _cell_value(v)}
                vals.append(_cell_value(cached if formula else v))
            rows.append(vals)
        pivots = []
        for pt in getattr(ws, "_pivots", []) or []:
            try:
                src = pt.cache.cacheSource.worksheetSource
                fields = [cf.name for cf in pt.cache.cacheFields]
                row_fields = [fields[rf.x] for rf in (pt.rowFields or []) if 0 <= rf.x < len(fields)]
                data_fields = [(d.name, d.subtotal) for d in (pt.dataFields or [])]
                pivots.append({"name": pt.name, "source_sheet": src.sheet, "source_ref": src.ref, "cache_fields": fields, "row_fields": row_fields, "data_fields": data_fields})
            except Exception as ex:  # structure present but unreadable: record, never crash the grader
                pivots.append({"name": getattr(pt, "name", None), "error": f"{type(ex).__name__}"})
        sheets[ws.title] = {"dimensions": ws.dimensions, "max_row": ws.max_row, "max_col": ws.max_column, "cells": cells, "rows": rows,
                            "pivots": pivots, "tables": sorted(ws.tables.keys()) if hasattr(ws, "tables") else [],
                            "auto_filter": ws.auto_filter.ref if ws.auto_filter and ws.auto_filter.ref else None}
    return {"path": path, "sheets": sheets, "sheet_order": wb_f.sheetnames}


RESOURCE_EXCEPTIONS = (MemoryError, OSError, RecursionError, TimeoutError)
XML_PART_LIMIT = 64 * 1024 * 1024


def classify_exception(ex: BaseException) -> str:
    """resource (grader-side infrastructure) / structural (the file itself) / parser (undetermined)."""
    import xml.etree.ElementTree as ET
    import zipfile
    if isinstance(ex, RESOURCE_EXCEPTIONS):
        return "resource"
    if isinstance(ex, (zipfile.BadZipFile, zipfile.LargeZipFile, ET.ParseError)):
        return "structural"
    try:
        from lxml import etree
        if isinstance(ex, etree.XMLSyntaxError):
            return "structural"
    except ImportError:
        pass
    return "parser"


def format_check(path: str) -> dict:
    """Independent structural validation of an .xlsx, separate from the parser the grader uses:
    zip integrity, the OOXML parts [Content_Types].xml and xl/workbook.xml, and every XML part
    parsed with the standard library (a worksheet XML that does not parse is structural damage of
    the file itself, whatever openpyxl does). ``structure_ok`` summarises these independent checks;
    the openpyxl load is recorded separately. ``error_kind`` classifies a failure: zip_error /
    missing_part / xml_error (structural: the file), resource_error (MemoryError, I/O: the grader),
    resource_limit (an XML part above the grader's own validation cap XML_PART_LIMIT: the grader;
    the part's name and size and the limit are recorded), parser_error (openpyxl could not read a
    structurally valid file: validity undetermined)."""
    import xml.etree.ElementTree as ET
    import zipfile
    out = {"zip_ok": False, "content_types": False, "workbook_part": False, "xml_parts_ok": None, "xml_parts_checked": 0, "openpyxl_loads": False, "structure_ok": False,
           "sheets": [], "error": None, "error_kind": None, "bytes": os.path.getsize(path) if os.path.exists(path) else 0}
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            out["zip_ok"] = bad is None
            names = set(z.namelist())
            out["content_types"] = "[Content_Types].xml" in names
            out["workbook_part"] = "xl/workbook.xml" in names
            if bad is not None:
                out.update({"error": f"corrupt zip member {bad}", "error_kind": "zip_error"})
                return out
            if not (out["content_types"] and out["workbook_part"]):
                out.update({"error": "required OOXML part missing ([Content_Types].xml / xl/workbook.xml)", "error_kind": "missing_part"})
                return out
            bad_xml, over_limit = [], []
            for info in z.infolist():
                if not info.filename.lower().endswith((".xml", ".rels")):
                    continue
                if info.file_size > XML_PART_LIMIT:
                    # The grader's own validation cap, not a property of the file: recorded as a resource limit,
                    # never as malformed XML. The part stays unvalidated and the structure is not confirmed.
                    over_limit.append({"part": info.filename, "bytes": info.file_size, "limit_bytes": XML_PART_LIMIT})
                    continue
                try:
                    ET.fromstring(z.read(info.filename))
                    out["xml_parts_checked"] += 1
                except ET.ParseError as ex:
                    bad_xml.append((info.filename, f"ParseError: {str(ex)[:80]}"))
            out["xml_parts_ok"] = not bad_xml and not over_limit
            if bad_xml:  # structural damage of the file itself takes precedence: it is confirmed on the parts that were read
                out.update({"error": "malformed XML part(s): " + "; ".join(f"{n} ({e})" for n, e in bad_xml[:3]), "error_kind": "xml_error", "resource_limit": over_limit or None})
                return out
            if over_limit:
                out.update({"error": f"{len(over_limit)} XML part(s) above the grader's validation limit of {XML_PART_LIMIT} bytes: " + "; ".join(f"{o['part']} ({o['bytes']} bytes)" for o in over_limit[:3]),
                            "error_kind": "resource_limit", "resource_limit": over_limit, "xml_parts_unchecked": len(over_limit)})
                return out
    except RESOURCE_EXCEPTIONS as ex:
        out.update({"error": f"{type(ex).__name__}: {str(ex)[:120]}", "error_kind": "resource_error"})
        return out
    except Exception as ex:
        kind = classify_exception(ex)
        out.update({"error": f"{type(ex).__name__}: {str(ex)[:120]}", "error_kind": {"structural": "zip_error", "resource": "resource_error"}.get(kind, "parser_error")})
        return out
    out["structure_ok"] = True
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
        out["sheets"] = list(wb.sheetnames)
        out["openpyxl_loads"] = True
        wb.close()
    except RESOURCE_EXCEPTIONS as ex:
        out.update({"error": f"openpyxl: {type(ex).__name__}: {str(ex)[:120]}", "error_kind": "resource_error"})
    except Exception as ex:
        kind = classify_exception(ex)
        out.update({"error": f"openpyxl: {type(ex).__name__}: {str(ex)[:120]}", "error_kind": "xml_error" if kind == "structural" else "parser_error"})
        if kind == "structural":
            out["structure_ok"] = False
    return out


def recalculate_xlsx(copy_path: str, work_dir: str, runner=subprocess.run, timeout_s: int = 300) -> dict:
    """LibreOffice headless recalculation of the copy inside the trusted image (no network, scratch
    mount only). Every call uses a fresh, uniquely named scratch directory; soffice's own exit
    status is checked (not the status of a later shell command); the output must be newly created
    in that directory, non-empty, openable and carry the expected sheets. Nothing is cached or
    reused: a failure returns status 'failed' with the reason and never an earlier result."""
    import tempfile
    os.makedirs(work_dir, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="recalc_", dir=work_dir)
    out_dir = os.path.join(scratch, "out")
    os.makedirs(out_dir)
    src = os.path.join(scratch, "in.xlsx")
    shutil.copyfile(copy_path, src)
    in_sha = sha256(src)
    assert os.listdir(out_dir) == [], "fresh output directory must be empty"
    script = ("cd /work && (soffice --version > /work/soffice.version 2>/dev/null || true); "
              "timeout 240 soffice --headless --norestore --convert-to 'xlsx:Calc MS Excel 2007 XML' --outdir /work/out /work/in.xlsx "
              "> /work/soffice.stdout 2> /work/soffice.stderr; rc=$?; echo \"SOFFICE_RC=$rc\"; exit $rc")
    cmd = ["docker", "run", "--rm", "--pull=never", "--network", "none", "--cap-drop", "ALL", "-v", f"{os.path.realpath(scratch)}:/work", IMAGE, "bash", "-c", script]
    record = {"scratch": scratch, "input_path": src, "source_copy": copy_path, "input_sha256": in_sha, "image": IMAGE, "engine": "LibreOffice headless in image " + IMAGE}
    try:
        res = runner(cmd, capture_output=True, text=True, timeout=timeout_s)
    except Exception as ex:
        return {**record, "status": "failed", "reason": f"converter did not run: {type(ex).__name__}: {str(ex)[:200]}"}
    stdout, stderr = (res.stdout or ""), (res.stderr or "")
    m = re.search(r"SOFFICE_RC=(\d+)", stdout)
    soffice_rc = int(m.group(1)) if m else None
    try:
        so_err = open(os.path.join(scratch, "soffice.stderr"), encoding="utf-8", errors="replace").read()[-500:]
        so_out = open(os.path.join(scratch, "soffice.stdout"), encoding="utf-8", errors="replace").read()[-500:]
    except OSError:
        so_err, so_out = "", ""
    try:
        version = open(os.path.join(scratch, "soffice.version"), encoding="utf-8", errors="replace").read().strip()[:120] or None
    except OSError:
        version = None
    produced = sorted(os.listdir(out_dir))
    out_path = os.path.join(out_dir, "in.xlsx")
    record.update({"soffice_rc": soffice_rc, "runner_rc": res.returncode, "soffice_stdout": so_out, "soffice_stderr": so_err, "converter_version": version,
                   "output_path": out_path})
    if soffice_rc != 0 or res.returncode != 0:
        return {**record, "status": "failed", "reason": f"soffice exit status {soffice_rc} (runner {res.returncode})", "produced": produced}
    if produced != ["in.xlsx"] or os.path.getsize(out_path) == 0:
        return {**record, "status": "failed", "reason": "conversion produced no new workbook in the fresh output directory", "produced": produced}
    if "could not be loaded" in so_out or "could not be loaded" in so_err:
        return {**record, "status": "failed", "reason": "soffice reported that the source could not be loaded", "produced": produced}
    fmt = format_check(out_path)
    if not fmt["openpyxl_loads"]:
        return {**record, "status": "failed", "reason": f"recalculated workbook unreadable: {fmt['error']}", "produced": produced}
    try:
        wb = openpyxl.load_workbook(out_path, data_only=True)
        values = {ws.title: {c.coordinate: _cell_value(c.value) for row in ws.iter_rows() for c in row if c.value is not None} for ws in wb.worksheets}
    except Exception as ex:
        return {**record, "status": "failed", "reason": f"recalculated workbook unreadable: {type(ex).__name__}", "produced": produced}
    return {**record, "status": "ok", "values": values, "recalculated_copy": out_path, "output_sha256": sha256(out_path), "sheets": list(values)}


def compare_recalc(extracted: dict, recalc: dict) -> dict:
    """Per formula cell: cached value vs recalculated value → equal / differs / cached_missing /
    recalculation_failed. Gives the three-way separation the methods require."""
    summary = {"formula_cells": 0, "equal": 0, "differs": 0, "cached_missing": 0, "recalculation_failed": 0, "details": []}
    for sheet, s in extracted["sheets"].items():
        for coord, c in s["cells"].items():
            if not c["formula"]:
                continue
            summary["formula_cells"] += 1
            if recalc.get("status") != "ok":
                summary["recalculation_failed"] += 1
                continue
            rv = recalc["values"].get(sheet, {}).get(coord)
            cv = c["cached"]
            if cv is None:
                summary["cached_missing"] += 1
                summary["details"].append({"sheet": sheet, "cell": coord, "cached": None, "recalculated": rv, "class": "cached_missing"})
            elif _num_equal(cv, rv):
                summary["equal"] += 1
            else:
                summary["differs"] += 1
                summary["details"].append({"sheet": sheet, "cell": coord, "cached": cv, "recalculated": rv, "class": "differs"})
    return summary


def _num_equal(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return a == b


def apply_recalc_values(extracted: dict) -> dict:
    """Fill formula cells that have no cached value with the recalculated value (when the
    recalculation succeeded) so the checks can read them; every such cell is recorded under
    ``value_sources`` as 'recalculated'. Cached values are never replaced."""
    rc = extracted.get("recalc", {})
    filled = []
    if rc.get("status") != "ok":
        extracted["value_sources"] = {"recalculated_cells": filled, "recalc_status": rc.get("status")}
        return extracted
    for sheet, s in extracted["sheets"].items():
        rows = s["rows"]
        for coord, c in s["cells"].items():
            if c["formula"] and c["cached"] is None:
                rv = rc["values"].get(sheet, {}).get(coord)
                if rv is not None:
                    c["cached"] = rv
                    c["value_source"] = "recalculated"
                    col = openpyxl.utils.cell.column_index_from_string(re.match(r"[A-Z]+", coord).group(0)) - 1
                    r = int(re.search(r"\d+", coord).group(0)) - 1
                    if r < len(rows) and col < len(rows[r]):
                        rows[r][col] = rv
                    filled.append({"sheet": sheet, "cell": coord})
    extracted["value_sources"] = {"recalculated_cells": filled, "recalc_status": "ok"}
    return extracted


def extract_docx(path: str) -> dict:
    doc = Document(path)
    paragraphs = [{"index": i, "style": p.style.name if p.style is not None else None, "text": p.text} for i, p in enumerate(doc.paragraphs)]
    tables = [[[cell.text for cell in row.cells] for row in t.rows] for t in doc.tables]
    text = "\n".join(p["text"] for p in paragraphs if p["text"].strip())
    for t in tables:
        text += "\n" + "\n".join(" | ".join(r) for r in t)
    return {"path": path, "paragraphs": paragraphs, "tables": tables, "text": text, "headings": [p for p in paragraphs if p["style"] and p["style"].lower().startswith("heading")]}


def extract_all(final_dir: str, work_dir: str, *, recalc: bool = True, runner=subprocess.run) -> dict:
    """Inventory, copies, xlsx/docx extraction and (optionally) recalculation for every deliverable."""
    os.makedirs(work_dir, exist_ok=True)
    inv = inventory(final_dir)
    copies = copy_originals(final_dir, work_dir)
    result = {"final_dir": final_dir, "inventory": inv, "xlsx": {}, "docx": {}, "other": [i["path"] for i in inv if i["kind"] == "other"]}
    result["copies"] = copies
    for item in inv:
        rec = copies[item["path"]]
        cp, original = rec["copy"], os.path.join(final_dir, item["path"])
        provenance = {"sha256": item["sha256"], "copy_sha256": rec["copy_sha256"], "copy_verified": rec["copy_verified"], "copy_path": cp}
        if item["kind"] == "xlsx":
            # Structural check on the ORIGINAL (read-only). Attribution follows the evidence, not the stage:
            # structural damage of the file -> original_corrupt (model, if the transfer is verified);
            # resource / I/O failure -> grader_error; a parser failure on a structurally valid file -> parser_undetermined.
            fmt = format_check(original)
            provenance["format"] = fmt
            if fmt["error_kind"] in ("zip_error", "missing_part", "xml_error"):
                result["xlsx"][item["path"]] = {"error": f"original workbook structurally corrupt: {fmt['error']}", "error_class": "original_corrupt", **provenance}
                continue
            if fmt["error_kind"] == "resource_error":
                result["xlsx"][item["path"]] = {"error": f"grader resource failure during the structural check: {fmt['error']}", "error_class": "grader_error", "exception_type": (fmt["error"] or "").split(":")[0].replace("openpyxl", "").strip() or None, **provenance}
                continue
            if fmt["error_kind"] == "resource_limit":
                # The file could not be validated within the grader's own limit: grader-side, with the limit, the part sizes
                # and the file size kept as evidence; nothing about the file's validity is asserted.
                result["xlsx"][item["path"]] = {"error": f"grader validation limit reached during the structural check: {fmt['error']}", "error_class": "grader_error", "exception_type": "XmlPartLimit",
                                                "resource_limit": fmt.get("resource_limit"), "file_bytes": fmt.get("bytes"), **provenance}
                continue
            if not fmt["openpyxl_loads"]:
                result["xlsx"][item["path"]] = {"error": f"parser could not read a structurally valid workbook: {fmt['error']}", "error_class": "parser_undetermined", **provenance}
                continue
            provenance["copy_verified_before_parse"] = rec["copy_verified"] and sha256(cp) == item["sha256"]
            if not provenance["copy_verified_before_parse"]:
                result["xlsx"][item["path"]] = {"error": "working copy differs from the original before any transformation", "error_class": "copy_fault", **provenance}
                continue
            try:
                ex = extract_xlsx(cp)
            except Exception as e:
                kind = classify_exception(e)
                if kind == "structural":  # structural damage found later than the basic check: still the file's
                    cls = "original_corrupt"
                elif kind == "resource":
                    cls = "grader_error"
                else:
                    cls = "parser_undetermined"
                result["xlsx"][item["path"]] = {"error": f"parser raised {type(e).__name__}: {str(e)[:120]}", "error_class": cls, "exception_type": type(e).__name__, **provenance}
                continue
            ex.update(provenance)
            ex["error_class"] = None
            rc = recalculate_xlsx(cp, os.path.join(work_dir, "recalc_" + hashlib.sha1(item["path"].encode()).hexdigest()[:8]), runner=runner) if recalc else {"status": "skipped"}
            ex["recalc"] = rc
            ex["recalc_comparison"] = compare_recalc(ex, rc)
            apply_recalc_values(ex)
            result["xlsx"][item["path"]] = ex
        elif item["kind"] == "docx":
            provenance["copy_verified_before_parse"] = rec["copy_verified"] and sha256(cp) == item["sha256"]
            try:
                d = extract_docx(cp) if provenance["copy_verified_before_parse"] else None
                result["docx"][item["path"]] = ({**d, **provenance} if d else {"error": "working copy differs from the original", "error_class": "copy_fault", **provenance})
            except Exception as e:
                kind = classify_exception(e)
                result["docx"][item["path"]] = {"error": f"parser raised {type(e).__name__}", "error_class": {"structural": "original_corrupt", "resource": "grader_error"}.get(kind, "parser_undetermined"), "exception_type": type(e).__name__, **provenance}
    # Lifecycle invariant: the originals are only read; record that their hashes are unchanged.
    result["originals_unchanged"] = all(sha256(os.path.join(final_dir, i["path"])) == i["sha256"] for i in inv)
    with open(os.path.join(work_dir, "extraction.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in result.items() if k not in ("xlsx", "docx")} | {"xlsx": {k: {kk: vv for kk, vv in v.items() if kk != "sheets"} | {"sheets": list(v.get("sheets", {}))} for k, v in result["xlsx"].items()},
                                                                                  "docx": {k: {kk: vv for kk, vv in v.items() if kk not in ("paragraphs", "tables", "text", "headings")} for k, v in result["docx"].items()}},
                  f, indent=1, default=str)
    return result
