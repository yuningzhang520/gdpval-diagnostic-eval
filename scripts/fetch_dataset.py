#!/usr/bin/env python
"""Download the GDPval parquet at the verified dataset revision and check its sha256.

Inverse of verify_dataset_revision.py for a clean clone: that script established the revision from a
local parquet; this one rebuilds the local parquet from the revision and hash recorded in
data/dataset_revision.json. Fails (exit 1) and removes the copy if the hash does not match.

Usage:
    python scripts/fetch_dataset.py --revision-file data/dataset_revision.json --out data/gdpval.parquet
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

from huggingface_hub import hf_hub_download

DEFAULT_REPO = "openai/gdpval"


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    args = ap.parse_args()

    rev = json.load(open(args.revision_file, encoding="utf-8"))
    revision = rev["chosen_revision"]
    paths = rev["parquet_paths_at_main"]
    expected_sha = rev["local_parquet"]["sha256"]
    expected_size = rev["local_parquet"]["size"]
    if not revision or len(paths) != 1:
        print(f"ERROR: revision file must name one revision and exactly one parquet path; got {revision!r}, {paths!r}", file=sys.stderr)
        return 2
    print(f"downloading {paths[0]} from {args.repo} @ {revision}")
    cached = hf_hub_download(args.repo, filename=paths[0], repo_type="dataset", revision=revision)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    shutil.copyfile(cached, args.out)  # copyfile follows the cache symlink
    sha, size = sha256_of(args.out), os.path.getsize(args.out)
    print(f"local parquet: {args.out} size={size} sha256={sha}")
    print(f"expected:      size={expected_size} sha256={expected_sha}")
    if sha != expected_sha or size != expected_size:
        os.remove(args.out)
        print("ERROR: hash mismatch; the copy was removed", file=sys.stderr)
        return 1
    print("OK: parquet matches the recorded revision hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
