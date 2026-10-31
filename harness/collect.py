"""Collect /output/final/ from the sandbox onto the host.

Runs in the scorer (normal completion) and in the Task cleanup hook (fallback and resume when
the scorer did not run or did not finish). Everything the sandbox returns (the file listing, each
path, each size and hash) is untrusted input: the host re-validates every path before it decides
where a byte may be written, and the destination is created with O_EXCL | O_NOFOLLOW inside the
sample's own collection directory, whose real path is checked rather than its string prefix.

Collection status (``status`` in ``collection.json``):

- ``listing_failed``: the enumeration did not produce a trustworthy result (exec failure, timeout,
  unparsable output, the sandbox directory is not a plain directory, the host collection root is
  invalid). Nothing is known about the deliverables. ``harness_error`` is true.
- ``no_files_confirmed``: the enumeration completed without any item-level error and found no
  regular file and no special entry. Only this status may be read as "the model wrote nothing".
- ``complete``: at least one regular file, every one collected (or already present with the same
  hash) and no rejected, skipped, oversized or failed item.
- ``partial``: anything else: some item was skipped, rejected, oversized or failed, or the
  enumeration reported item-level errors. ``harness_error`` is true; a human decides what the
  model delivered.

The record of every pass is kept under ``passes``; a later pass never overwrites a collected file
(identical content is skipped, differing content is a recorded conflict). Downstream extraction and
rendering must work on copies: collected files are made read-only (not tamper-proof).

Grading contract: only cleanup publishes authoritative ``run_outcome.json``. The scorer's
ScoreEvent is provisional and unscored, with no ability metric. A grading entry point MUST call
``load_run_outcome(..., for_grading=True)`` with identity independently obtained from the eval log.
Missing, invalid, mismatched or non-final outcomes fail closed. Persistent listing_failed or
unrecovered partial collection is a harness error, NEVER evidence of model non-delivery. An
execution error (provider request failure, transport fault, container or harness exception) keeps
``execution.status == "error"`` and ``grading_eligible == false`` even when collection succeeded.

Execution budgets: exhausting a pre-configured budget that is identical for both models (Inspect
``time_limit``, ``working_limit``, ``message_limit``, ``token_limit``; ``BUDGET_LIMIT_TYPES``) is a
result of the model under fixed resources, not a harness error. The outcome keeps
``execution.status == "limited"`` with the limit type and the Inspect event UUIDs, and is
``grading_eligible`` when the final collection is ``complete`` or ``no_files_confirmed`` and no
error was recorded. Collected deliverables are graded against the rubric; requirements whose
deliverable is missing fail as not delivered; the attempt stays in the k=1 results and in the
sample denominators. ``grading_eligible`` means only that the run may enter grading, not that any
criterion passed. A recovered single tool timeout (a ToolEvent error with the sample continuing) is
not an execution error. Attribution uses the recorded exception type and Inspect events, never the
word "timeout" in a log. Limits outside the budget set (``operator``, ``custom``, ``turn``,
``cost``) are not pre-declared budgets here and require review.

Stage 3 must integrate this gate into the actual grader and cross-check the completed Inspect log
(cleanup precedes log close). The caps below are cumulative per sample across the scorer and
cleanup passes (files and bytes already collected count; an idempotent re-collection of the same
path does not count twice; repeated passes cannot bypass them), and ``time_budget_s`` is a hard
per-pass deadline enforced on the in-flight read (``anyio.fail_after``); a read cut off at the
deadline is recorded as ``read_deadline_exceeded``, files not attempted as
``time_budget_exceeded``, and the pass records ``deadline_hit`` and the cumulative counts.
"""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
import posixpath
import re
import secrets
import stat
import time

import anyio
from inspect_ai.scorer import Score, Target, scorer
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox
from inspect_ai.log import transcript

FINAL_DIR = "/output/final"
LIMITS = {
    "max_files": 200,  # cumulative per sample across scorer and cleanup passes (merged set; idempotent re-collection not counted twice)
    "max_file_bytes": 64 * 1024 ** 2,  # below Inspect's 100 MiB read_file limit so oversized is our own, clear status
    "max_total_bytes": 512 * 1024 ** 2,  # cumulative per sample across passes
    "time_budget_s": 600,  # hard deadline per pass: checked before each read AND enforced on the in-flight read (anyio.fail_after)
    "listing_timeout_s": 120,
}
STATUSES = ("no_files_confirmed", "complete", "partial", "listing_failed")

