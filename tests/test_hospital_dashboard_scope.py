import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Models.admin_profile import AdminProfile  # noqa: F401
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.ipd_profile import IpdProfile  # noqa: F401
from Models.lab_technician_profile import LabTechnicianProfile  # noqa: F401
from Models.manager_profile import ManagerProfile  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.opd_billing_profile import OpdBillingProfile  # noqa: F401
from Models.pharmacist_profile import PharmacistProfile  # noqa: F401
from Models.receptionist_profile import ReceptionistProfile  # noqa: F401
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Services.manager_service import get_dashboard


def _tenant(code: str) -> Tenant:
    today = date.today()
    return Tenant(
        name=code,
        code=code,
        hospital_type="General",
        plan="Professional",
        billing_cycle="Monthly",
        subscription_started_on=today,
        subscription_renews_on=today,
    )


def _user(first: str, role: Role, tenant_id: int | None) -> User:
    return User(
        first_name=first,
        email=f"{first}@example.com",
        password="hashed",
        role_id=role.id,
        tenant_id=tenant_id,
        is_active=True,
    )


class HospitalDashboardScopeTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Tenant.__table__.create(engine)
        Department.__table__.create(engine)
        Role.__table__.create(engine)
        User.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.hospital = _tenant("H1")
        self.other = _tenant("H2")
        self.db.add_all([self.hospital, self.other])
        self.db.flush()
        self.roles = {}
        for name in ("admin", "doctor", "crm", "accountant", "platform_admin"):
            role = Role(name=name)
            self.db.add(role)
            self.roles[name] = role
        self.db.flush()
        self.db.add_all([
            _user("admin", self.roles["admin"], self.hospital.id),
            _user("doctor", self.roles["doctor"], self.hospital.id),
            _user("other", self.roles["doctor"], self.other.id),
            _user("crm", self.roles["crm"], None),
            _user("accounts", self.roles["accountant"], None),
            _user("platform", self.roles["platform_admin"], None),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_counts_only_this_hospital_and_excludes_platform_roles(self):
        result = get_dashboard(self.db, tenant_id=self.hospital.id)
        self.assertEqual(result.total_staff, 2)
        self.assertEqual(result.total_roles, 2)
        self.assertEqual(
            {item.role_name for item in result.staff_by_role},
            {"admin", "doctor"},
        )
        self.assertEqual(sum(item.count for item in result.staff_by_role), 2)

    def test_count_changes_when_hospital_staff_is_added(self):
        self.db.add(_user("nurse", self.roles["doctor"], self.hospital.id))
        self.db.commit()
        result = get_dashboard(self.db, tenant_id=self.hospital.id)
        self.assertEqual(result.total_staff, 3)

    def test_other_hospital_is_not_included(self):
        result = get_dashboard(self.db, tenant_id=self.other.id)
        self.assertEqual(result.total_staff, 1)
        self.assertEqual(
            next(item.count for item in result.staff_by_role if item.role_name == "doctor"),
            1,
        )
        self.assertEqual(
            next(item.count for item in result.staff_by_role if item.role_name == "admin"),
            0,
        )


if __name__ == "__main__":
    unittest.main()
