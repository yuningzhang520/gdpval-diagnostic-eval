"""Gate between paid units (trusted host side, never model-visible; approved by the human 2026-11-01).

Reads only run-level records: the class inventory line of the unit, run_outcome.json, the artifact manifest, the
settlement, the counts-only metadata of harness.run_metadata, and structural checks of the collected files (zip
container and part names, an openpyxl read-only open for workbooks, PDF header and trailer, image verify). No file
content, file name, message, tool argument or tool output is returned or printed, so the gate also runs on sealed
validation units. Original outcomes are never changed: the gate records a decision next to them.

Gemini dev / validation policy (config.batches.<label>.gemini_unit_policy):
  accept   execution ``completed``, or ``limited`` by time / working / cost / token only; grading-eligible outcome;
           collection complete, confirmed empty or partial with model-caused rejections only; consistent manifest;
           every collected file structurally valid; settlement not estimated, no hold, no stop; no suspected
           tool-error loop.
  stop     anything else (execution error, a message or other limit, unknown outcome, integrity failure, hold).
  two-limit rule: count distinct canonical Gemini units across dev and validation whose recorded limits include
           time, working or cost (token-limited units are recorded, not counted; diagnostic / superseded attempts in
           canonical_designations.jsonl are excluded); at the threshold no further Gemini unit is launched.
Candidate (compat) units keep their approved stopping policy (the batch's return code and the ledger); the gate only
records its facts for them as observations.

Canonical designations: <runs_root>/canonical_designations.jsonl, append-only, one line per decision
(canonical | diagnostic | superseded) with reason and authorization; the run inventory itself is never edited."""
import datetime as dt
import json
import os
import zipfile

