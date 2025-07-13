"""Market analysis tables

Revision ID: 002
Revises: 001
Create Date: 2024-03-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create market_metrics table for caching aggregated metrics
    op.create_table(
        'market_metrics',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('metric_date', sa.Date, nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    )
    
    # Create index for faster lookups
    op.create_index(
        'ix_market_metrics_date_type',
        'market_metrics',
        ['metric_date', 'metric_type']
    )

def downgrade() -> None:
    op.drop_index('ix_market_metrics_date_type')
    op.drop_table('market_metrics') 