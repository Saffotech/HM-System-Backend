# Hospital Management System (HMS) — Overview

**Audience:** Manager / leadership (for PowerPoint)  
**Purpose:** Explain what the system does and who uses which tools.

---

## What is HMS?

HMS is a hospital software for **outpatient (OPD)** operations:

- Register patients and create bills  
- Book doctor appointments  
- Collect payment  
- Manage doctor waiting queue  
- Support clinical work (doctor, nurse)  
- Pharmacy dispensing and lab reports  
- Staff and hospital administration  

One hospital install (not multi-hospital SaaS).

---

## Main modules (tools)

| Module | Used by | What it does |
|--------|---------|--------------|
| **Authentication** | All roles | Login, role-based access |
| **OPD & Billing** | OPD Billing staff | Patient register, bill, pay, book appointment |
| **Reception** | Receptionist | View today’s appointments & doctor queues |
| **Doctor workspace** | Doctor | Queue, consultation, prescription, lab orders |
| **Nurse workspace** | Nurse | Vitals, notes, medication, handover, alerts |
| **Pharmacy** | Pharmacist | View & dispense prescriptions |
| **Laboratory** | Lab technician | Receive orders, enter/upload results |
| **Admin panel** | Hospital Admin | Staff management, dashboard, reports (view) |
| **Super Admin panel** | Owner / director | Highest control: roles, settings, audit |

---

## How work is separated

| Job | Who |
|-----|-----|
| Collect money / create bill | **OPD Billing** |
| Book / cancel appointment | **OPD Billing** |
| Watch queue / schedules | **Receptionist** (view mostly) |
| Treat patient / complete visit | **Doctor** |
| Support care on floor | **Nurse** |
| Give medicines | **Pharmacist** |
| Lab reports | **Lab Technician** |
| Manage staff | **Admin** |
| System / policy control | **Super Admin** |

---

## Important product rules (current)

1. **Register does not always create an appointment** — appointment is booked as a separate step (or linked when UI/API supports it).  
2. **“Pending” is not an appointment status** — it means **scheduled + unpaid**.  
3. **Doctor only completes** consultation; **OPD cancels**; **system marks no-show** for past missed appointments.  
4. Patient joins **doctor queue only after payment** and when visit is linked to an appointment.  

---

## Status words used in the system

### Appointment / queue status

| Status | Meaning |
|--------|---------|
| `scheduled` | Booked, not finished |
| `completed` | Doctor finished consultation |
| `cancelled` | Cancelled by OPD |
| `no_show` | Missed (past day) — set by system |

Removed / not used anymore for appointments: `waiting`, `in_progress`.

### Payment status (bill)

| Status | Meaning |
|--------|---------|
| `pending` | Not paid |
| `partial` | Part paid |
| `paid` | Fully paid |

---

## Presentation tip

Use this page for **slides 1–2**. Next open **Roles and Permissions**, then **Patient Journey**, then each role file under `Roles/`.
