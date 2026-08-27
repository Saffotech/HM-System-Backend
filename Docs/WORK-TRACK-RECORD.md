# HMS Backend — Work Track Record (Manager Summary)

**Project:** Hospital Management System (HMS)  
**Scope:** Backend APIs + related frontend integration topics  
**Purpose:** Track which modules / topics were worked on, by phase  

---

## How to read this document

| Term | Meaning |
|------|---------|
| **Phase 1** | Core / foundation — models, auth, RBAC, basic role APIs |
| **Phase 2** | Clinical & operations — doctor, nurse, OPD, pharmacy flows |
| **Phase 3** | IPD stay, pricing, nurse↔billing sync |
| **Phase 4** | IPD insurance + unified billing (daily / hospital charges) |

Status legend: **Done** · **In progress** · **Pending / next**

---

## Phase 1 — Foundation (RBAC, Auth, Core Models)

| Topic | Module | What was done | Status |
|-------|--------|---------------|--------|
| App entry & routers | Core | FastAPI `main.py`, CORS, router registration | Done |
| Database session | Core | `database.py`, SQLAlchemy engine, `get_db` | Done |
| Models | Core | User, Role, Permission, Patient, OPD, etc. | Done |
| Auth | Auth | Login / JWT / register staff | Done |
| RBAC | Auth | Roles + permissions (`seed.py`), `PermissionChecker` | Done |
| Admin panel docs | Admin | Staff / roles documentation | Done |

**Key idea:** Every API is gated by role permissions (doctor, nurse, IPD, pharmacy, etc.).

---

## Phase 2 — Doctor, Nurse, OPD, Pharmacy

### Doctor

| Topic | What was done | Status |
|-------|---------------|--------|
| Consultation / OPD–IPD patient views | Doctor APIs for patients, history, visits | Done |
| Doctor patient visits (nurse-logged) | `GET /doctor/patient-visits` — day-wise visit count | Done |
| IPD patient visit counts on doctor UI | Uses nurse doctor-visit records | Done |
| Appointment service stability | Indentation / syntax fixes so server starts | Done |

### Nurse

| Topic | What was done | Status |
|-------|---------------|--------|
| Doctor visits registry | `POST/GET/PUT /nurse/doctor-visits` (+ void) | Done |
| Visit number / day count (scale) | SQL window + COUNT (no full-day load) | Done |
| Active doctors / departments pickers | Nurse doctor-visit supporting APIs | Done |
| Sync nurse visit → IPD billable visit | On create/update/void → `ipd_doctor_visits` + fee snapshot | Done |

### OPD / Billing (counter)

| Topic | What was done | Status |
|-------|---------------|--------|
| OPD settings / pricing source | Consultation fees, bed tariff in settings | Done |
| Payment modes | Cash / card / UPI / insurance (payment mode) | Done |

### Pharmacy

| Topic | What was done | Status |
|-------|---------------|--------|
| Prescription duration handling | String duration → supply qty (no `int()` crash) | Done |
| Dispense line pricing | `unit_price`, `amount`, `dispensings.total_amount` | Done |
| List performance | COUNT-optimized listing | Done |

---

## Phase 3 — IPD Stay, Pricing, Nurse Billing Sync

| Topic | Module | What was done | Status |
|-------|--------|---------------|--------|
| IPD admit / register | IPD | `POST /ipd/patients/register`, `POST /ipd/admissions` | Done |
| Bed / ward rates on IPD APIs | IPD | `charge_per_day` on beds/wards; doctor fees on reference doctors | Done |
| Resolve consultation / bed rates | IPD + Settings | Doctor → dept → hospital fee; bed special rates | Done |
| Nurse visit → billable IPD visit | Nurse + IPD | Migration: `nurse_visit_id`, `is_voided`, indexes | Done |
| Fee snapshot on visit | IPD | Charge frozen at visit create/update | Done |
| Bill preview includes visits | IPD | Non-voided doctor visits on running bill | Done |

