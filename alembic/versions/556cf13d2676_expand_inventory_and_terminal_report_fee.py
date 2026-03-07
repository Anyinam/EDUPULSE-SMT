"""expand_inventory_and_terminal_report_fee

Revision ID: 556cf13d2676
Revises: af935fa0e071
Create Date: 2026-02-25 19:45:49.245883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '556cf13d2676'
down_revision: Union[str, Sequence[str], None] = 'af935fa0e071'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    school_cols = {c["name"] for c in inspector.get_columns("school_settings")}
    if "terminal_report_fee" not in school_cols:
        op.add_column("school_settings", sa.Column("terminal_report_fee", sa.Float(), nullable=True))

    inventory_cols = {c["name"] for c in inspector.get_columns("inventory")}
    if "category" not in inventory_cols:
        op.add_column("inventory", sa.Column("category", sa.String(length=30), nullable=True))
    if "item_type" not in inventory_cols:
        op.add_column("inventory", sa.Column("item_type", sa.String(length=50), nullable=True))
    if "size" not in inventory_cols:
        op.add_column("inventory", sa.Column("size", sa.String(length=20), nullable=True))
    if "class_group" not in inventory_cols:
        op.add_column("inventory", sa.Column("class_group", sa.String(length=30), nullable=True))
    if "gender" not in inventory_cols:
        op.add_column("inventory", sa.Column("gender", sa.String(length=10), nullable=True))
    if "sku" not in inventory_cols:
        op.add_column("inventory", sa.Column("sku", sa.String(length=30), nullable=True))
    if "unit" not in inventory_cols:
        op.add_column("inventory", sa.Column("unit", sa.String(length=20), nullable=True))
    if "is_active" not in inventory_cols:
        op.add_column("inventory", sa.Column("is_active", sa.Boolean(), nullable=True))
    if "created_at" not in inventory_cols:
        op.add_column("inventory", sa.Column("created_at", sa.DateTime(), nullable=True))

    unique_names = {u.get("name") for u in inspector.get_unique_constraints("inventory")}
    if "uq_inventory_sku" not in unique_names:
        with op.batch_alter_table("inventory", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_inventory_sku", ["school_id", "sku"])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    unique_names = {u.get("name") for u in inspector.get_unique_constraints("inventory")}
    if "uq_inventory_sku" in unique_names:
        with op.batch_alter_table("inventory", schema=None) as batch_op:
            batch_op.drop_constraint("uq_inventory_sku", type_="unique")

    inventory_cols = {c["name"] for c in inspector.get_columns("inventory")}
    if "created_at" in inventory_cols:
        op.drop_column("inventory", "created_at")
    if "is_active" in inventory_cols:
        op.drop_column("inventory", "is_active")
    if "unit" in inventory_cols:
        op.drop_column("inventory", "unit")
    if "sku" in inventory_cols:
        op.drop_column("inventory", "sku")
    if "gender" in inventory_cols:
        op.drop_column("inventory", "gender")
    if "class_group" in inventory_cols:
        op.drop_column("inventory", "class_group")
    if "size" in inventory_cols:
        op.drop_column("inventory", "size")
    if "item_type" in inventory_cols:
        op.drop_column("inventory", "item_type")
    if "category" in inventory_cols:
        op.drop_column("inventory", "category")

    school_cols = {c["name"] for c in inspector.get_columns("school_settings")}
    if "terminal_report_fee" in school_cols:
        op.drop_column("school_settings", "terminal_report_fee")
