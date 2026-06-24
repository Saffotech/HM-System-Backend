# Super Admin (`super_admin`)

**Status:** Not built — industry-level plan for later.

Platform owner role — sits **above** [Hospital Admin](./admin.md).

| Item | Planned value |
|------|----------------|
| Role name (DB) | `super_admin` |
| Frontend route | `/super-admin/` |
| Scope | All hospitals / whole platform |
| Tenant model | One `hospitals` row = one hospital |

---

## Admin vs Super Admin

| | Hospital Admin (`admin`) | Super Admin (`super_admin`) |
|--|--------------------------|-----------------------------|
| Manages | Staff inside **one** hospital | **All hospitals** on the platform |
| Creates doctors/nurses | Yes | No (hospital admin does) |
| Creates hospitals | No | Yes |
| System settings | Hospital-level (later) | Platform-level |
| Clinical work | No | No |
| Your project | Phase 1 ready | Not started |

---

## Industry-level modules (what Super Admin typically has)

### 1. Hospital / tenant management

Onboard and manage each hospital on the platform.

| Feature | Purpose |
|---------|---------|
| List hospitals | All tenants with status (active/suspended/trial) |
| Create hospital | Name, code, address, timezone, contact |
| Edit hospital | Update details, logo, branding |
| Suspend / activate hospital | Block access without deleting data |
| Hospital subscription plan | Basic / Pro / Enterprise |
| Assign first hospital admin | Auto-create `admin` user for that hospital |

**Planned APIs:**
```
GET    /super-admin/hospitals
POST   /super-admin/hospitals
GET    /super-admin/hospitals/{id}
PATCH  /super-admin/hospitals/{id}
PATCH  /super-admin/hospitals/{id}/suspend
POST   /super-admin/hospitals/{id}/admin   → create hospital admin
```

**Permission:** `hospitals:view`, `hospitals:create`, `hospitals:update`, `hospitals:suspend`

---

### 2. Platform dashboard

God-view metrics across all hospitals.

| Metric | Example |
|--------|---------|
| Total hospitals | 24 active, 3 trial |
| Total users (all roles) | 1,240 |
| Total patients (platform) | 85,000 |
| Visits today (all hospitals) | 320 |
| Revenue today (if billing module) | platform total |
| System health | API up, DB ok |

**Planned API:**
```
GET /super-admin/dashboard
```

**Permission:** `system:manage` or `global_reports:view`

---

### 3. Global user oversight

Super admin does **not** replace hospital admin for daily staff CRUD, but can:

| Feature | Purpose |
|---------|---------|
| Search users across hospitals | Support / compliance |
| Force deactivate user | Security incident |
| Reset locked account | Help desk |
| View login history | Audit |

**Planned APIs:**
```
GET   /super-admin/users?hospital_id=&search=
PATCH /super-admin/users/{id}/force-deactivate
GET   /super-admin/users/{id}/audit
```

**Permission:** `global_users:manage`, `audit:view`

---

### 4. Roles & permissions (platform level)

| Feature | Purpose |
|---------|---------|
| Define global permission catalog | Same list for all hospitals |
| Create custom roles (optional) | Per-tenant role templates |
| Feature modules per hospital | Enable/disable OPD, pharmacy, lab per hospital |

**Planned APIs:**
```
GET   /super-admin/permissions
GET   /super-admin/hospitals/{id}/modules
PATCH /super-admin/hospitals/{id}/modules
```

Example modules: `opd`, `ipd`, `pharmacy`, `lab`, `nurse`, `billing`

**Permission:** `system:manage`, `tenants:configure`

---

### 5. Subscription & billing (SaaS)

If you sell HMS as software to many hospitals:

| Feature | Purpose |
|---------|---------|
| Plans | Free trial, monthly, yearly |
| Hospital subscription | Start/end date, plan |
| Invoices | Platform bills hospitals |
| Usage limits | Max users, max patients per plan |

**Planned APIs:**
```
GET  /super-admin/plans
POST /super-admin/hospitals/{id}/subscription
GET  /super-admin/billing/invoices
```

**Permission:** `billing:platform:manage`

---

### 6. Platform settings

| Setting | Example |
|---------|---------|
| App name | HMS Cloud |
| Default timezone | Asia/Kolkata |
| Password policy | min length, expiry |
| Session timeout | 30 min |
| Email/SMS provider | SMTP, Twilio keys (encrypted) |
| Maintenance mode | Block all hospitals |