**Migrations (examples):**  
`l5m6n7o8p9q0` (nurse↔IPD visit link) · pharmacy pricing revision earlier in chain

---

## Phase 4 — IPD Insurance + Unified Billing

### Insurance (cashless / copay)

| Topic | What was done | Status |
|-------|---------------|--------|
| Persist insurance on **admit** (not only register) | `payment_mode` + `insurance` on `POST /ipd/admissions` | Done |
| Claim table | `ipd_insurance_claims` (company, policy, holder, claimed, estimate, status) | Done |
| Admission payment type | `payment_type`: self / insurance_cashless / insurance_copay | Done |
| Insurance APIs | `/ipd/insurance/patients`, claims, bills, admission insurance, payments | Done |
| FE stubs → live APIs | `IPD_INSURANCE_API_READY = true` | Done |

### Unified billing (daily + hospital heads)

| Topic | What was done | Status |
|-------|---------------|--------|
| Billing storage | `ipd_admission_billing` (charge heads + daily lines) | Done |
| APIs | `GET/PUT /ipd/admissions/{id}/billing`, `/daily`, `/final` | Done |
| Auto pull charges | Bed (per day) + doctor visits + pharmacy dispensings | Done |
| FE live flag | `IPD_BILLING_USE_LIVE_API = true` | Done |
| Billing route by payment type | Cashless → insurance billing URL; self/copay → preview | Done |

**Migrations:**  
`m6n7o8p9q0r1` (insurance claims) · `o8p9q0r1s2t3` (admission billing)

---

## Module-wise snapshot (for manager)

| Module | Phase | Main topics worked |
|--------|-------|--------------------|
| **RBAC / Auth / Admin** | 1 | Roles, permissions, staff access |
| **Doctor** | 2–3 | Consultation context, patient visits from nurse logs |
| **Nurse** | 2–3 | Doctor visits CRUD, scaled visit numbering, IPD sync |
| **OPD** | 1–2 | Visits, settings, pricing source of truth |
| **Pharmacy** | 2–4 | Duration parse, dispense amounts, IPD auto pharmacy lines |
| **IPD** | 3–4 | Admit, beds, visits, insurance claim, unified billing |
| **Insurance (IPD)** | 4 | Cashless/copay profile, lists, edit, billing bundle |
| **Frontend (IPD only)** | 4 | Admit insurance payload, billing flags, correct billing routes |

---

## Recent stability / bug fixes (support)

| Issue | Fix | Status |
|-------|-----|--------|
| Backend won't start (`IndentationError` in appointments) | Fixed `_appointment_out` + doctor availability slots indent | Done |
| Insurance toast “waiting for API contract” | Implemented backend insurance APIs + FE live flag | Done |
| Billing after admit OK, but Patients → Billing wrong screen | FE route: cashless → insurance billing, not self-pay preview | Done |

---

## Suggested “topics I worked on” (one-liner list for standup)

1. RBAC / permissions foundation  
2. Doctor & nurse clinical APIs  
3. Pharmacy dispense pricing & duration  
4. IPD bed/doctor pricing display  
5. Nurse doctor visit → IPD billable visit sync  
6. IPD insurance claim on admit + insurance CRUD APIs  
7. IPD unified billing (daily/final) with auto bed / visit / pharmacy  
8. Frontend insurance billing navigation fix  

---

## Pending / next (if asked)

| Item | Notes |
|------|--------|
| Lab auto-lines in insurance billing | Lab orders exist; pricing pull not fully wired like pharmacy |
| Insurance approval / TPA workflow | Basic `claim_status` / `approved_amount` only |
| Bed tariff for IPD role without `opd:view` | Prefer rates already on `/ipd/beds` in FE |

---

## Document control

| Field | Value |
|-------|--------|
| Location | `hms-backend/Docs/WORK-TRACK-RECORD.md` |
| Audience | Manager / lead — progress by module & phase |
| Code changes in this file | **None** — documentation only |

---

*Prepared for internal track record. Does not modify application source code.*
