# Hospital Settings (`hospital_settings`)

**Super Admin feature:** [super-admin.md](./super-admin.md)  
**Permission:** `settings:manage`  
**API:** `GET/PATCH /super-admin/settings`  
**Status:** Phase 1 **implemented** — see Phase 2 below for OPD integration

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | DB table + GET/PATCH API + seed default row + audit on update |
| **Phase 2** | OPD invoice + default fees + logo (later) |

---

## What is it?

`hospital_settings` is **one configuration record for your hospital**.

This project is **one hospital per install** (not multi-hospital SaaS). There is no list of hospitals — only **a single row** in the database that stores:

- Hospital **name, address, contact**
- **Legal / tax** details (GSTIN, etc.)
- **Default OPD billing** values (registration fee, consultation fee, GST %)

Super Admin edits this from `/super-admin/settings`.  
Hospital Admin (`admin`) **cannot** view or change it.

---

## What it is NOT

| Not hospital settings | Where it lives |
|----------------------|----------------|
| Staff, roles, permissions | `users`, `roles` |
| Departments (Cardiology, etc.) | `departments` table |
| Patient records | `patients` |
| Each OPD bill’s actual fees | `opd_visits` (historical — never overwrite from settings) |
| Audit history | `audit_logs` |
| Multi-hospital / tenant config | Out of scope |

**Rule:** Settings = **profile + defaults**. Transaction data stays on visits/bills.

---

## Why we need it

Today the bill/invoice builder uses a **hardcoded** hospital name in OPD code:

```
"hospital": { "name": "CarePoint Hospital", "address": "", "gstin": "" }
```

After settings is built, bills and printouts should read **name, address, GSTIN** from `hospital_settings` instead.

OPD staff can also **pre-fill** default fees when registering or billing a patient (settings are defaults only; each visit still stores its own fees).

---

## Who can access

| Role | Read settings | Update settings |
|------|:-------------:|:---------------:|
| `super_admin` | Yes | Yes |
| `admin` | No | No |
| Clinical roles (doctor, nurse, OPD, etc.) | No* | No |

\* Later, OPD may **read** name/address/GSTIN internally for invoices — not a settings admin screen.

**Permission in seed:** `settings:manage` (Super Admin gets it via `__all__`).

---

## Database design (planned)

**Table:** `hospital_settings`  
**Rows:** Always **one** row (`id = 1`). Created by `seed.py` if missing.

### Phase 1 fields (implement first)

#### Hospital identity

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `name` | string | City Care Hospital | Bills, reports, UI |
| `tagline` | string, optional | Your health, our priority | Subtitle |
| `address_line1` | string | 12 MG Road | Letterhead / bill |
| `address_line2` | string, optional | Near City Mall | |
| `city` | string | Pune | |
| `state` | string | Maharashtra | |
| `pincode` | string | 411001 | |
| `phone` | string | +91 9876543210 | Contact on bill |
| `email` | string | info@citycare.com | |
| `website` | string, optional | https://citycare.com | |

#### Legal / tax

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `gstin` | string, optional | 27AAAAA0000A1Z5 | GST on bills |
| `pan` | string, optional | AAAAA0000A | Invoice / compliance |
| `registration_number` | string, optional | State reg. no. | Optional license id |

#### OPD billing defaults

These are **defaults for new bills** — not retroactive changes to old visits.

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `default_registration_fee` | float | 100.00 | Pre-fill OPD register/bill |
| `default_consultation_fee` | float | 500.00 | Pre-fill |
| `default_gst_percent` | float | 0 or 18 | Pre-fill GST |
| `currency` | string | INR | Display |

#### System meta

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `timezone` | string | Asia/Kolkata | App timezone |
| `updated_at` | datetime | auto | Last save time |
| `updated_by` | int FK → users | null | Who last saved |

### Phase 2 (later — not in first build)

| Field | Why later |
|-------|-----------|
| `logo_url` | Needs file upload / storage |
| `receipt_footer_text` | Print customization |
| `bill_number_prefix` | Bill numbering rules |
| `maintenance_mode` | Whole-app lock |
| SMS / email toggles | External integrations |