**Planned APIs:**
```
GET   /super-admin/settings
PATCH /super-admin/settings
POST  /super-admin/maintenance  { "enabled": true, "message": "..." }
```

**Permission:** `system:settings`

---

### 7. Audit log & compliance

Industry requirement for healthcare systems.

| Event logged | Detail |
|--------------|--------|
| User login/logout | who, when, hospital |
| Role/permission change | |
| Patient data export | |
| Super admin actions | |
| Failed login attempts | |

**Planned APIs:**
```
GET /super-admin/audit?hospital_id=&from=&to=&action=
GET /super-admin/audit/export
```

**Permission:** `audit:view`, `audit:export`

---

### 8. Global reports & analytics

| Report | Audience |
|--------|----------|
| Hospitals by region | Super admin |
| Active users per hospital | Super admin |
| OPD volume trend (platform) | Super admin |
| Module adoption | Which hospitals use pharmacy |

**Planned APIs:**
```
GET /super-admin/reports/overview
GET /super-admin/reports/hospitals/{id}/summary
```

**Permission:** `global_reports:view`

---

### 9. Data & operations

| Feature | Purpose |
|---------|---------|
| Backup status | Last backup per hospital |
| Data export | Hospital requests full export (GDPR) |
| Data retention policy | Auto-archive old visits |
| Impersonate hospital admin | Support only (with audit) |

**Planned APIs:**
```
POST /super-admin/hospitals/{id}/export
GET  /super-admin/operations/backups
POST /super-admin/support/impersonate/{user_id}
```

**Permission:** `data:export`, `support:impersonate`

---

### 10. Security & access control

| Feature | Purpose |
|---------|---------|
| IP allowlist (super admin) | Extra protection |
| 2FA for super admin | Industry standard |
| API keys for integrations | Per hospital |
| Rate limiting config | Platform-wide |

**Permission:** `security:manage`

---

## Database changes needed (multi-tenant)

Before most Super Admin features work:

```
hospitals
  id, name, code, status, plan_id, created_at, ...

users
  + hospital_id   (null for super_admin only)

patients, opd_visits, ...
  + hospital_id   (every row scoped to one hospital)
```

Super admin users: `hospital_id = NULL`, role = `super_admin`.

Hospital admin users: `hospital_id = 5`, role = `admin`.

All hospital APIs filter by `hospital_id` from JWT.

---

## Permissions to add in seed.py (planned)

```
hospitals:view, hospitals:create, hospitals:update, hospitals:suspend, hospitals:delete
tenants:manage, tenants:configure
system:manage, system:settings
global_users:manage
global_reports:view
audit:view, audit:export
billing:platform:manage
data:export
security:manage
support:impersonate
```

Role:
```python
"super_admin": {
    "description": "Platform super administrator",
    "permissions": "__all__"   # or explicit list above only
}
```

Narrow hospital `admin` — remove `__all__`, hospital-scoped permissions only.

---

## Super Admin screens (frontend plan)

| # | Screen | Route |
|---|--------|-------|
| 1 | Platform dashboard | `/super-admin/dashboard` |
| 2 | Hospitals list | `/super-admin/hospitals` |
| 3 | Create hospital | `/super-admin/hospitals/new` |
| 4 | Hospital detail | `/super-admin/hospitals/:id` |
| 5 | Subscriptions | `/super-admin/subscriptions` |
| 6 | Global users | `/super-admin/users` |
| 7 | Audit log | `/super-admin/audit` |
| 8 | Platform settings | `/super-admin/settings` |
| 9 | Global reports | `/super-admin/reports` |

---

## Recommended build order

| Phase | What | Why first |
|-------|------|-----------|
| A | `hospitals` table + `hospital_id` on users | Foundation |
| B | `super_admin` role + login | Access |
| C | `GET/POST /super-admin/hospitals` | Core value |
| D | Assign hospital admin on create | Hospitals can run alone |
| E | Platform dashboard | Visibility |
| F | Audit log | Trust & compliance |
| G | Settings, reports, billing | SaaS maturity |

---

## Out of scope for Super Admin UI

- OPD counter, nurse station, doctor queue (hospital roles)
- Day-to-day staff management inside a hospital (hospital `admin`)

---

## Related

- Hospital Admin (built): [admin.md](./admin.md)
- Frontend (later): `Docs/frontend/roles/super-admin.md`