# Runs inside the sandbox. Enumerates FINAL_DIR without following symlinks, classifies every entry by
# lstat, hashes regular files up to argv[2] bytes, and prints one JSON object. Its output is data,
# not trusted: the host validates every field again.
LIST_SCRIPT = r'''
import hashlib, json, os, stat, sys
root, max_hash = sys.argv[1], int(sys.argv[2])
out = {"ok": True, "root": root, "root_state": None, "entries": [], "skipped": [], "errors": []}
def finish():
    print(json.dumps(out)); sys.exit(0)
try:
    st = os.lstat(root)
except FileNotFoundError:
    out["root_state"] = "missing"; finish()
except OSError as e:
    out["root_state"] = "unreadable"; out["errors"].append({"path": root, "reason": "lstat:" + type(e).__name__}); finish()
if stat.S_ISLNK(st.st_mode):
    out["root_state"] = "symlink"; finish()
if not stat.S_ISDIR(st.st_mode):
    out["root_state"] = "not_a_directory"; finish()
try:
    os.scandir(root).close()
except OSError as e:
    out["root_state"] = "unreadable"; out["errors"].append({"path": root, "reason": "scandir:" + type(e).__name__}); finish()
out["root_state"] = "dir"
def onerror(e):
    out["errors"].append({"path": getattr(e, "filename", None) or root, "reason": "walk:" + type(e).__name__})
def opener(path, flags):
    return os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)
for dp, dn, fn in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
    for d in list(dn):
        p = os.path.join(dp, d)
        try:
            ds = os.lstat(p)
        except OSError as e:
            out["errors"].append({"path": p, "reason": "lstat:" + type(e).__name__}); dn.remove(d); continue
        if stat.S_ISLNK(ds.st_mode):
            try: tgt = os.readlink(p)
            except OSError: tgt = None
            out["skipped"].append({"path": p, "reason": "symlink_directory", "target": tgt}); dn.remove(d)
    for f in fn:
        p = os.path.join(dp, f)
        try:
            fs = os.lstat(p)
        except OSError as e:
            out["errors"].append({"path": p, "reason": "lstat:" + type(e).__name__}); continue
        m = fs.st_mode
        if stat.S_ISLNK(m):
            try: tgt = os.readlink(p)
            except OSError: tgt = None
            out["skipped"].append({"path": p, "reason": "symlink" + ("" if os.path.exists(p) else "_broken"), "target": tgt})
        elif stat.S_ISFIFO(m):
            out["skipped"].append({"path": p, "reason": "fifo"})
        elif stat.S_ISSOCK(m):
            out["skipped"].append({"path": p, "reason": "socket"})
        elif stat.S_ISCHR(m) or stat.S_ISBLK(m):
            out["skipped"].append({"path": p, "reason": "device"})
        elif stat.S_ISREG(m):
            e = {"path": p, "size": fs.st_size, "nlink": fs.st_nlink, "sha256": None}
            if fs.st_size <= max_hash:
                h = hashlib.sha256()
                try:
                    with open(p, "rb", opener=opener) as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b""):
                            h.update(chunk)
                except OSError as ex:
                    out["errors"].append({"path": p, "reason": "hash:" + type(ex).__name__}); continue
                e["sha256"] = h.hexdigest()
            out["entries"].append(e)
        else:
            out["skipped"].append({"path": p, "reason": "unknown_type"})
finish()
'''


def sample_dir(runs_root: str, state: TaskState) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", state.uuid):
        raise ValueError("invalid execution UUID")
    return os.path.join(runs_root, state.uuid)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb", opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW)) as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _within(root_real: str, path_real: str) -> bool:
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def validate_sandbox_path(raw) -> tuple[list[str] | None, str | None]:
    """Return (relative segments, None) for a path strictly under FINAL_DIR, else (None, reason).
    Checks the raw string before any normalisation."""
    if not isinstance(raw, str):
        return None, "path_not_string"
    if "\x00" in raw:
        return None, "path_contains_nul"
    prefix = FINAL_DIR + "/"
    if not raw.startswith(prefix):
        return None, "path_outside_final_dir"
    segs = raw[len(prefix):].split("/")
    for s in segs:
        if s in ("", ".", ".."):
            return None, "path_segment_invalid"
    if posixpath.normpath(raw) != raw:
        return None, "path_not_normalized"
    return segs, None


@contextmanager
def _directory_fd(path: str, *, create: bool = False):
    """Walk ALL raw absolute components from / using directory FDs and O_NOFOLLOW.

    This includes the trusted collection root's ancestors, before any mkdir or normalization.
    Callers must supply a real path (e.g. /private/tmp, not macOS's /tmp symlink).
    """
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
        raise ValueError("invalid absolute host directory")
    parts = path.split("/")[1:]
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError("invalid raw host directory component")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _prepare_host_root(host_dir: str) -> tuple[str | None, str | None]:
    final_root = os.path.join(host_dir, "final")
    try:
        with _directory_fd(final_root, create=True):
            return final_root, None
    except (OSError, ValueError):
        return None, "host_final_root_not_a_directory"


def _host_destination(root_real: str, segs: list[str]) -> tuple[str | None, str | None]:
    """Create intermediate directories under root_real one segment at a time, refusing symlinks,
    and return the destination path whose parent's real path is inside root_real."""
    cur = root_real
    for s in segs[:-1]:
        cur = os.path.join(cur, s)
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            os.mkdir(cur)
            continue
        if stat.S_ISLNK(st.st_mode):
            return None, "host_path_component_symlink"
        if not stat.S_ISDIR(st.st_mode):
            return None, "host_path_component_not_directory"
    parent_real = os.path.realpath(cur)
    if not _within(root_real, parent_real):
        return None, "host_parent_escapes_root"
    dest = os.path.join(parent_real, segs[-1])
    if not _within(root_real, os.path.realpath(os.path.dirname(dest))):
        return None, "host_destination_escapes_root"
    return dest, None


RECORD_NAMES = {"run.json", "collection.json", "run_outcome.json"}


def _read_json(host_dir: str, name: str) -> dict | None:
    if name not in RECORD_NAMES:
        raise ValueError("invalid record name")
    with _directory_fd(host_dir) as directory:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise ValueError("record is not an unlinked regular file")
            return json.load(f)


def _load_prior(host_dir: str) -> dict | None:
    return _read_json(host_dir, "collection.json")


def _atomic_json(host_dir: str, name: str, info: dict) -> None:
    """Random, exclusive temporary file (mkstemp semantics), anchored rename, no symlink writes."""
    if name not in RECORD_NAMES:
        raise ValueError("invalid record name")
    with _directory_fd(host_dir) as directory:
        try:
            st = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            st = None
        if st and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1):
            raise ValueError("unsafe record target")
        tmp = f".{name}.{secrets.token_hex(16)}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2, ensure_ascii=False, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(tmp, dir_fd=directory)
            except FileNotFoundError:
                pass


def _write_record(host_dir: str, info: dict) -> None:
    _atomic_json(host_dir, "collection.json", info)


def _status(root_state, listing_errors, files, skipped, rejected) -> str:
    if root_state not in ("dir", "missing"):
        return "listing_failed"
    ok = [f for f in files if f["status"] in ("collected", "already_collected")]
    bad = [f for f in files if f["status"] not in ("collected", "already_collected")]
    if not files and not skipped and not rejected and not listing_errors:
        return "no_files_confirmed"
    if ok and not bad and not skipped and not rejected and not listing_errors:
        return "complete"
    return "partial"


