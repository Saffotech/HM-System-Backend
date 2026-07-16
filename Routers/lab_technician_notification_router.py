"""Lab technician notification APIs."""

from fastapi import APIRouter

from Routers.doctor_notification_router import register_notification_routes

router = APIRouter(
    prefix="/lab/notifications",
    tags=["Lab Technician Notifications"],
)

register_notification_routes(router)
