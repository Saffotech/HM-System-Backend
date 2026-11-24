"""Manager OPD saves must ignore an unchanged admin_edit payload."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from Schemas.opd_settings_schema import OpdSettingsUpdate
from Services.admin_edit_policy import DEFAULT_ADMIN_EDIT
from Services.opd_settings_service import update_settings


def _user(role: str, tenant_id: int = 1):
    return SimpleNamespace(
        id=10,
        tenant_id=tenant_id,
        role_obj=SimpleNamespace(name=role),
    )


def _row(**extra):
    return SimpleNamespace(
        id=5,
        tenant_id=1,
        allow_patient_delete=True,
        allow_appointment_delete=True,
        allow_unpaid_bill_delete=True,
        require_admin_approval_for_delete=False,
        extra=extra,
        updated_at=None,
        updated_by=None,
    )


class ManagerEditLockSaveTests(unittest.TestCase):
    def _run(self, actor, payload, stored_locks=None):
        row = _row(admin_edit=stored_locks or {"delete_controls": True})
        db = MagicMock()
        data = OpdSettingsUpdate.model_validate(payload)
        with patch("Services.opd_settings_service.get_settings_row", return_value=row), patch(
            "Services.opd_settings_service._to_out", return_value={"ok": True}
        ), patch("Services.opd_settings_service.audit_service.log_event"):
            result = update_settings(db, data, actor)
        return result, row, db

    def test_manager_save_without_admin_edit(self):
        _, row, db = self._run(
            _user("manager"),
            {"delete_controls": {"allow_patient_delete": False}},
        )
        self.assertFalse(row.allow_patient_delete)
        db.commit.assert_called_once()

    def test_manager_unchanged_full_admin_edit_is_ignored(self):
        locks = dict(DEFAULT_ADMIN_EDIT)
        _, row, db = self._run(
            _user("manager"),
            {
                "admin_edit": locks,
                "delete_controls": {"allow_patient_delete": False},
            },
            stored_locks=locks,
        )
        self.assertFalse(row.allow_patient_delete)
        self.assertEqual(row.extra["admin_edit"], locks)
        db.commit.assert_called_once()

    def test_manager_partial_unchanged_admin_edit_is_ignored(self):
        _, row, db = self._run(
            _user("manager"),
            {
                "admin_edit": {"delete_controls": True},
                "delete_controls": {"allow_appointment_delete": False},
            },
            stored_locks={"delete_controls": True},
        )
        self.assertFalse(row.allow_appointment_delete)
        db.commit.assert_called_once()

    def test_manager_cannot_change_a_lock(self):
        row = _row(admin_edit={"delete_controls": False})
        db = MagicMock()
        data = OpdSettingsUpdate.model_validate(
            {
                "admin_edit": {"delete_controls": True},
                "delete_controls": {"allow_patient_delete": False},
            }
        )
        with patch("Services.opd_settings_service.get_settings_row", return_value=row):
            with self.assertRaises(HTTPException) as caught:
                update_settings(db, data, _user("manager"))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertTrue(row.allow_patient_delete)
        db.commit.assert_not_called()

    def test_manager_cannot_write_a_locked_section(self):
        row = _row(admin_edit={"delete_controls": False})
        db = MagicMock()
        data = OpdSettingsUpdate.model_validate(
            {"delete_controls": {"allow_patient_delete": False}}
        )
        with patch("Services.opd_settings_service.get_settings_row", return_value=row):
            with self.assertRaises(HTTPException) as caught:
                update_settings(db, data, _user("manager"))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertTrue(row.allow_patient_delete)
        db.commit.assert_not_called()

    def test_unchanged_locked_section_does_not_block_an_unlocked_section(self):
        _, row, db = self._run(
            _user("manager"),
            {
                "delete_controls": {"allow_patient_delete": True},
                "discount_refund": {"allow_discount": False},
            },
            stored_locks={"delete_controls": False, "discount_refund": True},
        )
        self.assertTrue(row.allow_patient_delete)
        self.assertFalse(row.extra["discount_refund"]["allow_discount"])
        db.commit.assert_called_once()

    def test_admin_can_change_a_lock(self):
        _, row, db = self._run(
            _user("admin"),
            {"admin_edit": {"delete_controls": False}},
            stored_locks={"delete_controls": True},
        )
        self.assertFalse(row.extra["admin_edit"]["delete_controls"])
        db.commit.assert_called_once()

    def test_other_hospital_row_is_the_one_loaded_for_that_actor(self):
        hospital_b = _row(admin_edit={"delete_controls": True})
        hospital_b.tenant_id = 2
        db = MagicMock()
        data = OpdSettingsUpdate.model_validate(
            {"delete_controls": {"allow_patient_delete": False}}
        )
        with patch(
            "Services.opd_settings_service.get_settings_row", return_value=hospital_b
        ) as loaded, patch("Services.opd_settings_service._to_out", return_value={"ok": True}), patch(
            "Services.opd_settings_service.audit_service.log_event"
        ):
            update_settings(db, data, _user("manager", tenant_id=2))
        loaded.assert_called_once_with(db, 2)
        self.assertEqual(hospital_b.tenant_id, 2)
        self.assertFalse(hospital_b.allow_patient_delete)


if __name__ == "__main__":
    unittest.main()
