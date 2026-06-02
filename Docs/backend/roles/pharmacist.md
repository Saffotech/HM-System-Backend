# Pharmacist (`pharmacist`)

Pharmacist receives prescriptions from doctors and dispenses medicines.

**Start simple.** Inventory and suppliers come later.

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

## Phase 1 — Build these first

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

## Phase 2 — Later (Word file Views 5–12)

Do **not** build until Phase 1 works:

- Medicine inventory
- Stock inward / outward
- Suppliers
- Purchase orders
- Expiry alerts

These need tables: `medicines`, `medicine_stock`, `suppliers`, etc.

---

## What pharmacist can see

- Patient name, allergies (from patient record)
- Prescription items from doctor
- **Cannot** change diagnosis or create new prescription
