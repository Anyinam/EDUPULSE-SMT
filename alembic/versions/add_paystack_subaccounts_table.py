"""add paystack subaccounts table

Revision ID: ps001_subaccounts
Revises: 
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ps001_subaccounts'
down_revision = None  # Update this to the most recent migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Create paystack_subaccounts table for virtual account management."""
    op.create_table(
        'paystack_subaccounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.String(length=20), nullable=False),
        sa.Column('payment_type', sa.String(length=20), nullable=False),
        sa.Column('subaccount_code', sa.String(length=50), nullable=False),
        sa.Column('business_name', sa.String(length=100), nullable=False),
        sa.Column('virtual_bank_account', sa.String(length=50), nullable=True),
        sa.Column('virtual_bank_name', sa.String(length=100), nullable=True),
        sa.Column('momo_shortcode', sa.String(length=20), nullable=True),
        sa.Column('momo_provider', sa.String(length=20), nullable=True),
        sa.Column('percentage_charge', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('is_verified', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subaccount_code', name='uq_subaccount_code'),
        sa.UniqueConstraint('school_id', 'payment_type', name='uq_school_payment_subaccount')
    )
    
    # Create index for faster lookups
    op.create_index(
        'ix_paystack_subaccounts_school_payment',
        'paystack_subaccounts',
        ['school_id', 'payment_type', 'is_active']
    )


def downgrade():
    """Remove paystack_subaccounts table."""
    op.drop_index('ix_paystack_subaccounts_school_payment', table_name='paystack_subaccounts')
    op.drop_table('paystack_subaccounts')
