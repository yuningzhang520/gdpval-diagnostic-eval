"""Build Inspect Samples with an explicit per-task file allowlist.

Only the task's own inputs (and, for the GCP design task, the pre-staged resource snapshot)
are staged into the sandbox. Every path is listed one by one from data/manifest.json and the
resources record; no directory globs. check_allowlist() refuses anything under private/,
plan/, scripts/, harness/, the parquet, the preregistration file, or another task's id."""
import json
import os

from inspect_ai.dataset import Sample

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "manifest.json")
SELECTED = os.path.join(ROOT, "data", "selected_tasks.json")
PROMPTS_DIR = os.path.join(ROOT, "data", "prompts")
RESOURCES_TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
INPUTS_MOUNT = "/workspace/inputs"
RESOURCES_MOUNT = "/workspace/resources"
FORBIDDEN = ("private/", "plan/", "preregistration", "gdpval.parquet", "scripts/", "harness/",
             "docs/", ".env", "logs/", "runs/")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def task_files(task_id: str, manifest: dict) -> dict[str, str]:
    """Sandbox path -> host path, explicit per file."""
    files: dict[str, str] = {}
    for e in manifest["entries"]:
        if e.get("role") == "input" and e.get("task_id") == task_id:
            base = os.path.basename(e["local_path"])
            files[f"{INPUTS_MOUNT}/{base}"] = os.path.join(ROOT, e["local_path"])
    if task_id == RESOURCES_TASK:
        rec = load_json(os.path.join(ROOT, "data", "resources", task_id, "resources.json"))
        for it in rec["items"]:
            if not it.get("ok"):
                continue
            sub = "icons" if it.get("kind") == "icon_pack" else "pages"
            lp = it["local_path"]
            files[f"{RESOURCES_MOUNT}/{sub}/{os.path.basename(lp)}"] = os.path.join(ROOT, lp)
            tp = it.get("text_path")
            if tp:
                files[f"{RESOURCES_MOUNT}/pages/{os.path.basename(tp)}"] = os.path.join(ROOT, tp)
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


def build_samples(task_ids: list[str] | None = None) -> list[Sample]:
    sel = load_json(SELECTED)
    manifest = load_json(MANIFEST)
    all_ids = [t["task_id"] for t in sel["tasks"]]
    samples = []
    for t in sel["tasks"]:
        tid = t["task_id"]
        if task_ids and tid not in task_ids:
            continue
        files = task_files(tid, manifest)
        check_allowlist(tid, files, all_ids)
        with open(os.path.join(PROMPTS_DIR, f"{tid}.txt"), encoding="utf-8") as f:
            prompt = f.read()
        samples.append(Sample(id=tid, input=prompt, files=files,
                              metadata={"occupation": t["occupation"], "group": t["group"],
                                        "staged_files": sorted(files)}))
    return samples


if __name__ == "__main__":
    for s in build_samples():
        print(s.id, len(s.files), "files")
        for dst in sorted(s.files):
            print("   ", dst, "<-", os.path.relpath(s.files[dst], ROOT))
