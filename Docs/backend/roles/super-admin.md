# Super Admin (`super_admin`)

**Source of truth:** [HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)  
**Hospital Admin (separate panel):** [admin.md](./admin.md)

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | Backend: staff, roles, register security, audit, hospital settings, reports reuse — see below |
| **Phase 2** | Frontend `/super-admin/` panel, optional APIs, OPD settings integration — end of file |

> **Current status (backend):** Phase 1 is largely **done**. Build Super Admin UI on existing APIs. See **Phase 2 — Planned** at the bottom.

---

## Read this first — we did not plan this panel early

We built the **admin panel** (staff, dashboard, roles) first. The proposal adds a **second panel** for the hospital owner.

| Panel | Route | Who |
|-------|-------|-----|
| **Super Admin** | `/super-admin/` | Owner / director — highest power in one hospital |
| **Hospital Admin** | `/admin/` | Manager — staff only |

**You do not rebuild staff APIs.** Super Admin **reuses** the same `/users/` and `/auth/register` backend. Super Admin gets **extra** features on top.

**One hospital per install. Not multi-hospital SaaS.**

---

## What Super Admin is allowed to do (from proposal)

| Feature | Super Admin? | Admin? |
|---------|:------------:|:------:|
| Dashboard | Yes | Yes |
| Staff list / CRUD | Yes | Yes |
| Register clinical staff | Yes | Yes |
| Register **Admin** users | Yes | No |
| Register **Super Admin** users | Yes | No |
| View roles | Yes | Yes (read-only) |
| Create roles & assign permissions | Yes | No |
| Hospital settings | Yes | No |
| Hospital reports (full) | Yes | View only |
| Audit log | Yes | No |
| Clinical modules (OPD, doctor, nurse, pharmacy) | No | No |

---

## Permissions — KEEP for super admin

**Recommended (proposal):** `__all__` in `seed.py`

**Or explicit list:**

```
users:list, users:create, users:activate, users:delete
roles:view, roles:create
reports:view
settings:manage
audit:view          ← add to seed when API built
admins:manage       ← add to seed when enforced
```

> **Today:** `super_admin` role **not in `seed.py` yet**. Admin has `__all__` temporarily.

---

## Phase 1 — Done (backend)

### Reuse from admin work — already DONE ✅

No new backend needed for staff + roles. Same APIs as [admin.md](./admin.md).

| Feature | API | Backend |
|---------|-----|---------|
| Staff list / detail | `GET /users/`, `GET /users/{id}` | ✅ Done |
| Activate / update / delete | `PATCH ...`, `DELETE ...` | ✅ Done |
| Register staff (any role) | `POST /auth/register` | ✅ Done |
| List roles | `GET /roles/` | ✅ Done |
| Create role | `POST /roles/` | ✅ Done |
| Assign permissions | `POST /roles/{id}/permissions` | ✅ Done |
| Dashboard (interim) | `GET /admin/dashboard` | ✅ Done |
| Hospital settings | `GET/PATCH /super-admin/settings` | ✅ Done |
| Audit log | `GET /super-admin/audit` | ✅ Done |
| Reports (reuse admin) | `GET /admin/reports/overview`, `/visits` | ✅ Done |
| Register security | `POST /auth/register` + role policy | ✅ Done |
| `super_admin` role in seed | `python seed.py` | ✅ Done |
| Optional super admin user | `seed.py --super-admin-email ...` | ✅ Done |

**Move to Super Admin UI** if these are on admin panel today:
- Create role screen
- Assign permissions screen
- Register user with role `admin`

---

## Super Admin ONLY — original plan (historical) 🔨

> **Note:** Settings and audit are **built** (Phase 1). Items still open are listed in **Phase 2 — Planned** below.

| Feature | Planned API | Permission |
|---------|-------------|------------|
| Super Admin dashboard | `GET /super-admin/dashboard` | TBD — use `GET /admin/dashboard` interim |
| Hospital settings | `GET/PATCH /super-admin/settings` | `settings:manage` — **✅ Done** |
| Reports | `GET /super-admin/reports/...` | `reports:view` — reuse `/admin/reports/` |
| Audit log | `GET /super-admin/audit` | `audit:view` — **✅ Done** |
| `super_admin` role in DB | `python seed.py` | `__all__` — **✅ Done** |
| Register guard (admin/super roles) | `auth.py` | **✅ Done** |

`settings:manage` and `reports:view` are in seed. Dedicated `/super-admin/reports` route is optional.

---

## Super Admin screens (frontend plan)

