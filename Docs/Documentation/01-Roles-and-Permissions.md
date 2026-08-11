# Roles and Permissions — Overview

**Audience:** Manager / PPT  
**Purpose:** One-page matrix of who can do what.

---

## Roles in the system

| Role (system name) | Display name | Main job |
|--------------------|--------------|----------|
| `admin` | Hospital Admin | Staff + dashboard + view reports |
| `super_admin` | Super Admin | Owner / highest control |
| `opd_billing` | OPD Billing | Register, bill, pay, appointments |
| `receptionist` | Receptionist | View queue & schedules |
| `doctor` | Doctor | Consultation & clinical orders |
| `nurse` | Nurse | Vitals, notes, meds, alerts |
| `pharmacist` | Pharmacist | Dispense medicines |
| `lab_technician` | Lab Technician | Lab results & reports |

---

## Capability matrix (simple)

| Capability | Admin | Super Admin | OPD | Reception | Doctor | Nurse | Pharmacy | Lab |
|------------|:-----:|:-----------:|:---:|:---------:|:------:|:-----:|:--------:|:---:|
| Login / own profile | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Register patient | | | ✓ | | | | | |
| Create / collect bill | | | ✓ | | | | | |
| Book / cancel appointment | | | ✓ | | | | | |
| View today’s queue | | | ✓* | ✓ | ✓ | ✓ | | |
| Start / complete consultation | | | | | ✓ | | | |
| Prescriptions create | | | | | ✓ | | | |
| Dispense medicines | | | | | | | ✓ | |
| Lab order (doctor) | | | | | ✓ | | | |
| Lab result / upload | | | | | | | | ✓ |
| Vitals / nursing notes | | | | | | ✓ | | |
| Staff create / activate | ✓ | ✓ | | | | | | |
| Create roles / settings / audit | | ✓ | | | | | | |

\* OPD “today queue” is **billing visits**, not the same as doctor clinical queue.

---

## Who changes appointment status?

| Action | Who |
|--------|-----|
| Create as `scheduled` | OPD (book appointment) |
| Set `completed` | Doctor only |
| Set `cancelled` | OPD only |
| Set `no_show` | System (past day cleanup) |

---

## Who handles money?

**Only OPD Billing** collects payment.  
Receptionist can **see** paid vs unpaid but should not collect payment in the intended design.

---

## Presentation tip

Turn this into:

- Slide: “Roles in HMS” (table of 8 roles)  
- Slide: “Who does what” (capability matrix)  
- Slide: “Status ownership” (complete / cancel / no-show)
