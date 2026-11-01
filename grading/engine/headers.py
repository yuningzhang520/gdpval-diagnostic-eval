"""Shared header mapping (engine): canonical fields from a header row with a uniqueness requirement. Moved from the
1137e2bb grader on 2026-11-01 and generalised over the task's schema (exact synonyms, containment of long synonyms,
keyword rules with per-field ``keyword_exclude``); the 1137 behaviour is unchanged (its wrapper passes its schemas and
the former special case as ``keyword_exclude``)."""
from .cells import norm_text


def map_columns(header: list, schema: dict, flag_schema: dict | None = None) -> dict:
    """Map a header row to canonical fields with a uniqueness requirement. For every field all
    candidate columns are collected (exact synonyms; containment of long synonyms and keyword rules
    only when no exact candidate exists). A column claimed exactly by one field is withdrawn from
    the non-exact candidate lists of other fields. A field is mapped only when exactly one candidate
    remains and no other field claims that column; otherwise it is ``ambiguous`` (candidates kept as
    evidence). A field with no candidate is ``confirmed_missing`` when no unrecognised header remains
    in the row (structural evidence that the column does not exist) and ``unmapped`` otherwise (the
    column may exist under a name the schema does not know). Column order never decides."""
    hdr = [norm_text(h) for h in header]
    cands: dict[str, list[tuple[int, str]]] = {}
    for field, spec in schema.items():
        exact = [(j, "exact") for j, h in enumerate(hdr) if h and h in spec["synonyms"]]
        cands[field] = exact or [(j, "contains") for j, h in enumerate(hdr) if h and any(len(s) >= 6 and s in h for s in spec["synonyms"])]
    for field, spec in (flag_schema or {}).items():
        exact = [(j, "exact") for j, h in enumerate(hdr) if h and h in spec["synonyms"]]
        if exact:
            cands[field] = exact
            continue
        must_any, also_any = spec["keywords"]
        kw = []
        for j, h in enumerate(hdr):
            if not h or not any(m in h for m in must_any) or (also_any and not any(a in h for a in also_any)):
                continue
            if any(x in h for x in spec.get("keyword_exclude", ())):  # a keyword match that another field's wording would explain (task spec)
                continue
            kw.append((j, "keyword"))
        cands[field] = kw
    exact_owner: dict[int, set[str]] = {}
    for field, lst in cands.items():
        for j, m in lst:
            if m == "exact":
                exact_owner.setdefault(j, set()).add(field)
    for field, lst in cands.items():  # exact precedence: a column exactly claimed elsewhere is not a weak candidate here
        cands[field] = [(j, m) for j, m in lst if m == "exact" or j not in exact_owner]
    claims: dict[int, set[str]] = {}
    for field, lst in cands.items():
        for j, _ in lst:
            claims.setdefault(j, set()).add(field)
    cols, method, ambiguous = {}, {}, {}
    for field, lst in cands.items():
        if len(lst) == 1 and len(claims[lst[0][0]]) == 1:
            cols[field], method[field] = lst[0][0], lst[0][1]
        elif lst:
            ambiguous[field] = [{"col": j, "header": hdr[j], "method": m, "also_claimed_by": sorted(claims[j] - {field})} for j, m in lst]
    taken = set(cols.values()) | {j for lst in ambiguous.values() for j in (c["col"] for c in lst)}
    unmapped_headers = [hdr[j] for j in range(len(hdr)) if hdr[j] and j not in taken]
    field_status = {}
    for field in list(schema) + list(flag_schema or {}):
        if field in cols:
            field_status[field] = "ok"
        elif field in ambiguous:
            field_status[field] = "ambiguous"
        elif unmapped_headers:
            field_status[field] = "unmapped"
        else:
            field_status[field] = "confirmed_missing"
    return {"cols": cols, "method": method, "ambiguous": ambiguous, "field_status": field_status,
            "candidates": {f: [{"col": j, "header": hdr[j], "method": m} for j, m in lst] for f, lst in cands.items() if lst},
            "unmapped_headers": unmapped_headers, "headers": hdr}
