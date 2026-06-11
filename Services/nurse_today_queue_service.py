from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue


# ==========================================================
# NURSE TODAY'S QUEUE
# ==========================================================

def get_nurse_today_queue_service(
    db: Session,

    search: str | None = None,

    status: str | None = None,
    doctor_id: int | None = None,
    priority: str | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.queue_date == date.today()
        )
    )

    # ======================================================
    # SEARCH
    # ======================================================

    if search:

        search_filters = [

            PatientQueue.patient_name.ilike(
                f"%{search}%"
            ),

            PatientQueue.patient_uhid.ilike(
                f"%{search}%"
            ),

            PatientQueue.patient_phone.ilike(
                f"%{search}%"
            ),

            PatientQueue.appointment_uid.ilike(
                f"%{search}%"
            )
        ]

        if search.isdigit():

            search_filters.append(
                PatientQueue.token_number == int(search)
            )

            search_filters.append(
                PatientQueue.patient_id == int(search)
            )

        query = query.filter(
            or_(*search_filters)
        )

    # ======================================================
    # FILTERS
    # ======================================================

    if status:
        query = query.filter(
            PatientQueue.status == status
        )

    if doctor_id:
        query = query.filter(
            PatientQueue.doctor_id == doctor_id
        )

    if priority:
        query = query.filter(
            PatientQueue.priority == priority
        )

    # ======================================================
    # TOTAL COUNT
    # ======================================================

    total = query.count()

    # ======================================================
    # SORTING
    # ======================================================

    items = (
        query
        .order_by(
            PatientQueue.priority.desc(),
            PatientQueue.token_number.asc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }