# Admin (`admin`)

**What admin does:** Manage hospital staff and roles for **one hospital**.  
Admin does **not** run OPD counter, nurse station, or doctor consultation — those are other roles.

**Login role name from API:** `admin`  
**Permissions:** Admin gets **all** permissions from `seed.py` (full access).

---

## Admin screens (simple list)

| Screen | Route (frontend) | What it does |
|--------|------------------|--------------|
| Dashboard | `/admin/dashboard` | Overview numbers |
| Staff list | `/admin/staff` | See all staff |
| Register staff | `/admin/staff/new` | Add doctor, nurse, OPD, etc. |
| Roles list | `/admin/roles` | See roles and permissions |

---

## ✅ What we HAVE (ready now)

| # | Feature | API | Status |
|---|---------|-----|--------|
| 1 | **Register staff** | `POST /auth/register` | ✅ Ready |
| 2 | **Login** | `POST /auth/login` | ✅ Ready |
| 3 | **My profile** | `GET /auth/me` | ✅ Ready |
| 4 | **List roles** | `GET /roles/` | ✅ Ready |
| 5 | **Create role** | `POST /roles/` | ✅ Ready |
| 6 | **Assign permissions** | `POST /roles/{role_id}/permissions` | ✅ Ready |
| 7 | **Load departments** | `GET /opd/departments` | ✅ Ready |
| 8 | **Staff list** | `GET /users/` | ✅ Ready |
| 9 | **Staff detail** | `GET /users/{id}` | ✅ Ready |
| 10 | **Activate / deactivate** | `PATCH /users/{id}/activate` | ✅ Ready |
| 11 | **Update staff** | `PATCH /users/{id}` | ✅ Ready |
| 12 | **Delete staff** | `DELETE /users/{id}` | ✅ Ready |
| 13 | **Dashboard** | `GET /admin/dashboard` | ✅ Ready |

### Register staff — fields

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name | Yes |
| email | Yes |
| password | Yes (min 8 chars) |
| role_id | Yes — get from `GET /roles/` |
| last_name | No |
| department_id | For doctor/nurse, optional for others |

### Register staff — steps

```
1. GET /roles/           → fill role dropdown
2. GET /opd/departments  → fill department dropdown (if doctor/nurse)
3. POST /auth/register   → create user
```

**Tip:** Use trailing slash on `GET /users/`.

---

## ❌ What we NEED to build (later)

| Feature | API | Notes |
|---------|-----|-------|
| Department CRUD | `POST/PATCH /departments` | Only `GET /opd/departments` today |
| Hospital settings | `GET/PATCH /settings` | Fees, GST, hospital name |
| Reports | `GET /reports/...` | Revenue, visits |
| Audit log | `GET /audit-log` | Who changed what |
| Protect register | `POST /auth/register` | Admin-only in production |

---

## Quick reference

```
POST   /auth/register
POST   /auth/login
GET    /auth/me

GET    /admin/dashboard
GET    /users/
GET    /users/{id}
PATCH  /users/{id}/activate
PATCH  /users/{id}
DELETE /users/{id}

GET    /roles/
POST   /roles/
POST   /roles/{role_id}/permissions

GET    /opd/departments
```

---

## Notes

- Staff must **re-login** after role or permission changes.
- `POST /auth/register` is open to anyone today — lock down later.
- Cannot deactivate or delete your own account.

---

## Related

- Frontend guide: [../../frontend/roles/admin.md](../../frontend/roles/admin.md)
- Super Admin (separate, not built): [super-admin.md](./super-admin.md)
