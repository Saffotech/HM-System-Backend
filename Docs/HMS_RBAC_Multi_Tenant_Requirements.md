# HMS — RBAC & Multi-Tenant Requirements

## 1. Document Purpose

This document explains how **Role-Based Access Control (RBAC)** and **multi-hospital (multi-tenant)** access should work in the **Hospital Management System (HMS)**.

It is written for:

- Backend developers  
- Frontend developers  
- QA  
- Product / architects  
- Reviewers  

Use this as the **HMS-specific** guide.  
A separate file, `RBAC_Authentication_Authorization_Requirements.md`, describes the same ideas for a Society Management product. **This file maps those ideas to HMS.**

> **Important:** This is a requirements / design document.  
> Do not treat every table or field as final until business decisions in **Section 15** are confirmed.

---

## 2. Simple Picture of What We Want

Today HMS behaves like **one hospital on one database**.

We want HMS to support **many hospitals on the same platform**, with each hospital’s data kept separate.

```text
Platform (SaffoCare / HMS)
│
├── Hospital A
│     ├── Staff users
│     ├── Patients
│     ├── OPD / IPD / Pharmacy / Lab
│     └── Billing & settings
│
├── Hospital B
│     ├── Staff users
│     ├── Patients
│     ├── OPD / IPD / Pharmacy / Lab
│     └── Billing & settings
│
└── Platform Super Admin
      └── Can register / manage hospitals
```

**Two security checks are always required on protected APIs:**

1. **Permission check** — Does this user’s role allow this action?  
2. **Tenant check** — Does this data belong to this user’s hospital?

```text
Login
  → Identify user
  → Identify hospital (tenant)
  → Load role(s) and permissions
  → API request
  → Check permission
  → Check hospital ownership of data
  → Allow or Deny (403 / 404)
```

---

## 3. Word Mapping (Society Doc → HMS)

| Society Management wording | HMS wording |
|----------------------------|-------------|
| Society / Tenant | Hospital / Organization |
| Society Registration | Hospital onboarding |
| Society Admin | Hospital Admin (`admin`) |
| Super Admin (platform) | Platform Super Admin (`super_admin`, no hospital) |
| Resident / Visitor | Patient / Appointment / Visit |
| Society-scoped data | Hospital-scoped data (`tenant_id` / `hospital_id`) |

In this document we use **hospital** and **tenant** to mean the same thing: one hospital organization on the platform.

---

## 4. What Already Exists in HMS (Current State)

HMS already has a working **single-hospital RBAC** foundation.

### 4.1 Already working

| Area | What exists today | Where |
|------|-------------------|--------|
| Users | Staff accounts with email + hashed password | `users` table |
| Roles | Fixed roles seeded in DB | `roles` (`admin`, `super_admin`, `doctor`, `nurse`, `opd_billing`, `receptionist`, `pharmacist`, lab tech, etc.) |
| Permissions | Permission catalog (`module:action`) | `permissions` + `role_permissions` |
| One role per user | `users.role_id` → role | `Models/user.py` |
| Login / tokens | JWT access + refresh | `Routers/auth.py`, `jwt_token` |
| Route permission checks | `PermissionChecker("opd:view")` etc. | `dependencies.py` + almost all routers |
| Live permission check | Permissions read from DB (not only stale JWT) | `PermissionChecker` |
| Hospital settings | Single settings row for the install | `hospital_settings` (`id = 1`) |
| Audit logs | Login + many module actions | `audit_logs`, Super Admin audit UI |
| Super Admin APIs | Settings + audit list | `/super-admin/*` |
| Module APIs | OPD, IPD, Doctor, Nurse, Pharmacy, Lab, Reception | Existing routers/services |

### 4.2 Current authorization flow (what we have)

```text
User logs in
  → Password verified
  → JWT issued (user id, role, permissions)
  → API call with Bearer token
  → PermissionChecker validates required permission
  → Business service runs
```

### 4.3 What is missing for multi-hospital

