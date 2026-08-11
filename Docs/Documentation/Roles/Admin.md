# Role: Hospital Admin (`admin`)

**Display name:** Hospital Admin / Operations Manager  
**PPT slides:** 1

---

## Purpose

Hospital manager tools for **staff**, **dashboard**, **view roles**, and **view reports**.  
Not a clinical role.

---

## Main tools

| Tool | What admin does |
|------|-----------------|
| Admin dashboard | Operational overview |
| Staff list / detail | Manage hospital users |
| Register staff | Create doctor, nurse, OPD, pharmacist, etc. |
| Activate / update / delete staff | HR operations |
| View roles | Read-only role list |
| View reports | When reports are available |

---

## Allowed vs not allowed

| Feature | Admin? |
|---------|:------:|
| Staff CRUD (clinical roles) | Yes |
| View roles | Yes |
| View reports | Yes |
| Create Admin / Super Admin | No |
| Create roles / assign permissions | No |
| Hospital settings | No |
| Audit log | No |

Those restricted items belong to **Super Admin**.

---

## Typical flow for PPT

1. Login to Admin panel  
2. Register new staff with correct role  
3. Activate / deactivate users  
4. Review dashboard / reports  

---

## Permissions (summary)

`users:list/create/activate/delete`, `roles:view`, `reports:view`  
(Seed may grant broader `admin` access in some installs — product intent is staff-focused.)