---

## Phase 1 — Done (API)

### `GET /super-admin/settings`

- **Auth:** Bearer token  
- **Permission:** `settings:manage`  
- **Returns:** The single hospital settings object (see JSON below)

### `PATCH /super-admin/settings`

- **Auth:** Bearer token  
- **Permission:** `settings:manage`  
- **Body:** Partial update — only send fields that change  
- **Side effects:** Write `audit_logs` entry with action `settings.update`

Hospital Admin must get **403** on both endpoints.

---

## Example response

```json
{
  "name": "City Care Hospital",
  "tagline": "",
  "address_line1": "12 MG Road",
  "address_line2": "",
  "city": "Pune",
  "state": "Maharashtra",
  "pincode": "411001",
  "phone": "+91 9876543210",
  "email": "info@citycare.com",
  "website": "",
  "gstin": "27AAAAA0000A1Z5",
  "pan": "",
  "registration_number": "",
  "default_registration_fee": 100,
  "default_consultation_fee": 500,
  "default_gst_percent": 0,
  "currency": "INR",
  "timezone": "Asia/Kolkata",
  "updated_at": "2026-06-17T10:00:00+05:30",
  "updated_by": 1
}
```

---

## Example PATCH body

```json
{
  "name": "City Care Hospital",
  "gstin": "27AAAAA0000A1Z5",
  "default_registration_fee": 150,
  "default_consultation_fee": 600
}
```

---

## Phase 1 — Done (backend files)

| File | Purpose | Status |
|------|---------|--------|
| `Models/hospital_settings.py` | SQLAlchemy model | ✅ Done |
| `alembic/versions/d2e3f4a5b6c7_add_hospital_settings.py` | Migration | ✅ Done |
| `Schemas/hospital_settings_schema.py` | Pydantic GET/PATCH schemas | ✅ Done |
| `Services/hospital_settings_service.py` | get + update logic | ✅ Done |
| `Routers/super_admin_router.py` | GET/PATCH routes | ✅ Done |
| `seed.py` | Insert default row if table empty | ✅ Done |

**Audit:** On PATCH, call `audit_service.log_event(..., action="settings.update", ...)`.

**Do not duplicate:** No second settings table, no `/admin/settings` route.

---

## How other modules will use it (after build)

| Module | Usage |
|--------|--------|
| OPD `build_invoice()` | Replace hardcoded `"CarePoint Hospital"` with settings `name`, address, `gstin` |
| OPD register / bill UI (frontend) | Pre-fill `default_registration_fee`, `default_consultation_fee`, `default_gst_percent` |
| Reports / PDF headers | Hospital name and address |

Settings API can ship **before** OPD is wired — Super Admin screen can work first; bill header update is a small follow-up.

---

## Implementation order (Phase 1 — complete)

```
1. Model + migration + seed default row          ✅
2. GET /super-admin/settings                     ✅
3. PATCH /super-admin/settings + audit log       ✅
4. (Later) OPD build_invoice reads from settings → Phase 2
5. (Later) Frontend /super-admin/settings form   → Phase 2
```

---

## Phase 2 — Planned

| # | Feature | Owner | Notes |
|---|---------|-------|--------|
| 1 | OPD invoice header from settings | Backend | `build_invoice()` reads `name`, address, `gstin` |
| 2 | OPD default fees endpoint | Backend | Read-only `GET /opd/billing-defaults` for OPD staff |
| 3 | Register/bill form pre-fill | Frontend | Use default fees from settings |
| 4 | Super Admin settings screen | Frontend | `GET/PATCH /super-admin/settings` |
| 5 | Logo upload | Backend + Frontend | `logo_url` field — Phase 2b |
| 6 | Receipt footer text | Backend | Optional print customization |

See also: [opd-billing.md](./opd-billing.md) Phase 2 (items 1–2 overlap).

---

## Related

- Super Admin panel: [super-admin.md](./super-admin.md)
- Hospital Admin (no settings access): [admin.md](./admin.md)
- Audit log (logs settings changes): `GET /super-admin/audit`
