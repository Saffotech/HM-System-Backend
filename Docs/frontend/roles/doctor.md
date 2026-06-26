# Doctor — Frontend Flow

**Role name from API:** `doctor`  
**Folder:** `src/pages/doctor/`  
**URL prefix:** `/doctor/`

**Full workflow:** [Receptionist Module](../../flows/receptionist-module.md) (doctor requests next → reception calls patient)

---

## Screens to build

| # | Screen | Route | Backend |
|---|--------|-------|---------|
| 1 | Dashboard | `/doctor/dashboard` | Partial (queue) |
| 2 | Patient list / EMR | `/doctor/patients` | Wait backend |
| 3 | Patient detail | `/doctor/patients/:id` | Wait backend |
| 4 | Consultation | `/doctor/consultation/:visitId` | Wait backend |
| 5 | Prescriptions | `/doctor/prescriptions` | Wait backend |
| 6 | New prescription | `/doctor/prescriptions/new` | Wait backend |
| 7 | Lab orders | `/doctor/lab-orders` | Wait backend |
| 8 | Calendar | `/doctor/calendar` | Wait backend |

---

## Sidebar menu

```
Dashboard
Patients
Prescriptions
Lab Orders
Calendar
Notifications
Sign out
```

---

## Flow 1 — Login → Dashboard

```
Login (role = doctor)
    → /doctor/dashboard
    → Load today's queue + stats
```

**API (now):** `GET /queue/today` — doctor's **clinical queue** (`patient_queue` for logged-in doctor).

> Do **not** use `GET /opd/queue/today` or `GET /opd/visits/today` — those are **billing visits** for OPD staff. See [Queue endpoints guide](../../flows/queue-endpoints-guide.md).

**Dashboard cards:**

- Patients waiting (count)
- Completed today
- Pending lab reports

**Table:** Today's appointments / queue

| Column | |
|--------|--|
| Time | visit_date |
| Patient | name |
| Token | token_number |
| Status | status |
| Action | Start consultation |

---

## Flow 2 — Start consultation

```
Dashboard → click patient row "Consult"
    → /doctor/consultation/:visitId
    → Form: symptoms, diagnosis, treatment plan
    → Save → Complete
```

**API (when ready):** `POST /doctor/consultations`

| Field | Input |
|-------|-------|
| patient_id | hidden |
| visit_id | hidden |
| symptoms | textarea |
| diagnosis | textarea |
| treatment_plan | textarea |

Buttons:

- **Save draft**
- **Complete consultation** → status completed → back to dashboard

---

## Flow 3 — Write prescription

```
Patients → select patient
    OR from consultation → "Add prescription"
    → /doctor/prescriptions/new?patientId=1
```

**Form — medicine rows (repeatable):**

| Field | |
|-------|--|
| medicine_name | text |
| dosage | text |
| frequency | text |
| duration_days | number |
| instructions | text |

Button: **+ Add medicine**

**API (when ready):** `POST /doctor/prescriptions`

**On success:** toast + go to prescriptions list

---

## Flow 4 — Order lab test

```
/doctor/lab-orders → "New order"
    → Select patient
    → test_name, test_category, priority (normal/urgent)
    → Submit
```

**API (when ready):** `POST /doctor/lab-orders`

**List page:** table with status Pending / In Progress / Completed

---

## Flow 5 — View patient EMR

**Route:** `/doctor/patients/:id`

**Tabs:**

| Tab | Content |
|-----|---------|
| Visits | past visits list |
| Diagnoses | consultation history |
| Prescriptions | active Rx |
| Labs | orders + results |

**API (when ready):** `GET /doctor/patients/{id}`

---

## Suggested files

```
pages/doctor/
├── DoctorRoutes.tsx
├── Dashboard.tsx
├── PatientList.tsx
├── PatientDetail.tsx
├── Consultation.tsx
├── PrescriptionList.tsx
├── PrescriptionForm.tsx
├── LabOrderList.tsx
└── LabOrderForm.tsx
```

---

## Build order

1. Dashboard + queue table (use existing OPD queue API)
2. Consultation form (when backend ready)
3. Prescription form
4. Lab order form
5. EMR patient detail
