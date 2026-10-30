#!/usr/bin/env python
"""Download the task inputs and expert deliverables for the selected tasks from a
fixed Hugging Face revision, verify every file against the hash Hugging Face
records for that revision, and save each task's rubric and prompt verbatim.

Verification: files stored with Git LFS are checked by sha256; files stored as
plain git blobs (no LFS metadata on the Hub) are checked by the git blob sha1
(sha1 of "blob <size>\\0" + content) against the Hub's blob_id. Both the
local sha256 and the method used are recorded.

Layout (paths use the full task UUID and the original basename from the parquet):
    data/inputs/<task_id>/<original filename>     task inputs (model-visible later)
    private/gold/<task_id>/<original filename>    expert deliverables (never model-visible)
    private/rubric/<task_id>.json                 rubric_json column, byte-for-byte
    data/prompts/<task_id>.txt                    prompt column, byte-for-byte

Re-running is idempotent: files that already verify are kept.

Usage:
    python scripts/download_materials.py --parquet data/gdpval.parquet \
        --tasks data/selected_tasks.json --revision-file data/dataset_revision.json \
        --log data/download_verification.json
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download, hf_hub_url

REPO = "openai/gdpval"


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1_of(path: str) -> str:
    size = os.path.getsize(path)
    h = hashlib.sha1(b"blob %d\0" % size)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path, info):
    """Return (verified, method, expected_hash)."""
    if not os.path.exists(path) or info is None:
        return False, None, None
    lfs = getattr(info, "lfs", None)
    if lfs and lfs.sha256:
        return sha256_of(path) == lfs.sha256, "lfs_sha256", lfs.sha256
    blob = getattr(info, "blob_id", None)
    if blob:
        return git_blob_sha1_of(path) == blob, "git_blob_sha1", blob
    return False, None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--revision-file", required=True)
    ap.add_argument("--inputs-dir", default="data/inputs")
    ap.add_argument("--gold-dir", default="private/gold")
    ap.add_argument("--rubric-dir", default="private/rubric")
    ap.add_argument("--prompts-dir", default="data/prompts")
    ap.add_argument("--log", required=True)
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()

    revision = json.load(open(args.revision_file))["chosen_revision"]
    if not revision:
        print("ERROR: no verified revision in", args.revision_file, file=sys.stderr)
        return 2
    selected = json.load(open(args.tasks))["tasks"]
    task_ids = [t["task_id"] for t in selected]

    rows = {r["task_id"]: r for r in pq.read_table(args.parquet).to_pylist() if r["task_id"] in task_ids}
    missing = [t for t in task_ids if t not in rows]
    if missing:
        print("ERROR: task ids not in parquet:", missing, file=sys.stderr)
        return 2

    expected = []  # (role, task_id, repo_path) straight from the parquet columns
    for tid in task_ids:
        r = rows[tid]
        for p in r["reference_files"] or []:
            expected.append(("input", tid, p))
        for p in r["deliverable_files"] or []:
            expected.append(("gold", tid, p))
    seen = set()
    for role, tid, p in expected:
        key = (role, tid, os.path.basename(p))
        if key in seen:
            print("ERROR: duplicate basename within a task directory:", key, file=sys.stderr)
            return 2
        seen.add(key)

    api = HfApi()
    infos = {}
    paths = [p for _, _, p in expected]
    for i in range(0, len(paths), 50):
        for info in api.get_paths_info(args.repo, paths=paths[i:i + 50], repo_type="dataset",
                                       revision=revision, expand=True):
            infos[info.path] = info

    records = []
    n_ok = 0
    for role, tid, repo_path in expected:
        base = os.path.basename(repo_path)
        target_dir = os.path.join(args.inputs_dir if role == "input" else args.gold_dir, tid)
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, base)
        info = infos.get(repo_path)
        action = "missing_on_hf"
        if info is not None:
            ok, _, _ = verify(target, info)
            if ok:
                action = "kept_existing"
            else:
                cached = hf_hub_download(args.repo, filename=repo_path, repo_type="dataset", revision=revision)
                shutil.copyfile(cached, target)  # copyfile follows the cache symlink
                action = "downloaded"
        verified, method, expected_hash = verify(target, info)
        n_ok += verified
        lfs = getattr(info, "lfs", None) if info else None
        records.append({
            "role": role, "task_id": tid, "original_filename": base, "source_path": repo_path,
            "url": hf_hub_url(args.repo, repo_path, repo_type="dataset", revision=revision),
            "revision": revision, "local_path": target,
            "hf_storage": "lfs" if lfs else ("git_blob" if info else None),
            "hf_size": (lfs.size if lfs else getattr(info, "size", None)) if info else None,
            "hf_expected_hash": expected_hash, "verification_method": method,
            "sha256": sha256_of(target) if os.path.exists(target) else None,
            "size": os.path.getsize(target) if os.path.exists(target) else None,
            "verified": verified, "action": action,
        })
        print(f"  {'OK ' if verified else 'BAD'} {role:<5} {tid[:8]} {base} ({action}, {method})")

    os.makedirs(args.rubric_dir, exist_ok=True)
    os.makedirs(args.prompts_dir, exist_ok=True)
    for tid in task_ids:
        r = rows[tid]
        rp = os.path.join(args.rubric_dir, f"{tid}.json")
        with open(rp, "w", encoding="utf-8", newline="") as f:
            f.write(r["rubric_json"])
        pp = os.path.join(args.prompts_dir, f"{tid}.txt")
        with open(pp, "w", encoding="utf-8", newline="") as f:
            f.write(r["prompt"])
        records.append({"role": "rubric", "task_id": tid, "original_filename": None,
                        "source_path": "parquet column rubric_json", "url": None, "revision": revision,
                        "local_path": rp, "sha256": sha256_of(rp), "size": os.path.getsize(rp),
                        "item_count": len(json.loads(r["rubric_json"])), "verified": True, "action": "written"})
        records.append({"role": "prompt", "task_id": tid, "original_filename": None,
                        "source_path": "parquet column prompt", "url": None, "revision": revision,
                        "local_path": pp, "sha256": sha256_of(pp), "size": os.path.getsize(pp),
                        "verified": True, "action": "written"})

    out = {"repo_id": args.repo, "revision": revision,
           "run_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "expected_counts": {"input": sum(1 for e in expected if e[0] == "input"),
                               "gold": sum(1 for e in expected if e[0] == "gold")},
           "verified_file_count": n_ok, "records": records}
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    json.dump(out, open(args.log, "w", encoding="utf-8"), indent=2)
    bad = [r for r in records if not r["verified"]]
    print(f"expected inputs={out['expected_counts']['input']} gold={out['expected_counts']['gold']}; "
          f"verified files={n_ok}; unverified={len(bad)}; log -> {args.log}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
