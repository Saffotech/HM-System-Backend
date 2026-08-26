"""
Seed reference data: permissions, roles, departments, beds.

Usage:
  python seed.py          Safe sync — upsert only (safe on existing DB)
  python seed.py --fresh  Wipe roles/permissions and reseed (empty DB only)
"""
import argparse
import sys
from decimal import Decimal

from sqlalchemy import text

from database import SessionLocal
from Models.department import Department
from Models.lab_test import LabTest
from Models.doctor_profile import DoctorProfile  # noqa: F401 — User relationship
from Models.hospital_settings import SETTINGS_ROW_ID, HospitalSettings
from Models.opd_settings import OPD_SETTINGS_ROW_ID, OpdSettings
from Models.nurse_profile import NurseProfile
from Models.receptionist_profile import ReceptionistProfile
from Models.lab_technician_profile import LabTechnicianProfile
from Models.opd_billing_profile import OpdBillingProfile
from Models.ipd_profile import IpdProfile
from Models.pharmacist_profile import PharmacistProfile
from Models.admin_profile import AdminProfile
from Models.super_admin_profile import SuperAdminProfile
from Models.role import Permission, Role, RolePermission
from Models.user import User

PERMISSIONS_LIST = [
    "patients:view",
    "patients:create",
    "patients:update",
    "patients:delete",
    "users:list",
    "users:create",
    "users:delete",
    "users:activate",
    "roles:create",
    "roles:view",
    "billing:view",
    "billing:create",
    "billing:update",
    "billing:delete",
    "opd:create",
    "opd:view",
    "lab:view",
    "lab:create",
    "lab:update",
    "lab:upload_report",
    "lab_catalog:view",
    "lab_catalog:create",
    "lab_catalog:update",
    "lab_catalog:activate",
    "prescriptions:create",
    "prescriptions:view",
    "prescriptions:update",
    "prescriptions:delete",
    "prescriptions:dispense",
    "appointments:view",
    "appointments:create",
    "appointments:update",
    "reports:view",
    "settings:manage",
    "audit:view",
    "nurse_vitals:view",
    "nurse_vitals:create",
    "nurse_vitals:update",
    "nurse_notes:view",
    "nurse_notes:create",
    "nurse_notes:update",
    "nurse_lab_reports:view",
    "doctor_vitals:view",
    "doctor_notes:view",
    "nurse_profile:view",
    "nurse_profile:update",
    "nurse_profile:upload_image",
    "nurse_profile:delete_image",
    "doctor_profile:view",
    "doctor_profile:update",
    "doctor_profile:upload_image",
    "doctor_profile:delete_image",
    "receptionist_profile:view",
    "receptionist_profile:update",
    "receptionist_profile:upload_image",
    "receptionist_profile:delete_image",
    "lab_technician_profile:view",
    "lab_technician_profile:update",
    "lab_technician_profile:upload_image",
    "lab_technician_profile:delete_image",
    "opd_billing_profile:view",
    "opd_billing_profile:update",
    "opd_billing_profile:upload_image",
    "opd_billing_profile:delete_image",
    "pharmacist_profile:view",
    "pharmacist_profile:update",
    "pharmacist_profile:upload_image",
    "pharmacist_profile:delete_image",
    "admin_profile:view",
    "admin_profile:update",
    "admin_profile:upload_image",
    "admin_profile:delete_image",
    "super_admin_profile:view",
    "super_admin_profile:update",
    "super_admin_profile:upload_image",
    "super_admin_profile:delete_image",
    "notifications:view",
    "notifications:update",
    "nurse_medication:view",
    "nurse_medication:create",
    "nurse_medication:update",
    "nurse_handover:view",
    "nurse_handover:create",
    "nurse_handover:update",
    "nurse_handover:submit",
    "nurse_doctor_visits:view",
    "nurse_doctor_visits:create",
    "nurse_doctor_visits:update",
    "nurse_other_visits:view",
    "nurse_other_visits:create",
    "nurse_other_visits:update",
    "doctor_patient_visits:view",
    "bed_allocation:view",
    "bed_allocation:create",
    "bed_allocation:update",
    "bed_allocation:delete",
    "bed_allocation:assign",
    "workforce:view",
    "workforce:create",
    "workforce:update",
    "workforce:delete",
    "roster:manage",
    "receptionist:view_queues",
    "receptionist:view_doctor_schedule",
    "ipd:dashboard",
    "ipd:patients:list",
    "ipd:patients:view",
    "ipd:admission:create",
    "ipd:admission:discharge",
    "ipd:beds:view",
    "ipd:beds:assign",
    "ipd:beds:transfer",
    "ipd:visits:create",
    "ipd:bill:view",
    "ipd:bill:generate",
    "ipd:bill:pay",
    "ipd:bill:history",
    "ipd_profile:view",
    "ipd_profile:update",
    "ipd_profile:upload_image",
    "ipd_profile:delete_image",
]

