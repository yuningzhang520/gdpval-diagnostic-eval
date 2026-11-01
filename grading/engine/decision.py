"""Shared verdict assembly (engine): ``Result`` rows and the ``Decision`` collector (confirmed violation -> FAIL;
otherwise unreliable required input -> cannot_assess; otherwise PASS; violations and unassessable inputs both kept in
the evidence), with the attribution map of unassessable kinds. Moved verbatim from the 1137e2bb grader on 2026-11-01."""
from .cells import INVALID_KINDS, UNRELIABLE_KINDS, describe_cell

ATTRIBUTION = {"ambiguous": "grader_extraction", "unmapped": "grader_extraction", "grader_error": "grader_caused_recalculation", "unknown": "unknown",
               "collision": "grader_extraction", "unidentified": "unknown", "split_tables": "grader_extraction", "split_overlap": "grader_extraction"}


class Result:
    def __init__(self, item, verdict, evidence, deliverable=None, reference=None, note="", attribution=None):
        self.item, self.verdict, self.evidence, self.deliverable, self.reference, self.note, self.attribution = item, verdict, evidence, deliverable, reference, note, attribution

    def as_dict(self):
        d = {"item": self.item, "verdict": self.verdict, "evidence": self.evidence, "deliverable_value": self.deliverable, "reference_value": self.reference, "note": self.note, "source": "D"}
        if self.attribution:
            d["attribution"] = self.attribution
        return d


class Decision:
    """Collects everything a criterion depends on, then decides: confirmed violation -> FAIL;
    otherwise unreliable required input -> cannot_assess; otherwise PASS. Violations and
    unassessable inputs are both kept in the evidence."""

    def __init__(self, item: int, base_evidence: dict):
        self.item, self.evidence = item, dict(base_evidence)
        self.violations: list[dict] = []
        self.unassessable: list[dict] = []
        self.deliverable, self.reference = None, None

    def violation(self, kind: str, detail, attribution: str = "model_caused", **extra):
        self.violations.append({"kind": kind, "detail": detail, "attribution": attribution, **extra})

    def unreliable(self, kind: str, field: str, detail=None, **extra):
        self.unassessable.append({"kind": kind, "field": field, "detail": detail, "attribution": ATTRIBUTION.get(kind, "grader_extraction"), **extra})

    def cell(self, field: str, st: str, value, coord: str, row: int | None = None, recalc=None):
        """Register one cell the criterion needs: reliably invalid -> violation; unreliable -> unassessable."""
        if st in UNRELIABLE_KINDS:
            self.unreliable("grader_error", field, {"row": row, "cell": coord, "recalc": recalc}, cell=coord)
        elif st in INVALID_KINDS:
            self.violation(st, f"{field} at {coord} is {describe_cell(st, value)}", cell=coord, row=row, value=value)

    def result(self, note_ok: str) -> Result:
        ev = {**self.evidence, "violations": self.violations[:10], "violation_count": len(self.violations), "unassessable": self.unassessable[:10], "unassessable_count": len(self.unassessable)}
        if self.violations:
            kinds = sorted({v["kind"] for v in self.violations})
            attribution = self.violations[0]["attribution"]
            note = "confirmed violation: " + "; ".join(str(v["detail"])[:160] for v in self.violations[:3]) + ("; other inputs unassessable: " + ", ".join(sorted({u["field"] for u in self.unassessable})) if self.unassessable else "")
            return Result(self.item, "fail", ev, self.deliverable, self.reference, note + f" [{', '.join(kinds)}]", attribution)
        if self.unassessable:
            u = self.unassessable[0]
            note = "extraction_failed: " + "; ".join(f"{x['field']} {x['kind']}" + (f" ({str(x['detail'])[:100]})" if x["detail"] else "") for x in self.unassessable[:4])
            return Result(self.item, "cannot_assess", ev, self.deliverable, self.reference, note, u["attribution"])
        return Result(self.item, "pass", ev, self.deliverable, self.reference, note_ok)
