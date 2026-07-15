from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base


from Models.role import Role, Permission, RolePermission
from Models.user import User
from Models.department import Department
from Models.patient import Patient, OpdVisit
from Models.opd_billing import BillItem, PaymentTransaction, Appointment, Bed
from Models.doctor_lab_test_order import LabTestOrder
from Models.doctor_patient_queue import PatientQueue
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.nurse_emergency_alert import EmergencyAlert
from Models.nurse_medication_administration import MedicationAdministration
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_handover import ShiftHandover, ShiftHandoverPatient
from Models.pharmacy_dispensing import Dispensing, DispensingItem
from Models.lab_result import LabResult, LabResultParameter

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()