#!/usr/bin/env python
"""Resolve the pre-declared 8-character task prefixes to full GDPval task UUIDs.

The prefixes are reading aids from the planning documents; every manifest and
path downstream uses the full UUID written by this script. The script fails if
any prefix is ambiguous or absent, and reports whether the "deep" group is a
complete occupation block.

Usage:
    python scripts/resolve_tasks.py --parquet data/gdpval.parquet --out data/selected_tasks.json \
        --deep b5d2e6f1 f841ddcf 47ef842d 1137e2bb c3525d4d \
        --supplementary 7b08cd4d 7d7fc9a7 2ea2e5b5 c357f0e2 a45bc83b
"""
import argparse
import collections
import hashlib
import json
import sys

import pyarrow.parquet as pq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--deep", nargs="+", required=True, help="prefixes of the occupation-complete block")
    ap.add_argument("--supplementary", nargs="+", required=True, help="prefixes of the supplementary tasks")
    args = ap.parse_args()

    table = pq.read_table(args.parquet, columns=["task_id", "occupation", "sector"])
    rows = table.to_pylist()
    ids = [r["task_id"] for r in rows]
    by_id = {r["task_id"]: r for r in rows}
    by_occ = collections.defaultdict(list)
    for r in rows:
        by_occ[r["occupation"]].append(r["task_id"])

    tasks = []
    errors = []
    for group, prefixes in (("deep", args.deep), ("supplementary", args.supplementary)):
        for p in prefixes:
            matches = [t for t in ids if t.startswith(p)]
            if len(matches) != 1:
                errors.append(f"prefix {p}: {len(matches)} matches {matches}")
                continue
            r = by_id[matches[0]]
            tasks.append({"task_id": r["task_id"], "prefix": p, "group": group,
                          "occupation": r["occupation"], "sector": r["sector"]})
    if errors:
        for e in errors:
            print("ERROR", e, file=sys.stderr)
        return 1
    if len({t["task_id"] for t in tasks}) != len(tasks):
        print("ERROR duplicate task ids", file=sys.stderr)
        return 1

    deep_ids = sorted(t["task_id"] for t in tasks if t["group"] == "deep")
    deep_occs = sorted({t["occupation"] for t in tasks if t["group"] == "deep"})
    complete_block = len(deep_occs) == 1 and sorted(by_occ[deep_occs[0]]) == deep_ids

    with open(args.parquet, "rb") as f:
        parquet_sha = hashlib.sha256(f.read()).hexdigest()
    out = {
        "parquet_sha256": parquet_sha,
        "groups": {
            "deep": {"description": "one occupation, complete block of 5 tasks",
                     "occupations": deep_occs, "is_complete_occupation_block": complete_block},
            "supplementary": {"description": "tasks from other occupations chosen to supplement the two research-question requirements",
                              "occupations": sorted({t["occupation"] for t in tasks if t["group"] == "supplementary"})},
        },
        "tasks": tasks,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"resolved {len(tasks)} tasks -> {args.out}; deep group complete block: {complete_block}")
    for t in tasks:
        print(f"  {t['group']:<13} {t['prefix']} -> {t['task_id']} | {t['occupation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
