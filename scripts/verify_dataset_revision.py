#!/usr/bin/env python
"""Verify that a local GDPval parquet file matches the parquet stored at specific
commits of the Hugging Face dataset repository, and record the result.

Only Hugging Face metadata is read (no file download). The local file is never
modified. Exit status is non-zero when no commit matches.

Usage:
    python scripts/verify_dataset_revision.py --parquet data/gdpval.parquet \
        --out data/dataset_revision.json
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys

from huggingface_hub import HfApi

DEFAULT_REPO = "openai/gdpval"


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    args = ap.parse_args()

    local_sha = sha256_of(args.parquet)
    local_size = os.path.getsize(args.parquet)
    print(f"local parquet: {args.parquet} size={local_size} sha256={local_sha}")

    api = HfApi()
    # Parquet files live under data/ in this repo; list that folder at main to learn the paths.
    data_entries = list(api.list_repo_tree(args.repo, repo_type="dataset", path_in_repo="data"))
    parquet_paths = sorted(e.path for e in data_entries if e.path.endswith(".parquet"))
    print("parquet paths at main:", parquet_paths)
    if not parquet_paths:
        print("no parquet files found under data/ at main", file=sys.stderr)
        return 2

    commits = api.list_repo_commits(args.repo, repo_type="dataset")  # newest first
    records = []
    for c in commits:
        rec = {
            "commit_id": c.commit_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "title": c.title,
            "files": [],
        }
        try:
            infos = api.get_paths_info(
                args.repo, paths=parquet_paths, repo_type="dataset", revision=c.commit_id, expand=True
            )
        except Exception as exc:  # noqa: BLE001 - record and continue
            rec["error"] = f"{type(exc).__name__}: {exc}"[:200]
            records.append(rec)
            continue
        for info in infos:
            lfs = getattr(info, "lfs", None)
            fsha = lfs.sha256 if lfs else None
            fsize = lfs.size if lfs else getattr(info, "size", None)
            rec["files"].append(
                {
                    "path": info.path,
                    "sha256": fsha,
                    "size": fsize,
                    "is_lfs": bool(lfs),
                    "matches_local": (fsha == local_sha),
                }
            )
        rec["matches_local"] = any(f["matches_local"] for f in rec["files"])
        records.append(rec)

    matching = [r for r in records if r.get("matches_local")]
    chosen = matching[0] if matching else None  # newest matching commit
    earliest = matching[-1] if matching else None
    out = {
        "repo_id": args.repo,
        "repo_type": "dataset",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "local_parquet": {"path": args.parquet, "size": local_size, "sha256": local_sha},
        "parquet_paths_at_main": parquet_paths,
        "commits": records,
        "matching_commit_count": len(matching),
        "chosen_revision": chosen["commit_id"] if chosen else None,
        "chosen_revision_created_at": chosen["created_at"] if chosen else None,
        "earliest_matching_revision": earliest["commit_id"] if earliest else None,
        "earliest_matching_created_at": earliest["created_at"] if earliest else None,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"commits examined: {len(records)}, matching: {len(matching)}")
    for r in records:
        flag = "MATCH" if r.get("matches_local") else "-----"
        shas = ",".join((f["sha256"] or "none")[:12] for f in r["files"]) or r.get("error", "?")
        print(f"  {flag} {r['commit_id'][:12]} {r['created_at']} {shas} | {r['title'][:60]}")
    print("chosen revision:", out["chosen_revision"])
    return 0 if chosen else 1


if __name__ == "__main__":
    sys.exit(main())
