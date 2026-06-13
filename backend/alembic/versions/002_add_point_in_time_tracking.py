"""Add point-in-time tracking

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create index_versions table
    op.create_table(
        'index_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_name', sa.String(length=100), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False),
        sa.Column('index_type', sa.String(length=50), nullable=False),
        sa.Column('vector_count', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('active_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_index_versions_version_name'), 'index_versions', ['version_name'], unique=True)
    op.create_index(op.f('ix_index_versions_active_from'), 'index_versions', ['active_from'], unique=False)
    op.create_index(op.f('ix_index_versions_active_until'), 'index_versions', ['active_until'], unique=False)

    # Add new columns to cache_events for point-in-time tracking
    op.add_column('cache_events', sa.Column('embedding_model', sa.String(length=100), nullable=True))
    op.add_column('cache_events', sa.Column('index_version_id', sa.Integer(), nullable=True))
    op.add_column('cache_events', sa.Column('provider_model', sa.String(length=100), nullable=True))

    # Add indexes for new columns
    op.create_index(op.f('ix_cache_events_embedding_model'), 'cache_events', ['embedding_model'], unique=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index(op.f('ix_cache_events_embedding_model'), table_name='cache_events')

    # Remove columns from cache_events
    op.drop_column('cache_events', 'provider_model')
    op.drop_column('cache_events', 'index_version_id')
    op.drop_column('cache_events', 'embedding_model')

    # Drop index_versions table
    op.drop_table('index_versions')
