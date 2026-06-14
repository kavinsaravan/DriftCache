"""add index rebuild infrastructure

Revision ID: 007
Revises: 006
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """Add index_rebuild_jobs table and enhance index_versions"""

    # Create index_rebuild_jobs table
    op.create_table(
        'index_rebuild_jobs',
        sa.Column('id', sa.Integer(), nullable=False),

        # Job metadata
        sa.Column('job_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('trigger_source', sa.String(length=50), nullable=False),

        # Index versions
        sa.Column('old_index_version_id', sa.Integer(), nullable=True),
        sa.Column('new_index_version_id', sa.Integer(), nullable=True),
        sa.Column('old_index_version', sa.String(length=100), nullable=True),
        sa.Column('new_index_version', sa.String(length=100), nullable=True),

        # Health metrics before rebuild
        sa.Column('old_vector_count', sa.Integer(), nullable=True),
        sa.Column('active_cache_count', sa.Integer(), nullable=True),
        sa.Column('stale_vector_ratio', sa.Float(), nullable=True),
        sa.Column('avg_search_latency_ms', sa.Float(), nullable=True),
        sa.Column('index_age_hours', sa.Float(), nullable=True),

        # Rebuild results
        sa.Column('new_vector_count', sa.Integer(), nullable=True),
        sa.Column('vectors_added', sa.Integer(), nullable=True),
        sa.Column('vectors_removed', sa.Integer(), nullable=True),
        sa.Column('rebuild_duration_ms', sa.Float(), nullable=True),

        # Validation results
        sa.Column('validation_passed', sa.String(length=50), nullable=True),
        sa.Column('validation_details', JSON, nullable=True),
        sa.Column('search_latency_after_ms', sa.Float(), nullable=True),
        sa.Column('search_quality_score', sa.Float(), nullable=True),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', JSON, nullable=True),

        # File paths
        sa.Column('old_index_path', sa.String(length=500), nullable=True),
        sa.Column('new_index_path', sa.String(length=500), nullable=True),
        sa.Column('backup_path', sa.String(length=500), nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for index_rebuild_jobs
    op.create_index('ix_index_rebuild_jobs_job_id', 'index_rebuild_jobs', ['job_id'])
    op.create_index('ix_index_rebuild_jobs_status', 'index_rebuild_jobs', ['status'])
    op.create_index('ix_index_rebuild_jobs_tenant_id', 'index_rebuild_jobs', ['tenant_id'])
    op.create_index('ix_index_rebuild_jobs_created_at', 'index_rebuild_jobs', ['created_at'])

    # Enhance index_versions table with rebuild tracking
    op.add_column('index_versions', sa.Column('rebuild_job_id', sa.Integer(), nullable=True))
    op.add_column('index_versions', sa.Column('file_path', sa.String(length=500), nullable=True))
    op.add_column('index_versions', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('index_versions', sa.Column('tenant_id', sa.String(length=100), nullable=True))

    # Create index for tenant_id on index_versions
    op.create_index('ix_index_versions_tenant_id', 'index_versions', ['tenant_id'])


def downgrade():
    """Remove index rebuild infrastructure"""

    # Drop index for tenant_id on index_versions
    op.drop_index('ix_index_versions_tenant_id', table_name='index_versions')

    # Remove columns from index_versions
    op.drop_column('index_versions', 'tenant_id')
    op.drop_column('index_versions', 'is_active')
    op.drop_column('index_versions', 'file_path')
    op.drop_column('index_versions', 'rebuild_job_id')

    # Drop indexes for index_rebuild_jobs
    op.drop_index('ix_index_rebuild_jobs_created_at', table_name='index_rebuild_jobs')
    op.drop_index('ix_index_rebuild_jobs_tenant_id', table_name='index_rebuild_jobs')
    op.drop_index('ix_index_rebuild_jobs_status', table_name='index_rebuild_jobs')
    op.drop_index('ix_index_rebuild_jobs_job_id', table_name='index_rebuild_jobs')

    # Drop index_rebuild_jobs table
    op.drop_table('index_rebuild_jobs')
