"""add school holidays and country code

Revision ID: 0f3a2b9c6b1d
Revises: b7a1c1f2d9ab
Create Date: 2026-02-24 13:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0f3a2b9c6b1d"
down_revision = "b7a1c1f2d9ab"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("country_code", sa.String(length=2), nullable=True))

    op.create_table(
        "school_holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.String(length=20), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("is_holiday", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("school_id", "holiday_date", name="uq_school_holiday_date"),
    )


def downgrade():
    op.drop_table("school_holidays")
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.drop_column("country_code")