| Missing piece | Why it matters |
|---------------|----------------|
| No `tenants` / `hospitals` table | Cannot store multiple hospitals |
| No `tenant_id` / `hospital_id` on users | Users are not linked to a hospital |
| No `tenant_id` on patients, visits, beds, IPD, etc. | Data is not hospital-scoped |
| JWT has no hospital context | Backend cannot trust “which hospital” from auth |
| Services do not filter by hospital | Cross-hospital data leakage risk if multi-tenant is added without filters |
| Roles are global only | Role names unique across whole platform; not per hospital |
| Email is globally unique | Same email cannot join two hospitals |
| `hospital_settings` is single-row | Not one settings row per hospital |
| Audit has no hospital id | Cannot filter audit by hospital |
| No hospital registration API | Super Admin cannot onboard a new hospital like Society Registration |

**Bottom line today:**  
**RBAC permissions work. Multi-tenant isolation does not exist yet.**

---

## 5. Target Roles in Multi-Tenant HMS

### 5.1 Platform level (global)

| Role | Scope | Main job |
|------|--------|----------|
| **Platform Super Admin** | No hospital (`tenant_id = null`) | Register hospitals, deactivate hospitals, platform audit, system roles/permissions catalog |

### 5.2 Hospital level (tenant-scoped)

| Role | Scope | Main job |
|------|--------|----------|
| **Hospital Admin** | One hospital | Staff users, departments, reports (as permitted), hospital settings |
| **OPD Billing** | One hospital | Register patient, bill, pay, appointments |
| **Receptionist** | One hospital | Queue / schedule visibility |
| **Doctor** | One hospital | Consultation, Rx, lab orders, IPD patients under them |
| **Nurse** | One hospital | Vitals, notes, meds, handover |
| **Pharmacist** | One hospital | Dispense medicines |
| **Lab Technician** | One hospital | Lab orders and reports |

Hospital staff must **never** see another hospital’s patients, bills, beds, or staff.

---

## 6. Feature List (HMS Multi-Tenant RBAC Scope)

| # | Feature | Status today | Need to do |
|---|---------|--------------|------------|
| 1 | Login | Exists | Add hospital context to token / session |
| 2 | Logout | Exists (basic) | Keep; optional refresh-token revoke later |
| 3 | User management | Exists (global staff create) | Scope to hospital; hospital admin only manages own staff |
| 4 | Role management | Exists (global) | Decide: keep global templates + clone per hospital, or tenant-scoped roles |
| 5 | Permission management | Exists (global catalog) | Keep permissions global; assign via roles |
| 6 | User–role assignment | Exists (`role_id`) | Enforce role belongs to user’s hospital / allowed system roles |
| 7 | Role–permission assignment | Exists | Scope who can change which roles |
| 8 | Hospital (tenant) management | **Missing** | Create / list / activate / deactivate hospitals |
| 9 | Hospital registration | **Missing** | Super Admin creates hospital + first admin + default seed |
| 10 | Password management | Exists (hash + login) | Forgot/reset policy if product needs it |
| 11 | Account status | Exists (`is_active`, soft delete) | Align with ACTIVE / INACTIVE / SUSPENDED if needed |
| 12 | Audit logs | Exists | Add `tenant_id` / `hospital_id` |
| 13 | Data isolation | **Missing** | Filter every domain query by hospital |

---

## 7. Hospital Registration (New — like Society Registration)

### 7.1 Purpose

Allow **Platform Super Admin** to register a new hospital on the platform.

Hospital Admin and normal staff must **not** create hospitals.

```text
Platform Super Admin
       ↓
Register New Hospital
       ↓
Create Hospital (tenant)
       ↓
Create Hospital Admin user
       ↓
Seed default roles / settings for that hospital
       ↓
Audit: hospital.register
```

### 7.2 Suggested fields

**Hospital**

- Name  
- Code (unique, e.g. `SAFFO-PUNE`)  
- Email  
- Phone  
- Address, city, state, pincode  
- Status (`active` / `inactive`)  

**First Hospital Admin**

- First name, last name  
- Email  
- Temporary password (or invite flow)  
- Phone (optional)  

### 7.3 Business rules

