# Lab Technician — Frontend Flow

**Role name from API:** `lab_technician` (add to backend seed)  
**Folder:** `src/pages/lab-technician/`  
**URL prefix:** `/lab/`

---

## Screens to build

| # | Screen | Route | Backend |
|---|--------|-------|---------|
| 1 | Dashboard | `/lab/dashboard` | Wait |
| 2 | Test requests | `/lab/orders` | Wait |
| 3 | Upload report | `/lab/orders/:id/upload` | Wait |
| 4 | Completed reports | `/lab/reports` | Wait |

---

## Sidebar menu

```
Dashboard
Pending Tests
Completed Reports
Sign out
```

---

## Flow 1 — Dashboard

**Cards:**

- Total tests today
- Pending reports
- Completed reports
- Urgent tests (highlight red)

**API (when ready):** aggregate from `GET /lab/orders?status=pending`

---

## Flow 2 — Pending test list

**Route:** `/lab/orders`

**Table:**

| Column | |
|--------|--|
| Request ID | |
| Patient name | |
| Patient ID | |
| Doctor name | |
| Test name | |
| Category | Blood / Radiology |
| Priority | normal / urgent |
| Requested date | |
| Status | |
| Action | Upload report |

**Filters:** status, priority, date, patient search

**API:** `GET /lab/orders?status=pending`

---

## Flow 3 — Upload report

**Route:** `/lab/orders/:id/upload`

**Read-only top section:**

- Patient name, ID
- Test name, doctor name

**Editable:**

| Field | Input |
|-------|-------|
| sample_collected_at | datetime |
| test_performed_at | datetime |
| report_file | file upload (PDF/image) |
| remarks | textarea |
| status | in_progress / completed |

**Parameters table (add rows):**

| parameter_name | value | unit | normal_range | flag |
|----------------|-------|------|--------------|------|

Button: **+ Add row**

**API:** `POST /lab/orders/{id}/report`

**On success:** go to completed list

---

## Flow 4 — Completed reports

**Route:** `/lab/reports`

**Table:** Report ID, patient, test, uploaded date, action View/Print

**API:** `GET /lab/reports`

---

## Dependency

**Doctor must order lab tests first.** Build doctor lab UI before lab technician UI.

---

## Suggested files

```
pages/lab-technician/
├── LabRoutes.tsx
├── Dashboard.tsx
├── OrderList.tsx
├── UploadReport.tsx
└── CompletedReports.tsx
```
