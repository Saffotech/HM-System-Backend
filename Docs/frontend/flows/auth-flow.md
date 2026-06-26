# Auth Flow (All Roles)

Same for every staff member until they reach **their role dashboard**.

---

## Flow diagram

```
[Open app]
    │
    ├─ No token? ──► /login
    │
    └─ Has token? ──► read role from storage
                          │
                          ├─ opd_billing   ──► /opd-billing/dashboard
                          ├─ receptionist  ──► /receptionist/dashboard
                          ├─ doctor        ──► /doctor/dashboard
                          ├─ nurse        ──► /nurse/dashboard
                          ├─ pharmacist   ──► /pharmacy/dashboard
                          ├─ admin        ──► /admin/dashboard
                          └─ lab_technician ► /lab/dashboard
```

---

## Step 1 — Login screen

**Route:** `/login`  
**File:** `pages/auth/LoginPage.tsx` (exists)

| User action | API | Body |
|-------------|-----|------|
| Click Sign in | `POST /auth/login` | `{ email, password }` |

**On success:**

1. Save `access_token`
2. Save `role`, `permissions`, `first_name`, `user_id`
3. `navigate` to role dashboard (see table above)

**On error:** Show message from API (`Invalid email or password`)

---

## Step 2 — Register staff (optional page)

**Route:** `/register`  
**File:** `pages/auth/RegisterPage.tsx` (exists)

| Step | API | Notes |
|------|-----|-------|
| Load roles | `GET /roles/` | Fill role dropdown |
| Load departments | `GET /opd/departments` or departments API | For doctor/nurse |
| Submit | `POST /auth/register` | `role_id`, `department_id`, etc. |

**On success:** Show message → redirect to `/login`

---

## Step 3 — Complete profile (optional)

**Route:** `/profile/complete`  
**File:** `pages/auth/CompleteProfilePage.tsx` (exists)

Show **different fields by role** (do not use same form for everyone):

| Role | Fields to show |
|------|----------------|
| doctor | qualification, registration_no, experience, bio |
| nurse | nursing_license_no, qualification, shift |
| opd_billing | phone, address only |
| pharmacist | pharmacy_license, qualification |

**API:** `PUT /auth/profile/complete` (confirm with backend team when ready)

---

## Step 4 — Protected routes

Every page after login must:

1. Check `token` exists → else `Navigate to="/login"`
2. Check user `role` matches this section → else “Access denied” page

---

## Step 5 — Logout

| User action | Code |
|-------------|------|
| Click Sign out | `logout()` from AuthContext |
| | Clear token, role, permissions |
| | `navigate('/login')` |

---

## APIs summary

| Method | Path | When |
|--------|------|------|
| POST | `/auth/login` | Login |
| POST | `/auth/register` | Register |
| GET | `/auth/me` | Refresh user on dashboard load |
| PUT | `/auth/profile/complete` | Profile page (when backend ready) |
