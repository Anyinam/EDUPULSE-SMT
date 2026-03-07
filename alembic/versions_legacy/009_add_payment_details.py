"""Add school payment account details"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    # Add payment account columns to schools table
    op.add_column("schools", sa.Column("momo_number", sa.String(20), nullable=True))
    op.add_column(
        "schools", sa.Column("momo_account_name", sa.String(100), nullable=True)
    )
    op.add_column("schools", sa.Column("bank_name", sa.String(100), nullable=True))
    op.add_column("schools", sa.Column("bank_account", sa.String(50), nullable=True))
    op.add_column(
        "schools", sa.Column("bank_account_name", sa.String(100), nullable=True)
    )
    op.add_column("schools", sa.Column("bank_branch", sa.String(100), nullable=True))


def downgrade():
    # Remove payment account columns from schools table
    op.drop_column("schools", "bank_branch")
    op.drop_column("schools", "bank_account_name")
    op.drop_column("schools", "bank_account")
    op.drop_column("schools", "bank_name")
    op.drop_column("schools", "momo_account_name")
    op.drop_column("schools", "momo_number")