ACCEPTED_LIMITS = ("time", "working", "cost", "token")
OOXML_PARTS = {".xlsx": "xl/workbook.xml", ".xlsm": "xl/workbook.xml", ".docx": "word/document.xml", ".pptx": "ppt/presentation.xml"}
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inventory(runs_root: str) -> list[dict]:
    path = os.path.join(runs_root, "run_inventory.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def unit_record(runs_root: str, *, task_id: str, model: str, since: str) -> dict | None:
    """Newest real inventory line of (task, model) recorded at or after ``since`` (ISO UTC): the unit's own record."""
    recs = [r for r in inventory(runs_root) if r.get("task_id") == task_id and r.get("model") == model and not r.get("dry_run") and r.get("kind") != "dry_run"
            and (r.get("recorded_at") or "") >= since]
    return recs[-1] if recs else None


# ----------------------------------------------------------------------------- designations
def designations(runs_root: str) -> list[dict]:
    path = os.path.join(runs_root, "canonical_designations.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def designate(runs_root: str, *, run_uuid: str, task_id: str, model: str, designation: str, reason: str, by: str, ref: str) -> dict:
    if designation not in ("canonical", "diagnostic", "superseded"):
        raise ValueError(f"unknown designation {designation!r}")
    rec = {"recorded_at": _now(), "run_uuid": run_uuid, "task_id": task_id, "model": model, "designation": designation, "reason": reason, "by": by, "ref": ref}
    path = os.path.join(runs_root, "canonical_designations.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return rec


def excluded_run_uuids(runs_root: str) -> set:
    """Run uuids whose latest designation is diagnostic or superseded."""
    latest = {}
    for d in designations(runs_root):
        latest[d["run_uuid"]] = d["designation"]
    return {u for u, d in latest.items() if d in ("diagnostic", "superseded")}


# ----------------------------------------------------------------------------- structure
def structural_check(path: str) -> dict:
    """Structural integrity of one collected file, by extension; returns the extension, size and a verdict only."""
    ext = os.path.splitext(path)[1].lower()
    out = {"ext": ext, "bytes": os.path.getsize(path) if os.path.isfile(path) else None, "ok": False, "check": None}
    try:
        if not os.path.isfile(path) or os.path.islink(path):
            out["check"] = "not a regular file"; return out
        if out["bytes"] == 0:
            out["check"] = "empty file"; return out
        if ext in OOXML_PARTS:
            if not zipfile.is_zipfile(path):
                out["check"] = "not a zip container"; return out
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                bad = z.testzip()
            if bad is not None:
                out["check"] = "zip member CRC failure"; return out
            if "[Content_Types].xml" not in names or OOXML_PARTS[ext] not in names:
                out["check"] = "OOXML main part missing"; return out
            if ext in (".xlsx", ".xlsm"):
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True)
                wb.close()
                out["check"] = "zip + parts + openpyxl read-only open"
            else:
                out["check"] = "zip + parts"
            out["ok"] = True
        elif ext == ".pdf":
            with open(path, "rb") as f:
                head = f.read(8)
                f.seek(max(0, out["bytes"] - 2048))
                tail = f.read()
            out["ok"] = head.startswith(b"%PDF-") and b"%%EOF" in tail
            out["check"] = "PDF header and trailer"
        elif ext in IMAGES:
            from PIL import Image
            with Image.open(path) as im:
                im.verify()
            out["ok"], out["check"] = True, "Pillow verify"
        else:
            out["ok"], out["check"] = True, "non-empty regular file (no format-specific check for this type)"
    except Exception as ex:  # a defective file is a recorded finding, never hidden
        out["ok"], out["check"] = False, f"check raised {type(ex).__name__}"
    return out


# ----------------------------------------------------------------------------- unit decision
def evaluate_unit(runs_root: str, rec: dict | None, *, gemini: bool, expected_exts: list[str] | None = None, require_files: bool = False, metadata_fn=None) -> dict:
    """Decision for one finished unit: {"decision": "accept" | "stop", "reasons": [...], ...facts}. ``require_files``
    (the replacement acceptance): at least one collected file and every expected type present."""
    reasons, facts = [], {"evaluated_at": _now()}
    if rec is None:
        return {"decision": "stop", "reasons": ["no inventory record for the unit: outcome unknown"], **facts}
    facts.update({k: rec.get(k) for k in ("kind", "unit_id", "run_uuid", "task_id", "model", "settlement_cost_usd", "estimated", "estimate_basis", "inferred", "manual_review_required", "stop_recorded", "engineering_failure", "config_sha256")})
    if rec.get("kind") != "sample" or rec.get("engineering_failure"):
        reasons.append(f"not a completed sample record (kind {rec.get('kind')!r}, engineering failure {rec.get('engineering_failure')!r})")
    # engine .10 (Codex Review 2 R2-B3): an inferred buffer is now marked estimated; the approved policy settles it without a
    # hold, so the inferred buffer ALONE is no stop reason. Any other estimate basis stops, and so does a record written
    # before estimate_basis existed (then 'estimated' never meant the inferred buffer). Engine .12 (Codex delta review
    # N1): the exception needs exactly the non-empty basis ["inferred_buffer"] and the record's inferred settlement; an
    # empty, missing, unknown or mixed basis stops.
    inferred_only = rec.get("estimate_basis") == ["inferred_buffer"] and rec.get("inferred") is True
    other_estimate = rec.get("estimated") and not inferred_only
    if other_estimate or rec.get("manual_review_required") or rec.get("stop_recorded"):
        reasons.append("settlement estimated, held for manual review, or a stop was recorded")
    uuid = rec.get("run_uuid")
    outcome_path = os.path.join(runs_root, str(uuid), "run_outcome.json") if uuid else None
    if not outcome_path or not os.path.isfile(outcome_path):
        reasons.append("run_outcome.json missing: outcome unknown")
        return {"decision": "stop", "reasons": reasons, **facts}
    outcome = _read_json(outcome_path)
    ex, col = outcome.get("execution") or {}, outcome.get("collection") or {}
    limits = sorted({str(l) for l in (ex.get("limit_types") or [])})
    facts.update({"execution_status": ex.get("status"), "limit_types": limits, "solver_finished": ex.get("solver_finished"), "collection_status": col.get("status"),
                  "outcome_class": outcome.get("outcome_class"), "grading_eligible": outcome.get("grading_eligible"), "harness_error": outcome.get("harness_error")})
    if ex.get("status") == "limited":
        if not limits or any(t not in ACCEPTED_LIMITS for t in limits):
            reasons.append(f"limited by {limits}: not an accepted limit type for this class")
    elif ex.get("status") != "completed":
        reasons.append(f"execution status {ex.get('status')!r}")
    if outcome.get("harness_error") or not outcome.get("grading_eligible"):
        reasons.append(f"outcome not grading-eligible ({outcome.get('outcome_class')!r}) or harness error")
    if col.get("status") not in ("complete", "no_files_confirmed", "partial"):
        reasons.append(f"collection status {col.get('status')!r}")
    final = os.path.join(runs_root, str(uuid), "final")
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(final) for f in fs] if os.path.isdir(final) else []
    checks = [structural_check(p) for p in sorted(files)]
    facts["files"] = [{"ext": c["ext"], "bytes": c["bytes"], "ok": c["ok"], "check": c["check"]} for c in checks]
    if any(not c["ok"] for c in checks):
        reasons.append("a collected file failed its structural check")
    man_path = os.path.join(runs_root, str(uuid), "artifact_manifest.json")
    if os.path.isfile(man_path):
        man = _read_json(man_path)
        cross = man.get("collector_cross_check") or {}
        facts["manifest"] = {"file_count": man.get("file_count"), "consistent": cross.get("consistent")}
        if cross.get("consistent") is not True or man.get("file_count") != len(files) or (col.get("file_count") is not None and col.get("file_count") != len(files)):
            reasons.append("artifact manifest inconsistent with the collector record or the collected files")
    else:
        reasons.append("artifact manifest missing")
    exts = sorted({c["ext"] for c in checks})
    if expected_exts is not None:
        missing = sorted({("." + e.lstrip(".")).lower() for e in expected_exts} - set(exts))
        facts["expected_types"] = {"expected": sorted(("." + e.lstrip(".")).lower() for e in expected_exts), "present": exts, "missing": missing}
        if require_files and missing:
            reasons.append(f"expected file type(s) {missing} not collected")
    if require_files and not files:
        reasons.append("no collected file")
    if rec.get("log_file"):
        try:
            meta = (metadata_fn or _summarize)(rec["log_file"])
            facts["metadata"] = meta
            if meta.get("suspected_tool_error_loop"):
                reasons.append("suspected tool-error loop (harness.run_metadata rule)")
        except Exception as e:
            reasons.append(f"run metadata unreadable ({type(e).__name__})")
    else:
        reasons.append("no log file recorded")
    if not gemini:  # candidate units keep their approved stopping policy (batch return code, ledger); facts are observations only
        return {"decision": "accept", "reasons": [], "observations": reasons, **facts}
    return {"decision": "accept" if not reasons else "stop", "reasons": reasons, **facts}


def _summarize(log_file: str) -> dict:
    from .run_metadata import summarize_log
    return summarize_log(log_file)


# ----------------------------------------------------------------------------- two-limit rule
def counted_limit_units(roots_by_label: dict, *, model: str, counted_types=("time", "working", "cost")) -> list[dict]:
    """Distinct canonical units (not designated diagnostic / superseded) of ``model`` across the given classes whose
    recorded limits include a counted type."""
    out = []
    for label, runs_root in roots_by_label.items():
        excluded = excluded_run_uuids(runs_root)
        seen = set()
        for r in inventory(runs_root):
            if r.get("kind") != "sample" or r.get("engineering_failure") or r.get("model") != model:
                continue
            uuid = r.get("run_uuid")
            if not uuid or uuid in excluded or uuid in seen:
                continue
            seen.add(uuid)
            p = os.path.join(runs_root, uuid, "run_outcome.json")
            if not os.path.isfile(p):
                continue
            limits = set((_read_json(p).get("execution") or {}).get("limit_types") or [])
            hit = sorted(limits & set(counted_types))
            if hit:
                out.append({"run_label": label, "run_uuid": uuid, "task_id": r.get("task_id"), "limits": hit})
    return out