1. Only Platform Super Admin can register a hospital.  
2. Hospital code must be unique.  
3. Hospital email uniqueness rule must be decided (global vs not).  
4. First admin must be linked to the new hospital.  
5. Admin gets hospital-scoped `admin` role + default permissions.  
6. Create hospital settings / OPD settings for that hospital.  
7. Registration must be auditable.  
8. Duplicate / inactive hospital rules must be defined.

### 7.4 Backend outcome (high level)

```text
POST /super-admin/hospitals  (proposed)
  → validate
  → insert tenants/hospitals
  → insert hospital_settings for that tenant
  → create admin user with tenant_id
  → clone/seed hospital roles if using per-tenant roles
  → write audit log
```

---

## 8. Login (Extend What Exists)

### 8.1 Purpose

Authenticate staff and establish **user + hospital + permissions**.

### 8.2 Exists today

- Email + password  
- Active / deleted checks  
- JWT with `sub`, `role`, `role_id`, `permissions`  
- Failed login audit  

### 8.3 Need to add

1. User must belong to a valid hospital **or** be Platform Super Admin.  
2. Authentication response / JWT must include hospital context (`tenant_id` / `hospital_id`, hospital name/code optional).  
3. If email can exist in multiple hospitals (future Option B), login must select hospital (`hospital_code` or tenant picker).  
4. Never trust a client-only `hospital_id` for authorization without server validation.

### 8.4 Target login flow

```text
Email + Password (+ optional Hospital Code)
        ↓
Validate request
        ↓
Find user (and hospital if needed)
        ↓
Verify password
        ↓
Check account active
        ↓
Check hospital active (if hospital user)
        ↓
Resolve role + permissions
        ↓
Issue JWT with user_id + hospital_id + role
        ↓
Return tokens + role + permissions + hospital info
```

---

## 9. Authorization Model

### 9.1 Exists

```text
User → Role → Permissions
API → PermissionChecker(required_permission)
```

Example:

```text
POST /opd/patient/register
Required: patients:create
Role has it? → Yes = continue / No = 403
```

### 9.2 Need to add (tenant ownership)

```text
Permission OK?
    ↓
Does patient / admission / bill belong to user's hospital?
    ↓
Yes → process
No  → reject (prefer 404 for "not found" to avoid leaking IDs)
```

Both checks are mandatory for hospital-scoped APIs.

### 9.3 Platform Super Admin exception

Platform Super Admin may:

- Manage hospitals  
- View cross-hospital audit / reports **only** where product explicitly allows  

They still must not casually read Hospital B clinical data unless a dedicated platform API exists and is permission-gated.

---

## 10. Proposed Database Changes

### 10.1 New core table: `tenants` (or `hospitals`)

```text
id              PK
name
code            UNIQUE
email
phone
address
city
state
pincode
status          active | inactive
created_at
updated_at
```

### 10.2 Change `users`

Add:

```text
tenant_id   FK → tenants.id   NULL allowed for Platform Super Admin
```

Email rule (choose one before coding):

| Option | Rule | DB constraint |
|--------|------|----------------|
| A | One email for whole platform | `users.email UNIQUE` (current) |
| B | Same email allowed in different hospitals | `UNIQUE (tenant_id, email)` |

### 10.3 Roles & permissions

**Recommended for HMS Phase 1**

| Table | Approach |
|-------|----------|
| `permissions` | Keep **global** (already seeded names like `opd:view`, `ipd:bill:pay`) |
| `roles` | Either keep global templates **or** add `tenant_id` and clone roles per hospital |
| `role_permissions` | Keep mapping as today |
| `user_roles` | Optional later; today one `role_id` is enough for Phase 1 |

### 10.4 Tables that need `tenant_id` (hospital ownership)

Add `tenant_id` (indexed) to hospital-owned data, including at least:

| Domain | Examples |
|--------|----------|
| Master | `departments`, `beds`, `hospital_settings`, `opd_settings` |
| Patients / OPD | `patients`, `opd_visits`, `appointments`, bill/payment tables |
| IPD | `ipd_admissions`, IPD bills, insurance, care team |
| Clinical | prescriptions, lab orders/results, nurse vitals/notes, queue |
| Ops | notifications (if hospital-specific), audit_logs |

