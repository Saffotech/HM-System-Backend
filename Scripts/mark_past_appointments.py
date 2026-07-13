"""
Mark past open appointments as no_show (CROSS-1).

Run from hms-backend root:

  python Scripts/mark_past_appointments.py
  python Scripts/mark_past_appointments.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python Scripts/...` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import SessionLocal
from Services.appointment_lifecycle_service import mark_past_appointments_no_show


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mark past scheduled/waiting appointments as no_show"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matches only; do not update the database",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = mark_past_appointments_no_show(db, dry_run=args.dry_run)
    finally:
        db.close()

    mode = "DRY-RUN" if result["dry_run"] else "UPDATED"
    print(f"[{mode}] as_of={result['as_of']}")
    print(f"matched={result['matched']} updated={result['updated']}")
    if result["appointment_ids"]:
        print("appointment_ids:", ", ".join(str(i) for i in result["appointment_ids"]))
    else:
        print("No past open appointments found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
