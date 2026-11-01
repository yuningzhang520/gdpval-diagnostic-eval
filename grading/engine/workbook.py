"""Shared workbook gate (engine): the deliverable-presence and provenance decision every spreadsheet task starts with.
Moved from the 1137e2bb grader on 2026-11-01 (behaviour unchanged): no .xlsx -> the file item and every workbook item
fail as not delivered; an unreadable workbook is attributed from the evidence (structurally corrupt original with
verified transfer -> model-caused; working-copy or resource fault on a valid original -> grader-caused; undetermined
-> unknown); a readable workbook passes the file item. ``fill`` is the caller's "set a verdict on every listed item
unless already decided" helper, ``status['workbooks']`` receives the per-file record."""
from .decision import Result


def workbook_gate(extraction: dict, integrity: dict, results: dict, status: dict, fill, *, workbook_items: list, file_item: int = 1,
                  single_file: bool = False) -> dict:
    """Returns the readable workbooks ({name: extracted}); on a missing or unreadable deliverable the results of
    ``workbook_items`` are filled. ``single_file``: the rubric asks for exactly one workbook (two or more fail the
    file item; the rest is graded on the first readable one, recorded)."""
    inventory_xlsx = [i["path"] for i in extraction["inventory"] if i["kind"] == "xlsx"]
    readable = {k: v for k, v in extraction["xlsx"].items() if "sheets" in v}
    unreadable = {k: v for k, v in extraction["xlsx"].items() if "sheets" not in v}
    status.setdefault("workbooks", {})
    if not inventory_xlsx:
        ev = {"files": [i["path"] for i in extraction["inventory"]]}
        results[file_item] = Result(file_item, "fail", ev, False, True, "no .xlsx deliverable in the collected set", "model_caused_missing")
        fill(workbook_items, "fail", "no workbook delivered (requirement not met)", "model_caused_missing", ev)
        return readable
    if not readable:
        name, info = next(iter(unreadable.items()))
        intact = integrity.get(name)
        fmt = info.get("format", {})
        cls = info.get("error_class") or "parser_undetermined"
        ev = {"file": name, "format_check": fmt, "transfer_integrity": intact, "error": info.get("error"), "error_class": cls, "exception_type": info.get("exception_type"),
              "copy_verified": info.get("copy_verified"), "original_sha256": info.get("sha256"), "copy_sha256": info.get("copy_sha256"), "resource_limit": fmt.get("resource_limit")}
        structural_ok = bool(fmt.get("structure_ok"))
        if cls == "original_corrupt" and intact is True:
            status["workbooks"][name] = {"attribution": "model_caused_corrupt", "error_class": cls, "format": fmt, "transfer_integrity": True}
            results[file_item] = Result(file_item, "fail", ev, False, True, f"original workbook structurally corrupt ({fmt.get('error_kind')}: {fmt.get('error')}); transfer integrity verified -> model-delivered corrupt file", "model_caused_corrupt")
            fill(workbook_items, "fail", "workbook structurally corrupt; treated as not delivered (model-caused, transfer verified)", "model_caused_corrupt", ev)
        elif cls == "original_corrupt":
            status["workbooks"][name] = {"attribution": "unknown_transfer", "error_class": cls, "format": fmt, "transfer_integrity": intact}
            results[file_item] = Result(file_item, "cannot_assess", ev, None, True, "original workbook structurally corrupt but transfer integrity not verified -> cause unknown", "unknown")
            fill(workbook_items, "cannot_assess", "workbook corrupt; cause unknown (transfer not verified)", "unknown", ev)
        elif cls in ("grader_error", "copy_fault"):
            status["workbooks"][name] = {"attribution": "grader_caused_extraction", "error_class": cls, "format": fmt, "transfer_integrity": intact}
            results[file_item] = (Result(file_item, "pass", ev, True, True, f"original workbook structure independently valid; grader-side {cls} ({info.get('error')})") if structural_ok
                                  else Result(file_item, "cannot_assess", ev, None, True, f"grader-side {cls} before the structure could be verified ({info.get('error')})", "grader_caused_extraction"))
            fill(workbook_items, "cannot_assess", f"extraction_failed: grader-side {cls} ({info.get('error')}); not a model failure", "grader_caused_extraction", ev)
        else:  # parser_undetermined: a parser could not handle the file; its validity is undetermined
            status["workbooks"][name] = {"attribution": "unknown", "error_class": cls, "format": fmt, "transfer_integrity": intact}
            results[file_item] = (Result(file_item, "pass", ev, True, True, f"zip and XML parts independently valid; a parser failed ({info.get('error')}); validity beyond the structural check undetermined") if structural_ok
                                  else Result(file_item, "cannot_assess", ev, None, True, f"workbook validity undetermined ({info.get('error')})", "unknown"))
            fill(workbook_items, "cannot_assess", f"extraction_failed: parser could not read the workbook ({info.get('error')}); file validity undetermined, reason kept", "unknown", ev)
        return readable
    if single_file and len(inventory_xlsx) > 1:
        results[file_item] = Result(file_item, "fail", {"files": sorted(inventory_xlsx)}, len(inventory_xlsx), 1, f"{len(inventory_xlsx)} workbooks delivered where the task asks for a single one; graded on {sorted(readable)[0]}", "model_caused")
    else:
        results[file_item] = Result(file_item, "pass", {"files": sorted(readable)}, True, True, "readable .xlsx deliverable present")
    return readable