> Exact list must be finalized during implementation inventory.

### 10.5 Audit logs

Add:

```text
tenant_id   FK → tenants.id (nullable for pure platform events)
```

Keep existing fields: actor, action, resource, details, IP, user agent, created_at.

---

## 11. Backend Design Rules (How to Implement Safely)

### 11.1 Tenant context from server, not client

```text
Trusted:
  JWT / DB user.tenant_id

Not trusted alone:
  Body/query hospital_id from frontend
```

### 11.2 Create rules

On create APIs:

- Set `tenant_id` from current user (server-side)  
- Ignore client-supplied hospital id  

### 11.3 Read / update / delete rules

1. Load resource by id  
2. If `resource.tenant_id != current_user.tenant_id` → deny  
3. Then apply normal permission / business rules  

### 11.4 List APIs

Always filter:

```text
WHERE tenant_id = current_user.tenant_id
```

### 11.5 Keep PermissionChecker

Do **not** remove existing permission checks.  
Multi-tenant adds a **second** layer; it does not replace RBAC.

---

## 12. Suggested Implementation Phases

Do this in order. Do not try to change every table on day one without a migration plan.

| Phase | Work | Result |
|-------|------|--------|
| **Phase 0** | Finalize decisions in Section 15 | Clear rules for DB/auth |
| **Phase 1** | Add `tenants` + `users.tenant_id` + JWT hospital claim | Users belong to a hospital |
| **Phase 2** | Hospital registration API + per-hospital settings | Super Admin can onboard hospitals |
| **Phase 3** | Add `tenant_id` to core tables; backfill current DB as Hospital #1 | Existing data becomes first tenant |
| **Phase 4** | Scope all services/queries (patients, OPD, IPD, pharmacy, lab, nurse) | Real isolation |
| **Phase 5** | Scope admin user/role management to hospital | Hospital admin cannot manage other hospitals |
| **Phase 6** | Audit `tenant_id` + Super Admin filters + QA cross-tenant tests | Production-ready multi-tenant RBAC |

---

## 13. Exists vs Need-to-Do Checklist

### Authentication

| Item | Exists | Need to do |
|------|--------|------------|
| Login with email/password | Yes | Add hospital context |
| JWT access token | Yes | Include `tenant_id` |
| Refresh token | Yes | Keep; optionally store/revoke per session later |
| Inactive user blocked | Yes | Also block inactive hospital |
| Logout | Basic | Optional server-side refresh invalidation |

### RBAC

| Item | Exists | Need to do |
|------|--------|------------|
| Permissions catalog | Yes | Keep; extend as modules grow |
| Roles seed | Yes | Decide global vs per-hospital roles |
| PermissionChecker on APIs | Yes | Keep |
| Multiple roles per user | No | Optional later (`user_roles`) |
| Hospital-scoped role edits | Partial / global | Restrict by hospital |

### Multi-tenant

| Item | Exists | Need to do |
|------|--------|------------|
| Hospitals table | No | Create |
| Users linked to hospital | No | Add FK |
| Domain data linked to hospital | No | Add FKs + backfill |
| Hospital registration | No | Build Super Admin API |
| Query isolation | No | Filter every service |
| Cross-tenant reject tests | No | Add QA suite |

### Audit

| Item | Exists | Need to do |
|------|--------|------------|
| Security / module audit events | Yes | Add hospital id |
| Super Admin audit UI | Yes | Optional filter by hospital |

---

## 14. Security Requirements (Must Follow)

1. Passwords stay hashed (already).  
2. Authorization is enforced on backend (already for permissions; add tenant).  
3. Frontend hiding buttons is **not** security.  
4. Client-sent hospital id is not enough for access.  
5. Cross-hospital access must be rejected.  
6. Inactive / deleted users cannot use protected APIs.  
7. Important admin actions stay auditable (login, role changes, hospital create, billing voids, etc.).  

---

## 15. Decisions to Finalize Before Coding

