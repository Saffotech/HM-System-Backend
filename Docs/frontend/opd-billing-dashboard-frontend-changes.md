# OPD Billing Dashboard — Frontend changes

**For:** Frontend  
**Backend:** `GET /opd/dashboard` is already updated.  
**Goal:** Load the OPD Billing **landing dashboard** with **one API call**.

Do **not** change Appointments, Patients, Billing, or the full **Today’s Overview** page in this task.

---

## Why

The dashboard currently calls **4 APIs**:

| Call | Used for |
|------|----------|
| `GET /opd/dashboard` | KPI chips |
| `GET /opd/appointments?date=YYYY-MM-DD&limit=50` | Today’s appointments table |
| `GET /opd/patients?page=1&limit=20` | Recent patients |
| `GET /opd/bills?today_only=true&limit=100` | Today’s Overview **card** |

Backend now returns all of that on **`GET /opd/dashboard`**. Extra calls on this page are no longer needed.

---

## Keep using (other screens)

These APIs stay for other pages. **Do not delete** the hooks globally.

| API | Keep for |
|-----|----------|
| `GET /opd/appointments` | Appointments list / book |
| `GET /opd/patients` | Patient list |
| `GET /opd/bills` | Billing + full Today’s Overview **page** |
| `GET /opd/visits/today` | Full Today’s Overview **page** |

---

## API: `GET /opd/dashboard`

**Permission:** `opd:view`  
**Auth:** Bearer token (same as today)

### Response (current)

Old fields are unchanged. New fields are additive.

```json
{
  "visits_today": 12,
  "patients_total": 340,
  "pending_bills": 5,
  "appointments_today": 8,
  "recent_visits": [],
  "today_collected": 10500.0,
  "today_bills_count": 15,
  "today_pending_payments": 3,
  "recent_patients": [
    {
      "id": 13,
      "patient_uid": "P-1007",
      "name": "Test Patient",
      "phone": "9876511111",
      "created_at": "2026-07-16T10:00:00+05:30"
    }
  ],
  "today_appointments": [
    {
      "id": 5,
      "appointment_uid": "APT-0005",
      "patient_id": 13,
      "patient_name": "Test Patient",
      "patient_uid": "P-1007",
      "doctor_id": 5,
      "doctor_name": "Dr. Adesh Zinj",
      "department_id": 12,
      "department_name": "Cardiology",
      "scheduled_at": "2026-07-16T14:00:00+05:30",
      "reason": "OPD",
      "notes": "test",
      "appointment_type": "opd",
      "status": "scheduled",
      "payment_status": "pending",
      "bill_id": 4,
      "bill_number": "BILL-004",
      "total_amount": 1050.0,
      "paid_amount": 0.0,
      "balance_amount": 1050.0
    }
  ]
}
```

### Field mapping

| UI | Use this field |
|----|----------------|
| Patients chip | `patients_total` |
| Appointments today chip | `appointments_today` |
| Pending bills chip | `pending_bills` |
| Today’s visits (overview card) | `visits_today` |
| Bills generated (overview card) | `today_bills_count` |
| Collected today | `today_collected` |
| Pending payments (overview card) | `today_pending_payments` |
| Appointments table (max 8) | `today_appointments` |
| Recent patients (max 20) | `recent_patients` |

### Notes

- `today_appointments`: already **max 8**, **non-cancelled**, today’s date, payment fields included (same shape as `GET /opd/appointments` rows).
- `recent_patients`: compact object (`id`, `patient_uid`, `name`, `phone`, `created_at`). **Not** full patient list payload. Do not assume `first_name` / `last_name`.
- `pending_bills` (chip) = all-time pending/partial (unchanged).  
  `today_pending_payments` (card) = **today** bills with balance due.
- `recent_visits` is still returned (max 5). The landing page does not have to display it.

---

## Files to change

| File | Change |
|------|--------|
| `src/shared/api/services/opdDashboard.js` | Map new fields in `apiToUiDashboard`. Remove `fetchOpdDashboardFallback` (it fires 5 extra APIs on error). |
| `src/features/opd/pages/DashboardPage.jsx` | Use dashboard payload for appointments table + recent patients. Remove `useTodayAppointmentsQuery` and `usePatientsQuery` from **this page only**. |
| `src/features/opd/today-overview/components/TodayOverviewCard.jsx` | Use `today_bills_count`, `today_collected`, `today_pending_payments`. Remove `useTodayBillsQuery` from **this card only**. |

You can keep using:

- `enrichAppointmentsWithApiPayment`
- `prepareOpdDashboardAppointments`

on `today_appointments` for Paid / Unpaid badges.

---

## Do not do

- Do not delete `useTodayAppointmentsQuery`, `usePatientsQuery`, `useTodayBillsQuery` globally.
- Do not rewrite the full Today’s Overview **page** (`useTodayOverview`) in this task.
- Do not call `/opd/beds` for this dashboard (backend does not return `beds_free` / `ward_bed_stats`).

---

## How to verify

1. Open OPD Billing Dashboard.
2. Network tab: **one** `GET /opd/dashboard` (plus auth if any).
3. Chips, appointments table, recent patients, and Today’s Overview card still look correct.
4. Appointments / Patients / Billing / Today’s Overview **pages** still work.

---

## Questions

Backend: OPD dashboard work in `hms-backend` (`GET /opd/dashboard`, `OpdDashboardResponse`).
