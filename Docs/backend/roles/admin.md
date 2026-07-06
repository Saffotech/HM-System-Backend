# Admin (`admin`)

**Source of truth:** [HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)  
**Super Admin (separate panel):** [super-admin.md](./super-admin.md)

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | Staff CRUD, dashboard, roles view, register security — documented below |
| **Phase 2** | Frontend wiring, reports UI, optional polish — end of file |

> **Current status (backend):** Phase 1 APIs are **done**. Admin UI still uses mock data in frontend.

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

> **Today:** `seed.py` gives admin the 6 permissions above (not `__all__`). Re-login required after seed changes.

---

## Phase 1 — Done (backend)

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
| Hospital reports (view) UI | `GET /admin/reports/...` | **Backend ✅ Done** — frontend Phase 2 |
| Department CRUD UI | `POST/PATCH /departments/` | **Backend ✅ Done** — admin uses via `users:list` |

---

## Backend fixes needed (config + security) 🔧

> **Updated:** Items 1–4 below are **done** in codebase.

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Change admin from `__all__` to permissions above | `seed.py` | ✅ Done |
| 2 | Protect register (logged-in admin/super only) | `auth.py` | ✅ Done |
| 3 | Block admin from creating admin/super_admin roles | `auth.py` | ✅ Done |
| 4 | Add `roles:view` check on `GET /roles/` | `roles.py` | ✅ Done |

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

---

## Phase 2 — Planned

Phase 1 backend content above is **kept as-is**. Phase 2 is mostly **frontend** and polish.

### Frontend — Phase 2 (primary)

| # | Task | Backend API |
|---|------|-------------|
| 1 | Replace mock `admin.js` with real API client | All Phase 1 endpoints |
| 2 | Dashboard page | `GET /admin/dashboard` |
| 3 | Staff list / detail / register | `GET /users/`, `PATCH`, `POST /auth/register` |
| 4 | Roles page (read-only) | `GET /roles/` — hide `admin`, `super_admin` in dropdown |
| 5 | Reports page | `GET /admin/reports/overview`, `/visits` |
| 6 | Department management (optional) | `GET/POST/PATCH /departments/` |

**Do not add on admin UI:** create role, assign permissions, settings, audit (Super Admin only).

### Backend — Phase 2 (optional)

| # | Feature | Notes |
|---|---------|--------|
| 1 | Filter `GET /roles/` response for admin callers | Hide privileged role names in list |
| 2 | Tests | Admin cannot register `admin` role; reports 403 for clinical roles |
| 3 | Doc sync | Keep this file aligned with seed permissions |

### Phase 2 — Suggested order

```
1. Wire staff + dashboard to live APIs
2. Register staff (clinical roles only)
3. Reports screen
4. Optional departments UI
```
