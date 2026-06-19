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

| Lab technician APIs (`/lab/*`) | Done (11 endpoints) |

| Role `lab_technician` in seed | Done |

| Tables `lab_results`, `lab_result_parameters` | Done |

| File upload + download | Done |



---



## Flow (production)



```

Doctor orders test

  → Lab: sample collected → processing

  → POST /lab/orders/{id}/report     (parameters, optional)

  → PATCH /lab/orders/{id}/complete

  → POST /lab/orders/{id}/upload-file (PDF/image, optional)

  → GET /lab/reports?source=BOTH

  → GET /lab/reports/{id}/file       (download)

```



---



## Permissions



```

lab:view

lab:create

lab:update

lab:upload_report

patients:view

```



See [lab-test.md](./lab-test.md) for full seed snippet.



---



## APIs (all built)



| # | What | Method | URL |

|---|------|--------|-----|

| 1 | Dashboard stats | GET | `/lab/dashboard` |

| 2 | Pending / all orders | GET | `/lab/orders` |

| 3 | Order detail | GET | `/lab/orders/{id}` |

| 4 | Sample collected | PATCH | `/lab/orders/{id}/sample-collected` |

| 5 | Processing | PATCH | `/lab/orders/{id}/processing` |

| 6 | Create report | POST | `/lab/orders/{id}/report` |

| 7 | Complete test | PATCH | `/lab/orders/{id}/complete` |

| 8 | Upload file | POST | `/lab/orders/{id}/upload-file` |

| 9 | Completed reports | GET | `/lab/reports` |

| 10 | Report detail | GET | `/lab/reports/{id}` |

| 11 | Download file | GET | `/lab/reports/{id}/file` |



Full request/response specs → [lab-test.md](./lab-test.md) Part B.



---



## Register lab technician



**POST** `/auth/register` with `role_id` of `lab_technician` from `GET /roles/`.



---



## Do not build yet



- Full radiology PACS integration

- Patient portal download (separate module)

- Doctor view report API (`GET /lab-tests/{id}/report`)

