# Lab Technician (`lab_technician`)

Lab staff receives test orders from doctors and uploads reports.

**Full API guide (start here):** [lab-test.md](./lab-test.md)

**Word file:** Lab Technician Views 1–5 (`_extracted_fields_requirements.txt`)

**Frontend flow:** [../../frontend/roles/lab-technician.md](../../frontend/roles/lab-technician.md)

---

## Status

| Area | Status |
|------|--------|
| Doctor orders (`/lab-tests`) | Done |
| Lab technician APIs (`/lab/*`) | To build |
| Role `lab_technician` in seed | To add |
| Tables `lab_results`, `lab_result_parameters` | To create |

---

## Flow (simple)

```
Doctor orders test  →  Lab tech sees pending list
                   →  Mark sample collected
                   →  Upload report + results
                   →  Doctor & patient can view
```

Uses table `lab_test_orders` (exists) + `lab_results`, `lab_result_parameters` (to create).

---

## Permissions (add in seed.py)

**New role:** `lab_technician`

```
lab:view
lab:update
lab:upload_report
patients:view
```

See [lab-test.md](./lab-test.md) for full seed snippet.

---

## APIs to build

| Step | What | Method | URL |
|------|------|--------|-----|
| 1 | Dashboard stats | GET | `/lab/dashboard` |
| 2 | Pending / all orders | GET | `/lab/orders` |
| 3 | Order detail | GET | `/lab/orders/{id}` |
| 4 | Sample collected | PATCH | `/lab/orders/{id}/sample-collected` |
| 5 | Processing | PATCH | `/lab/orders/{id}/processing` |
| 6 | Upload report | POST | `/lab/orders/{id}/report` |
| 7 | Completed reports | GET | `/lab/reports` |
| 8 | Report detail | GET | `/lab/reports/{id}` |

Full request/response specs → [lab-test.md](./lab-test.md) Part B.

---

## Register lab technician

**POST** `/auth/register` with `role_id` of `lab_technician` from `GET /roles/`.

---

## Do not build yet

- Full radiology PACS integration
- Patient portal download (separate module)
