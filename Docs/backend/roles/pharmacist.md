Tables:

Product
Category
Unit# Pharmacist (`pharmacist`)

Pharmacist receives prescriptions from doctors and dispenses medicines.

**Start simple.** Inventory and suppliers come later.

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | View prescriptions, dispense medicines, dispense history — documented below |
| **Phase 2** | Pagination, inventory, pharmacist profile, frontend polish — end of this file |

---

## Permissions

**In seed (`pharmacist` role):**

```
patients:view
prescriptions:view
prescriptions:dispense
```

| Permission | Feature |
|------------|---------|
| `patients:view` | Patient name, allergies on prescription detail |
| `prescriptions:view` | List/detail prescriptions, dispense history |
| `prescriptions:dispense` | `POST /pharmacy/dispense/{id}` |

Doctor creates prescriptions; pharmacist **views** and **dispenses** only.

---

## Register pharmacist

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password, role_id | Yes |
| department_id | No |

**Profile (later):** pharmacy_license_no, qualification (B.Pharm)

---

## Phase 1 — Done (backend)

| What | Method | URL | Status |
|------|--------|-----|--------|
| List prescriptions | GET | `/pharmacy/prescriptions?status=pending&search=` | ✅ Done |
| Prescription detail | GET | `/pharmacy/prescriptions/{id}` | ✅ Done |
| Dispense (item-level) | POST | `/pharmacy/dispense/{prescription_id}` | ✅ Done |
| Dispense history | GET | `/pharmacy/history?page=1&limit=20` | ✅ Done |

**Status values:** `pending`, `partially_dispensed`, `dispensed`

**Tables:** `prescriptions`, `prescription_items` (doctor module), `dispensings`, `dispensing_items`

> **Note:** Prescribed quantity currently uses `duration` on each item until a dedicated `quantity_prescribed` column exists (Phase 2).

---

## Dispense (item-level)

**POST** `/pharmacy/dispense/{prescription_id}`

**Permission:** `prescriptions:dispense`

**Body:**

```json
{
  "items": [
    { "prescription_item_id": 1, "quantity_dispensed": 5 }
  ],
  "remarks": "After food",
  "batch_number": "BATCH-001"
}
```

| Field | Required |
|-------|----------|
| `items` | Yes — one row per medicine line |
| `items[].prescription_item_id` | Yes |
| `items[].quantity_dispensed` | Yes — must not exceed remaining qty |
| `remarks` | No |
| `batch_number` | No (header-level for MVP) |

Sets prescription status: `partially_dispensed` or `dispensed`.  
`dispensed_by` = logged-in pharmacist.

---

## Tables (Phase 1)

### dispensings + dispensing_items

```
dispensings
  id, prescription_id, dispensed_by, quantity_dispensed,
  remarks, batch_number, status, dispensed_at

dispensing_items
  id, dispensing_id, prescription_item_id, quantity_dispensed
```

Uses **prescriptions** + **prescription_items** from [doctor.md](./doctor.md).

---

## What pharmacist can see

- Patient name, phone, allergies (from patient record)
- Prescription items from doctor (read-only)
- Dispensed vs remaining quantity per line
- **Cannot** change diagnosis or create a new prescription

---

## Phase 2 — Planned

Work **after** Phase 1 dispense flow is stable in Postman and UI. Phase 1 APIs stay; Phase 2 adds polish, inventory, and integrations.

### Backend — Phase 2

| # | Feature | API / area | Why |
|---|---------|------------|-----|
| 1 | **Prescriptions list pagination** | `GET /pharmacy/prescriptions` | Add `page`, `limit`; today loads all rows |
| 2 | **Dedicated prescribed quantity** | `prescription_items` column | Replace `duration` → quantity hack in `pharmacy_service` |
| 3 | **Pharmacist profile** | User profile or `pharmacist_profiles` | `pharmacy_license_no`, `qualification` (B.Pharm) |
| 4 | **Dispense receipt** | `GET /pharmacy/dispense/{id}/receipt` | Print slip with patient, items, pharmacist |
| 5 | **Hospital name on receipt** | Read `hospital_settings` | Same pattern as OPD invoice — [hospital-settings.md](./hospital-settings.md) |
| 6 | **Audit log on dispense** | `audit_service.log_event` | `pharmacy.dispense` in Super Admin audit |
| 7 | **Medicine master** | `GET/POST/PATCH /pharmacy/medicines` | Catalog: name, SKU, unit, reorder level |
| 8 | **Stock inward / outward** | `/pharmacy/stock/...` | Receive stock, adjust qty, link batch + expiry |
| 9 | **Suppliers** | `/pharmacy/suppliers` | Supplier name, contact, GST |
| 10 | **Purchase orders** | `/pharmacy/purchase-orders` | Order from supplier → stock inward |
| 11 | **Low stock + expiry alerts** | `GET /pharmacy/alerts` | Dashboard warnings before dispense |
| 12 | **Stock check on dispense** | `POST /pharmacy/dispense/{id}` | Block dispense if out of stock (after inventory exists) |
| 13 | **Pharmacy dashboard** | `GET /pharmacy/dashboard` | Pending count, dispensed today, low-stock count |
| 14 | **Tests** | `tests/` | Dispense partial/full, quantity validation, history pagination |
| 15 | **Expand Phase 1 doc** | This file | Keep API tables aligned with code |

### Frontend — Phase 2 (separate developer)

| Screen | Change |
|--------|--------|
| Prescription list | Status tabs (`pending` / `partially_dispensed` / `dispensed`) + search → `GET /pharmacy/prescriptions` |
| Prescription detail | Show allergies banner, item remaining qty |
| Dispense page | Item-level qty inputs → `POST /pharmacy/dispense/{id}` |
| Dispense history | Wire `page`/`limit` → `GET /pharmacy/history` (backend ready) |
| Print receipt | Dispense slip after successful dispense |
| Inventory (later) | Medicines, stock, suppliers UI after backend Phase 2b |

### Phase 2 — Out of scope

- Pharmacist creating or editing prescriptions (doctor only)
- Changing diagnosis or clinical notes
- Multi-warehouse / multi-branch pharmacy
- Full accounting / GST billing for medicine sales (OPD billing is separate)
- Inventory before Phase 1 dispense UI is verified

### Phase 2 — Suggested order

```
1. Frontend wire Phase 1 screens (list, detail, dispense, history)
2. Backend: prescriptions pagination + quantity_prescribed column
3. Dispense receipt + hospital_settings on print
4. Audit log on dispense
5. Medicine master + stock inward (inventory MVP)
6. Suppliers + purchase orders + alerts
7. Stock check integrated into dispense
8. Tests + doc sync
```

### Related Phase 2 docs

- Doctor prescriptions: [doctor.md](./doctor.md)
- Hospital settings (receipt header): [hospital-settings.md](./hospital-settings.md)
- OPD billing (patient bills — separate): [opd-billing.md](./opd-billing.md)
