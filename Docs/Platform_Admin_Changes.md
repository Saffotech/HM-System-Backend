# Platform Admin changes

Base URL: `http://127.0.0.1:8000`

Send `Authorization: Bearer <access_token>` on every call. The signed-in role must be `platform_admin` with `tenant_id` null.

`401` means sign in again. `403` means this role cannot call that API. `422` means a field is invalid. Extra fields on an update are rejected.

## Staff directory

`GET /platform/staff`

Call this when the staff page opens or after a successful create, so the list survives a refresh. It returns CRM and accountant accounts only. It does not return the platform admin or hospital staff, and it does not return passwords.

Each row: `user_id`, `first_name`, `last_name`, `email`, `role` (`crm` or `accountant`), `tenant_id` (null), `is_active`.

Create is still `POST /platform/staff`.

## Hospital edit

`PATCH /tenants/{tenant_id}`

Permission: `hospitals:create`.

Send only the fields that changed. Allowed fields:

| Field | Rule |
|---|---|
| `name`, `address`, `phone` | Required text if sent |
| `plan` | `Starter`, `Professional`, or `Enterprise` |
| `billing_cycle` | `Monthly` or `Annual` |
| `subscription_renews_on` | `YYYY-MM-DD`, year from 2000 through five years ahead |
| `subscription_amount` | Whole rupees, 1 to 10000000 |

If `plan` or `billing_cycle` changes and `subscription_amount` is omitted, the server sets the amount from the current catalog. That amount is what future invoices use. Already issued invoices stay as they were.

The response is the same hospital summary as `GET /tenants/{tenant_id}`, including `subscription_amount`.

Suspend and activate stay on `PATCH /tenants/{tenant_id}/active` with `{ "is_active": true }` or `false`.

## Plans

`GET /platform/plans`

Use this for the plan screen and for plan dropdowns. Each row: `name`, `monthly_price`, `annual_price`, `billing_cycles` (`Monthly`, `Annual`), `is_active`.

Annual price is monthly × 10. Changing a catalog price later does not rewrite old invoices or a hospital that already has `subscription_amount`.

## Revenue

`GET /platform/revenue`

Company-wide subscription invoices. Failed invoices are counted, not added into the money.

| Field | Meaning |
|---|---|
| `collected_amount`, `collected_count` | Paid |
| `pending_amount`, `pending_count` | Pending and not past due |
| `overdue_amount`, `overdue_count` | Pending and past due |
| `outstanding_amount` | Pending + overdue |
| `failed_count` | Failed |
| `invoice_count` | All of the above |

## CRM analytics

`GET /platform/crm/analytics`

Company-wide lead counts. Does not replace `GET /crm/leads`.

```json
{
  "statuses": {
    "New": 0,
    "Contacted": 0,
    "Agreed": 0,
    "Registered": 0,
    "Not Interested": 0,
    "total": 0
  }
}
```

A status with no leads is `0`.

## Platform admin profile

These are the platform admin's own account. Do not call `/admin/profile` for this login. That path is the hospital admin.

| Action | Call |
|---|---|
| Load | `GET /platform/admin/profile` |
| Save phone, address, job title | `PATCH /platform/admin/profile` |
| Change password | `POST /platform/admin/password` |
| Upload photo | `POST /platform/admin/profile/photo` |
| Remove photo | `DELETE /platform/admin/profile/photo` |

Profile body fields, all optional: `phone`, `phone_code`, `address`, `city`, `state`, `postal_code`, `job_title`. Do not send `email`, `role`, or `permissions`.

Password body:

```json
{ "current_password": "...", "new_password": "Secret123" }
```

The new password needs at least 8 characters, one letter, and one number, and must differ from the current password. On success the old token stops working. Sign in again.

Photo is `multipart/form-data`, field name `file`. JPG, JPEG, PNG, or WEBP, max 5 MB. The profile response includes `profile_image_url`. The same URL is on `GET /auth/me` after the next load.
