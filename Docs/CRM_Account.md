# CRM account

Base URL: `http://127.0.0.1:8000`

Send `Authorization: Bearer <access_token>` on every call. The signed-in role must be `crm` with `tenant_id` null.

`401` means sign in again. `403` means this role cannot call that API. `422` means a field is invalid. Extra fields on an update are rejected.

Lead work is unchanged: keep using `/crm/leads`.

## Attributed revenue

`GET /crm/revenue`

Permission: `leads:manage`.

Paid subscription invoices for hospitals registered from this CRM user's own leads. Another CRM user's hospitals are not included. Pending invoices are not included in the money.

| Field | Meaning |
|---|---|
| `collected_amount` | Sum of paid invoices |
| `collected_count` | Number of paid invoices |
| `hospitals` | One row per hospital: `tenant_id`, `hospital_name`, `plan`, `paid_amount`, `paid_count` |
| `months` | Last 6 months, oldest first: `year`, `month`, `amount` by invoice date |

A month with no payments is `amount: 0`. If this user has no registered hospitals, `hospitals` is empty and every month is `0`.

Use `collected_amount` on the dashboard. Use `hospitals` for the per-hospital revenue table. Use `months` for the performance chart.

## CRM profile

| Action | Call |
|---|---|
| Load | `GET /crm/account/profile` |
| Save phone, address, job title | `PATCH /crm/account/profile` |
| Change password | `POST /crm/account/password` |
| Upload photo | `POST /crm/account/profile/photo` |
| Remove photo | `DELETE /crm/account/profile/photo` |

Profile permissions: `crm_profile:view`, `crm_profile:update`, `crm_profile:upload_image`, `crm_profile:delete_image`.

Profile body fields, all optional: `phone`, `phone_code`, `address`, `city`, `state`, `postal_code`, `job_title`. Do not send `email`, `role`, or `permissions`.

The response includes `user_id`, `first_name`, `last_name`, `email`, `role`, the address fields, `job_title`, `profile_image_url`, `is_active`, and `created_at`. Email is returned so the form can show it, and it cannot be changed here.

Password body:

```json
{ "current_password": "...", "new_password": "Secret123" }
```

The new password needs at least 8 characters, one letter, and one number, and must differ from the current password. On success the old token stops working. Sign in again.

Photo is `multipart/form-data`, field name `file`. JPG, JPEG, PNG, or WEBP, max 5 MB. `DELETE` returns `404` when there is no photo. After upload or delete, `profile_image_url` is also on `GET /auth/me`.
