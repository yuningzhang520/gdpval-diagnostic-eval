"""2ea2e5b5-257f-42e6-a7dc-93763f28b19d: hours by activity category and by segment from 'Work Time Study - Source.xlsx'.
Segment mappings are the ones stated in the task prompt."""
import collections
import re
from common import inp, rubric, ws_values, save

TID = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"
COST = {"Audit/Compliance", "Break/Fix", "Deployment of Upgrades", "Patching", "Service Request", "Shift Handover Meeting"}
TIME = {"High": {"Break/Fix"}, "Medium": {"Audit/Compliance", "Automation", "Change Management Meeting", "Develop/Integrate Tooling", "Problem Management", "Process Improvement", "Patching", "Service Request"},
        "Low": {"Deployment of Upgrades", "Shift Handover Meeting", "Training"}}
STRAT = {"High": {"Automation", "Problem Management", "Process Improvement"}, "Medium": {"Audit/Compliance", "Change Management Meeting", "Develop/Integrate Tooling", "Service Request", "Shift Handover Meeting", "Training"},
         "Low": {"Break/Fix", "Deployment of Upgrades", "Patching"}}


def canon(s):
    """Canonical activity label: trimmed, whitespace around '/' removed, internal runs of spaces collapsed.
    Merges the source variants 'Audit / Compliance' and 'Break/ Fix' into the prompt's spellings."""
    return re.sub(r"\s+", " ", re.sub(r"\s*/\s*", "/", str(s).strip()))


def main():
    ws = ws_values(inp(TID, "Work Time Study - Source.xlsx"), "source")
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[2] is not None]
    raw_labels = collections.Counter(str(r[2]) for r in rows)
    hours = collections.defaultdict(float)
    merges = collections.defaultdict(set)
    for r in rows:
        merges[canon(r[2])].add(str(r[2]))
        hours[canon(r[2])] += float(r[4] or 0)
    label_merges = {k: sorted(v) for k, v in merges.items() if len(v) > 1 or sorted(v)[0] != k}
    print("raw labels merged into canonical labels:", label_merges)
    total = sum(hours.values())
    print(f"rows={len(rows)} raw activity labels={dict(raw_labels)}")
    print(f"total hours={total}")
    pct = {k: v / total * 100 for k, v in sorted(hours.items())}
    for k, v in pct.items():
        print(f"  {k:<28} hours={hours[k]:>8.2f} pct={v:.2f}%")
    cats = set(hours)
    print("categories not in the prompt's 12:", cats - (COST | TIME["Medium"] | TIME["High"] | TIME["Low"]))
    margin = {"Cost": sum(hours[k] for k in hours if k in COST), "Investment": sum(hours[k] for k in hours if k not in COST)}
    time = {lvl: sum(hours[k] for k in hours if k in s) for lvl, s in TIME.items()}
    strat = {lvl: sum(hours[k] for k in hours if k in s) for lvl, s in STRAT.items()}
    print("margin %:", {k: round(v / total * 100, 2) for k, v in margin.items()})
    print("time %:", {k: round(v / total * 100, 2) for k, v in time.items()})
    print("strategic %:", {k: round(v / total * 100, 2) for k, v in strat.items()})
    rub = [(it["criterion"][:80], re.findall(r"(\d+\.\d+)%", it["criterion"])) for it in rubric(TID) if re.search(r"\d+\.\d+%", it["criterion"])]
    print("rubric percentages for side-by-side reading:")
    for c, n in rub:
        print("  ", n, "|", c)
    save(TID, {"rows": len(rows), "raw_labels": dict(raw_labels), "label_merges": label_merges, "total_hours": total, "hours": dict(hours), "pct": pct,
               "margin": margin, "time": time, "strategic": strat})
