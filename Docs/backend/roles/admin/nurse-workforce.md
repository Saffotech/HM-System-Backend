# Nurse Workforce Management

Additive Admin module for shifts, roster, and workforce dashboard KPIs.

## Prefix
`/admin/nurse-workforce`

## Permissions
- `workforce:view|create|update|delete`
- `roster:manage`

Assigned to Admin / Super Admin (`__all__` + ADMIN_PERMISSIONS list).

## Tables
- `nurse_workforce_shifts`
- `nurse_workforce_rosters`

Migration: `n7o8p9q0r1s2_create_nurse_workforce_tables.py`

## Key behaviours
- Dashboard reports on-duty / off-duty nurses from roster plus bed assignment counts.
- Notifications reuse `create_notification` (`SHIFT_UPDATED` / `ADMIN_UPDATE`).

## Frontend
`/admin/nurse-workforce` and sub-routes: shifts, roster.