def _merge_files(prior_files: list[dict], current: list[dict]) -> list[dict]:
    """Union by sandbox path. A file collected in an earlier pass stays collected; the current
    pass's result is recorded for everything else."""
    merged = {f["sandbox_path"]: dict(f) for f in prior_files}
    for f in current:
        p = f["sandbox_path"]
        old = merged.get(p)
        if old and old["status"] == "collected" and f["status"] == "already_collected":
            old["seen_again_at"] = f["at"]
            continue
        merged[p] = dict(f)
    return [merged[k] for k in sorted(merged)]


def _validate_listing(value) -> None:
    """Reject malformed enumeration as a whole; never filter it into an empty listing."""
    if not isinstance(value, dict) or value.get("ok") is not True or value.get("root") != FINAL_DIR:
        raise ValueError("invalid outer object, ok or root")
    if value.get("root_state") not in ("dir", "missing", "symlink", "not_a_directory", "unreadable"):
        raise ValueError("invalid root_state")
    for key in ("entries", "skipped", "errors"):
        if not isinstance(value.get(key), list):
            raise ValueError(f"{key} is not a list")
        for i, item in enumerate(value[key]):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
                raise ValueError(f"{key}[{i}] is not an item with a string path")
            if key == "entries":
                if (type(item.get("size")) is not int or item["size"] < 0
                        or type(item.get("nlink")) is not int or item["nlink"] < 1
                        or "sha256" not in item or not (item["sha256"] is None or
                            isinstance(item["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]))):
                    raise ValueError(f"entries[{i}] has invalid size, nlink or sha256")
            elif not isinstance(item.get("reason"), str) or not item["reason"]:
                raise ValueError(f"{key}[{i}] lacks a string reason")
            if "target" in item and item["target"] is not None and not isinstance(item["target"], str):
                raise ValueError(f"{key}[{i}] has invalid target")
    if len({e["path"] for e in value["entries"]}) != len(value["entries"]):
        raise ValueError("duplicate entry paths")
    if value["root_state"] == "missing" and any(value[k] for k in ("entries", "skipped", "errors")):
        raise ValueError("missing root has entries or errors")


def _collection_failure(binding: dict, reason: str) -> dict:
    return {"record_version": 3, "run": binding, "status": "listing_failed", "harness_error": True,
            "outcome_class": "harness_collection_error", "all_intact": False, "file_count": 0,
            "bytes_collected": 0, "error": reason, "files": [], "passes": [], "listing_errors": [{"path": FINAL_DIR, "reason": reason}],
            "skipped": [], "rejected": [],
            "attribution": {"rule_version": ATTRIBUTION_RULE_VERSION, "class": "harness_caused", "counts": {"model_caused": 0, "harness_caused": 1, "unknown": 0},
                            "requires_adjudication": False, "items": [{"source": "listing", "path": FINAL_DIR, "reason": reason, "class": "harness_caused",
                                                                        "basis": "collector could not record safely", "evidence": "collection failure record"}]}}


async def collect_final_outputs(host_dir: str, note: str, run_binding: dict, sb=None,
                                _simulate_read_failure: set[str] | None = None) -> dict:
    """One collection pass. ``run_binding`` carries the full execution identity. ``sb`` defaults
    to the current sample's sandbox; tests pass a fake. ``_simulate_read_failure`` is for the
    resume regression only."""
    t0 = time.monotonic()
    sb = sb or sandbox()
    try:
        _validate_binding(run_binding)
        with _directory_fd(host_dir, create=True):
            pass
        prior = _load_prior(host_dir)
        if prior and prior.get("run") != run_binding:
            return _collection_failure(run_binding, "run_binding_mismatch: nothing written")
    except (OSError, ValueError) as ex:
        # No fallback write to a directory or marker that failed validation.
        return _collection_failure(run_binding, f"host_record_invalid:{type(ex).__name__}")
    passes = list(prior.get("passes", [])) if prior else []
    prior_files = list(prior.get("files", [])) if prior else []
    this_pass = {"note": note, "started_at": _now(), "limits": dict(LIMITS)}
    listing_errors: list[dict] = []
    skipped: list[dict] = []
    rejected: list[dict] = []
    files: list[dict] = []
    root_state = None
    listing_ok = False
    stderr_tail = ""

    def finish() -> dict:
        merged = _merge_files(prior_files, files) if prior else files
        status = _status(root_state, listing_errors, merged, skipped, rejected) if listing_ok else "listing_failed"
        this_pass.update({"finished_at": _now(), "status": status, "root_state": root_state, "listing_ok": listing_ok,
                          "listing_stderr_tail": stderr_tail[-500:], "listing_errors": listing_errors, "skipped": skipped,
                          "rejected": rejected, "files_this_pass": len(files), "files": files,
                          "elapsed_s": round(time.monotonic() - t0, 3)})
        passes.append(this_pass)
        info = {"record_version": 3, "run": run_binding, "collected_at_utc": _now(), "sandbox_dir": FINAL_DIR,
                "status": status,
                "all_intact": status == "complete", "file_count": sum(1 for f in merged if f["status"] in ("collected", "already_collected")),
                "bytes_collected": sum(f.get("size", 0) for f in merged if f["status"] in ("collected", "already_collected")),
                "root_state": root_state, "listing_ok": listing_ok, "listing_errors": listing_errors, "skipped": skipped,
                "rejected": rejected, "files": merged, "limits": dict(LIMITS), "passes": passes}
        attribution = attribute_collection(info)
        info["attribution"] = attribution
        info["harness_error"] = harness_error_flag(info, attribution)
        info["outcome_class"] = ({"complete": "collected", "no_files_confirmed": "no_deliverable_files_confirmed"}.get(status)
                                 or ("harness_collection_error" if info["harness_error"] else
                                     "requires_adjudication" if attribution["class"] in ("unknown", "none") else "collected_with_model_caused_rejections"))
        _write_record(host_dir, info)
        return info

    root_real, err = _prepare_host_root(host_dir)
    if err:
        listing_errors.append({"path": host_dir, "reason": err})
        return finish()

    try:
        res = await sb.exec(["python3", "-c", LIST_SCRIPT, FINAL_DIR, str(LIMITS["max_file_bytes"])], timeout=LIMITS["listing_timeout_s"])
        stderr_tail = res.stderr or ""
        if not res.success:
            listing_errors.append({"path": FINAL_DIR, "reason": f"listing_exec_failed:returncode={res.returncode}"})
            return finish()
        lines = (res.stdout or "").strip().splitlines()
        parsed = json.loads(lines[-1]) if lines else None
    except Exception as ex:  # timeout, transport, JSON
        listing_errors.append({"path": FINAL_DIR, "reason": f"listing_failed:{type(ex).__name__}"})
        return finish()
    try:
        _validate_listing(parsed)
    except ValueError as ex:
        listing_errors.append({"path": FINAL_DIR, "reason": f"listing_output_invalid:{ex}"})
        return finish()
    root_state = parsed.get("root_state")
    listing_errors.extend(parsed["errors"])
    skipped.extend(parsed["skipped"])
    listing_ok = True
    if root_state not in ("dir", "missing"):
        return finish()

    entries = sorted(parsed["entries"], key=lambda e: e["path"])
    # Cumulative limits across passes of the same sample: files and bytes already collected in
    # earlier passes count toward the caps; an idempotent re-collection of the same path does not
    # count twice; new admissions are limited to what remains of the cumulative budget.
    prior_ok = {f["sandbox_path"]: f for f in prior_files if f.get("status") in ("collected", "already_collected")}
    total = sum(int(f.get("size", 0) or 0) for f in prior_ok.values())
    new_admitted = 0
    new_budget = max(LIMITS["max_files"] - len(prior_ok), 0)
    deadline = t0 + LIMITS["time_budget_s"]
    deadline_hit = False
    this_pass["cumulative"] = {"prior_files": len(prior_ok), "prior_bytes": total, "max_files": LIMITS["max_files"], "max_total_bytes": LIMITS["max_total_bytes"]}
    for e in entries:
        raw = e.get("path")
        segs, why = validate_sandbox_path(raw)
        if why:
            rejected.append({"path": repr(raw)[:300], "reason": why})
            continue
        size, sha, nlink = e.get("size"), e.get("sha256"), e.get("nlink")
        rec = {"sandbox_path": raw, "size": size, "sha256_in_sandbox": sha, "nlink": nlink, "at": _now()}
        if not isinstance(size, int) or size < 0 or (sha is not None and not (isinstance(sha, str) and len(sha) == 64)):
            rejected.append({"path": raw, "reason": "listing_fields_invalid"})
            continue
        is_new = raw not in prior_ok
        if is_new and new_admitted >= new_budget:
            files.append({**rec, "status": "error", "reason": "file_limit"})
            continue
        if size > LIMITS["max_file_bytes"] or sha is None:
            files.append({**rec, "status": "error", "reason": "oversized"})
            continue
        if is_new and total + size > LIMITS["max_total_bytes"]:
            files.append({**rec, "status": "error", "reason": "total_limit"})
            continue
        if deadline_hit or time.monotonic() >= deadline:
            files.append({**rec, "status": "error", "reason": "time_budget_exceeded"})
            continue
        try:
            dest, why = _host_destination(root_real, segs)
        except OSError as ex:
            dest, why = None, f"host_mkdir_failed:{type(ex).__name__}"
        if why:
            rejected.append({"path": raw, "reason": why})
            continue
        rec["host_path"] = dest
        try:
            est = os.lstat(dest)
        except FileNotFoundError:
            est = None
        if est is not None:
            if not stat.S_ISREG(est.st_mode):
                rejected.append({"path": raw, "reason": "host_destination_not_regular_file"})
                continue
            try:
                existing = _sha256_file(dest)
            except OSError as ex:
                files.append({**rec, "status": "error", "reason": f"host_existing_unreadable:{type(ex).__name__}"})
                continue
            if existing == sha and est.st_size == size:
                files.append({**rec, "status": "already_collected", "sha256_collected": existing})
                if is_new:  # a host file from a pass whose record was lost still counts once
                    total += size
                    new_admitted += 1
            else:
                files.append({**rec, "status": "error", "reason": "conflict_existing_differs", "sha256_existing": existing})
            continue
        try:
            if _simulate_read_failure and raw in _simulate_read_failure:
                raise RuntimeError("simulated read failure")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("collection deadline reached before the read started")
            with anyio.fail_after(remaining):
                data = await sb.read_file(raw, text=False)
        except TimeoutError:
            deadline_hit = True
            files.append({**rec, "status": "error", "reason": "read_deadline_exceeded"})
            continue
        except Exception as ex:
            files.append({**rec, "status": "error", "reason": f"read_failed:{type(ex).__name__}"})
            continue
        host_sha = hashlib.sha256(data).hexdigest()
        if len(data) != size or host_sha != sha:
            files.append({**rec, "status": "error", "reason": "integrity_mismatch", "size_collected": len(data), "sha256_collected": host_sha})
            continue
        try:
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        except FileExistsError:
            files.append({**rec, "status": "error", "reason": "conflict_created_concurrently"})
            continue
        except OSError as ex:
            files.append({**rec, "status": "error", "reason": f"host_open_failed:{type(ex).__name__}"})
            continue
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(dest, 0o444)
        except OSError as ex:
            files.append({**rec, "status": "error", "reason": f"host_write_failed:{type(ex).__name__}"})
            continue
        total += size
        new_admitted += 1
        files.append({**rec, "status": "collected", "size_collected": len(data), "sha256_collected": host_sha})
    this_pass["deadline_hit"] = deadline_hit
    this_pass["cumulative"].update({"files_after_pass": len(prior_ok) + new_admitted, "bytes_after_pass": total})
    return finish()


BINDING_KEYS = {"uuid", "model", "task_id", "eval_id", "sample_id", "epoch"}
EXECUTION_KEY = "harness.execution"
# Inspect sample limits that are pre-configured budgets, identical for both models (config.json).
# "cost" is Inspect's per-sample dollar limit (eval(cost_limit=...)); it is a safety net behind the
# pilot ledger and requires valid price data for the model (the launcher fails closed without it).
BUDGET_LIMIT_TYPES = ("time", "working", "message", "token", "cost")
EXECUTION_STATUSES = ("completed", "limited", "error", "unknown")
OUTCOME_CLASSES = ("collected", "no_deliverable_files_confirmed", "collected_with_model_caused_rejections",
                   "harness_collection_error", "requires_adjudication",
                   "execution_error", "execution_unknown", "execution_limit_requires_review")

# ----------------------------------------------------------------------------- attribution
# Per-item attribution of a non-complete collection (policy approved 2026-10-30). Only the classes
# below are produced automatically; everything else is `unknown` and waits for a human
# adjudication recorded in a separate file. Reason names alone never decide `unknown` items.
ATTRIBUTION_RULE_VERSION = "2026-10-30"
ATTRIBUTION_CLASSES = ("model_caused", "harness_caused", "unknown")
_MODEL_CAUSED_SKIPPED = {"symlink", "symlink_broken", "symlink_directory", "fifo", "socket", "device", "unknown_type"}
_HARNESS_CAUSED_FILE = {"read_deadline_exceeded", "time_budget_exceeded", "conflict_existing_differs", "conflict_created_concurrently"}


def attribute_item(source: str, reason: str) -> tuple[str, str]:
    """(class, basis) for one non-collected entry. ``source`` is skipped / rejected / file / listing."""
    r = str(reason or "")
    if source == "skipped":
        if r in _MODEL_CAUSED_SKIPPED:
            return "model_caused", "lstat classification of an entry the model created under /output/final (not a regular file)"
        return "unknown", "unrecognised skip reason"
    if source == "rejected":
        if r.startswith("host_"):
            return "harness_caused", "host-side destination problem (collector environment)"
        return "unknown", "listing entry refused by host validation; cause (model filename vs listing defect) needs the execution log"
    if source == "file":
        if r in _HARNESS_CAUSED_FILE or r.startswith("host_"):
            return "harness_caused", "collector deadline, host conflict or host write problem"
        return "unknown", "read failure, integrity mismatch or limit hit: judge with the file, the execution log and the approved limit policy"
    if source == "listing":
        if r.startswith(("listing_exec_failed", "listing_failed", "listing_output_invalid")):
            return "harness_caused", "enumeration failed in the collector"
        return "unknown", "item-level enumeration error inside the sandbox tree"
    return "unknown", "unrecognised source"


def attribute_collection(collection: dict) -> dict:
    """Derive the attribution record from the collection evidence (deterministic, re-derivable)."""
    status = collection.get("status")
    items = []
    if status == "listing_failed":
        errs = collection.get("listing_errors") or [{"path": FINAL_DIR, "reason": "listing_failed"}]
        for i, e in enumerate(errs):
            items.append({"source": "listing", "path": e.get("path"), "reason": e.get("reason"), "class": "harness_caused",
                          "basis": "enumeration did not complete; nothing is known about the deliverables", "evidence": f"collection.json listing_errors[{i}]"})
    elif status == "partial":
        for i, e in enumerate(collection.get("skipped", [])):
            cls, basis = attribute_item("skipped", e.get("reason"))
            items.append({"source": "skipped", "path": e.get("path"), "reason": e.get("reason"), "target": e.get("target"), "class": cls, "basis": basis, "evidence": f"collection.json skipped[{i}]"})
        for i, e in enumerate(collection.get("rejected", [])):
            cls, basis = attribute_item("rejected", e.get("reason"))
            items.append({"source": "rejected", "path": e.get("path"), "reason": e.get("reason"), "class": cls, "basis": basis, "evidence": f"collection.json rejected[{i}]"})
        for f in collection.get("files", []):
            if f.get("status") == "error":
                cls, basis = attribute_item("file", f.get("reason"))
                items.append({"source": "file", "path": f.get("sandbox_path"), "reason": f.get("reason"), "class": cls, "basis": basis,
                              "evidence": f"collection.json files[sandbox_path={f.get('sandbox_path')}]"})
        for i, e in enumerate(collection.get("listing_errors", [])):
            cls, basis = attribute_item("listing", e.get("reason"))
            items.append({"source": "listing", "path": e.get("path"), "reason": e.get("reason"), "class": cls, "basis": basis, "evidence": f"collection.json listing_errors[{i}]"})
    counts = {k: sum(1 for it in items if it["class"] == k) for k in ATTRIBUTION_CLASSES}
    overall = ("none" if not items else "harness_caused" if counts["harness_caused"] else "unknown" if counts["unknown"] else "model_caused")
    return {"rule_version": ATTRIBUTION_RULE_VERSION, "class": overall, "counts": counts, "requires_adjudication": overall == "unknown", "items": items}


def effective_attribution(attribution: dict | None, adjudication: dict | None) -> dict:
    """Apply a human adjudication (separate record) to the `unknown` items only; harness_caused
    items can never be adjudicated into eligibility, model_caused items are not changed."""
    if not attribution:
        return {"class": "unknown", "counts": {}, "requires_adjudication": True, "items": [], "adjudicated": False}
    items = [dict(it) for it in attribution.get("items", [])]
    decisions = (adjudication or {}).get("items", {}) if isinstance(adjudication, dict) else {}
    applied = 0
    for it in items:
        key = it.get("path")
        if it["class"] == "unknown" and key in decisions and decisions[key] in ("model_caused", "harness_caused"):
            it["class"] = decisions[key]
            it["adjudicated"] = True
            applied += 1
    counts = {k: sum(1 for it in items if it["class"] == k) for k in ATTRIBUTION_CLASSES}
    overall = ("none" if not items else "harness_caused" if counts["harness_caused"] else "unknown" if counts["unknown"] else "model_caused")
    return {"class": overall, "counts": counts, "requires_adjudication": overall == "unknown", "items": items, "adjudicated": applied > 0, "adjudicated_items": applied}


class OutcomeValidationError(ValueError):
    """The outcome is absent, invalid, mismatched, non-final, or ineligible for grading."""


def _validate_binding(binding: dict) -> None:
    if not isinstance(binding, dict) or set(binding) != BINDING_KEYS:
        raise OutcomeValidationError("incomplete execution binding")
    if any(not isinstance(binding[k], str) or not binding[k] for k in ("uuid", "model", "task_id", "eval_id")):
        raise OutcomeValidationError("unresolved execution identity")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", binding["uuid"]):
        raise OutcomeValidationError("invalid execution UUID")
    if type(binding["sample_id"]) not in (str, int) or binding["sample_id"] == "":
        raise OutcomeValidationError("invalid sample_id")
    if type(binding["epoch"]) is not int or binding["epoch"] < 1:
        raise OutcomeValidationError("invalid epoch")


def run_binding(state: TaskState) -> dict:
    """Bind real Inspect 0.3.286 runtime identity; never substitute a launcher label.

    TaskState has no task/eval ID. The two pinned internal accessors below are checked against
    logged EvalSpec IDs by lifecycle regressions. Missing context fails closed, with no fallback.
    """
    from importlib.metadata import version
    from inspect_ai.log._samples import sample_active
    from inspect_ai._control.eval_state import get_eval_state

    if version("inspect_ai") != "0.3.286":
        raise OutcomeValidationError("Inspect runtime identity adapter requires revalidation")
    active = sample_active()
    registered = get_eval_state(active.eval_id) if active else None
    if (not active or not registered or not registered.task_id or active.sample_uuid != state.uuid
            or active.sample.id != state.sample_id or active.epoch != state.epoch
            or active.model != str(state.model)):
        raise OutcomeValidationError("Inspect runtime identity unavailable or inconsistent")
    binding = {"uuid": state.uuid, "model": str(state.model), "task_id": registered.task_id,
               "eval_id": active.eval_id, "sample_id": state.sample_id, "epoch": state.epoch}
    _validate_binding(binding)
    return binding


def bind_run(host_dir: str, binding: dict, run_label: str | None, phase: str) -> None:
    """First trusted TaskState creates run.json; every later entry checks the COMPLETE binding."""
    _validate_binding(binding)
    with _directory_fd(host_dir, create=True):
        pass
    manifest = _read_json(host_dir, "run.json")
    # Check every existing record before writing anything, including a missing run.json.
    for record in (manifest, _load_prior(host_dir), _read_json(host_dir, "run_outcome.json")):
        if record is not None and (not isinstance(record, dict) or record.get("run") != binding):
            raise OutcomeValidationError("run_binding_mismatch: nothing written")
    if manifest is None:
        _atomic_json(host_dir, "run.json", {"record_version": 1, "run": binding,
                     "run_label": run_label, "first_bound_at": _now(), "first_bound_phase": phase})


def execution_snapshot(state: TaskState) -> dict:
    """TaskState.completed alone is NOT success: Inspect also sets it after errors/limits."""
    events = list(transcript().events)
    errors = [{"event_uuid": e.uuid, "message": e.error.message} for e in events if e.event == "error"]
    limits = [{"event_uuid": e.uuid, "type": e.type, "limit": e.limit, "message": e.message}
              for e in events if e.event == "sample_limit"]
    progress = state.store.get(EXECUTION_KEY, {})
    status = _execution_status(errors, limits, progress.get("solver_finished") is True)
    return {"status": status, "errors": errors, "limits": limits,
            "limit_types": sorted({str(l["type"]) for l in limits}),
            "solver_finished": progress.get("solver_finished") is True,
            "collector_scorer_executed": progress.get("collector_scorer_executed") is True,
            "source": "Inspect transcript + trusted solver completion marker",
            "scope": "sample execution through Task.cleanup; final eval log close is later"}


def _execution_status(errors: list, limits: list, solver_finished: bool) -> str:
    return "error" if errors else "limited" if limits else "completed" if solver_finished else "unknown"


def grading_decision(execution: dict, collection_status: str, attribution: dict | None = None,
                     adjudication: dict | None = None) -> tuple[bool, str, str]:
    """Single source of the attribution rule (used by the writer and re-derived by the loader).

    Returns (grading_eligible, outcome_class, basis). Order: ``listing_failed`` is a harness error;
    a ``partial`` collection is routed by its per-item attribution — any unrecovered
    harness/provider-caused item → harness error (run error, never model failure); any remaining
    ``unknown`` item → ``requires_adjudication`` (no automatic verdict either way); only when every
    non-collected item is model-caused does the attempt proceed to grading, with the unaccepted
    files treated as not delivered. Then an execution error or unknown state blocks grading, and a
    limit is eligible only when every recorded limit type is a pre-configured budget."""
    if collection_status == "listing_failed":
        return False, "harness_collection_error", "unrecovered collection fault; never model non-delivery"
    if collection_status == "partial":
        eff = effective_attribution(attribution, adjudication)
        if eff["class"] == "harness_caused":
            return False, "harness_collection_error", "unrecovered harness/provider-caused collection fault; run error, never model non-delivery"
        if eff["class"] in ("unknown", "none"):
            return False, "requires_adjudication", "non-collected items of undetermined cause; human adjudication required (no automatic model-failure or harness-fault verdict)"
    status = execution.get("status")
    if status == "error":
        return False, "execution_error", "execution error recorded (provider, transport, container or harness); run review"
    if status == "unknown":
        return False, "execution_unknown", "no completion marker, no error, no limit; run review"
    delivered = {"complete": "collected", "no_files_confirmed": "no_deliverable_files_confirmed",
                 "partial": "collected_with_model_caused_rejections"}[collection_status]
    model_note = "; unaccepted model-created files are treated as not delivered" if collection_status == "partial" else ""
    if status == "limited":
        types = sorted({str(l.get("type")) for l in execution.get("limits", [])})
        if not types or any(t not in BUDGET_LIMIT_TYPES for t in types):
            return False, "execution_limit_requires_review", f"limit type(s) {types} are not pre-configured budgets"
        return True, delivered, (f"pre-configured budget exhausted ({', '.join(types)}); graded on the collected "
                                 f"deliverables, missing deliverables fail, attempt kept in k=1 results{model_note}")
    if status == "completed":
        return True, delivered, f"execution completed; graded on the collected deliverables{model_note}"
    return False, "execution_unknown", f"unrecognised execution status {status!r}"


def harness_error_flag(collection: dict, attribution: dict) -> bool:
    """Collection-level harness error: enumeration failed, or any harness/provider-caused item."""
    return collection.get("status") == "listing_failed" or attribution.get("class") == "harness_caused"


def write_run_outcome(host_dir: str, binding: dict, collection: dict, execution: dict) -> dict:
    """Publish the cleanup result atomically; provisional ScoreEvents remain historical. The
    attribution is derived from the collection evidence and stored; human adjudications live in a
    separate file (adjudication.json) and are applied only when the outcome is loaded."""
    _validate_binding(binding)
    bind_run(host_dir, binding, None, "cleanup")
    if collection.get("run") != binding:
        raise OutcomeValidationError("collection identity mismatch")
    attribution = attribute_collection(collection)
    eligible, outcome_class, basis = grading_decision(execution, collection["status"], attribution)
    outcome = {"record_version": 1, "final": True, "finalized_by": "task_cleanup",
               "finalized_at": _now(), "run": binding, "execution": execution,
               "collection_status": collection["status"], "collection": collection,
               "attribution": attribution,
               "harness_error": harness_error_flag(collection, attribution),
               "requires_adjudication": outcome_class == "requires_adjudication",
               "grading_eligible": eligible, "outcome_class": outcome_class, "grading_basis": basis,
               "budget_limit_types": list(BUDGET_LIMIT_TYPES),
               "score_event_role": "provisional_collection_only_not_a_capability_score"}
    _atomic_json(host_dir, "run_outcome.json", outcome)
    return outcome


def load_adjudication(host_dir: str, expected_binding: dict) -> dict | None:
    """Read the separate human adjudication record (never written by the harness). Must name the
    same run; item decisions are {path: model_caused | harness_caused}."""
    try:
        with _directory_fd(host_dir) as directory:
            try:
                fd = os.open("adjudication.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                return None
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                adj = json.load(f)
    except (OSError, ValueError) as ex:
        raise OutcomeValidationError(f"invalid adjudication record: {type(ex).__name__}") from ex
    if not isinstance(adj, dict) or adj.get("run") != expected_binding or not isinstance(adj.get("items"), dict) \
            or not all(isinstance(k, str) and v in ("model_caused", "harness_caused") for k, v in adj["items"].items()) \
            or not isinstance(adj.get("by"), str) or not isinstance(adj.get("at"), str) or not isinstance(adj.get("basis"), str):
        raise OutcomeValidationError("adjudication record malformed or for another run")
    return adj


def load_run_outcome(host_dir: str, expected_binding: dict, *, for_grading: bool = True,
                     apply_adjudication: bool = True) -> dict:
    """Fail-closed Stage 3 grading gate. expected_binding MUST come from the completed eval log.

    for_grading=False permits inspection of a VALID error outcome; it never relaxes schema,
    identity, finality, collection-record or raw-file integrity validation. The Stage 3 consumer
    must additionally join the completed Inspect log to catch teardown/logging failures after
    cleanup. It must not turn exceptions from this gate into failed model criteria.

    The stored attribution is re-derived from the collection evidence and compared. When a separate
    `adjudication.json` for this run exists and ``apply_adjudication`` is true, its decisions are
    applied to the `unknown` items only and the effective decision is returned under
    ``effective`` (the stored outcome is never modified).
    """
    try:
        _validate_binding(expected_binding)
        outcome = _read_json(host_dir, "run_outcome.json")
        manifest = _read_json(host_dir, "run.json")
        collection = _load_prior(host_dir)
        if not isinstance(outcome, dict) or outcome.get("record_version") != 1:
            raise OutcomeValidationError("missing or invalid outcome")
        if outcome.get("final") is not True or outcome.get("finalized_by") != "task_cleanup":
            raise OutcomeValidationError("non-final outcome")
        if not all(isinstance(r, dict) and r.get("run") == expected_binding for r in (outcome, manifest, collection)):
            raise OutcomeValidationError("outcome/manifest/collection identity mismatch")
        c = outcome.get("collection")
        if c != collection or c.get("record_version") != 3:
            raise OutcomeValidationError("outcome is stale or collection is invalid")
        status = c.get("status")
        if status not in STATUSES or outcome.get("collection_status") != status:
            raise OutcomeValidationError("invalid collection status")
        if type(c.get("listing_ok")) is not bool or not all(isinstance(c.get(k), list) for k in
                                                          ("listing_errors", "skipped", "rejected")):
            raise OutcomeValidationError("invalid collection listing fields")
        passes, files = c.get("passes"), c.get("files")
        if not isinstance(passes, list) or not passes or not isinstance(files, list):
            raise OutcomeValidationError("missing collection history")
        for p in passes:
            if (not isinstance(p, dict) or p.get("status") not in STATUSES or
                    not all(isinstance(p.get(k), list) for k in ("files", "listing_errors", "skipped", "rejected")) or
                    p.get("files_this_pass") != len(p["files"])):
                raise OutcomeValidationError("invalid collection pass")
            if any(not isinstance(f, dict) or not isinstance(f.get("sandbox_path"), str) or
                   f.get("status") not in ("collected", "already_collected", "error") for f in p["files"]):
                raise OutcomeValidationError("invalid per-file history")
        if passes[-1]["status"] != status:
            raise OutcomeValidationError("last pass disagrees with final status")
        calculated = (_status(c.get("root_state"), c["listing_errors"], files, c["skipped"], c["rejected"])
                      if c["listing_ok"] else "listing_failed")
        if calculated != status:
            raise OutcomeValidationError("collection status disagrees with evidence")
        derived = attribute_collection(c)
        stored = outcome.get("attribution")
        if not isinstance(stored, dict) or stored.get("class") != derived["class"] or stored.get("counts") != derived["counts"] \
                or [(i["source"], i.get("path"), i.get("reason"), i["class"]) for i in stored.get("items", [])] != \
                   [(i["source"], i.get("path"), i.get("reason"), i["class"]) for i in derived["items"]]:
            raise OutcomeValidationError("stored attribution disagrees with the collection evidence")
        error = harness_error_flag(c, derived)
        if c.get("harness_error") is not error or outcome.get("harness_error") is not error or c.get("all_intact") is not (status == "complete"):
            raise OutcomeValidationError("inconsistent collection flags")
        e = outcome.get("execution")
        if (not isinstance(e, dict) or e.get("status") not in EXECUTION_STATUSES or
                not isinstance(e.get("errors"), list) or not isinstance(e.get("limits"), list)):
            raise OutcomeValidationError("invalid execution state")
        for item in e["limits"]:
            if (not isinstance(item, dict) or not isinstance(item.get("type"), str) or not item["type"]
                    or not isinstance(item.get("event_uuid"), str) or not item["event_uuid"]):
                raise OutcomeValidationError("invalid limit evidence")
        for item in e["errors"]:
            if not isinstance(item, dict) or not isinstance(item.get("event_uuid"), str) or not item["event_uuid"]:
                raise OutcomeValidationError("invalid error evidence")
        if e["status"] != _execution_status(e["errors"], e["limits"], e.get("solver_finished") is True):
            raise OutcomeValidationError("inconsistent execution state")
        if e.get("limit_types") is not None and e["limit_types"] != sorted({str(l["type"]) for l in e["limits"]}):
            raise OutcomeValidationError("inconsistent limit types")
        eligible, expected_class, _basis = grading_decision(e, status, derived)
        if (outcome.get("grading_eligible") is not eligible or outcome.get("outcome_class") != expected_class
                or expected_class not in OUTCOME_CLASSES or not isinstance(outcome.get("grading_basis"), str)
                or outcome.get("requires_adjudication") is not (expected_class == "requires_adjudication")):
            raise OutcomeValidationError("inconsistent attribution")
        ok = [f for f in files if isinstance(f, dict) and f.get("status") in ("collected", "already_collected")]
        if status == "complete" and (not ok or len(ok) != len(files) or any(c.get(k) for k in ("listing_errors", "skipped", "rejected"))):
            raise OutcomeValidationError("inconsistent complete collection")
        if status == "no_files_confirmed" and (files or any(c.get(k) for k in ("listing_errors", "skipped", "rejected"))):
            raise OutcomeValidationError("inconsistent empty collection")
        if c.get("file_count") != len(ok) or c.get("bytes_collected") != sum(f["size"] for f in ok):
            raise OutcomeValidationError("inconsistent collection counts")
        for f in ok:
            segs, why = validate_sandbox_path(f["sandbox_path"])
            expected = os.path.join(host_dir, "final", *(segs or []))
            if why or f.get("host_path") != expected:
                raise OutcomeValidationError("invalid artifact location")
            with _directory_fd(os.path.dirname(expected)):
                pass
            if _sha256_file(expected) != f["sha256_collected"] or os.stat(expected).st_size != f["size"]:
                raise OutcomeValidationError("raw artifact changed")
        adjudication = load_adjudication(host_dir, expected_binding) if apply_adjudication else None
        eff_elig, eff_class, eff_basis = grading_decision(e, status, derived, adjudication)
        result = dict(outcome)
        result["effective"] = {"grading_eligible": eff_elig, "outcome_class": eff_class, "grading_basis": eff_basis,
                               "attribution": effective_attribution(derived, adjudication), "adjudication_applied": adjudication is not None,
                               "adjudication": adjudication}
        if for_grading and not eff_elig:
            raise OutcomeValidationError(f"run requires review: {eff_class}")
        return result
    except OutcomeValidationError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as ex:
        raise OutcomeValidationError(f"invalid outcome: {type(ex).__name__}") from ex


@scorer(metrics=[])
def collect_outputs_scorer(runs_root: str, run_label: str | None = None, _simulate_read_failure: set[str] | None = None):
    async def score(state: TaskState, target: Target) -> Score:
        binding, d = run_binding(state), sample_dir(runs_root, state)
        bind_run(d, binding, run_label, "scorer")
        progress = dict(state.store.get(EXECUTION_KEY, {}))
        progress["collector_scorer_executed"] = True
        state.store.set(EXECUTION_KEY, progress)
        info = await collect_final_outputs(d, note="collected in scorer", run_binding=binding,
                                           _simulate_read_failure=_simulate_read_failure)
        return Score.unscored(reason="provisional_collection_only", answer=info["status"],
                              explanation="No capability score. Final delivery attribution requires cleanup run_outcome.json.",
                              metadata={"provisional": True, "collection": info})
    return score


def collect_on_cleanup(runs_root: str, run_label: str | None = None):
    async def cleanup(state: TaskState) -> None:
        binding, d = run_binding(state), sample_dir(runs_root, state)
        bind_run(d, binding, run_label, "cleanup")
        prior = _load_prior(d)
        if prior and prior.get("status") == "complete":
            info = prior
        else:
            note = "collected in cleanup (resume of earlier pass)" if prior else "collected in cleanup (scorer did not run)"
            info = await collect_final_outputs(d, note=note, run_binding=binding)
        # Even a complete scorer pass needs finalization; ScoreEvent remains provisional.
        # If safe persistence fails, Inspect logs cleanup's exception and the final gate rejects
        # the missing/stale outcome. Never invent a successful fallback record.
        write_run_outcome(d, binding, info, execution_snapshot(state))
    return cleanup
