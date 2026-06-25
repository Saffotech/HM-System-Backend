# Admin — Frontend Flow

**Source of truth:** [../../HMS_Role_Permission_Proposal.docx](../../HMS_Role_Permission_Proposal.docx)  
**Backend:** [../../backend/roles/admin.md](../../backend/roles/admin.md)  
**Super Admin panel (separate):** [../../backend/roles/super-admin.md](../../backend/roles/super-admin.md)

---

## Two panels — do not mix

| Panel | Route | Your work |
|-------|-------|-----------|
| **Admin** | `/admin/` | Staff + dashboard + roles **view only** |
| **Super Admin** | `/super-admin/` | Everything admin has **plus** create role, settings, audit |

We started with one admin panel. Per proposal, **remove** create-role and assign-permission from `/admin/` — those go to `/super-admin/` later.

---

## Admin screens — build these

| Screen | Route | Backend |
|--------|-------|---------|
| Dashboard | `/admin/dashboard` | `GET /admin/dashboard` ✅ |
| Staff list | `/admin/staff` | `GET /users/` ✅ |
| Staff detail | `/admin/staff/:id` | `GET /users/{id}` ✅ |
| Register staff | `/admin/staff/new` | `POST /auth/register` ✅ |
| Roles list | `/admin/roles` | `GET /roles/` ✅ read-only |

**Do not put on admin:** Create role, assign permissions, settings, audit.

---

## Register staff flow

```
/admin/staff/new
  → GET /roles/           (hide admin, super_admin)
  → GET /opd/departments
  → POST /auth/register
```

Allowed roles: `doctor`, `nurse`, `opd_billing`, `pharmacist`.

---

## Sidebar (admin only)

```
Dashboard
Staff
Roles        ← view only, no Create button
Sign out
```

---

## Suggested files

```
pages/admin/
├── AdminRoutes.tsx
├── Dashboard.tsx
├── StaffList.tsx
├── StaffDetail.tsx
├── StaffRegister.tsx
└── RolesList.tsx      ← read-only
```

Create role / settings → `pages/super-admin/` later.
