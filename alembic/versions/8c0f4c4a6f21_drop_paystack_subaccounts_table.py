"""drop paystack subaccounts table

Revision ID: 8c0f4c4a6f21
Revises: 5f8c1a9d2b6e
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c0f4c4a6f21"
down_revision: Union[str, Sequence[str], None] = "5f8c1a9d2b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove the retired Paystack route metadata table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paystack_subaccounts" in inspector.get_table_names():
        op.drop_table("paystack_subaccounts")


def downgrade() -> None:
    """Restore the legacy Paystack route metadata table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paystack_subaccounts" in inspector.get_table_names():
        return

    op.create_table(
        "paystack_subaccounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.String(length=20), nullable=False),
        sa.Column("payment_type", sa.String(length=20), nullable=False),
        sa.Column("subaccount_code", sa.String(length=50), nullable=False),
        sa.Column("business_name", sa.String(length=100), nullable=False),
        sa.Column("virtual_bank_account", sa.String(length=50), nullable=True),
        sa.Column("virtual_bank_name", sa.String(length=100), nullable=True),
        sa.Column("momo_shortcode", sa.String(length=20), nullable=True),
        sa.Column("momo_provider", sa.String(length=20), nullable=True),
        sa.Column("percentage_charge", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subaccount_code", name="uq_subaccount_code"),
        sa.UniqueConstraint("school_id", "payment_type", name="uq_school_payment_subaccount"),
    )
    op.create_index(
        "ix_paystack_subaccounts_school_payment",
        "paystack_subaccounts",
        ["school_id", "payment_type", "is_active"],
    )