# Hospital Admin panel — see Docs/backend/roles/admin.md
ADMIN_PERMISSIONS = [
    "users:list",
    "users:create",
    "users:activate",
    "users:delete",
    "roles:view",
    "reports:view",
    "admin_profile:view",
    "admin_profile:update",
    "admin_profile:upload_image",
    "admin_profile:delete_image",
    "notifications:view",
    "notifications:update",
    "bed_allocation:view",
    "bed_allocation:create",
    "bed_allocation:update",
    "bed_allocation:delete",
    "bed_allocation:assign",
    "workforce:view",
    "workforce:create",
    "workforce:update",
    "workforce:delete",
    "roster:manage",
]

ROLES_DATA = {
    "admin": {
        "description": "System administrator",
        "permissions": "__all__",
    },
    "super_admin": {
        "description": "Hospital owner / super administrator",
        "permissions": "__all__",
    },
    "doctor": {
        "description": "Clinical doctor",
        "permissions": [
            "patients:view",
            "prescriptions:create",
            "prescriptions:update",
            "prescriptions:delete",
            "lab:create",
            "lab:view",
            "lab_catalog:view",
            "appointments:view",
            "appointments:update",
            "doctor_profile:view",
            "doctor_profile:update",
            "doctor_profile:upload_image",
            "doctor_profile:delete_image",
            "notifications:view",
            "notifications:update",
            "doctor_patient_visits:view",
            "doctor_vitals:view",
            "doctor_notes:view",
        ],
    },
    "nurse": {
        "description": "Nursing staff",
        "permissions": [
            "patients:view",
            "opd:view",
            "nurse_vitals:view",
            "nurse_vitals:create",
            "nurse_vitals:update",
            "nurse_notes:view",
            "nurse_notes:create",
            "nurse_notes:update",
            "nurse_lab_reports:view",
            "nurse_profile:view",
            "nurse_profile:update",
            "nurse_profile:upload_image",
            "nurse_profile:delete_image",
            "notifications:view",
            "notifications:update",
            "nurse_medication:view",
            "nurse_medication:create",
            "nurse_medication:update",
            "nurse_handover:view",
            "nurse_handover:create",
            "nurse_handover:update",
            "nurse_handover:submit",
            "nurse_doctor_visits:view",
            "nurse_doctor_visits:create",
            "nurse_doctor_visits:update",
            "nurse_other_visits:view",
            "nurse_other_visits:create",
            "nurse_other_visits:update",
        ],
    },
    "opd_billing": {
        "description": "OPD and Billing staff",
        "permissions": [
            "patients:view",
            "patients:create",
            "patients:update",
            "patients:delete",
            "opd:create",
            "opd:view",
            "billing:view",
            "billing:create",
            "billing:update",
            "billing:delete",
            "appointments:view",
            "appointments:create",
            "appointments:update",
            "opd_billing_profile:view",
            "opd_billing_profile:update",
            "opd_billing_profile:upload_image",
            "opd_billing_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
    "ipd": {
        "description": "IPD admissions, beds, stay billing, and discharge",
        "permissions": [
            "patients:view",
            "patients:create",
            "patients:update",
            "ipd:dashboard",
            "ipd:patients:list",
            "ipd:patients:view",
            "ipd:admission:create",
            "ipd:admission:discharge",
            "ipd:beds:view",
            "ipd:beds:assign",
            "ipd:beds:transfer",
            "ipd:visits:create",
            "ipd:bill:view",
            "ipd:bill:generate",
            "ipd:bill:pay",
            "ipd:bill:history",
            "ipd_profile:view",
            "ipd_profile:update",
            "ipd_profile:upload_image",
            "ipd_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
    "pharmacist": {
        "description": "Pharmacy staff",
        "permissions": [
            # FE-backed only (patients:view unused — allergies come on prescription payloads)
            "prescriptions:view",
            "prescriptions:dispense",
            "pharmacist_profile:view",
            "pharmacist_profile:update",
            "pharmacist_profile:upload_image",
            "pharmacist_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
    "lab_technician": {
        "description": "Laboratory technician",
        "permissions": [
            # FE-backed only (patients:view unused; lab:create is doctor-owned)
            "lab:view",
            "lab:update",
            "lab:upload_report",
            "lab_technician_profile:view",
            "lab_technician_profile:update",
            "lab_technician_profile:upload_image",
            "lab_technician_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
    "receptionist": {
        "description": "Reception / front desk queue monitoring (view only)",
        "permissions": [
            "receptionist:view_queues",
            "receptionist:view_doctor_schedule",
            "receptionist_profile:view",
            "receptionist_profile:update",
            "receptionist_profile:upload_image",
            "receptionist_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
}

DEPARTMENTS = [
    {"name": "General Medicine", "code": "GEN"},
    {"name": "Cardiology", "code": "CARD"},
    {"name": "Orthopedics", "code": "ORTH"},
    {"name": "Pediatrics", "code": "PED"},
    {"name": "Gynecology", "code": "GYN"},
    {"name": "Neurology", "code": "NEURO"},
    {"name": "Dermatology", "code": "DERM"},
    {"name": "ENT", "code": "ENT"},
    {"name": "Ophthalmology", "code": "EYE"},
    {"name": "Laboratory", "code": "LAB"},
    {"name": "Radiology", "code": "RAD"},
]

LAB_TEST_CATALOG = [
    {"test_name": "Blood Test", "department_code": "LAB", "price": 500},
    {"test_name": "Urine Test", "department_code": "LAB", "price": 150},
    {"test_name": "Stool Test", "department_code": "LAB", "price": 150},
    {"test_name": "Biochemistry", "department_code": "LAB", "price": 400},
    {"test_name": "Hematology", "department_code": "LAB", "price": 350},
    {"test_name": "Microbiology", "department_code": "LAB", "price": 450},
    {"test_name": "Histopathology", "department_code": "LAB", "price": 800},
    {"test_name": "CBC", "department_code": "LAB", "price": 300},
    {"test_name": "Lipid Profile", "department_code": "LAB", "price": 500},
    {"test_name": "Blood Sugar", "department_code": "LAB", "price": 120},
    {"test_name": "Urine Routine", "department_code": "LAB", "price": 150},
    {"test_name": "X-Ray", "department_code": "RAD", "price": 800},
    {"test_name": "Ultrasound (USG)", "department_code": "RAD", "price": 1200},
    {"test_name": "CT Scan", "department_code": "RAD", "price": 3500},
    {"test_name": "MRI", "department_code": "RAD", "price": 5000},
    {"test_name": "Mammography", "department_code": "RAD", "price": 2000},
    {"test_name": "X-Ray Chest", "department_code": "RAD", "price": 800},
    {"test_name": "MRI Brain", "department_code": "RAD", "price": 5500},
    {"test_name": "CT Scan Abdomen", "department_code": "RAD", "price": 4000},
]



def upsert_permissions(db) -> dict[str, int]:
    perm_ids: dict[str, int] = {}
    added = 0
    for name in PERMISSIONS_LIST:
        row = db.query(Permission).filter(Permission.name == name).first()
        if not row:
            row = Permission(name=name)
            db.add(row)
            db.flush()
            added += 1
        perm_ids[name] = row.id
    db.commit()
    print(f"Permissions synced: {len(perm_ids)} total ({added} new)")
    return perm_ids


def fresh_clear_roles(db) -> None:
    user_count = db.query(User).count()
    if user_count > 0:
        print(
            "ERROR: --fresh cannot delete roles while users exist.\n"
            "  Use default sync mode: python seed.py\n"
            "  Or drop/recreate the database for a full reset."
        )
        sys.exit(1)
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.query(Role).delete()
    db.commit()
    print("Fresh mode: cleared roles and permissions")


def _target_permission_ids(
    role_name: str,
    role_data: dict,
    perm_ids: dict[str, int],
) -> set[int]:
    raw = role_data["permissions"]
    if raw == "__all__":
        return set(perm_ids.values())

    target: set[int] = set()
    for perm_name in raw:
        pid = perm_ids.get(perm_name)
        if pid is None:
            print(f"  WARNING: role '{role_name}' references unknown permission '{perm_name}' — skipped")
            continue
        target.add(pid)
    return target


def upsert_roles(db, perm_ids: dict[str, int]) -> dict[str, int]:
    role_ids: dict[str, int] = {}
    roles_added = 0
    links_added = 0
    links_removed = 0

    for role_name, role_data in ROLES_DATA.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name, description=role_data["description"])
            db.add(role)
            db.flush()
            roles_added += 1
        elif role.description != role_data["description"]:
            role.description = role_data["description"]

        role_ids[role_name] = role.id

        target_perm_ids = _target_permission_ids(role_name, role_data, perm_ids)
        existing_links = (
            db.query(RolePermission)
            .filter(RolePermission.role_id == role.id)
            .all()
        )
        existing_perm_ids = {link.permission_id for link in existing_links}

        for link in existing_links:
            if link.permission_id not in target_perm_ids:
                db.delete(link)
                links_removed += 1

        for pid in target_perm_ids:
            if pid in existing_perm_ids:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=pid))
            links_added += 1

    db.commit()
    print(
        f"Roles synced: {len(role_ids)} total "
        f"({roles_added} new, {links_added} links added, {links_removed} links removed)"
    )
    return role_ids


def upsert_departments(db) -> dict[str, int]:
    dept_ids: dict[str, int] = {}
    added = 0
    for item in DEPARTMENTS:
        dept = db.query(Department).filter(Department.code == item["code"]).first()
        if not dept:
            dept = Department(name=item["name"], code=item["code"], is_active=True)
            db.add(dept)
            db.flush()
            added += 1
        else:
            dept.name = item["name"]
            dept.is_active = True
        dept_ids[item["code"]] = dept.id
    db.commit()
    print(f"Departments synced: {len(dept_ids)} total ({added} new)")
    return dept_ids


def upsert_lab_tests(db, department_ids: dict[str, int]) -> None:
    added = 0
    updated = 0
    for item in LAB_TEST_CATALOG:
        department_id = department_ids[item["department_code"]]
        price = Decimal(str(item["price"]))
        test = (
            db.query(LabTest)
            .filter(
                LabTest.test_name == item["test_name"],
                LabTest.department_id == department_id,
            )
            .first()
        )
        if test:
            changed = False
            current_price = Decimal(str(test.price if test.price is not None else 0))
            if current_price != price:
                test.price = price
                changed = True
            if not test.active:
                test.active = True
                changed = True
            if changed:
                updated += 1
            continue
        db.add(
            LabTest(
                test_name=item["test_name"],
                department_id=department_id,
                price=price,
                active=True,
            )
        )
        added += 1
    if added or updated:
        db.commit()
    print(
        f"Lab test catalog synced: {added} new, {updated} updated "
        f"({len(LAB_TEST_CATALOG)} defaults)"
    )


def backfill_lab_order_prices(db) -> None:
    """Copy current catalog prices onto orders that still have 0 / NULL."""
    result = db.execute(
        text(
            """
            UPDATE lab_test_orders AS orders
            SET lab_test_id = COALESCE(orders.lab_test_id, tests.id),
                price = tests.price
            FROM lab_tests AS tests
            WHERE (orders.price IS NULL OR orders.price = 0)
              AND tests.price > 0
              AND (
                orders.lab_test_id = tests.id
                OR (
                  orders.lab_test_id IS NULL
                  AND lower(trim(orders.test_name)) = lower(trim(tests.test_name))
                  AND orders.department_id = tests.department_id
                )
              )
            """
        )
    )
    db.commit()
    print(f"Lab order prices backfilled: {result.rowcount}")


def ensure_hospital_settings(db) -> None:
    row = db.query(HospitalSettings).filter(HospitalSettings.id == SETTINGS_ROW_ID).first()
    if row:
        print("Hospital settings row already exists")
        return

    db.add(
        HospitalSettings(
            id=SETTINGS_ROW_ID,
            name="",
            default_registration_fee=0.0,
            default_consultation_fee=0.0,
            default_gst_percent=0.0,
            currency="INR",
            timezone="Asia/Kolkata",
        )
    )
    db.commit()
    print("Hospital settings default row created (id=1)")


def ensure_opd_settings(db) -> None:
    row = db.query(OpdSettings).filter(OpdSettings.id == OPD_SETTINGS_ROW_ID).first()
    if row:
        print("OPD settings row already exists")
        return

    db.add(
        OpdSettings(
            id=OPD_SETTINGS_ROW_ID,
            allow_patient_delete=True,
            allow_appointment_delete=True,
            allow_unpaid_bill_delete=True,
            require_admin_approval_for_delete=True,
            extra={},
        )
    )
    db.commit()
    print("OPD settings default row created (id=1)")


def ensure_nurse_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty nurse_profiles for nurse-role users missing a profile row."""
    nurse_role_id = role_ids.get("nurse")
    if not nurse_role_id:
        print("WARNING: nurse role not found — skipped nurse profile backfill")
        return

    nurses = (
        db.query(User)
        .filter(User.role_id == nurse_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for nurse in nurses:
        exists = (
            db.query(NurseProfile.id)
            .filter(NurseProfile.user_id == nurse.id)
            .first()
        )
        if exists:
            continue
        db.add(
            NurseProfile(
                user_id=nurse.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(f"Nurse profiles synced: {added} new ({len(nurses)} nurse users)")


def ensure_doctor_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty doctor_profiles for doctor-role users missing a profile row."""
    doctor_role_id = role_ids.get("doctor")
    if not doctor_role_id:
        print("WARNING: doctor role not found — skipped doctor profile backfill")
        return

    doctors = (
        db.query(User)
        .filter(User.role_id == doctor_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for doctor in doctors:
        exists = (
            db.query(DoctorProfile.id)
            .filter(DoctorProfile.user_id == doctor.id)
            .first()
        )
        if exists:
            continue
        db.add(
            DoctorProfile(
                user_id=doctor.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(f"Doctor profiles synced: {added} new ({len(doctors)} doctor users)")


def ensure_receptionist_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty receptionist_profiles for receptionist-role users missing a row."""
    receptionist_role_id = role_ids.get("receptionist")
    if not receptionist_role_id:
        print(
            "WARNING: receptionist role not found — skipped receptionist profile backfill"
        )
        return

    receptionists = (
        db.query(User)
        .filter(User.role_id == receptionist_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for receptionist in receptionists:
        exists = (
            db.query(ReceptionistProfile.id)
            .filter(ReceptionistProfile.user_id == receptionist.id)
            .first()
        )
        if exists:
            continue
        db.add(
            ReceptionistProfile(
                user_id=receptionist.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"Receptionist profiles synced: {added} new "
        f"({len(receptionists)} receptionist users)"
    )


def ensure_lab_technician_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty lab_technician_profiles for lab technician users missing a row."""
    lab_role_id = role_ids.get("lab_technician")
    if not lab_role_id:
        print(
            "WARNING: lab_technician role not found — skipped lab profile backfill"
        )
        return

    lab_techs = (
        db.query(User)
        .filter(User.role_id == lab_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for lab_tech in lab_techs:
        exists = (
            db.query(LabTechnicianProfile.id)
            .filter(LabTechnicianProfile.user_id == lab_tech.id)
            .first()
        )
        if exists:
            continue
        db.add(
            LabTechnicianProfile(
                user_id=lab_tech.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"Lab technician profiles synced: {added} new "
        f"({len(lab_techs)} lab technician users)"
    )


def ensure_opd_billing_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty opd_billing_profiles for OPD billing users missing a row."""
    opd_role_id = role_ids.get("opd_billing")
    if not opd_role_id:
        print(
            "WARNING: opd_billing role not found — skipped OPD billing profile backfill"
        )
        return

    opd_users = (
        db.query(User)
        .filter(User.role_id == opd_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for opd_user in opd_users:
        exists = (
            db.query(OpdBillingProfile.id)
            .filter(OpdBillingProfile.user_id == opd_user.id)
            .first()
        )
        if exists:
            continue
        db.add(
            OpdBillingProfile(
                user_id=opd_user.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"OPD billing profiles synced: {added} new "
        f"({len(opd_users)} opd_billing users)"
    )


def ensure_ipd_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty ipd_profiles for IPD users missing a row."""
    ipd_role_id = role_ids.get("ipd")
    if not ipd_role_id:
        print("WARNING: ipd role not found — skipped IPD profile backfill")
        return

    ipd_users = (
        db.query(User)
        .filter(User.role_id == ipd_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for staff in ipd_users:
        exists = (
            db.query(IpdProfile.id).filter(IpdProfile.user_id == staff.id).first()
        )
        if exists:
            continue
        db.add(IpdProfile(user_id=staff.id, languages=[], is_profile_completed=False))
        added += 1
    if added:
        db.commit()
    print(f"IPD profiles synced: {added} new ({len(ipd_users)} ipd users)")


def ensure_pharmacist_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty pharmacist_profiles for pharmacist-role users missing a row."""
    pharmacist_role_id = role_ids.get("pharmacist")
    if not pharmacist_role_id:
        print(
            "WARNING: pharmacist role not found — skipped pharmacist profile backfill"
        )
        return

    pharmacists = (
        db.query(User)
        .filter(User.role_id == pharmacist_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for pharmacist in pharmacists:
        exists = (
            db.query(PharmacistProfile.id)
            .filter(PharmacistProfile.user_id == pharmacist.id)
            .first()
        )
        if exists:
            continue
        db.add(
            PharmacistProfile(
                user_id=pharmacist.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"Pharmacist profiles synced: {added} new "
        f"({len(pharmacists)} pharmacist users)"
    )


def ensure_admin_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty admin_profiles for admin-role users missing a row."""
    admin_role_id = role_ids.get("admin")
    if not admin_role_id:
        print("WARNING: admin role not found — skipped admin profile backfill")
        return

    admins = (
        db.query(User)
        .filter(User.role_id == admin_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for admin in admins:
        exists = (
            db.query(AdminProfile.id)
            .filter(AdminProfile.user_id == admin.id)
            .first()
        )
        if exists:
            continue
        db.add(
            AdminProfile(
                user_id=admin.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"Admin profiles synced: {added} new "
        f"({len(admins)} admin users)"
    )


def ensure_super_admin_profiles(db, role_ids: dict[str, int]) -> None:
    """Backfill empty super_admin_profiles for super_admin-role users missing a row."""
    super_role_id = role_ids.get("super_admin")
    if not super_role_id:
        print("WARNING: super_admin role not found — skipped super admin profile backfill")
        return

    owners = (
        db.query(User)
        .filter(User.role_id == super_role_id, User.deleted_at.is_(None))
        .all()
    )
    added = 0
    for owner in owners:
        exists = (
            db.query(SuperAdminProfile.id)
            .filter(SuperAdminProfile.user_id == owner.id)
            .first()
        )
        if exists:
            continue
        db.add(
            SuperAdminProfile(
                user_id=owner.id,
                languages=[],
                is_profile_completed=False,
            )
        )
        added += 1
    if added:
        db.commit()
    print(
        f"Super Admin profiles synced: {added} new "
        f"({len(owners)} super_admin users)"
    )


def ensure_super_admin_user(
    db,
    role_ids: dict[str, int],
    *,
    email: str,
    password: str,
    first_name: str = "Super",
    last_name: str = "Admin",
) -> None:
    from hash import hash_password

    if len(password) < 8:
        print("ERROR: --super-admin-password must be at least 8 characters")
        sys.exit(1)

    super_role_id = role_ids.get("super_admin")
    if not super_role_id:
        print("WARNING: super_admin role not found — skipped super admin user")
        return

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.first_name = first_name
        user.last_name = last_name
        user.role_id = super_role_id
        user.password = hash_password(password)
        user.is_active = True
        user.deleted_at = None
        db.commit()
        print(f"Super admin user updated: {email}")
        ensure_super_admin_profiles(db, role_ids)
        return

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=hash_password(password),
        role_id=super_role_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    print(f"Super admin user created: {email}")
    ensure_super_admin_profiles(db, role_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HMS reference data")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe roles/permissions and reseed (only when no users exist)",
    )
    parser.add_argument(
        "--super-admin-email",
        metavar="EMAIL",
        help="Create or update a super_admin user (use with --super-admin-password)",
    )
    parser.add_argument(
        "--super-admin-password",
        metavar="PASSWORD",
        help="Password for super_admin user (min 8 characters)",
    )
    parser.add_argument(
        "--super-admin-first-name",
        default="Super",
        help="First name for super_admin user (default: Super)",
    )
    parser.add_argument(
        "--super-admin-last-name",
        default="Admin",
        help="Last name for super_admin user (default: Admin)",
    )
    args = parser.parse_args()

    if bool(args.super_admin_email) ^ bool(args.super_admin_password):
        print(
            "ERROR: pass both --super-admin-email and --super-admin-password, or neither."
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        print("HMS seed - mode:", "fresh" if args.fresh else "sync (safe)")
        if args.fresh:
            fresh_clear_roles(db)

        perm_ids = upsert_permissions(db)
        role_ids = upsert_roles(db, perm_ids)
        department_ids = upsert_departments(db)
        upsert_lab_tests(db, department_ids)
        backfill_lab_order_prices(db)
        ensure_hospital_settings(db)
        ensure_opd_settings(db)
        ensure_nurse_profiles(db, role_ids)
        ensure_doctor_profiles(db, role_ids)
        ensure_receptionist_profiles(db, role_ids)
        ensure_lab_technician_profiles(db, role_ids)
        ensure_opd_billing_profiles(db, role_ids)
        ensure_ipd_profiles(db, role_ids)
        ensure_pharmacist_profiles(db, role_ids)
        ensure_admin_profiles(db, role_ids)
        ensure_super_admin_profiles(db, role_ids)

        if args.super_admin_email and args.super_admin_password:
            ensure_super_admin_user(
                db,
                role_ids,
                email=args.super_admin_email.strip(),
                password=args.super_admin_password,
                first_name=args.super_admin_first_name.strip(),
                last_name=args.super_admin_last_name.strip(),
            )

        # Beds are admin-managed (Settings → OPD → Beds & wards). No hardcoded seed.
        from Services.bed_service import seed_default_beds

        seed_default_beds(db)
        print("Bed inventory: admin-managed (no hardcoded defaults)")

        print("\nSeed completed successfully!")
        print("\nRole IDs:")
        for name, rid in role_ids.items():
            perm_count = (
                len(PERMISSIONS_LIST)
                if ROLES_DATA[name]["permissions"] == "__all__"
                else len(ROLES_DATA[name]["permissions"])
            )
            print(f"  role_id={rid} -> {name} ({perm_count} permissions)")
        print("\nAdmin panel role: admin")
        print("Super Admin role: super_admin")
        if not args.super_admin_email:
            print(
                "\nNo super admin user created. First-time setup:\n"
                "  python seed.py --super-admin-email YOU@hospital.com "
                "--super-admin-password 'YourPass123'"
            )
        print("\nExisting staff must re-login after permission changes.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
