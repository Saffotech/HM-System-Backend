# Super Admin (`super_admin`)

**Source of truth:** [HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)  
**Hospital Admin (separate panel):** [admin.md](./admin.md)

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

## Reuse from admin work — already DONE ✅

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

**Move to Super Admin UI** if these are on admin panel today:
- Create role screen
- Assign permissions screen
- Register user with role `admin`

---

## Super Admin ONLY — not built yet 🔨

| Feature | Planned API | Permission |
|---------|-------------|------------|
| Super Admin dashboard | `GET /super-admin/dashboard` | TBD |
| Hospital settings | `GET/PATCH /super-admin/settings` | `settings:manage` |
| Reports | `GET /super-admin/reports/...` | `reports:view` |
| Audit log | `GET /super-admin/audit` | `audit:view` |
| `super_admin` role in DB | `python seed.py` | `__all__` |
| Register guard (admin/super roles) | `auth.py` | Super Admin only |

`settings:manage` and `reports:view` are in seed permissions list — APIs not built.

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
| Settings | `/super-admin/settings` | 🔨 not built |
| Reports | `/super-admin/reports` | 🔨 not built |
| Audit log | `/super-admin/audit` | 🔨 not built |

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

| # | Task | File |
|---|------|------|
| 1 | Add `super_admin` role with `__all__` | `seed.py` |
| 2 | Narrow `admin` to staff + `roles:view` + `reports:view` | `seed.py` |
| 3 | Run `python seed.py` + re-login | ops |
| 4 | Only Super Admin can set `role_id` = admin or super_admin | `auth.py` |
| 5 | Protect `POST /auth/register` | `auth.py` |

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
