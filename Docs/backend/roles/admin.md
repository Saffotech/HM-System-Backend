# Admin (`admin`)

**What admin does:** Manage hospital staff and roles.  
Admin does **not** run OPD counter, nurse station, or doctor consultation — those are other roles.

**Login role name from API:** `admin`  
**Permissions:** Admin gets **all** permissions from `seed.py` (full access).

---

## Admin screens (simple list)

| Screen | Route (frontend) | What it does |
|--------|------------------|--------------|
| Dashboard | `/admin/dashboard` | Overview numbers |
| Staff list | `/admin/staff` | See all staff |
| Register staff | `/admin/staff/new` | Add new doctor, nurse, OPD, etc. |
| Roles list | `/admin/roles` | See roles and permissions |

---

## ✅ What we HAVE (ready now)

Backend APIs already exist. You can build these screens today.

| # | Feature | API | Status |
|---|---------|-----|--------|
| 1 | **Register staff** | `POST /auth/register` | ✅ Ready |
| 2 | **Login** | `POST /auth/login` | ✅ Ready |
| 3 | **My profile** | `GET /auth/me` | ✅ Ready |
| 4 | **List roles** | `GET /roles/` | ✅ Ready |
| 5 | **Create role** | `POST /roles/` | ✅ Ready (needs `roles:create` token) |
| 6 | **Assign permissions to role** | `POST /roles/{role_id}/permissions` | ✅ Ready |
| 7 | **Load departments** (for register form) | `GET /opd/departments` | ✅ Ready |

### Register staff — fields

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name | Yes |
| email | Yes |
| password | Yes (min 8 chars) |
| role_id | Yes — get from `GET /roles/` |
| last_name | No |
| department_id | Yes for doctor/nurse, optional for others |

### Register staff — steps

```
1. GET /roles/           → fill role dropdown
2. GET /opd/departments  → fill department dropdown (if doctor/nurse)
3. POST /auth/register   → create user
```

---

## ❌ What we NEED to build

These are **not built yet**. Do them in this order.

### Step 1 — Staff list (do this first)

| API to build | Permission | Purpose |
|--------------|------------|---------|
| `GET /users` | `users:list` | Show all staff in a table |
| `GET /users/{id}` | `users:list` | View one staff member |

**Staff table columns:** name, email, role, department, active yes/no, last login

---

### Step 2 — Manage staff

| API to build | Permission | Purpose |
|--------------|------------|---------|
| `PATCH /users/{id}/activate` | `users:activate` | Turn account on / off |
| `PATCH /users/{id}` | `users:create` | Change role or department |
| `DELETE /users/{id}` | `users:delete` | Remove staff (soft delete) |

---

### Step 3 — Admin dashboard

| API to build | Purpose |
|--------------|---------|
| `GET /admin/dashboard` | Counts: total staff, staff per role, departments |

Can be one simple endpoint that returns JSON counts.

---

### Step 4 — Later (not urgent)

| Feature | API | Notes |
|---------|-----|-------|
| Add / edit departments | `POST /departments`, `PATCH /departments/{id}` | Today only `GET /opd/departments` exists |
| Hospital settings | `GET/PATCH /settings` | Fees, GST, hospital name |
| Reports | `GET /reports/...` | Revenue, visits |
| Audit log | `GET /audit-log` | Who changed what |

---

## 🚀 Where to start

**Backend work order:**

1. `GET /users` — staff list  
2. `PATCH /users/{id}/activate` — activate / deactivate  
3. `GET /admin/dashboard` — simple counts  

**Frontend work order (can start in parallel):**

1. Register staff page — uses existing `POST /auth/register`  
2. Roles list page — uses existing `GET /roles/`  
3. Staff list page — wait for `GET /users`  

---

## Quick reference — existing APIs

```
POST   /auth/register
POST   /auth/login
GET    /auth/me

GET    /roles/
POST   /roles/
POST   /roles/{role_id}/permissions

GET    /opd/departments
```

---

## Notes

- After you change someone's role or permissions, they must **login again** to get a new token.
- `POST /auth/register` is open to anyone today — later protect it with admin login only.
- Permissions like `users:list` exist in `seed.py` but **no API uses them yet** — that is Step 1 above.

---

## Related

- Frontend guide: [../../frontend/roles/admin.md](../../frontend/roles/admin.md)
