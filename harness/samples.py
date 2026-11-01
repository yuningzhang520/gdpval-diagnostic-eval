"""Build Inspect Samples with an explicit per-task file allowlist, and verify the staged files
against the hashes recorded in config.json before a sample may start (I1).

Only the task's own inputs (and, for the GCP design task, the pre-staged resource snapshot)
are staged into the sandbox. Every path is listed one by one from data/manifest.json and the
resources record; no directory globs. check_allowlist() refuses anything under private/,
plan/, scripts/, harness/, the parquet, the preregistration file, or another task's id.
verify_staged_files() additionally requires every source to be a regular file whose path
contains no symlink and lies in this task's own data directory, every destination to be a
normalised path under the two mounts with no duplicate target, and every file's size and
SHA-256 to equal the config entry; the set of staged files must equal the config set. Any
mismatch fails closed (StagingError) and the sample is not built."""
import hashlib
import json
import os
import posixpath

from inspect_ai.dataset import Sample

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "manifest.json")
SELECTED = os.path.join(ROOT, "data", "selected_tasks.json")
PROMPTS_DIR = os.path.join(ROOT, "data", "prompts")
CONFIG = os.path.join(ROOT, "config.json")
RESOURCES_TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
INPUTS_MOUNT = "/workspace/inputs"
RESOURCES_MOUNT = "/workspace/resources"
FORBIDDEN = ("private/", "plan/", "preregistration", "gdpval.parquet", "scripts/", "harness/",
             "docs/", ".env", "logs/", "runs/")


class StagingError(ValueError):
    """The staged file set does not match the recorded, verified set; the sample must not start."""


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _add(files: dict[str, str], dst: str, src: str, task_id: str) -> None:
    if dst in files and files[dst] != src:
        raise StagingError(f"{task_id}: duplicate destination {dst}: {files[dst]} and {src}")
    files[dst] = src


def task_files(task_id: str, manifest: dict) -> dict[str, str]:
    """Sandbox path -> host path, explicit per file; a destination may be listed only once."""
    files: dict[str, str] = {}
    for e in manifest["entries"]:
        if e.get("role") == "input" and e.get("task_id") == task_id:
            base = os.path.basename(e["local_path"])
            _add(files, f"{INPUTS_MOUNT}/{base}", os.path.join(ROOT, e["local_path"]), task_id)
    if task_id == RESOURCES_TASK:
        rec = load_json(os.path.join(ROOT, "data", "resources", task_id, "resources.json"))
        for it in rec["items"]:
            if not it.get("ok"):
                continue
            sub = "icons" if it.get("kind") == "icon_pack" else "pages"
            lp = it["local_path"]
            _add(files, f"{RESOURCES_MOUNT}/{sub}/{os.path.basename(lp)}", os.path.join(ROOT, lp), task_id)
            tp = it.get("text_path")
            if tp:
                _add(files, f"{RESOURCES_MOUNT}/pages/{os.path.basename(tp)}", os.path.join(ROOT, tp), task_id)
    return files


def check_allowlist(task_id: str, files: dict[str, str], all_task_ids: list[str]) -> None:
    for dst, src in files.items():
        rel = os.path.relpath(src, ROOT).replace(os.sep, "/")
        if any(s in rel for s in FORBIDDEN):
            raise ValueError(f"{task_id}: forbidden source path staged: {rel}")
        if not rel.startswith(("data/inputs/", "data/resources/")):
            raise ValueError(f"{task_id}: source outside data/inputs or data/resources: {rel}")
        for other in all_task_ids:
            if other != task_id and other in rel:
                raise ValueError(f"{task_id}: another task's file staged: {rel}")
        if "*" in src or "*" in dst or "?" in src:
            raise ValueError(f"{task_id}: glob pattern in allowlist: {src} -> {dst}")
        if not os.path.isfile(src):
            raise FileNotFoundError(src)
        if not dst.startswith((INPUTS_MOUNT + "/", RESOURCES_MOUNT + "/")):
            raise ValueError(f"{task_id}: destination outside the workspace mounts: {dst}")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb", opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW)) as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


COMPAT_SELECTED = os.path.join(ROOT, "data", "compat_tasks.json")
COMPAT_MANIFEST = os.path.join(ROOT, "data", "compat_manifest.json")
TASK_SETS = {"selected": {"selected": SELECTED, "manifest": MANIFEST, "config_key": "tasks"},
             "compat": {"selected": COMPAT_SELECTED, "manifest": COMPAT_MANIFEST, "config_key": "compat_tasks"}}


def task_set_for_manifest(task_manifest: str) -> str:
    """The task set ('selected' or 'compat') a batch's task_manifest path names (config.batches.<label>.task_manifest)."""
    norm = task_manifest.replace(os.sep, "/")
    for name, ts in TASK_SETS.items():
        if norm == os.path.relpath(ts["selected"], ROOT).replace(os.sep, "/") or norm == ts["selected"]:
            return name
    raise ValueError(f"unknown task manifest {task_manifest!r}; expected one of {[os.path.relpath(t['selected'], ROOT) for t in TASK_SETS.values()]}")


