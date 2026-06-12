from database import SessionLocal
from Models.department import Department
from Models.role import Permission, Role, RolePermission
from Models.user import User
import sys
import argparse

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
    "emergency_alerts:view",
    "emergency_alerts:create",
    "emergency_alerts:update",
    "emergency_alerts:escalate",
    ]

perm_objects = {}
for p in permissions_list:
    perm = Permission(name=p)
    db.add(perm)
    db.flush()
    perm_objects[p] = perm.id

print("Permissions created:", len(perm_objects))

# ── Create roles with permissions ─────────────────────────────
roles_data = {
    "admin": {
        "description": "System administrator",
        "permissions": list(perm_objects.keys())  # admin gets ALL permissions
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
            "emergency_alerts:view",
            "emergency_alerts:create",
            "emergency_alerts:update",
            "emergency_alerts:escalate",
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


def upsert_roles(db, perm_ids: dict[str, int]) -> dict[str, int]:
    role_ids: dict[str, int] = {}
    roles_added = 0
    links_added = 0

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

        if role_data["permissions"] == "__all__":
            target_perms = set(perm_ids.keys())
        else:
            target_perms = set(role_data["permissions"])

        existing_perm_ids = {
            rp.permission_id
            for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        }
        for perm_name in target_perms:
            pid = perm_ids.get(perm_name)
            if pid is None or pid in existing_perm_ids:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=pid))
            links_added += 1

    db.commit()
    print(f"Roles synced: {len(role_ids)} total ({roles_added} new, {links_added} permission links added)")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HMS reference data")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe roles/permissions and reseed (only when no users exist)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("HMS seed - mode:", "fresh" if args.fresh else "sync (safe)")
        if args.fresh:
            fresh_clear_roles(db)

        perm_ids = upsert_permissions(db)
        role_ids = upsert_roles(db, perm_ids)
        upsert_departments(db)

        from Services.bed_service import seed_default_beds

        seed_default_beds(db)
        print("Default beds seeded (if empty)")

        print("\nSeed completed successfully!")
        print("\nRole IDs:")
        for name, rid in role_ids.items():
            print(f"  role_id={rid} -> {name}")
        print("\nExisting staff must re-login after permission changes.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
