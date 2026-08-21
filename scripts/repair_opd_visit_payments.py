"""One-off: cap OPD payment rows and visit paid_amount to bill grand_total."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.super_admin_profile import SuperAdminProfile  # noqa: F401
from Services.opd_helpers import repair_visit_payment_ledger


def main() -> None:
    db = SessionLocal()
    try:
        updated = repair_visit_payment_ledger(db)
        db.commit()
        print(f"repaired {updated} OPD visit(s)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
