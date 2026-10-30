#!/usr/bin/env python
"""Build data/manifest.json from the verified state on disk: the dataset copy,
each selected task's inputs, expert deliverables, rubric, prompt, and any
pre-staged resources. Every entry carries the role, full task UUID, original
filename, source path and URL, fixed revision, local relative path, size and
sha256. Counts are computed from the data, never typed in.

Usage:
    python scripts/build_manifest.py --tasks data/selected_tasks.json \
        --revision-file data/dataset_revision.json \
        --verification-log data/download_verification.json \
        --resources-dir data/resources --out data/manifest.json
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--revision-file", required=True)
    ap.add_argument("--verification-log", required=True)
    ap.add_argument("--resources-dir", default="data/resources")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sel = json.load(open(args.tasks))
    rev = json.load(open(args.revision_file))
    log = json.load(open(args.verification_log))
    revision = rev["chosen_revision"]
    if log["revision"] != revision:
        print("ERROR: verification log revision differs from dataset revision file", file=sys.stderr)
        return 2

    entries = []
    # Dataset copy
    lp = rev["local_parquet"]["path"]
    commit = next(c for c in rev["commits"] if c["commit_id"] == revision)
    pq_file = next(f for f in commit["files"] if f["matches_local"])
    present = os.path.exists(lp)
    entries.append({
        "role": "dataset", "task_id": None, "original_filename": os.path.basename(pq_file["path"]),
        "source_path": pq_file["path"],
        "url": f"https://huggingface.co/datasets/{rev['repo_id']}/resolve/{revision}/{pq_file['path']}",
        "revision": revision, "local_path": lp, "size": os.path.getsize(lp) if present else None,
        "sha256": sha256_of(lp) if present else None, "hf_expected_hash": pq_file["sha256"],
        "verification_method": "lfs_sha256",
        "verified": present and sha256_of(lp) == pq_file["sha256"], "present": present,
    })
    # Task materials from the verification log, re-hashed from disk now.
    for r in log["records"]:
        present = os.path.exists(r["local_path"])
        sha = sha256_of(r["local_path"]) if present else None
        e = {
            "role": r["role"], "task_id": r["task_id"], "original_filename": r["original_filename"],
            "source_path": r["source_path"], "url": r["url"], "revision": r["revision"],
            "local_path": r["local_path"], "size": os.path.getsize(r["local_path"]) if present else None,
            "sha256": sha, "present": present,
        }
        if r["role"] in ("input", "gold"):
            e["hf_storage"] = r.get("hf_storage")
            e["hf_expected_hash"] = r.get("hf_expected_hash")
            e["verification_method"] = r.get("verification_method")
            e["verified"] = bool(present and r.get("verified") and sha == r["sha256"])
        else:
            e["verified"] = bool(present and sha == r["sha256"])
            if "item_count" in r:
                e["item_count"] = r["item_count"]
        entries.append(e)
    # Pre-staged resources
    if os.path.isdir(args.resources_dir):
        for tid in sorted(os.listdir(args.resources_dir)):
            rj = os.path.join(args.resources_dir, tid, "resources.json")
            if not os.path.exists(rj):
                continue
            res = json.load(open(rj))
            for it in res["items"]:
                lp = it.get("local_path")
                present = bool(lp) and os.path.exists(lp)
                entries.append({
                    "role": "resource", "resource_kind": it["kind"], "task_id": tid,
                    "original_filename": os.path.basename(lp) if lp else None,
                    "source_path": None, "url": it.get("zip_url") or it["listed_url"],
                    "listed_url": it["listed_url"], "final_url": it.get("final_url"),
                    "fetched_at_utc": it.get("fetched_at_utc"), "revision": None,
                    "local_path": lp, "text_path": it.get("text_path"),
                    "size": os.path.getsize(lp) if present else None,
                    "sha256": sha256_of(lp) if present else None,
                    "recorded_sha256": it.get("sha256"), "title": it.get("title"),
                    "word_count": it.get("word_count"), "zip_entries": it.get("zip_entries"),
                    "zip_ext_counts": it.get("zip_ext_counts"), "present": present,
                    "ok_at_fetch": it["ok"], "notes": it.get("notes", []),
                })

    def count(role, **kw):
        return sum(1 for e in entries if e["role"] == role and all(e.get(k) == v for k, v in kw.items()))

    summary = {
        "tasks": len(sel["tasks"]),
        "inputs": count("input"), "inputs_verified": count("input", verified=True),
        "gold": count("gold"), "gold_verified": count("gold", verified=True),
        "rubrics": count("rubric"), "rubric_items_total": sum(e.get("item_count", 0) for e in entries if e["role"] == "rubric"),
        "prompts": count("prompt"),
        "resources": count("resource"), "resources_present": count("resource", present=True),
        "resources_ok_at_fetch": count("resource", ok_at_fetch=True),
    }
    out = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dataset": {"repo_id": rev["repo_id"], "repo_type": "dataset", "revision": revision,
                    "revision_created_at": rev["chosen_revision_created_at"]},
        "selected_tasks": sel["tasks"],
        "summary": summary,
        "entries": entries,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(json.dumps(summary, indent=2))
    print("manifest ->", args.out, "entries:", len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