def expected_staged_from_config(config_path: str = CONFIG, config_key: str = "tasks") -> dict[str, dict[str, dict]]:
    """task_id -> {sandbox_path: {"source", "bytes", "sha256"}} from config.json (``tasks`` or ``compat_tasks``)."""
    cfg = load_json(config_path)
    out: dict[str, dict[str, dict]] = {}
    for t in cfg.get(config_key, []):
        entries = {}
        for e in t["staged_files"]:
            if e["sandbox_path"] in entries:
                raise StagingError(f"{t['task_id']}: config lists destination {e['sandbox_path']} twice")
            entries[e["sandbox_path"]] = {"source": e["source"], "bytes": int(e["bytes"]), "sha256": e["sha256"]}
        out[t["task_id"]] = entries
    return out


def _dest_problems(dst) -> list[str]:
    p = []
    if not isinstance(dst, str) or "\x00" in dst:
        return ["destination is not a clean string"]
    if not dst.startswith((INPUTS_MOUNT + "/", RESOURCES_MOUNT + "/")):
        p.append("destination outside the workspace mounts")
    if posixpath.normpath(dst) != dst or any(s in ("", ".", "..") for s in dst.split("/")[1:]):
        p.append("destination path not normalised (empty, '.' or '..' segment)")
    return p


def verify_staged_files(task_id: str, files: dict[str, str], expected: dict[str, dict], all_task_ids: list[str],
                        root: str = ROOT) -> dict:
    """Fail-closed verification of one task's staged set against config.json. Returns a report;
    raises StagingError listing every problem found."""
    problems: list[str] = []
    root_real = os.path.realpath(root)
    allowed_dirs = (f"data/inputs/{task_id}/", f"data/resources/{task_id}/")
    for dst, src in sorted(files.items()):
        problems.extend(f"{dst}: {m}" for m in _dest_problems(dst))
        if not isinstance(src, str) or "\x00" in src or not os.path.isabs(src):
            problems.append(f"{dst}: source is not an absolute clean path")
            continue
        if os.path.normpath(src) != src or ".." in src.split(os.sep):
            problems.append(f"{dst}: source path not normalised: {src}")
            continue
        rel = os.path.relpath(src, root).replace(os.sep, "/")
        if not rel.startswith(allowed_dirs):
            problems.append(f"{dst}: source outside this task's data directories: {rel}")
        if any(other != task_id and other in rel for other in all_task_ids):
            problems.append(f"{dst}: source names another task: {rel}")
        try:
            st = os.lstat(src)
        except OSError as ex:
            problems.append(f"{dst}: source missing ({type(ex).__name__})")
            continue
        if os.path.islink(src) or not os.path.isfile(src) or os.path.islink(os.path.dirname(src)):
            problems.append(f"{dst}: source is not a regular file or sits behind a symlink")
            continue
        if os.path.realpath(src) != os.path.normpath(os.path.join(root_real, rel)):
            problems.append(f"{dst}: a component of the source path is a symlink")
            continue
        exp = expected.get(dst)
        if exp is None:
            problems.append(f"{dst}: staged file not recorded in config.json")
            continue
        if exp["source"] != rel:
            problems.append(f"{dst}: source {rel} differs from the recorded {exp['source']}")
        if st.st_size != exp["bytes"]:
            problems.append(f"{dst}: size {st.st_size} differs from the recorded {exp['bytes']}")
        digest = _sha256(src)
        if digest != exp["sha256"]:
            problems.append(f"{dst}: sha256 {digest[:16]}… differs from the recorded {exp['sha256'][:16]}…")
    for dst in sorted(set(expected) - set(files)):
        problems.append(f"{dst}: recorded in config.json but not staged")
    if problems:
        raise StagingError(f"{task_id}: staging verification failed ({len(problems)} problem(s)):\n  " + "\n  ".join(problems))
    return {"task_id": task_id, "files_verified": len(files), "sha256_checked": True, "config": os.path.relpath(CONFIG, ROOT)}


def build_samples(task_ids: list[str] | None = None, verify_config: str | None = None, task_set: str = "selected") -> list[Sample]:
    """Build the samples of one task set ('selected': the ten formal tasks; 'compat': the compatibility task, from its own
    manifest and config block); with ``verify_config`` every staged file is verified against that config and a failure
    prevents the sample from being built (the launcher always verifies). The cross-task check uses the ids of BOTH sets,
    so a compatibility sample can never carry a formal task's file and vice versa."""
    ts = TASK_SETS[task_set]
    sel = load_json(ts["selected"])
    manifest = load_json(ts["manifest"])
    all_ids = sorted({t["task_id"] for name in TASK_SETS for t in load_json(TASK_SETS[name]["selected"])["tasks"] if os.path.exists(TASK_SETS[name]["selected"])})
    expected = expected_staged_from_config(verify_config, ts["config_key"]) if verify_config else None
    samples = []
    for t in sel["tasks"]:
        tid = t["task_id"]
        if task_ids and tid not in task_ids:
            continue
        files = task_files(tid, manifest)
        check_allowlist(tid, files, all_ids)
        meta = {"occupation": t["occupation"], "group": t["group"], "staged_files": sorted(files), "task_set": task_set}
        if expected is not None:
            meta["staging_verified"] = verify_staged_files(tid, files, expected.get(tid, {}), all_ids)
        with open(os.path.join(PROMPTS_DIR, f"{tid}.txt"), encoding="utf-8") as f:
            prompt = f.read()
        samples.append(Sample(id=tid, input=prompt, files=files, metadata=meta))
    return samples


if __name__ == "__main__":
    for s in build_samples(verify_config=CONFIG):
        print(s.id, len(s.files), "files", s.metadata["staging_verified"])
