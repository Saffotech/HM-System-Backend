# Backend Guide (Simple)

## What is this project?

A **Hospital Management System API** built with:

- **FastAPI** — web API
- **SQLAlchemy** — database tables
- **JWT** — login token
- **RBAC** — each staff member has a **role**, each role has **permissions**

---

## Folder structure

```
hms-backend/
├── main.py           → starts app, adds routers
├── seed.py           → creates roles & permissions (run once)
├── dependencies.py   → checks login + permissions
├── Models/           → database tables
├── Schemas/          → what JSON body should look like
└── Routers/          → API URLs (endpoints)
```

---

## How login works (3 steps)

1. User calls `POST /auth/login` with email + password
2. Server returns `access_token`
3. For other APIs, send header: `Authorization: Bearer <token>`

Inside the token we store **permissions** like `patients:view`, `opd:create`.

---

## How to protect an API

```python
from dependencies import get_current_user, PermissionChecker

@router.post("/something")
def my_api(
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:create"))
):
    ...
```

If the user does not have `patients:create` → **403 Forbidden**.

---

## Roles in database (from seed.py)

| Role name | Who |
|-----------|-----|
| `admin` | Everything |
| `doctor` | Consult, prescribe, order lab |
| `nurse` | Vitals, nursing notes, view patients |
| `opd_billing` | Register patient, OPD, billing (front desk) |
| `pharmacist` | Dispense medicines |

**Note:** Word file says "Billing Counter" = our role `opd_billing`.

---

## What is already built

### Auth
| Method | URL | What |
|--------|-----|------|
| POST | `/auth/register` | Create staff user |
| POST | `/auth/login` | Login, get token |
| GET | `/auth/me` | Current user info |

### Roles
| Method | URL | What |
|--------|-----|------|
| GET | `/roles/` | List all roles + permissions |

### OPD + Billing (partial)
| Method | URL | What |
|--------|-----|------|
| GET | `/opd/patient/search?phone=` | Find patient by phone |
| GET | `/opd/departments` | List departments |
| GET | `/opd/doctors/department/{id}` | Doctors in department |
| POST | `/opd/patient/preview-bill` | Calculate bill |
| POST | `/opd/patient/register` | New patient + pay + visit |
| GET | `/opd/visit/{id}/invoice` | Invoice data |
| GET | `/opd/queue/today` | Today's OPD queue |

### Tables that exist
- `users`, `roles`, `permissions`, `role_permissions`
- `departments`
- `patients`, `opd_visits`

---

## How to add a new feature (5 steps)

Every developer should follow this order:

1. **Permission** — add name in `seed.py` (example: `vitals:create`)
2. **Assign** — give permission to the right role in `seed.py`
3. **Model** — new file in `Models/` (database table)
4. **Schema** — new file in `Schemas/` (request body rules)
5. **Router** — new file in `Routers/`, register in `main.py`

Then run migration (Alembic) if you changed tables.

---

## Build order (recommended)

| Phase | Module | Why first |
|-------|--------|-----------|
| 1 | Finish OPD billing | Already started |
| 2 | Doctor | Prescriptions & lab need doctor |
| 3 | Nurse | Vitals, notes |
| 4 | Pharmacist | Needs prescriptions from doctor |
| 5 | Lab technician | Needs lab orders from doctor |
| 6 | HR | Separate, do last |

---

## Permission naming rule

Always use: **`resource:action`**

Examples:
- `patients:view`
- `billing:create`
- `vitals:create`

---

## Common mistakes to avoid

| Problem | Fix |
|---------|-----|
| Doctor list shows nurses too | Filter users where `role.name == 'doctor'` |
| Old name `receptionist` in code | Use `opd_billing` |
| Pharmacist has `prescriptions:create` | Doctor creates; pharmacist should `dispense` (change in seed when you build pharmacy) |

---

## After changing seed.py

```bash
cd hms-backend
python seed.py
```

Warning: seed clears and recreates roles. Use only in dev, not production with real data.

---

## Checklist before you say "done"

- [ ] Permission in seed + assigned to role
- [ ] Table (model) exists
- [ ] API works in `/docs`
- [ ] Correct role can call it
- [ ] Wrong role gets 403
