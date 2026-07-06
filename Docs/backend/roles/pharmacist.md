# Pharmacist (`pharmacist`)

Pharmacist receives prescriptions from doctors and dispenses medicines.

**Start simple.** Inventory and suppliers come later.

---

## Phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | View prescriptions + dispense — below |
| **Phase 2** | Inventory, stock, suppliers — later section in this file |

---

## Permissions

**Current seed (fix when building):**

- Has `prescriptions:create` — **wrong** for pharmacist
- Doctor should **create** prescription
- Pharmacist should **view** and **dispense**

**Recommended in seed:**

```
prescriptions:view
prescriptions:dispense
patients:view
```

---

## Register pharmacist

**POST** `/auth/register`

| Field | Required |
|-------|----------|
| first_name, email, password, role_id | Yes |
| department_id | No |

**Profile (later):** pharmacy_license_no, qualification (B.Pharm)

---

## Phase 1 — Done / build these first

| What | Method | URL |
|------|--------|-----|
| Pending prescriptions | GET | `/pharmacy/prescriptions?status=pending` |
| Prescription detail | GET | `/pharmacy/prescriptions/{id}` |
| Dispense | POST | `/pharmacy/dispense/{prescription_id}` |
| Dispense history | GET | `/pharmacy/history` |

---

## Dispense (Word file View 4)

**POST** `/pharmacy/dispense/{prescription_id}`

| Field | Required |
|-------|----------|
| quantity_dispensed | Yes |
| remarks | No |
| batch_number | No (for MVP) |

Set status: `dispensed` or `partially_dispensed`.

`dispensed_by` = logged-in pharmacist.

---

## Table to create

### dispensings
```
id
prescription_id  → FK
dispensed_by     → user id
quantity_dispensed
remarks
status           → pending / partial / dispensed
dispensed_at
```

Uses **prescriptions** table from doctor module.

---

## Phase 2 — Later (inventory & stock)

Do **not** build until Phase 1 dispense flow works in UI:

- Medicine inventory
- Stock inward / outward
- Suppliers
- Purchase orders
- Expiry alerts

These need tables: `medicines`, `medicine_stock`, `suppliers`, etc.

### Frontend — Phase 2 (after Phase 1 UI)

| # | Screen | Notes |
|---|--------|--------|
| 1 | Pending prescriptions list | `GET /pharmacy/prescriptions?status=pending` |
| 2 | Prescription detail + dispense | `POST /pharmacy/dispense/{id}` |
| 3 | Dispense history | `GET /pharmacy/history` |

### Backend — Phase 2b (inventory)

See bullet list above (medicines, stock, suppliers, purchase orders, expiry alerts).

## What pharmacist can see

- Patient name, allergies (from patient record)
- Prescription items from doctor
- **Cannot** change diagnosis or create new prescription
