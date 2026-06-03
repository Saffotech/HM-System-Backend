# Pharmacist — Frontend Flow

**Role name from API:** `pharmacist`  
**Folder:** `src/pages/pharmacist/`  
**URL prefix:** `/pharmacy/`

---

## Screens to build (Phase 1 only)

| # | Screen | Route | Backend |
|---|--------|-------|---------|
| 1 | Dashboard | `/pharmacy/dashboard` | Wait |
| 2 | Prescription queue | `/pharmacy/prescriptions` | Wait |
| 3 | Prescription detail | `/pharmacy/prescriptions/:id` | Wait |
| 4 | Dispense | `/pharmacy/dispense/:id` | Wait |
| 5 | Dispense history | `/pharmacy/history` | Wait |

**Phase 2 (later):** inventory, suppliers, stock — separate screens, do not mix in Phase 1 folder sub-routes until needed.

---

## Sidebar menu (Phase 1)

```
Dashboard
Prescriptions
History
Sign out
```

---

## Flow 1 — Dashboard

```
Login (role = pharmacist)
    → /pharmacy/dashboard
```

**Cards:**

- Pending prescriptions count
- Dispensed today
- Low stock alert (Phase 2)

**API (when ready):** `GET /pharmacy/prescriptions?status=pending`

---

## Flow 2 — Prescription queue

**Route:** `/pharmacy/prescriptions`

**Table:**

| Column | |
|--------|--|
| Prescription ID | |
| Patient name | |
| Doctor name | |
| Date | |
| # medicines | |
| Status | pending / processing / dispensed |
| Action | View |

**Filters:** status dropdown, search patient name

**API:** `GET /pharmacy/prescriptions?status=pending`

---

## Flow 3 — Prescription detail → Dispense

```
Queue → click row
    → /pharmacy/prescriptions/:id
    → Show patient info + medicine list + stock (later)
    → Click "Dispense"
    → /pharmacy/dispense/:id
```

**Dispense form:**

| Field | |
|-------|--|
| quantity_dispensed | number |
| remarks | optional |

**API:** `POST /pharmacy/dispense/{prescription_id}`

**On success:**

- Show success message
- Button: Print slip (later)
- Back to queue

---

## Flow 4 — History

**Route:** `/pharmacy/history`

**Table:** past dispensings (date, patient, pharmacist, status)

**API:** `GET /pharmacy/history`

---

## Important rules

- Pharmacist **does not create** prescriptions — only **views** and **dispenses**
- Hide "New prescription" button for this role
- Show patient allergies on detail screen (from patient API)

---

## Suggested files

```
pages/pharmacist/
├── PharmacyRoutes.tsx
├── Dashboard.tsx
├── PrescriptionQueue.tsx
├── PrescriptionDetail.tsx
├── DispenseForm.tsx
└── DispenseHistory.tsx
```

---

## Build order

1. Queue list (when backend ready)
2. Detail + dispense form
3. History
4. Dashboard stats
5. Inventory module (new sub-folder `pages/pharmacist/inventory/` in Phase 2)
