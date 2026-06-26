# Queue endpoints — which API to use

HMS has **four different “queue” concepts**. Using the wrong URL is a common integration mistake.

---

## Quick reference

| Who | What you need | Correct API | Data source |
|-----|---------------|-------------|-------------|
| **OPD billing** | Today’s registered visits, bills, payment status | `GET /opd/visits/today` | `opd_visits` |
| **Receptionist** | Patients to check in (not yet in queue) | `GET /receptionist/arrivals` | `appointments` |
| **Receptionist** | **All doctors** — checked in today | `GET /receptionist/today-queue` | `patient_queue` |
| **Receptionist** | One doctor — live waiting room / tokens | `GET /receptionist/doctor-queue/{doctor_id}` | `patient_queue` |
| **Receptionist** | Doctor clicked “next patient” | `GET /receptionist/pending-calls` | `doctor_queue_next_requests` |
| **Receptionist** | Queue history / CSV export | `GET /receptionist/queue-history` / `.../export` | `patient_queue` |
| **Doctor** | My patients today in queue | `GET /queue/today` | `patient_queue` |
| **Nurse** | Vitals queue view | `GET /nurse/queue/today` | `patient_queue` (+ vitals flags) |

**`today-queue` filters:** `doctor_id`, `doctor_name`, `patient_id`, `status`, `search` (name, UHID, phone, patient id, token, appointment UID, doctor name), `page`, `limit`.  
**Sort:** priority (high first) → `called` / `waiting` → token.

**Queue status flow (clinical):** `waiting` → `called` → `in_progress` → `completed`

---

## OPD billing vs receptionist (most confused pair)

### `GET /opd/visits/today` — billing visits

- **Role:** `opd_billing`
- **Table:** `opd_visits`
- **Shows:** Bill number, billing token (`OPD-20260623-001`), payment status, fees
- **Use for:** Billing counter — “who paid / who owes today”
- **Does NOT show:** Check-in status, doctor queue position, `called_at`, `called_by`, consultation state

### `GET /receptionist/*` — clinical queue

- **Role:** `receptionist`
- **Table:** `patient_queue` (+ `appointments`)
- **Shows:** Queue token, `waiting` / `called` / `in_progress` / `no_show`, `called_at`, `called_by`
- **Use for:** Front desk — check-in, call patient to doctor room, no-show

**A patient can have an OPD visit (bill paid) and still not be in the clinical queue until reception checks them in.**

---

## Deprecated / misleading paths

| Old path | Problem | Use instead |
|----------|---------|-------------|
| `GET /opd/queue/today` | Name says “queue” but returns **billing visits** | `GET /opd/visits/today` |
| `GET /opd/queue/next-requests` | Legacy doctor-next signal | `GET /receptionist/pending-calls` |
| `POST /opd/queue/send-in` | Legacy call patient | `POST /receptionist/call-patient/{queue_id}` |
| `POST /queue/add` | Legacy check-in | `POST /receptionist/check-in/{appointment_id}` |

---

## Typical day flow (how endpoints connect)

```
OPD Billing                    Receptionist                    Doctor
───────────                    ────────────                    ──────
POST /opd/patient/register  →  POST /receptionist/check-in
   (creates opd_visit            (creates patient_queue row)
    + appointment)

GET /opd/visits/today       →  GET /receptionist/arrivals
   (billing list)                (who still needs check-in)

                               GET /receptionist/today-queue
                               GET /receptionist/doctor-queue/{id}
                               GET /receptionist/pending-calls
                               POST /receptionist/call-patient/{id}
                                                                  POST /queue/request-next
                                                                  PUT /queue/start/{id}
                                                                  PUT /queue/complete/{id}
```

---

## Response shape: `/opd/visits/today`

```json
{
  "source": "opd_visits",
  "description": "Registered OPD visits and bills for today. This is NOT the clinical waiting-room queue...",
  "total": 12,
  "visits": [
    {
      "visit_id": 1,
      "token_number": "OPD-20260623-001",
      "bill_number": "BILL-001",
      "payment_status": "paid",
      "grand_total": 1050.0
    }
  ]
}
```

The `source` and `description` fields are intentional — they prevent mixing this list with `/receptionist/doctor-queue`.

---

## Related docs

- [Receptionist module](./receptionist-module.md)
- [OPD billing (backend)](../backend/roles/opd-billing.md)
- [API Reference](../frontend/API-REFERENCE.md)