| Screen | Route | Backend now |
|--------|-------|-------------|
| Dashboard | `/super-admin/dashboard` | Use `GET /admin/dashboard` until new API |
| Staff list | `/super-admin/staff` | ✅ `GET /users/` |
| Register staff | `/super-admin/staff/new` | ✅ `POST /auth/register` (any role) |
| Roles list | `/super-admin/roles` | ✅ `GET /roles/` |
| Create role | `/super-admin/roles/new` | ✅ `POST /roles/` |
| Assign permissions | `/super-admin/roles/:id` | ✅ `POST /roles/{id}/permissions` |
| Settings | `/super-admin/settings` | ✅ `GET/PATCH /super-admin/settings` |
| Reports | `/super-admin/reports` | ✅ reuse `GET /admin/reports/...` |
| Audit log | `/super-admin/audit` | ✅ `GET /super-admin/audit` |

---

## What to remove / not duplicate

| Do not | Reason |
|--------|--------|
| Rebuild staff CRUD for super admin | Reuse admin APIs |
| Put create-role on `/admin/` | Admin is view-only for roles |
| Build multi-hospital tenant UI | Out of scope per proposal |
| Give admin `roles:create` or `settings:manage` | Proposal split |

---

## Backend fixes needed (with admin) 🔧

> **Updated:** Items 1–5 below are **done** in codebase. Re-run `python seed.py` + re-login after permission changes.

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Add `super_admin` role with `__all__` | `seed.py` | ✅ Done |
| 2 | Narrow `admin` to staff + `roles:view` + `reports:view` | `seed.py` | ✅ Done |
| 3 | Run `python seed.py` + re-login | ops | Required after seed |
| 4 | Only Super Admin can set `role_id` = admin or super_admin | `auth.py` | ✅ Done |
| 5 | Protect `POST /auth/register` | `auth.py` | ✅ Done |

---

## Start work — super admin panel

**Order:**

1. Wait until admin panel Phase 1 works (staff + dashboard).
2. Add `super_admin` in `seed.py` + create owner account.
3. Build `/super-admin/` UI — reuse staff APIs; add create-role screens moved from admin.
4. Later → settings, reports, audit APIs.

---

## Quick API reference (reuse today)

```
GET    /admin/dashboard          → interim dashboard
GET    /users/
GET    /users/{id}
PATCH  /users/{id}/activate
PATCH  /users/{id}
DELETE /users/{id}
POST   /auth/register

GET    /roles/
POST   /roles/
POST   /roles/{role_id}/permissions
```

---

## Related

- Proposal: [../../HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)
- Hospital Admin: [admin.md](./admin.md)
- Hospital settings detail: [hospital-settings.md](./hospital-settings.md)

---

## Phase 2 — Planned

Work after Phase 1 backend is verified in Postman. Phase 1 content above is **not removed** — this section is what comes next.

### Frontend — Phase 2 (primary)

| # | Screen | Route | Backend to use |
|---|--------|-------|----------------|
| 1 | Dashboard | `/super-admin/dashboard` | `GET /admin/dashboard` |
| 2 | Staff list / detail | `/super-admin/staff` | `GET /users/`, `GET /users/{id}` |
| 3 | Register staff (any role) | `/super-admin/staff/new` | `POST /auth/register` |
| 4 | Roles list | `/super-admin/roles` | `GET /roles/` |
| 5 | Create role | `/super-admin/roles/new` | `POST /roles/` |
| 6 | Assign permissions | `/super-admin/roles/:id` | `POST /roles/{id}/permissions` |
| 7 | Settings form | `/super-admin/settings` | `GET/PATCH /super-admin/settings` |
| 8 | Reports | `/super-admin/reports` | `GET /admin/reports/...` |
| 9 | Audit log | `/super-admin/audit` | `GET /super-admin/audit` |

Replace mock admin API layer with real `apiClient` calls where shared.

### Backend — Phase 2 (optional polish)

| # | Feature | Notes |
|---|---------|--------|
| 1 | `GET /permissions/` | List all permission IDs for assign-permissions UI |
| 2 | Filter `GET /roles/` for hospital `admin` | Hide `admin` / `super_admin` in dropdown |
| 3 | `GET /super-admin/dashboard` | Optional; interim `/admin/dashboard` is enough |
| 4 | `GET /super-admin/reports/...` | Optional alias; `/admin/reports/` works today |
| 5 | `admins:manage` permission | Enforce if needed beyond role policy |
| 6 | Tests | Register rules, audit, settings PATCH |

### Cross-module — Phase 2

| Module | Task |
|--------|------|
| OPD billing | Invoice + default fees from [hospital-settings.md](./hospital-settings.md) |
| Admin panel | Wire frontend to real APIs (staff only; no create-role on `/admin/`) |

### Phase 2 — Suggested order

```
1. Super Admin UI shell + login route for super_admin role
2. Staff + register + roles (create/assign) screens
3. Settings + audit + reports screens
4. Optional backend polish (GET /permissions/, tests)
5. OPD invoice reads hospital_settings
```
