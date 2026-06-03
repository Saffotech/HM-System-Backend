# Lab Technician (`lab_technician`)

Lab staff receives test orders from doctors and uploads reports.

**This role is NOT in seed yet.** Add it when you start this module.

---

## Add to seed.py

**New role:** `lab_technician`

**Permissions:**

```
lab:view
lab:update
lab:upload_report
patients:view
```

---

## Register lab technician

Same as other staff: **POST** `/auth/register` with `role_id` of `lab_technician`.

---

## Flow (simple)

```
Doctor orders test  →  Lab tech sees pending list
                   →  Mark sample collected
                   →  Upload report + results
                   →  Doctor & patient can view
```

Uses tables from **doctor** module: `lab_orders`, `lab_results`, `lab_result_parameters`.

---

## APIs to build

| What | Method | URL |
|------|--------|-----|
| Pending tests | GET | `/lab/orders?status=pending` |
| Order detail | GET | `/lab/orders/{id}` |
| Sample collected | PATCH | `/lab/orders/{id}/sample-collected` |
| Upload report | POST | `/lab/orders/{id}/report` |
| Completed reports | GET | `/lab/reports` |

---

## Upload report (Word file View 3)

**POST** `/lab/orders/{id}/report`

| Field | Required |
|-------|----------|
| sample_collected_at | No |
| test_performed_at | No |
| report_file | No — PDF/image path or URL |
| remarks | No |
| status | completed |

**Parameters** (optional list for blood tests):

| Field | Example |
|-------|---------|
| parameter_name | Hemoglobin |
| value | 13.5 |
| unit | g/dL |
| normal_range | 12–16 |
| flag | normal / low / high |

---

## Build order

1. Doctor lab orders must work first
2. Lab tech pending list
3. Upload report
4. Completed list

---

## Do not build yet

- Full radiology PACS integration
- Patient portal download (separate module)
