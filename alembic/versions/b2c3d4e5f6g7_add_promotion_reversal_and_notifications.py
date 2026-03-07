"""Add promotion reversal tracking and student notifications

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "student_promotions" not in tables:
        op.create_table(
            "student_promotions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("promoted_from_class", sa.String(length=20), nullable=False),
            sa.Column("promoted_to_class", sa.String(length=20), nullable=False),
            sa.Column("promoted_by_user_id", sa.Integer(), nullable=False),
            sa.Column("promotion_date", sa.DateTime(), nullable=True),
            sa.Column("remarks", sa.String(length=500), nullable=True),
            sa.Column("is_reversed", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("reversed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reversed_at", sa.DateTime(), nullable=True),
            sa.Column("reversal_reason", sa.String(length=500), nullable=True),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["promoted_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        promo_cols = {c["name"] for c in inspector.get_columns("student_promotions")}
        if "is_reversed" not in promo_cols:
            op.add_column("student_promotions", sa.Column("is_reversed", sa.Boolean(), server_default="false", nullable=False))
        if "reversed_by_user_id" not in promo_cols:
            op.add_column("student_promotions", sa.Column("reversed_by_user_id", sa.Integer(), nullable=True))
        if "reversed_at" not in promo_cols:
            op.add_column("student_promotions", sa.Column("reversed_at", sa.DateTime(), nullable=True))
        if "reversal_reason" not in promo_cols:
            op.add_column("student_promotions", sa.Column("reversal_reason", sa.String(length=500), nullable=True))

        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("student_promotions")}
        if "fk_student_promotions_reversed_by_user_id" not in fk_names:
            with op.batch_alter_table("student_promotions", schema=None) as batch_op:
                batch_op.create_foreign_key(
                    "fk_student_promotions_reversed_by_user_id",
                    "users",
                    ["reversed_by_user_id"],
                    ["id"],
                )

    report_cols = {c["name"] for c in inspector.get_columns("report_cards")}
    if "promotion_status" not in report_cols:
        op.add_column("report_cards", sa.Column("promotion_status", sa.String(length=50), nullable=True))
    if "promotion_details" not in report_cols:
        op.add_column("report_cards", sa.Column("promotion_details", sa.JSON(), server_default="{}", nullable=True))

    if "student_notifications" not in tables:
        op.create_table(
            "student_notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("notification_type", sa.String(length=50), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("notification_metadata", sa.JSON(), server_default="{}", nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    notif_indexes = {idx.get("name") for idx in inspector.get_indexes("student_notifications")}
    if "ix_student_notifications_recipient" not in notif_indexes:
        op.create_index("ix_student_notifications_recipient", "student_notifications", ["recipient_user_id"])
    if "ix_student_notifications_student" not in notif_indexes:
        op.create_index("ix_student_notifications_student", "student_notifications", ["student_id"])
    if "ix_student_notifications_read" not in notif_indexes:
        op.create_index("ix_student_notifications_read", "student_notifications", ["is_read"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "student_notifications" in tables:
        notif_indexes = {idx.get("name") for idx in inspector.get_indexes("student_notifications")}
        if "ix_student_notifications_read" in notif_indexes:
            op.drop_index("ix_student_notifications_read", table_name="student_notifications")
        if "ix_student_notifications_student" in notif_indexes:
            op.drop_index("ix_student_notifications_student", table_name="student_notifications")
        if "ix_student_notifications_recipient" in notif_indexes:
            op.drop_index("ix_student_notifications_recipient", table_name="student_notifications")
        op.drop_table("student_notifications")

    report_cols = {c["name"] for c in inspector.get_columns("report_cards")}
    if "promotion_details" in report_cols:
        op.drop_column("report_cards", "promotion_details")
    if "promotion_status" in report_cols:
        op.drop_column("report_cards", "promotion_status")

    if "student_promotions" in tables:
        promo_cols = {c["name"] for c in inspector.get_columns("student_promotions")}
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("student_promotions")}
        if "fk_student_promotions_reversed_by_user_id" in fk_names:
            with op.batch_alter_table("student_promotions", schema=None) as batch_op:
                batch_op.drop_constraint("fk_student_promotions_reversed_by_user_id", type_="foreignkey")
        if "reversal_reason" in promo_cols:
            op.drop_column("student_promotions", "reversal_reason")
        if "reversed_at" in promo_cols:
            op.drop_column("student_promotions", "reversed_at")
        if "reversed_by_user_id" in promo_cols:
            op.drop_column("student_promotions", "reversed_by_user_id")
        if "is_reversed" in promo_cols:
            op.drop_column("student_promotions", "is_reversed")
