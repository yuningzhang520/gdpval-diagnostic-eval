"""a45bc83b-22f9-4def-8d89-9c5661b2b86f: GCP migration design from 'Current_Architecture.pdf' and 'Current_Architecture_Summary.docx'.
The task has no numeric expectation to recompute: its grader uses document-structure checks and judge criteria (requirement layers in grading.judge.A45_LAYERS).
This record states that, with the hashes of the source files, so that the official grading entry point
(grading.run_grading, which requires one reference per task and records its hash) can run. The grader does
not read any value from it."""
import hashlib
import os
from common import INPUTS, save

TID = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"


def main():
    d = os.path.join(INPUTS, TID)
    files = {f: hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest() for f in sorted(os.listdir(d)) if not f.startswith(".")}
    print("inputs:", files)
    save(TID, {"task_id": TID, "independent_recalculation": None, "reason": "no numeric expectation in this task; the grader's checks are structural, literal or judge-based and read no reference value",
               "inputs_sha256": files})


if __name__ == "__main__":
    main()
