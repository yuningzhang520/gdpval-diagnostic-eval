#!/usr/bin/env python
"""Run every independent recalculation and write one JSON per task under
private/checks/recalc/. Usage: python scripts/recalc/run_all.py [prefix ...]"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
MODULES = [
    "task_b5d2e6f1_sales_by_brand",
    "task_f841ddcf_po_log_june",
    "task_47ef842d_wos",
    "task_1137e2bb_po_audit",
    "task_c3525d4d_floorstand",
    "task_7b08cd4d_tour_pl",
    "task_7d7fc9a7_prepaid",
    "task_2ea2e5b5_work_study",
    "task_c357f0e2_uat_plan",
    "task_a45bc83b_gcp_design",
]
only = sys.argv[1:]
for m in MODULES:
    if only and not any(p in m for p in only):
        continue
    print("=" * 100)
    print(m)
    print("=" * 100)
    importlib.import_module(m).main()
