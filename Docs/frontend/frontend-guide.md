# Frontend Guide (Simple)

## Tech stack

- **React** + **TypeScript**
- **Vite** — dev server
- **React Router** — URLs / pages
- **`apiJson()`** in `src/lib/api.ts` — calls backend

---

## Project folders (use this structure)

```
hms-frontend/src/
├── App.tsx                 → main routes
├── context/
│   └── AuthContext.tsx     → token (extend: role + permissions)
├── lib/
│   ├── api.ts              → fetch helper
│   └── authStorage.ts      → token in localStorage
├── pages/
│   ├── auth/               → Login, Register (move existing pages here)
│   ├── opd-billing/        → NEW — front desk
│   ├── doctor/             → NEW
│   ├── nurse/              → NEW
│   ├── pharmacist/         → NEW
│   └── lab-technician/     → NEW
├── layouts/
│   ├── AuthLayout.tsx      → exists (login pages)
│   └── DashboardLayout.tsx → NEW — sidebar + header after login
└── components/             → shared buttons, tables, modals
```

**Rule:** One role = one folder under `pages/`. Never put doctor screens inside `opd-billing/`.

---

## How API calls work

```ts
import { apiJson } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const { token } = useAuth()

const data = await apiJson('/opd/departments', { token })
```

- Base URL: `/api` (proxy to backend)
- Send token: `{ token }` on every protected request
- POST body: `{ method: 'POST', body: { ... }, token }`

---

## Login response (save these)

**POST** `/auth/login`

```json
{
  "access_token": "eyJ...",
  "role": "opd_billing",
  "permissions": ["patients:view", "opd:create", ...],
  "first_name": "Ravi",
  "user_id": 3
}
```

### What frontend must store (team task)

Today only `access_token` is saved. **Add to AuthContext:**

| Field | Use |
|-------|-----|
| `role` | Which dashboard to open |
| `permissions` | Show/hide menu items |
| `first_name` | Header greeting |
| `user_id` | “Recorded by” displays |

---

## After login — redirect by role

| `role` value | Go to route |
|--------------|-------------|
| `opd_billing` | `/opd-billing/dashboard` |
| `doctor` | `/doctor/dashboard` |
| `nurse` | `/nurse/dashboard` |
| `pharmacist` | `/pharmacy/dashboard` |
| `admin` | `/admin/dashboard` |
| `lab_technician` | `/lab/dashboard` |

---

## Show menu only if user has permission

```ts
function can(permissions: string[], key: string) {
  return permissions.includes(key)
}

// Example: show "Register Patient" only if allowed
can(permissions, 'patients:create') && <Link to="/opd-billing/register">Register Patient</Link>
```

Backend still checks permissions. Frontend hiding is for **UX only**.

---

## Route pattern (add in App.tsx)

```tsx
// Protected wrapper — no token → go login
<Route element={<ProtectedRoute />}>
  <Route element={<DashboardLayout />}>
    <Route path="/opd-billing/*" element={<OpdBillingRoutes />} />
    <Route path="/doctor/*" element={<DoctorRoutes />} />
    ...
  </Route>
</Route>
```

Each role file exports its own `<Routes>`:

```tsx
// pages/opd-billing/OpdBillingRoutes.tsx
<Route path="dashboard" element={<Dashboard />} />
<Route path="register-patient" element={<RegisterPatient />} />
```

---

## Page build checklist

For every new screen:

1. Design URL (route)
2. List API calls (method + path)
3. List form fields
4. Loading + error state
5. Success message / redirect
6. Test with correct role login
7. Test wrong role cannot open URL (redirect or “No access”)

---

## What already exists in code

| Route | Page | Status |
|-------|------|--------|
| `/login` | LoginPage | Done |
| `/register` | RegisterPage | Done |
| `/profile/complete` | CompleteProfilePage | Done (backend endpoint may be missing) |
| `/` | HomePage | Placeholder — replace with role redirect |

---

## Build order (same as backend)

| Phase | Frontend module |
|-------|-----------------|
| 1 | Auth + role redirect + DashboardLayout |
| 2 | OPD Billing screens |
| 3 | Doctor screens |
| 4 | Nurse screens |
| 5 | Pharmacist screens |
| 6 | Lab technician screens |

Wait for backend API before building a screen. Check [backend roles docs](../backend/roles/).

---

## Design notes

- Use same layout for all roles: **sidebar (menu) + top bar + main content**
- Tables for lists, modals for quick actions
- Mobile later — start with desktop layout
