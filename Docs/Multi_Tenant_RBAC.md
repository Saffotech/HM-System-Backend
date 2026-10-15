# Multi-tenant RBAC (frontend)

One login belongs to one hospital. The frontend does not choose the hospital.

## Login

`POST /auth/login`

```json
{ "email": "...", "password": "..." }
```

Keep from the response:

| Field | Use |
|---|---|
| `access_token` | Send on every later call |
| `refresh_token` | `POST /auth/refresh` |
| `role` | Which hospital screens to open |
| `permissions` | Which buttons and calls are allowed |
| `user_id` | Signed-in user |
| `tenant_id` | This user's hospital. Required for hospital staff. |
| `hospital` | `{ id, name, code }`. Show this name in the shell. |

Header after login: `Authorization: Bearer <access_token>`

Do not send `tenant_id` on patients, staff, billing, or other hospital calls. The API reads it from the token and returns only that hospital's rows. New rows are stamped with the same hospital.

## What changed from single tenant

| Before | Now |
|---|---|
| One hospital for the whole app | Each staff user has one hospital |
| Login returned a user and a role | Login also returns `tenant_id` and `hospital` |
| Lists showed every record | Lists show only the logged-in hospital |
| No hospital check | Inactive hospital: login returns `403` `Hospital is inactive` |

## Rules for the UI

- `tenant_id` is null: this user is not hospital staff. Do not open the hospital app.
- Check `permissions` before showing an action. The role alone is not enough.
- `403` with `Permission denied` means the role cannot do that action.
- `401` means sign in again.
- On logout (`POST /auth/logout`), drop the token and any cached hospital data so the next user cannot see the previous hospital.
- `GET /auth/me` returns the same user, role, permissions, `tenant_id`, and `hospital` when the page reloads.
