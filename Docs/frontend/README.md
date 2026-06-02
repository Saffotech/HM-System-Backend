# HMS Frontend Documentation

Screens, user flows, and API calls for **React app only**.

Backend API details → see [../backend/](../backend/)

---

## Start here (in order)

1. **[frontend-guide.md](./frontend-guide.md)** — project setup, auth, routing rules
2. **[flows/auth-flow.md](./flows/auth-flow.md)** — login → dashboard (all roles)
3. Open **your role file** in [roles/](./roles/)

---

## Role flows (pick one)

| File | Role from login | Main job |
|------|-----------------|----------|
| [opd-billing.md](./roles/opd-billing.md) | `opd_billing` | Register patient, billing, queue |
| [doctor.md](./roles/doctor.md) | `doctor` | Consult, prescribe, lab orders |
| [nurse.md](./roles/nurse.md) | `nurse` | Vitals, nursing notes |
| [pharmacist.md](./roles/pharmacist.md) | `pharmacist` | Dispense medicines |
| [lab-technician.md](./roles/lab-technician.md) | `lab_technician` | Upload lab reports |
| [admin.md](./roles/admin.md) | `admin` | Staff & settings |

---

## Run frontend

```bash
cd hms-frontend
npm install
npm run dev
```

API proxy: `/api` → backend (see `vite.config.ts`)

---

## Folder rule (important)

Put each role’s pages in **its own folder**. Do not mix files.

```
hms-frontend/src/pages/
├── auth/              ← login, register (shared)
├── opd-billing/       ← only OPD staff screens
├── doctor/
├── nurse/
├── pharmacist/
└── lab-technician/
```
