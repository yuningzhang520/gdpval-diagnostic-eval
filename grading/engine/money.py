"""Shared money helpers (engine): exact Decimal parsing of monetary text and cells, HALF_UP cent quantization on the
Decimal (never on a float), and cent-level equality. Introduced for 7d7fc9a7 (2026-11-01); the 1137e2bb grader keeps
its own two-decimal price rule (``q2``) because its rule was approved separately with the same semantics."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_MONEY = re.compile(r"^\(?\s*-?\s*\$?\s*-?\s*([\d,]*\.?\d+)\s*\)?$")


def parse_money(v) -> Decimal | None:
    """Decimal from a number or monetary text ("$1,234.56", "(1,234.56)" negative, "1234.5"); None for anything else
    (blank, words, booleans, NaN / Infinity)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            d = Decimal(str(v))
        except InvalidOperation:
            return None
        return d if d.is_finite() else None
    if isinstance(v, Decimal):
        return v if v.is_finite() else None
    s = str(v).strip()
    if not s:
        return None
    m = _MONEY.match(s)
    if not m:
        return None
    negative = (s.startswith("(") and s.endswith(")")) or "-" in s.split(m.group(1))[0]
    try:
        d = Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    return -d if negative else d


def cents(x) -> Decimal | None:
    """HALF_UP quantization to cents of a Decimal or parseable value; None when not a finite number."""
    d = x if isinstance(x, Decimal) else parse_money(x)
    if d is None or not d.is_finite():
        return None
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def cents_equal(a, b) -> bool:
    ca, cb = cents(a), cents(b)
    return ca is not None and cb is not None and ca == cb


def close(a, b, tolerance: str = "0.005") -> bool:
    """|a - b| < tolerance on Decimals (identity checks on a deliverable's own stored values, which may carry float noise)."""
    da, db = parse_money(a), parse_money(b)
    return da is not None and db is not None and abs(da - db) < Decimal(tolerance)
