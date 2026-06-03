# Admin — Frontend Flow

**Role name from API:** `admin`  
**Folder:** `src/pages/admin/`  
**URL prefix:** `/admin/`

Admin can access everything. Start with **staff management** only.

---

## Screens (Phase 1)

| # | Screen | Route | Backend |
|---|--------|-------|---------|
| 1 | Dashboard | `/admin/dashboard` | — |
| 2 | Staff list | `/admin/staff` | Wait |
| 3 | Register staff | `/admin/staff/new` | Yes (`POST /auth/register`) |
| 4 | Roles list | `/admin/roles` | Yes (`GET /roles/`) |

---

## Flow 1 — Register new staff

```
/admin/staff/new
    → Load roles: GET /roles/
    → Load departments: GET /opd/departments
    → Form: name, email, password, role, department
    → POST /auth/register
    → Success → back to staff list
```

Reuse same fields as public `/register` page but inside admin layout.

---

## Flow 2 — View roles & permissions

**Route:** `/admin/roles`

**API:** `GET /roles/`

Show table: role name + permission list (read-only for now)

---

## Sidebar menu

```
Dashboard
Staff
Roles
Sign out
```

---

## Note

HR module (payroll, attendance) is **separate** — do not build under admin until clinical modules are done.

---

## Suggested files

```
pages/admin/
├── AdminRoutes.tsx
├── Dashboard.tsx
├── StaffList.tsx
├── StaffRegister.tsx
└── RolesList.tsx
```
