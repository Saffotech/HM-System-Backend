# Receptionist — Frontend Flow

**Role name from API:** `receptionist`  
**Folder:** `src/pages/receptionist/`  
**URL prefix:** `/receptionist/`

---

## Module purpose

Reception **monitors** the live OPD waiting line (view-only).

| Reception does (view) | Reception does not |
|-----------------------|-------------------|
| View dashboard metrics | Register patients or collect payment |
| View doctor queue boards | Check-in / call / no-show / rejoin |
| View queue history | Start or complete consultations |

---

## Screens to build

| # | Screen | Route | Primary API |
|---|--------|-------|-------------|
| 1 | Dashboard | `/receptionist/dashboard` | `GET /receptionist/dashboard` |
| 2 | Today's queue (all doctors) | `/receptionist/today` | `GET /receptionist/today-queue` |
| 3 | Doctor queues | `/receptionist/queues` | `GET /receptionist/doctor-queue/{doctor_id}` |
| 4 | Queue history | `/receptionist/history` | `GET /receptionist/queue-history` |

---

## Sidebar menu

```
Dashboard
Today's Queue
Doctor Queues
Queue History
Sign out
```

---

## Permissions

```
patients:view
receptionist:view_queue
```

---

## Removed APIs (do not call)

- `GET /receptionist/arrivals`
- `POST /receptionist/check-in/{appointment_id}`
- `GET /receptionist/pending-calls`
- `POST /receptionist/call-patient/{queue_id}`
- `PATCH /receptionist/queue/{queue_id}/no-show`
- `PATCH /receptionist/queue/{queue_id}/rejoin`
- `GET /receptionist/queue-history/export`

---

*PDF: `Docs/receptionist-module-guide.pdf`*
