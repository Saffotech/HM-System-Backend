# HMS — Manager Presentation Documentation

This folder is a **manager / PPT-ready** pack. It explains the Hospital Management System **role by role**, without deep API detail.

**Developer technical docs** remain under `Docs/backend/` and `Docs/frontend/`. Do not mix the two.

---

## How to use for PPT

1. Start with **00-HMS-Overview** (intro slides).
2. Use **01-Roles-and-Permissions** (who can do what).
3. Use **02-End-to-End-Patient-Journey** (story flow slide).
4. Add **1–2 slides per role** from `Roles/`.

Each role file is short (about 1–2 pages) so your manager can copy bullets into PowerPoint.

---

## Files

| File | PPT use |
|------|---------|
| [00-HMS-Overview.md](./00-HMS-Overview.md) | Title + system overview |
| [01-Roles-and-Permissions.md](./01-Roles-and-Permissions.md) | Roles matrix |
| [02-End-to-End-Patient-Journey.md](./02-End-to-End-Patient-Journey.md) | Patient journey |
| [Roles/](./Roles/) | One file per role |
| Same names as `.docx` | Open in Microsoft Word for copy/paste into PPT |

---

## Suggested PPT slide order

1. HMS overview  
2. Roles overview  
3. Patient journey  
4. OPD Billing  
5. Receptionist  
6. Doctor  
7. Nurse  
8. Pharmacist + Lab Technician  
9. Admin / Super Admin  
10. Appointment & queue statuses  
11. What’s live vs planned (optional)

---

## Regenerate Word files

From `hms-backend`:

```bash
python Docs/Documentation/generate_word_pack.py
```

Requires `python-docx` in the active virtual environment.
