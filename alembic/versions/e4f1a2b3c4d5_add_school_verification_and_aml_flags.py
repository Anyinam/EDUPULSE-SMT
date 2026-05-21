"""add school verification and aml flags

Revision ID: e4f1a2b3c4d5
Revises: b91d5f7c2a11
Create Date: 2026-05-21 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "b91d5f7c2a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_table("school_verifications"):
        op.create_table(
            "school_verifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("risk_tier", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("legal_name", sa.String(length=120), nullable=True),
            sa.Column("organization_id", sa.String(length=20), nullable=True),
            sa.Column("registration_number", sa.String(length=80), nullable=True),
            sa.Column("tax_id", sa.String(length=80), nullable=True),
            sa.Column("license_number", sa.String(length=80), nullable=True),
            sa.Column("bank_account_name", sa.String(length=120), nullable=True),
            sa.Column("bank_account_number", sa.String(length=255), nullable=True),
            sa.Column("bank_name", sa.String(length=120), nullable=True),
            sa.Column("owner_information", sa.JSON(), nullable=True),
            sa.Column("screening_results", sa.JSON(), nullable=True),
            sa.Column("documents", sa.JSON(), nullable=True),
            sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_by_platform_user_id", sa.Integer(), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_index("school_verifications", "ix_school_verifications_school_id"):
        op.create_index("ix_school_verifications_school_id", "school_verifications", ["school_id"])

    if not _has_table("aml_transaction_flags"):
        op.create_table(
            "aml_transaction_flags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("payment_id", sa.Integer(), nullable=True),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("rule_code", sa.String(length=60), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("summary", sa.String(length=255), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_index("aml_transaction_flags", "ix_aml_flags_school_status"):
        op.create_index("ix_aml_flags_school_status", "aml_transaction_flags", ["school_id", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    if _has_table("aml_transaction_flags"):
        if _has_index("aml_transaction_flags", "ix_aml_flags_school_status"):
            op.drop_index("ix_aml_flags_school_status", table_name="aml_transaction_flags")
        op.drop_table("aml_transaction_flags")

    if _has_table("school_verifications"):
        if _has_index("school_verifications", "ix_school_verifications_school_id"):
            op.drop_index("ix_school_verifications_school_id", table_name="school_verifications")
        op.drop_table("school_verifications")
