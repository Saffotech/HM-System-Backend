from logging.config import fileConfig
from sqlalchemy import engine_from_config, inspect, pool, text
from alembic import context
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import settings
from database import Base


from Models.role import Role, Permission, RolePermission
from Models.user import User
from Models.department import Department
from Models.patient import Patient, OpdVisit
from Models.opd_billing import BillItem, PaymentTransaction, Appointment, Bed
from Models.ipd import (
    IpdAdmission,
    IpdAdmissionBilling,
    IpdAdmissionCareTeam,
    IpdBill,
    IpdBillItem,
    IpdDoctorVisit,
    IpdInsuranceClaim,
    IpdPaymentTransaction,
)
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.doctor_lab_test_order import LabTestOrder
from Models.lab_test import LabTest
from Models.doctor_patient_queue import PatientQueue
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.nurse_medication_administration import MedicationAdministration
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_handover import ShiftHandover, ShiftHandoverPatient
from Models.nurse_doctor_visit import NurseDoctorVisit  # noqa: F401
from Models.pharmacy_dispensing import Dispensing, DispensingItem
from Models.hospital_settings import HospitalSettings
from Models.opd_settings import OpdSettings  # noqa: F401
from Models.lab_result import LabResult, LabResultParameter
from Models.notification import Notification  # noqa: F401
from Models.legal_case import (  # noqa: F401
    LegalCase,
    LegalDocument,
    LegalChecklistItem,
    LegalFinanceTerms,
    LegalCaseDecision,
)
from Models.audit_log import AuditLog  # noqa: F401
from Models.lead import Lead, LeadActivity  # noqa: F401
from Models.subscription_invoice import SubscriptionInvoice  # noqa: F401
from Models.subscription_plan import SubscriptionPlan  # noqa: F401
from Models.accountant_profile import AccountantProfile  # noqa: F401
from Models.platform_admin_profile import PlatformAdminProfile  # noqa: F401
from Models.crm_profile import CrmProfile  # noqa: F401
from Models.legal_finance_profile import LegalFinanceProfile  # noqa: F401
from Models.admin_profile import AdminProfile  # noqa: F401
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation  # noqa: F401
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory  # noqa: F401
from Models.nurse_workforce import NurseWorkforceRoster, NurseWorkforceShift  # noqa: F401
from Models.nurse_other_visit import PatientOtherVisit  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Keep Alembic on the same database as the FastAPI app (database.py).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

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
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        versioned = "alembic_version" in tables
        has_application_tables = bool(tables - {"alembic_version"})
        # inspect() starts a transaction. Roll it back so Alembic's
        # migration transaction is the outer one and its commit is kept.
        connection.rollback()
        proxy = getattr(context, "_proxy", None)
        options = getattr(proxy, "context_opts", {}) if proxy is not None else {}
        migration_fn = options.get("fn")
        is_upgrade = getattr(migration_fn, "__name__", "") == "upgrade"
        destination = None
        if is_upgrade and "destination_rev" in options:
            destination = context.get_revision_argument()
        head_ids = set(context.script.get_heads())
        if isinstance(destination, (tuple, list, set)):
            targets_head = set(destination) == head_ids
        else:
            targets_head = destination in head_ids
        upgrade_to_head = is_upgrade and targets_head
        if upgrade_to_head and not versioned and not has_application_tables:
            # Historical revisions alter a schema that already existed.
            # An empty database gets the current models, then the version
            # table is set to head. This is not a substitute for a failed
            # upgrade on a database that already has a revision.
            target_metadata.create_all(bind=connection)
            # Migration-only table. There is no SQLAlchemy model for it.
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS tenant_employee_sequences ("
                    "tenant_id INTEGER PRIMARY KEY REFERENCES tenants(id), "
                    "last_number INTEGER NOT NULL)"
                )
            )
            connection.commit()
            context.configure(connection=connection, target_metadata=target_metadata)
            context.get_context().stamp(context.script, "head")
            connection.commit()
            return
        if upgrade_to_head and not versioned and has_application_tables:
            raise RuntimeError(
                "This database has application tables but no alembic_version "
                "row. Alembic will not guess a revision and will not stamp "
                "head. If the tables were created by the current models and "
                "you accept that historical migrations will not be replayed, "
                "run: alembic stamp head. If the database is an older "
                "hospital database, restore alembic_version to its real "
                "revision and run: alembic upgrade head."
            )
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()