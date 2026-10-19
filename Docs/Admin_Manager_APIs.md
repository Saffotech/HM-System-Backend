# Admin and Manager APIs

Send the login token as `Authorization: Bearer <token>` on every call below.

Login is the same for both: `POST /auth/login` with `{ "email", "password" }`.  
The role in the response decides which menu to open.

| Role | Menu | Base path |
|---|---|---|
| `admin` | Hospital owner | `/admin` |
| `manager` | Operations | `/manager` |

Do not call the other role's paths.

## Admin (hospital owner)

| Screen | Call |
|---|---|
| Profile | `GET /admin/profile` |
| Save profile | `PUT /admin/profile` |
| Profile photo | `POST /admin/profile/image` |
| Remove photo | `DELETE /admin/profile/image` |
| Hospital details | `GET /admin/settings` |
| Save hospital details | `PATCH /admin/settings` |
| Audit list | `GET /admin/audit` |

Register a manager or clinical staff with `POST /auth/register`.  
The admin may assign role `manager`, `doctor`, `nurse`, `opd_billing`, `ipd`, `pharmacist`, `receptionist`, or `lab_technician`.

## Manager (operations)

| Screen | Call |
|---|---|
| Dashboard | `GET /manager/dashboard` |
| Profile | `GET /manager/profile` |
| Save profile | `PUT /manager/profile` |
| Profile photo | `POST /manager/profile/image` |
| Remove photo | `DELETE /manager/profile/image` |
| OPD settings | `GET /manager/settings/opd` |
| Save OPD settings | `PATCH /manager/settings/opd` |
| Reports | `GET /manager/reports/overview` and `GET /manager/reports/visits` |
| Notifications | `GET /manager/notifications` |
| Unread count | `GET /manager/notifications/unread-count` |
| Mark one read | `PATCH /manager/notifications/{id}/read` |
| Mark all read | `PATCH /manager/notifications/read-all` |
| Nurse shifts and roster | `/manager/nurse-workforce/...` |
| Bed allocation | `/manager/nurse-bed-allocations/...` |

Staff list and edits (same token):

| Action | Call |
|---|---|
| List | `GET /users` |
| One person | `GET /users/{id}` |
| Update | `PATCH /users/{id}` |
| Activate or deactivate | `PATCH /users/{id}/activate` |
| Delete | `DELETE /users/{id}` |
| Register | `POST /auth/register` |

A manager may assign only `doctor`, `nurse`, `opd_billing`, `ipd`, `pharmacist`, `receptionist`, or `lab_technician`.
