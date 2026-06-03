from datetime import date
from sqlalchemy.orm import Session
from Models.doctor_patient_queue import PatientQueue


# ==========================================================
# Nurse Today's Queue
# ==========================================================

def get_nurse_today_queue_service(
    db: Session
):

    queue = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.queue_date == date.today()
        )
        .order_by(
            PatientQueue.priority.desc(),
            PatientQueue.token_number.asc()
        )
        .all()
    )

    return queue