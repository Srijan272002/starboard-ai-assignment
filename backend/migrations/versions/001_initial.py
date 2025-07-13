"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-03-19 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create addresses table
    op.create_table(
        'addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('street', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('state', sa.String(2), nullable=False),
        sa.Column('postal_code', sa.String(10), nullable=False),
        sa.Column('country', sa.String(2), nullable=False, server_default='US'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create property_metrics table
    op.create_table(
        'property_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('square_footage', sa.Float(), nullable=False),
        sa.Column('lot_size', sa.Float(), nullable=False),
        sa.Column('year_built', sa.Integer(), nullable=True),
        sa.Column('bedrooms', sa.Integer(), nullable=True),
        sa.Column('bathrooms', sa.Float(), nullable=True),
        sa.Column('parking_spaces', sa.Integer(), nullable=True),
        sa.Column('additional_features', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create property_financials table
    op.create_table(
        'property_financials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('list_price', sa.Float(), nullable=True),
        sa.Column('sale_price', sa.Float(), nullable=True),
        sa.Column('last_sale_date', sa.Date(), nullable=True),
        sa.Column('estimated_value', sa.Float(), nullable=True),
        sa.Column('annual_tax', sa.Float(), nullable=True),
        sa.Column('monthly_hoa', sa.Float(), nullable=True),
        sa.Column('rental_estimate', sa.Float(), nullable=True),
        sa.Column('additional_fees', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create properties table
    op.create_table(
        'properties',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('property_type', sa.Enum('RESIDENTIAL', 'COMMERCIAL', 'INDUSTRIAL', 'LAND', name='propertytype'), nullable=False),
        sa.Column('zoning_type', sa.Enum('RESIDENTIAL', 'COMMERCIAL', 'INDUSTRIAL', 'MIXED', 'AGRICULTURAL', name='zoningtype'), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('address_id', sa.Integer(), nullable=False),
        sa.Column('metrics_id', sa.Integer(), nullable=False),
        sa.Column('financials_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['address_id'], ['addresses.id'], ),
        sa.ForeignKeyConstraint(['metrics_id'], ['property_metrics.id'], ),
        sa.ForeignKeyConstraint(['financials_id'], ['property_financials.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create data_versions table
    op.create_table(
        'data_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=False),
        sa.Column('user', sa.String(), nullable=True),
        sa.Column('comment', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_properties_type', 'properties', ['property_type'])
    op.create_index('idx_properties_zoning', 'properties', ['zoning_type'])
    op.create_index('idx_properties_location', 'properties', ['latitude', 'longitude'])
    op.create_index('idx_addresses_postal', 'addresses', ['postal_code'])
    op.create_index('idx_addresses_state', 'addresses', ['state'])
    op.create_index('idx_financials_value', 'property_financials', ['estimated_value'])
    op.create_index('idx_versions_entity', 'data_versions', ['entity_type', 'entity_id'])

def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_versions_entity')
    op.drop_index('idx_financials_value')
    op.drop_index('idx_addresses_state')
    op.drop_index('idx_addresses_postal')
    op.drop_index('idx_properties_location')
    op.drop_index('idx_properties_zoning')
    op.drop_index('idx_properties_type')

    # Drop tables
    op.drop_table('data_versions')
    op.drop_table('properties')
    op.drop_table('property_financials')
    op.drop_table('property_metrics')
    op.drop_table('addresses')

    # Drop enums
    op.execute('DROP TYPE propertytype')
    op.execute('DROP TYPE zoningtype') 