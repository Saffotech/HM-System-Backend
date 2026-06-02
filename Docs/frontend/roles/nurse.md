# Nurse — Frontend Flow

**Role name from API:** `nurse`  
**Folder:** `src/pages/nurse/`  
**URL prefix:** `/nurse/`

---

## Screens to build

| # | Screen | Route | Backend |
|---|--------|-------|---------|
| 1 | Dashboard | `/nurse/dashboard` | Partial |
| 2 | Assigned patients | `/nurse/patients` | Wait backend |
| 3 | Patient detail | `/nurse/patients/:id` | Wait backend |
| 4 | Update vitals | `/nurse/vitals/:patientId` | Wait backend |
| 5 | Nursing notes | `/nurse/notes/:patientId` | Wait backend |

**Do not build yet:** medication admin, shift handover (needs doctor prescriptions first)

---

## Sidebar menu

```
Dashboard
My Patients
Today's OPD
Sign out
```

---

## Flow 1 — Dashboard

```
Login (role = nurse)
    → /nurse/dashboard
```

**Cards:**

- Assigned patients count (when API ready)
- Critical alerts (later)
- Pending vitals (later)

**Quick actions:**

- View patients
- Today's OPD list

**API (now):** `GET /opd/queue/today` — read-only list

---

## Flow 2 — View patient list

**Route:** `/nurse/patients`

**Table columns (from Word file):**

| Column | |
|--------|--|
| Patient ID | |
| Name | |
| Ward / Room | later |
| Doctor | |
| Vitals status | Updated / Pending |
| Priority | |
| Action | View / Update vitals |

**API (when ready):** `GET /nurse/patients`

---

## Flow 3 — Update vitals (important)

```
Patient list → "Update vitals"
    → /nurse/vitals/:patientId
    → Fill form → Save
    → Back to patient detail
```

**Form fields:**

| Field | Input |
|-------|-------|
| temperature | number |
| blood_pressure | text (120/80) |
| heart_rate | number |
| respiratory_rate | number |
| oxygen_saturation | number |
| blood_sugar | optional |
| weight | optional |
| pain_level | 1–10 slider |
| observation_notes | textarea |
| status | normal / critical |

**API (when ready):** `POST /nurse/vitals`

**Extra buttons:**

- **Mark critical** → set status critical
- **Notify doctor** → later

---

## Flow 4 — Nursing note

**Route:** `/nurse/notes/:patientId`

| Field | |
|-------|--|
| symptoms | textarea |
| treatment_response | textarea |
| additional_notes | textarea |

**API (when ready):** `POST /nurse/notes`

---

## Flow 5 — Patient detail

**Route:** `/nurse/patients/:id`

**Sections (read-only + actions):**

- Basic info (name, age, allergies)
- Vitals timeline (list past vitals)
- Nursing notes list
- Buttons: Update vitals, Add note

---

## Profile form (register / complete profile)

**Do not use doctor fields.**

Show only:

- phone, address, city, state
- nursing_license_no
- qualification
- shift_preference

---

## Suggested files

```
pages/nurse/
├── NurseRoutes.tsx
├── Dashboard.tsx
├── PatientList.tsx
├── PatientDetail.tsx
├── VitalsForm.tsx
└── NursingNoteForm.tsx
```

---

## Build order

1. Dashboard + OPD queue (existing API)
2. Vitals form + list
3. Nursing notes
4. Full patient list when backend ready