These match the Society RBAC doc’s open questions, rewritten for HMS:

1. Is staff email **globally unique** or unique **per hospital**?  
2. Can one user have **multiple roles**?  
3. Are roles **global**, **per hospital**, or **hybrid**?  
4. Are permissions always **global**? (Recommended: yes)  
5. Is Super Admin only a **platform** user (`tenant_id` null)? (Recommended: yes)  
6. Can Hospital Admin create **custom roles**?  
7. Can Hospital Admin create **new permission codes**? (Recommended: no — only assign existing)  
8. Keep current JWT + refresh strategy? (Recommended: yes, add hospital claim)  
9. Which account statuses are required? (`is_active` vs ACTIVE/INACTIVE/SUSPENDED)  
10. What happens when a hospital is **deactivated**? (block all hospital logins)  
11. Exact list of tables that get `tenant_id`  
12. Column name: `tenant_id` vs `hospital_id` (pick one and use everywhere)  
13. After migration, current production/demo DB = **Hospital #1** — confirm name/code  

---

## 16. Recommended Defaults for HMS (If Team Agrees Quickly)

These are **suggestions** to move fast; change if product says otherwise.

| Topic | Recommended default |
|-------|---------------------|
| Column name | `tenant_id` (same idea as Society doc) |
| Platform Super Admin | `users.tenant_id = NULL` |
| Permissions | Global catalog (keep current names) |
| Roles Phase 1 | Global role templates; assign only within hospital users |
| Roles Phase 2 | Optional per-hospital custom roles |
| Email Phase 1 | Keep globally unique (simplest with current schema) |
| Email Phase 2 | Per-hospital unique if doctors work at multiple hospitals |
| Multiple roles | Keep single `role_id` until needed |
| Resource deny style | Cross-tenant → **404** |
| Existing data | Backfill all rows to first hospital tenant |

---

## 17. Example End-to-End Stories

### Story A — New hospital

1. Platform Super Admin registers “CarePoint Mumbai”.  
2. System creates hospital + admin `admin@carepoint-mumbai.example`.  
3. Admin logs in, creates Doctor / OPD / Nurse users for Mumbai only.  
4. Mumbai OPD registers patients; they get Mumbai `tenant_id`.  

### Story B — Isolation

1. Doctor from Hospital A requests patient id that belongs to Hospital B.  
2. Permission may be `patients:view`, but tenant check fails.  
3. API returns 404.  

### Story C — Same permission, different hospital

1. Two OPD users both have `billing:create`.  
2. Each can create bills only for their own hospital’s patients.  

---

## 18. What Frontend Will Need Later (Not Implementing Here)

This document is backend-focused. When multi-tenant is built, frontend will need:

- Super Admin: Hospital list + Register Hospital screen  
- Login: optional hospital selector if Option B email is chosen  
- Store hospital info from login response (display only)  
- No reliance on sending `tenant_id` for authorization  

---

## 19. Relation to Existing Docs

| File | Role |
|------|------|
| `RBAC_Authentication_Authorization_Requirements.md` | Generic Society multi-tenant RBAC reference |
| **`HMS_RBAC_Multi_Tenant_Requirements.md` (this file)** | HMS-specific exists / need-to-do plan |
| `hms-backend/Docs/Documentation/00-HMS-Overview.md` | Current product overview (still describes single-hospital install) |
| `hms-backend/Docs/Documentation/01-Roles-and-Permissions.md` | Current role/permission catalog |

When multi-tenant ships, update the Overview doc from “one hospital install” to “multi-hospital platform”.

---

## 20. Summary

| Question | Answer |
|----------|--------|
| Do we have RBAC today? | **Yes** — roles, permissions, JWT, `PermissionChecker` |
| Do we have multi-hospital isolation today? | **No** |
| Biggest work? | `tenants` table + `tenant_id` on data + query scoping + hospital registration |
| Keep current permission system? | **Yes** — extend it, don’t replace it |
| Who creates hospitals? | **Platform Super Admin only** |
| Who runs one hospital day-to-day? | **Hospital Admin + clinical/billing roles** |

---

*End of document.*
