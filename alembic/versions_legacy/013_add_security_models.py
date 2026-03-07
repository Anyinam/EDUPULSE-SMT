"""add security models

Revision ID: 013_add_security_models
Revises: 012
Create Date: 2026-02-21 21:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "013_add_security_models"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "two_fa_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "users", sa.Column("two_fa_method", sa.String(length=20), nullable=True)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    op.add_column("payments", sa.Column("created_at", sa.DateTime(), nullable=True))

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.String(length=20), sa.ForeignKey("schools.id")),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("locked_until", sa.DateTime()),
    )

    op.create_table(
        "two_factor_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("delivery", sa.String(length=20), nullable=True),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "consumed", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )


def downgrade():
    op.drop_table("password_resets")
    op.drop_table("two_factor_tokens")
    op.drop_table("login_attempts")
    op.drop_column("payments", "created_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "two_fa_method")
    op.drop_column("users", "two_fa_enabled")
