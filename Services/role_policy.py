"""Who may assign which roles when registering or updating staff."""

from fastapi import HTTPException

from Models.user import User

MANAGER_REGISTERABLE_ROLES = frozenset({
    "doctor",
    "nurse",
    "opd_billing",
    "ipd",
    "pharmacist",
    "receptionist",
    "lab_technician",
})


def caller_role_name(user: User) -> str:
    return user.role_obj.name if user.role_obj else ""


def assert_can_assign_role(caller_role: str, target_role_name: str) -> None:
    if caller_role == "admin":
        if target_role_name == "manager" or target_role_name in MANAGER_REGISTERABLE_ROLES:
            return
        raise HTTPException(
            status_code=403,
            detail=f"Admin cannot assign role '{target_role_name}'",
        )

    if caller_role == "manager":
        if target_role_name in MANAGER_REGISTERABLE_ROLES:
            return
        raise HTTPException(
            status_code=403,
            detail=f"Manager cannot assign role '{target_role_name}'",
        )

    raise HTTPException(status_code=403, detail="Not allowed to register staff")
