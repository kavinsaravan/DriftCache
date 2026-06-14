"""add threshold optimization tables

Revision ID: 006
Revises: 005
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add optimization_runs table and enhance threshold_versions"""

    # Create optimization_runs table
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.Integer(), nullable=False),

        # Run metadata
        sa.Column('run_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('trigger_source', sa.String(length=50), nullable=False),

        # Current state before optimization
        sa.Column('old_threshold', sa.Float(), nullable=False),
        sa.Column('precision_before', sa.Float(), nullable=True),
        sa.Column('recall_before', sa.Float(), nullable=True),
        sa.Column('false_hit_rate_before', sa.Float(), nullable=True),
        sa.Column('false_miss_rate_before', sa.Float(), nullable=True),
        sa.Column('f1_score_before', sa.Float(), nullable=True),

        # Optimization result
        sa.Column('new_threshold', sa.Float(), nullable=False),
        sa.Column('precision_after_estimate', sa.Float(), nullable=True),
        sa.Column('recall_after_estimate', sa.Float(), nullable=True),
        sa.Column('false_hit_rate_after_estimate', sa.Float(), nullable=True),
        sa.Column('false_miss_rate_after_estimate', sa.Float(), nullable=True),
        sa.Column('f1_score_after_estimate', sa.Float(), nullable=True),

        # Decision
        sa.Column('decision', sa.String(length=50), nullable=False),
        sa.Column('decision_reason', sa.Text(), nullable=False),
        sa.Column('optimization_score', sa.Float(), nullable=True),

        # Candidates tested
        sa.Column('candidates_tested', JSON, nullable=True),
        sa.Column('candidate_scores', JSON, nullable=True),

        # Scoring weights used
        sa.Column('precision_weight', sa.Float(), nullable=True),
        sa.Column('recall_weight', sa.Float(), nullable=True),
        sa.Column('cost_weight', sa.Float(), nullable=True),
        sa.Column('latency_weight', sa.Float(), nullable=True),

        # Execution details
        sa.Column('dataset_name', sa.String(length=100), nullable=True),
        sa.Column('dataset_size', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),

        # Safety constraints applied
        sa.Column('constraints_applied', JSON, nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for optimization_runs
    op.create_index('ix_optimization_runs_run_id', 'optimization_runs', ['run_id'])
    op.create_index('ix_optimization_runs_tenant_id', 'optimization_runs', ['tenant_id'])
    op.create_index('ix_optimization_runs_created_at', 'optimization_runs', ['created_at'])

    # Enhance threshold_versions table with optimization tracking
    op.add_column('threshold_versions', sa.Column('old_threshold', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('optimization_run_id', sa.Integer(), nullable=True))
    op.add_column('threshold_versions', sa.Column('precision_before', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('recall_before', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('false_hit_rate_before', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('false_miss_rate_before', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('precision_after_estimate', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('recall_after_estimate', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('false_hit_rate_after_estimate', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('false_miss_rate_after_estimate', sa.Float(), nullable=True))
    op.add_column('threshold_versions', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('threshold_versions', sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('threshold_versions', sa.Column('tenant_id', sa.String(length=100), nullable=True))

    # Create index for tenant_id on threshold_versions
    op.create_index('ix_threshold_versions_tenant_id', 'threshold_versions', ['tenant_id'])


def downgrade():
    """Remove threshold optimization tables"""

    # Drop indexes for threshold_versions
    op.drop_index('ix_threshold_versions_tenant_id', table_name='threshold_versions')

    # Remove columns from threshold_versions
    op.drop_column('threshold_versions', 'tenant_id')
    op.drop_column('threshold_versions', 'deployed_at')
    op.drop_column('threshold_versions', 'is_active')
    op.drop_column('threshold_versions', 'false_miss_rate_after_estimate')
    op.drop_column('threshold_versions', 'false_hit_rate_after_estimate')
    op.drop_column('threshold_versions', 'recall_after_estimate')
    op.drop_column('threshold_versions', 'precision_after_estimate')
    op.drop_column('threshold_versions', 'false_miss_rate_before')
    op.drop_column('threshold_versions', 'false_hit_rate_before')
    op.drop_column('threshold_versions', 'recall_before')
    op.drop_column('threshold_versions', 'precision_before')
    op.drop_column('threshold_versions', 'optimization_run_id')
    op.drop_column('threshold_versions', 'old_threshold')

    # Drop indexes for optimization_runs
    op.drop_index('ix_optimization_runs_created_at', table_name='optimization_runs')
    op.drop_index('ix_optimization_runs_tenant_id', table_name='optimization_runs')
    op.drop_index('ix_optimization_runs_run_id', table_name='optimization_runs')

    # Drop optimization_runs table
    op.drop_table('optimization_runs')
