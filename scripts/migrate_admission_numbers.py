"""One-off: rewrite ipd_admissions.admission_no to short IPD-100x format."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                UPDATE ipd_admissions
                SET admission_no = 'IPD-' || (1000 + id)::text
                WHERE admission_no <> 'IPD-' || (1000 + id)::text
                RETURNING id, admission_no
                """
            )
        ).fetchall()
        for row in rows:
            print(f"updated id={row.id} -> {row.admission_no}")
        if not rows:
            print("no rows needed update")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
