"""sync all models

Revision ID: 4de691ce7fd6
Revises: c3d4e5f6a7b8
Create Date: 2026-06-19 11:52:20.263251

Idempotent sync: adds missing indexes/FKs and safe column tweaks.
Skips PostgreSQL enum conversions (existing VARCHAR lowercase values are compatible).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4de691ce7fd6"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _index_names(table: str) -> set[str]:
    return {idx["name"] for idx in _inspector().get_indexes(table)}


def _fk_names(table: str) -> set[str]:
    return {fk["name"] for fk in _inspector().get_foreign_keys(table)}


def _unique_constraint_names(table: str) -> set[str]:
    return {
        uc["name"]
        for uc in _inspector().get_unique_constraints(table)
        if uc.get("name")
    }


def _create_index_if_missing(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, columns, unique=unique)


def _create_fk_if_missing(
    name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
) -> None:
    if name not in _fk_names(source_table):
        op.create_foreign_key(
            name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            postgresql_not_valid=True,
        )


def _drop_constraint_if_exists(name: str, table: str, constraint_type: str) -> None:
    if constraint_type == "unique":
        names = _unique_constraint_names(table)
    elif constraint_type == "foreignkey":
        names = _fk_names(table)
    else:
        return
    if name in names:
        op.drop_constraint(name, table, type_=constraint_type)


def _has_nulls(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(f"SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1")
    ).first()
    return result is not None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ix_lab_results_created_at is created in c3d4e5f6a7b8 — do not duplicate here.

    _create_fk_if_missing(
        "fk_lab_test_orders_appointment_id",
        "lab_test_orders",
        "appointments",
        ["appointment_id"],
        ["id"],
    )

    med_cols = {c["name"]: c for c in inspector.get_columns("medication_administrations")}
    if med_cols.get("medicine_name", {}).get("nullable", True):
        if _has_nulls("medication_administrations", "medicine_name"):
            op.execute(
                sa.text(
                    "UPDATE medication_administrations "
                    "SET medicine_name = 'Unknown' "
                    "WHERE medicine_name IS NULL"
                )
            )
        op.alter_column(
            "medication_administrations",
            "medicine_name",
            existing_type=sa.VARCHAR(length=255),
            nullable=False,
        )

    for idx_name, col in (
        ("ix_medication_administrations_administered_at", "administered_at"),
        ("ix_medication_administrations_administered_by", "administered_by"),
        ("ix_medication_administrations_scheduled_time", "scheduled_time"),
        ("ix_medication_administrations_status", "status"),
    ):
        _create_index_if_missing(idx_name, "medication_administrations", [col])

    nursing_cols = {c["name"]: c for c in inspector.get_columns("nursing_notes")}
    updated_at_col = nursing_cols.get("updated_at")
    if updated_at_col and str(updated_at_col.get("type", "")).upper().find("TIME ZONE") == -1:
        op.alter_column(
            "nursing_notes",
            "updated_at",
            existing_type=sa.TIMESTAMP(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    for idx_name, col in (
        ("ix_nursing_notes_appointment_id", "appointment_id"),
        ("ix_nursing_notes_created_at", "created_at"),
        ("ix_nursing_notes_nurse_id", "nurse_id"),
        ("ix_nursing_notes_patient_id", "patient_id"),
        ("ix_nursing_notes_status", "status"),
    ):
        _create_index_if_missing(idx_name, "nursing_notes", [col])

    for fk_name, ref_table, local_col in (
        ("fk_nursing_notes_created_by", "users", "created_by"),
        ("fk_nursing_notes_appointment_id", "appointments", "appointment_id"),
        ("fk_nursing_notes_updated_by", "users", "updated_by"),
        ("fk_nursing_notes_patient_id", "patients", "patient_id"),
    ):
        _create_fk_if_missing(fk_name, "nursing_notes", ref_table, [local_col], ["id"])

    pq_cols = {c["name"]: c for c in inspector.get_columns("patient_queue")}
    phone_col = pq_cols.get("patient_phone")
    if phone_col and getattr(phone_col.get("type"), "length", None) == 15:
        op.alter_column(
            "patient_queue",
            "patient_phone",
            existing_type=sa.VARCHAR(length=15),
            type_=sa.String(length=20),
            existing_nullable=True,
        )

    for col_name in (
        "queue_entered_at",
        "consultation_started_at",
        "consultation_completed_at",
        "created_at",
        "updated_at",
    ):
        col = pq_cols.get(col_name)
        if col and str(col.get("type", "")).upper().find("TIME ZONE") == -1:
            op.alter_column(
                "patient_queue",
                col_name,
                existing_type=sa.TIMESTAMP(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=col.get("nullable", True),
            )

    for idx_name, col in (
        ("ix_patient_queue_appointment_id", "appointment_id"),
        ("ix_patient_queue_appointment_uid", "appointment_uid"),
        ("ix_patient_queue_doctor_id", "doctor_id"),
        ("ix_patient_queue_id", "id"),
        ("ix_patient_queue_patient_id", "patient_id"),
        ("ix_patient_queue_patient_name", "patient_name"),
        ("ix_patient_queue_patient_uhid", "patient_uhid"),
        ("ix_patient_queue_queue_date", "queue_date"),
        ("ix_patient_queue_token_number", "token_number"),
    ):
        _create_index_if_missing(idx_name, "patient_queue", [col])

    for fk_name, ref_table, local_col in (
        ("fk_patient_queue_patient_id", "patients", "patient_id"),
        ("fk_patient_queue_updated_by", "users", "updated_by"),
        ("fk_patient_queue_created_by", "users", "created_by"),
        ("fk_patient_queue_appointment_id", "appointments", "appointment_id"),
        ("fk_patient_queue_doctor_id", "users", "doctor_id"),
    ):
        _create_fk_if_missing(fk_name, "patient_queue", ref_table, [local_col], ["id"])

    for idx_name, col in (
        ("ix_patient_vitals_appointment_id", "appointment_id"),
        ("ix_patient_vitals_patient_id", "patient_id"),
        ("ix_patient_vitals_recorded_at", "recorded_at"),
        ("ix_patient_vitals_recorded_by", "recorded_by"),
        ("ix_patient_vitals_status", "status"),
    ):
        _create_index_if_missing(idx_name, "patient_vitals", [col])

    for fk_name, ref_table, local_col in (
        ("fk_patient_vitals_appointment_id", "appointments", "appointment_id"),
        ("fk_patient_vitals_patient_id", "patients", "patient_id"),
        ("fk_patient_vitals_updated_by", "users", "updated_by"),
        ("fk_patient_vitals_created_by", "users", "created_by"),
    ):
        _create_fk_if_missing(fk_name, "patient_vitals", ref_table, [local_col], ["id"])

    _create_index_if_missing(
        "ix_prescription_items_prescription_id",
        "prescription_items",
        ["prescription_id"],
    )

    rx_cols = {c["name"]: c for c in inspector.get_columns("prescriptions")}
    if rx_cols.get("patient_name", {}).get("nullable", True):
        if _has_nulls("prescriptions", "patient_name"):
            op.execute(
                sa.text(
                    """
                    UPDATE prescriptions AS p
                    SET patient_name = TRIM(
                        CONCAT(pat.first_name, ' ', COALESCE(pat.last_name, ''))
                    )
                    FROM patients AS pat
                    WHERE p.patient_id = pat.id
                      AND p.patient_name IS NULL
                    """
                )
            )
            op.execute(
                sa.text(
                    "UPDATE prescriptions "
                    "SET patient_name = 'Unknown' "
                    "WHERE patient_name IS NULL OR TRIM(patient_name) = ''"
                )
            )
        op.alter_column(
            "prescriptions",
            "patient_name",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )

    for col_name, existing_type in (("diagnosis", sa.VARCHAR()), ("notes", sa.VARCHAR())):
        col = rx_cols.get(col_name)
        if col and "TEXT" not in str(col.get("type", "")).upper():
            op.alter_column(
                "prescriptions",
                col_name,
                existing_type=existing_type,
                type_=sa.Text(),
                existing_nullable=col.get("nullable", True),
            )

    # Only drop unique constraints that autogenerate incorrectly assumed; keep appointment unique.
    for uc_name in ("prescriptions_doctor_id_key", "prescriptions_patient_id_key"):
        _drop_constraint_if_exists(uc_name, "prescriptions", "unique")

    _create_index_if_missing(
        "ix_prescriptions_appointment_id",
        "prescriptions",
        ["appointment_id"],
        unique=True,
    )
    for idx_name, col in (
        ("ix_prescriptions_doctor_id", "doctor_id"),
        ("ix_prescriptions_patient_id", "patient_id"),
        ("ix_prescriptions_status", "status"),
    ):
        _create_index_if_missing(idx_name, "prescriptions", [col])

    for fk_name, ref_table, local_col in (
        ("fk_prescriptions_created_by", "users", "created_by"),
        ("fk_prescriptions_appointment_id", "appointments", "appointment_id"),
        ("fk_prescriptions_updated_by", "users", "updated_by"),
        ("fk_prescriptions_patient_id", "patients", "patient_id"),
    ):
        _create_fk_if_missing(fk_name, "prescriptions", ref_table, [local_col], ["id"])

    _create_fk_if_missing(
        "fk_users_department_id",
        "users",
        "departments",
        ["department_id"],
        ["id"],
    )


def downgrade() -> None:
    """Best-effort rollback of named objects added in upgrade."""
    for name, table in (
        ("fk_users_department_id", "users"),
        ("fk_prescriptions_patient_id", "prescriptions"),
        ("fk_prescriptions_updated_by", "prescriptions"),
        ("fk_prescriptions_appointment_id", "prescriptions"),
        ("fk_prescriptions_created_by", "prescriptions"),
        ("fk_patient_vitals_created_by", "patient_vitals"),
        ("fk_patient_vitals_updated_by", "patient_vitals"),
        ("fk_patient_vitals_patient_id", "patient_vitals"),
        ("fk_patient_vitals_appointment_id", "patient_vitals"),
        ("fk_patient_queue_doctor_id", "patient_queue"),
        ("fk_patient_queue_appointment_id", "patient_queue"),
        ("fk_patient_queue_created_by", "patient_queue"),
        ("fk_patient_queue_updated_by", "patient_queue"),
        ("fk_patient_queue_patient_id", "patient_queue"),
        ("fk_nursing_notes_patient_id", "nursing_notes"),
        ("fk_nursing_notes_updated_by", "nursing_notes"),
        ("fk_nursing_notes_appointment_id", "nursing_notes"),
        ("fk_nursing_notes_created_by", "nursing_notes"),
        ("fk_lab_test_orders_appointment_id", "lab_test_orders"),
    ):
        _drop_constraint_if_exists(name, table, "foreignkey")

    for name, table in (
        ("ix_prescriptions_status", "prescriptions"),
        ("ix_prescriptions_patient_id", "prescriptions"),
        ("ix_prescriptions_doctor_id", "prescriptions"),
        ("ix_prescriptions_appointment_id", "prescriptions"),
        ("ix_prescription_items_prescription_id", "prescription_items"),
        ("ix_patient_vitals_status", "patient_vitals"),
        ("ix_patient_vitals_recorded_by", "patient_vitals"),
        ("ix_patient_vitals_recorded_at", "patient_vitals"),
        ("ix_patient_vitals_patient_id", "patient_vitals"),
        ("ix_patient_vitals_appointment_id", "patient_vitals"),
        ("ix_patient_queue_token_number", "patient_queue"),
        ("ix_patient_queue_queue_date", "patient_queue"),
        ("ix_patient_queue_patient_uhid", "patient_queue"),
        ("ix_patient_queue_patient_name", "patient_queue"),
        ("ix_patient_queue_patient_id", "patient_queue"),
        ("ix_patient_queue_id", "patient_queue"),
        ("ix_patient_queue_doctor_id", "patient_queue"),
        ("ix_patient_queue_appointment_uid", "patient_queue"),
        ("ix_patient_queue_appointment_id", "patient_queue"),
        ("ix_nursing_notes_status", "nursing_notes"),
        ("ix_nursing_notes_patient_id", "nursing_notes"),
        ("ix_nursing_notes_nurse_id", "nursing_notes"),
        ("ix_nursing_notes_created_at", "nursing_notes"),
        ("ix_nursing_notes_appointment_id", "nursing_notes"),
        ("ix_medication_administrations_status", "medication_administrations"),
        ("ix_medication_administrations_scheduled_time", "medication_administrations"),
        ("ix_medication_administrations_administered_by", "medication_administrations"),
        ("ix_medication_administrations_administered_at", "medication_administrations"),
    ):
        if name in _index_names(table):
            op.drop_index(name, table_name=table)
