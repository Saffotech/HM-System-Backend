from database import SessionLocal
from Models.user import User
from Models.role import Role, Permission, RolePermission
from Models.department import Department
from hash import hash_password

db = SessionLocal()

# ── Clear existing data ───────────────────────────────────────
db.query(RolePermission).delete()
db.query(Permission).delete()
db.query(Role).delete()
db.commit()

# ── Create permissions ────────────────────────────────────────
permissions_list = [
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
    "opd:create",
    "opd:view",
    "lab:view",
    "lab:create",
    "prescriptions:create",
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
            "lab:create",
            "lab:view",
            "appointments:view",
            "appointments:create",
            "appointments:update"
        ]
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
            "nurse_handover:submit"
        ]
    },
    "opd_billing": {               # ← renamed from receptionist
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
            "appointments:view",
            "appointments:create",
            "appointments:update",
        ]
    },
    "pharmacist": {
        "description": "Pharmacy staff",
        "permissions": [
            "prescriptions:create",
            "patients:view"
        ]
    }
}

role_ids = {}
for role_name, role_data in roles_data.items():
    role = Role(name=role_name, description=role_data["description"])
    db.add(role)
    db.flush()
    role_ids[role_name] = role.id

    for perm_name in role_data["permissions"]:
        if perm_name in perm_objects:
            db.add(RolePermission(
                role_id=role.id,
                permission_id=perm_objects[perm_name]
            ))

db.commit()
print("Roles created:", list(role_ids.keys()))
print(f"  admin       → id: {role_ids['admin']}      (ALL permissions)")
print(f"  doctor      → id: {role_ids['doctor']}")
print(f"  nurse       → id: {role_ids['nurse']}")
print(f"  opd_billing → id: {role_ids['opd_billing']}")
print(f"  pharmacist  → id: {role_ids['pharmacist']}")

# ── Seed departments ──────────────────────────────────────────
db.query(Department).delete()
db.commit()

departments = [
    {"name": "General Medicine",  "code": "GEN"},
    {"name": "Cardiology",        "code": "CARD"},
    {"name": "Orthopedics",       "code": "ORTH"},
    {"name": "Pediatrics",        "code": "PED"},
    {"name": "Gynecology",        "code": "GYN"},
    {"name": "Neurology",         "code": "NEURO"},
    {"name": "Dermatology",       "code": "DERM"},
    {"name": "ENT",               "code": "ENT"},
    {"name": "Ophthalmology",     "code": "EYE"},
    {"name": "Radiology",         "code": "RAD"},
]

for d in departments:
    dept = Department(name=d["name"], code=d["code"])
    db.add(dept)

db.commit()
print("Departments created:", len(departments))

from Services.bed_service import seed_default_beds

seed_default_beds(db)
print("Default beds seeded (if empty)")

print("\n✅ Seed completed successfully!")
print("\nRole IDs to use in registration:")
for name, rid in role_ids.items():
    print(f"  role_id={rid} → {name}")

db.close()