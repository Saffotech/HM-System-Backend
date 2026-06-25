# Admin (`admin`)

**Source of truth:** [HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)  
**Super Admin (separate panel):** [super-admin.md](./super-admin.md)

---

## Read this first — two panels, not one

We started building **one admin panel** before the proposal split roles into two:

| Panel | Route | Who uses it |
|-------|-------|-------------|
| **Hospital Admin** | `/admin/` | Hospital manager (HR / operations) |
| **Super Admin** | `/super-admin/` | Hospital owner / director |

**Same hospital. Not multi-hospital SaaS.**

Most backend work you did is **staff management** — that stays with **Admin**.  
Some things we may have put on the admin panel belong to **Super Admin only** — remove those from admin UI (no backend rebuild needed).

---

## What Admin is allowed to do (from proposal)

Hospital manager — **staff + dashboard + view roles + view reports**. Nothing clinical.

| Feature | Admin? |
|---------|--------|
| Dashboard | Yes |
| Staff list / detail | Yes |
| Register staff (doctor, nurse, OPD, pharmacist) | Yes |
| Activate / update / delete staff | Yes |
| View roles (read-only) | Yes |
| View hospital reports | Yes (when built) |
| Create Admin or Super Admin users | **No** |
| Create roles / assign permissions | **No** |
| Hospital settings | **No** |
| Audit log | **No** |
| OPD, doctor, nurse, pharmacy work | **No** |

---

## Permissions — KEEP for admin

```
users:list
users:create
users:activate
users:delete
roles:view
reports:view
```

| Permission | Feature |
|------------|---------|
| `users:list` | Dashboard, staff list, staff detail |
| `users:create` | Update staff |
| `users:activate` | Activate / deactivate staff |
| `users:delete` | Soft delete staff |
| `roles:view` | Roles page — **view only** |
| `reports:view` | Reports page — when API exists |

> **Today:** `seed.py` still gives admin `__all__`. After approval → narrow to list above. Re-login required.

---

## What we already built — belongs to ADMIN ✅

Backend is **done** for admin Phase 1. Keep building admin UI on these.

| Feature | API | Backend |
|---------|-----|---------|
| Login | `POST /auth/login` | ✅ Done |
| My profile | `GET /auth/me` | ✅ Done |
| Dashboard | `GET /admin/dashboard` | ✅ Done |
| Staff list | `GET /users/` | ✅ Done |
| Staff detail | `GET /users/{id}` | ✅ Done |
| Activate / deactivate | `PATCH /users/{id}/activate` | ✅ Done |
| Update staff | `PATCH /users/{id}` | ✅ Done |
| Delete staff | `DELETE /users/{id}` | ✅ Done |
| Register staff | `POST /auth/register` | ✅ Done |
| Roles list | `GET /roles/` | ✅ Done |
| Department dropdown | `GET /opd/departments` | ✅ Done (helper for register) |

### Admin screens to build

| Screen | Route |
|--------|-------|
| Dashboard | `/admin/dashboard` |
| Staff list | `/admin/staff` |
| Staff detail | `/admin/staff/:id` |
| Register staff | `/admin/staff/new` |
| Roles list | `/admin/roles` (read-only) |

### Register staff rule

Admin may register only: `doctor`, `nurse`, `opd_billing`, `pharmacist`.

```
GET /roles/           → dropdown (hide admin, super_admin)
GET /opd/departments  → dropdown for doctor/nurse
POST /auth/register
```

**Tip:** Use trailing slash on `GET /users/`.

---

## Built for admin panel but REMOVE — Super Admin only ❌

If your admin UI has any of these, **remove from `/admin/`** and build under `/super-admin/` later.

| Feature | API | Why remove from admin |
|---------|-----|---------------------|
| Create role | `POST /roles/` | Proposal: Super Admin only |
| Assign permissions | `POST /roles/{id}/permissions` | Proposal: Super Admin only |
| Register `admin` user | `POST /auth/register` | Super Admin only |
| Register `super_admin` user | `POST /auth/register` | Super Admin only |
| Hospital settings | not built | Super Admin only |
| Audit log | not built | Super Admin only |

APIs stay in codebase — admin just loses permission after `seed.py` fix.

---

## Also REMOVE from admin — wrong role (clinical) ❌

Admin should never use these modules (other roles own them):

- Patients, OPD, billing, appointments
- Prescriptions, lab
- Nurse vitals, notes, medication, handover, emergency alerts
- Pharmacy dispense

No links in admin sidebar to `/opd/`, `/doctor/`, `/nurse/`, `/pharmacy/`.

---

## NOT built yet — admin still needs 🔨

| Feature | API | Notes |
|---------|-----|-------|
| Hospital reports (view) | `GET /admin/reports/...` | Permission `reports:view` exists, API missing |
| Department CRUD | `POST/PATCH /departments` | Only `GET /opd/departments` today |

---

## Backend fixes needed (config + security) 🔧

| # | Task | File |
|---|------|------|
| 1 | Change admin from `__all__` to permissions above | `seed.py` |
| 2 | Protect register (logged-in admin/super only) | `auth.py` |
| 3 | Block admin from creating admin/super_admin roles | `auth.py` |
| 4 | Add `roles:view` check on `GET /roles/` | `roles.py` |

Steps 2–4 are not done yet. Register and roles list are open today.

---

## Start work — admin panel

**Order:**

1. Build admin UI on **✅ Done** APIs (dashboard, staff, register, roles read-only).
2. **Remove** create-role / assign-permission from admin UI if added.
3. After manager approval → `seed.py` + security fixes.
4. Later → reports + department CRUD.

---

## Quick API reference

```
POST   /auth/login
GET    /auth/me
POST   /auth/register

GET    /admin/dashboard
GET    /users/
GET    /users/{id}
PATCH  /users/{id}/activate
PATCH  /users/{id}
DELETE /users/{id}

GET    /roles/              → view only
GET    /opd/departments     → register helper
```

---

## Related

- Proposal: [../../HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)
- Super Admin: [super-admin.md](./super-admin.md)
- Frontend: [../../frontend/roles/admin.md](../../frontend/roles/admin.md)
