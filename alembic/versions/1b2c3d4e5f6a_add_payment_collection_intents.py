"""add payment collection intents

Revision ID: 1b2c3d4e5f6a
Revises: c6e9f1a2b3d4
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b2c3d4e5f6a"
down_revision: Union[str, Sequence[str], None] = "c6e9f1a2b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_collection_intents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.String(length=20), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("parent_admission_application_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="paystack"),
        sa.Column("collection_channel", sa.String(length=40), nullable=False, server_default="dedicated_virtual_account"),
        sa.Column("intent_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reference_code", sa.String(length=80), nullable=False),
        sa.Column("payment_type", sa.String(length=40), nullable=False),
        sa.Column("payment_category", sa.JSON(), nullable=True),
        sa.Column("base_amount", sa.Float(), nullable=False),
        sa.Column("convenience_fee_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("estimated_provider_fee_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("platform_fee_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True, server_default="GH₵"),
        sa.Column("provider_customer_code", sa.String(length=80), nullable=True),
        sa.Column("provider_dedicated_account_id", sa.String(length=80), nullable=True),
        sa.Column("provider_bank_slug", sa.String(length=80), nullable=True),
        sa.Column("provider_bank_name", sa.String(length=120), nullable=True),
        sa.Column("provider_account_name", sa.String(length=120), nullable=True),
        sa.Column("provider_account_number", sa.String(length=40), nullable=True),
        sa.Column("provider_subaccount_code", sa.String(length=50), nullable=True),
        sa.Column("provider_reference", sa.String(length=80), nullable=True),
        sa.Column("provider_last_event", sa.String(length=80), nullable=True),
        sa.Column("payer_name", sa.String(length=120), nullable=True),
        sa.Column("payer_bank_name", sa.String(length=120), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("base_amount >= 0", name="ck_payment_collection_intent_base_amount"),
        sa.CheckConstraint("total_amount >= 0", name="ck_payment_collection_intent_total_amount"),
        sa.ForeignKeyConstraint(["parent_admission_application_id"], ["parent_admission_applications.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_number"),
    )
    op.create_index(op.f("ix_payment_collection_intents_provider_customer_code"), "payment_collection_intents", ["provider_customer_code"], unique=False)
    op.create_index(op.f("ix_payment_collection_intents_provider_dedicated_account_id"), "payment_collection_intents", ["provider_dedicated_account_id"], unique=False)
    op.create_index(op.f("ix_payment_collection_intents_reference_code"), "payment_collection_intents", ["reference_code"], unique=False)
    op.create_index(op.f("ix_payment_collection_intents_school_id"), "payment_collection_intents", ["school_id"], unique=False)
    op.create_index(op.f("ix_payment_collection_intents_student_id"), "payment_collection_intents", ["student_id"], unique=False)
    op.create_index(op.f("ix_payment_collection_intents_parent_admission_application_id"), "payment_collection_intents", ["parent_admission_application_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_collection_intents_parent_admission_application_id"), table_name="payment_collection_intents")
    op.drop_index(op.f("ix_payment_collection_intents_student_id"), table_name="payment_collection_intents")
    op.drop_index(op.f("ix_payment_collection_intents_school_id"), table_name="payment_collection_intents")
    op.drop_index(op.f("ix_payment_collection_intents_reference_code"), table_name="payment_collection_intents")
    op.drop_index(op.f("ix_payment_collection_intents_provider_dedicated_account_id"), table_name="payment_collection_intents")
    op.drop_index(op.f("ix_payment_collection_intents_provider_customer_code"), table_name="payment_collection_intents")
    op.drop_table("payment_collection_intents")