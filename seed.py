"""
Seed reference data: permissions, roles, departments, beds.

Usage:
  python seed.py          Safe sync — upsert only (safe on existing DB)
  python seed.py --fresh  Wipe roles/permissions and reseed (empty DB only)
"""
import argparse
import sys

from database import SessionLocal
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401 — required for User.doctor_profile relationship
from Models.hospital_settings import SETTINGS_ROW_ID, HospitalSettings
from Models.nurse_profile import NurseProfile  # noqa: F401 — required for User.nurse_profile relationship
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401 — User.receptionist_profile
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
    "nurse_medication:view",
    "nurse_medication:create",
    "nurse_medication:update",
    "nurse_handover:view",
    "nurse_handover:create",
    "nurse_handover:update",
    "nurse_handover:submit",
    "nurse_handover:take_over",
    "emergency_alerts:view",
    "emergency_alerts:create",
    "emergency_alerts:update",
    "emergency_alerts:escalate",
    "doctor_profile:view",
    "doctor_profile:update",
    "doctor_profile:upload_image",
    "doctor_profile:delete_image",
    "nurse_profile:view",
    "nurse_profile:update",
    "nurse_profile:upload_image",
    "nurse_profile:delete_image",
    "receptionist_profile:view",
    "receptionist_profile:update",
    "receptionist_profile:upload_image",
    "receptionist_profile:delete_image",
    "notifications:view",
    "notifications:update",
    "receptionist:view_doctor_schedule",
    "receptionist:view_queue",
]

# Hospital Admin panel — see Docs/backend/roles/admin.md
ADMIN_PERMISSIONS = [
    "users:list",
    "users:create",
    "users:activate",
    "users:delete",
    "roles:view",
    "reports:view",
]

ROLES_DATA = {
    "super_admin": {
        "description": "Hospital owner / highest privilege",
        "permissions": "__all__",
    },
    "admin": {
        "description": "System administrator",
        "permissions": "__all__",
    },
    "doctor": {
        "description": "Clinical doctor",
        "permissions": [
            "patients:view",
            "opd:view",
            "prescriptions:create",
            "prescriptions:view",
            "prescriptions:update",
            "prescriptions:delete",
            "lab:create",
            "lab:view",
            "appointments:view",
            "appointments:create",
            "appointments:update",
            "doctor_profile:view",
            "doctor_profile:update",
            "doctor_profile:upload_image",
            "doctor_profile:delete_image",
            "notifications:view",
            "notifications:update",
        ],
    },
    "nurse": {
        "description": "Nursing staff",
        "permissions": [
            "patients:view",
            "opd:view",
            "lab:view",
            "nurse_vitals:view",
            "nurse_vitals:create",
            "nurse_vitals:update",
            "nurse_notes:view",
            "nurse_notes:create",
            "nurse_notes:update",
            "nurse_medication:view",
            "nurse_medication:create",
            "nurse_medication:update",
            "nurse_handover:view",
            "nurse_handover:create",
            "nurse_handover:update",
            "nurse_handover:submit",
            "nurse_handover:take_over",
            "emergency_alerts:view",
            "emergency_alerts:create",
            "emergency_alerts:update",
            "emergency_alerts:escalate",
            "nurse_profile:view",
            "nurse_profile:update",
            "nurse_profile:upload_image",
            "nurse_profile:delete_image",
            "notifications:view",
            "notifications:update",
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
        ],
    },
    "pharmacist": {
        "description": "Pharmacy staff",
        "permissions": [
            "patients:view",
            "prescriptions:view",
            "prescriptions:dispense",
        ],
    },
    "lab_technician": {
        "description": "Laboratory technician",
        "permissions": [
            "patients:view",
            "lab:view",
            "lab:create",
            "lab:update",
            "lab:upload_report",
        ],
    },
    "receptionist": {
        "description": "Reception / front desk queue monitoring (view only)",
        "permissions": [
            "patients:view",
            "opd:view",
            "receptionist:view_queue",
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
    {"name": "Radiology", "code": "RAD"},
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
        upsert_departments(db)
        ensure_hospital_settings(db)

        if args.super_admin_email and args.super_admin_password:
            ensure_super_admin_user(
                db,
                role_ids,
                email=args.super_admin_email.strip(),
                password=args.super_admin_password,
                first_name=args.super_admin_first_name.strip(),
                last_name=args.super_admin_last_name.strip(),
            )

        from Services.bed_service import seed_default_beds

        seed_default_beds(db)
        print("Default beds seeded (if empty)")

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
