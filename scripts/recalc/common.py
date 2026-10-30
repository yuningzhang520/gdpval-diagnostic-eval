"""Shared helpers for the independent recalculations. Each task module computes
expected figures from the task's SOURCE files only; rubric and gold values are
read separately for comparison and never used inside the computation."""
import datetime as dt
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP

import openpyxl

INPUTS = "data/inputs"
GOLD = "private/gold"
RUBRIC = "private/rubric"
OUT = "private/checks/recalc"


def inp(task_id, name):
    return os.path.join(INPUTS, task_id, name)


def gold(task_id, name):
    return os.path.join(GOLD, task_id, name)


def rubric(task_id):
    return json.load(open(os.path.join(RUBRIC, f"{task_id}.json"), encoding="utf-8"))


def ws_values(path, sheet=None, data_only=True):
    wb = openpyxl.load_workbook(path, data_only=data_only)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return ws


def round_half_up(x, nd=0):
    q = Decimal(1).scaleb(-nd)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def save(task_id, payload):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{task_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"-> {path}")


def is_date(v):
    return isinstance(v, (dt.datetime, dt.date))


def numbers_in(text):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text)]
