"""c357f0e2-963d-4eb7-a6fa-3078fe55b3ba: UAT test plan from 'UAT Plan - Template.xlsx'.
The task has no numeric expectation to recompute: its grader uses structural and literal checks on the workbook (template columns, case rows, field values).
This record states that, with the hashes of the source files, so that the official grading entry point
(grading.run_grading, which requires one reference per task and records its hash) can run. The grader does
not read any value from it."""
import hashlib
import os
from common import INPUTS, save

TID = "c357f0e2-963d-4eb7-a6fa-3078fe55b3ba"


def main():
    d = os.path.join(INPUTS, TID)
    files = {f: hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest() for f in sorted(os.listdir(d)) if not f.startswith(".")}
    print("inputs:", files)
    save(TID, {"task_id": TID, "independent_recalculation": None, "reason": "no numeric expectation in this task; the grader's checks are structural, literal or judge-based and read no reference value",
               "inputs_sha256": files})


if __name__ == "__main__":
    main()
