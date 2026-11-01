"""Minimal manual reconciliation of one ledger unit (B2-1). Appends a non-overwriting manual_resolution event:
settled_amount (the verified amount in USD, from the provider account or an investigation) closes an open
reservation of unknown outcome at that amount, or adjusts an estimated settlement and lifts that unit's hold;
unresolvable records that the investigation could not establish the cost and changes nothing (the hold or the
open reservation stays; nothing is released; no further paid start is allowed). Blocking is lifted only when the
ledger shows no other open reservation, hold, unresolvable unit or stop. Nothing here calls a provider.
Usage: python -m harness.ledger_admin resolve --ledger <ledger.json> --unit-id <unit> --resolution settled_amount --amount-usd 0.1234 --basis "<evidence>" --by "<name>"
       python -m harness.ledger_admin resolve --ledger <ledger.json> --unit-id <unit> --resolution unresolvable --basis "<investigation>" --by "<name>"
       python -m harness.ledger_admin status  --ledger <ledger.json> [--run-uuid <uuid>]"""
import argparse
import json
import os
import sys

from .budget import BudgetLedger, LedgerConflict, RESOLUTIONS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ledger(path: str, config_path: str) -> BudgetLedger:
    from .launcher import load_config, prices_from_config
    cfg = load_config(config_path)
    return BudgetLedger.open_existing(path, prices_from_config(cfg))  # ceiling and run class come from the ledger itself


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="manual reconciliation of one budget-ledger unit (append-only)")
    p.add_argument("command", choices=("resolve", "status"))
    p.add_argument("--ledger", required=True)
    p.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    p.add_argument("--unit-id", default=None)
    p.add_argument("--resolution", choices=RESOLUTIONS, default=None)
    p.add_argument("--amount-usd", default=None, help="verified amount for settled_amount (USD)")
    p.add_argument("--currency", default="USD")
    p.add_argument("--basis", default=None, help="evidence the reconciliation rests on (account statement, investigation result)")
    p.add_argument("--by", default=None, help="audit identity of the person reconciling")
    p.add_argument("--run-uuid", default=None)
    args = p.parse_args(argv)
    ledger = _ledger(args.ledger, args.config)
    if args.command == "status":
        snap = ledger.snapshot()
        out = {k: snap[k] for k in ("ledger_id", "open_reservations", "review_pending_units", "unresolvable_units", "resolved_units", "stops", "settled_usd", "reserved_usd", "remaining_usd")}
        if args.run_uuid:
            out["run"] = ledger.units_for_run(args.run_uuid)
        print(json.dumps(out, indent=1, default=str))
        return 0
    if not (args.unit_id and args.resolution and args.basis and args.by):
        raise SystemExit("resolve needs --unit-id, --resolution, --basis and --by")
    if args.currency != "USD":
        raise SystemExit("only USD amounts are recorded")
    try:
        entry = ledger.resolve_manually(args.unit_id, resolution=args.resolution, by=args.by, basis=args.basis, amount_usd=args.amount_usd, currency=args.currency)
    except LedgerConflict as ex:
        print(f"refused: {ex}", file=sys.stderr)
        return 2
    snap = ledger.snapshot()
    print(json.dumps({"recorded": entry, "still_blocking": {"open_reservations": snap["open_reservations"], "review_pending_units": snap["review_pending_units"],
                                                             "unresolvable_units": snap["unresolvable_units"], "stops": snap["stops"]}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
