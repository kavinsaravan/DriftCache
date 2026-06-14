"""add supervisor orchestration

Revision ID: 008
Revises: 007
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """Add supervisor_runs table"""

    op.create_table(
        'supervisor_runs',
        sa.Column('id', sa.Integer(), nullable=False),

        # Run metadata
        sa.Column('run_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('trigger_source', sa.String(length=50), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),

        # Initial system state
        sa.Column('initial_drift_score', sa.Float(), nullable=True),
        sa.Column('initial_drift_severity', sa.String(length=50), nullable=True),
        sa.Column('initial_precision', sa.Float(), nullable=True),
        sa.Column('initial_recall', sa.Float(), nullable=True),
        sa.Column('initial_false_hit_rate', sa.Float(), nullable=True),
        sa.Column('initial_cache_hit_rate', sa.Float(), nullable=True),
        sa.Column('initial_stale_vector_ratio', sa.Float(), nullable=True),

        # Diagnosis
        sa.Column('diagnosis', sa.String(length=100), nullable=False),
        sa.Column('diagnosis_details', JSON, nullable=True),

        # Decision path
        sa.Column('decision_path', JSON, nullable=True),
        sa.Column('actions_taken', JSON, nullable=True),

        # Agents invoked
        sa.Column('threshold_optimizer_run_id', sa.Integer(), nullable=True),
        sa.Column('index_rebuild_job_id', sa.Integer(), nullable=True),
        sa.Column('cache_invalidation_count', sa.Integer(), nullable=True),

        # Final system state
        sa.Column('final_precision', sa.Float(), nullable=True),
        sa.Column('final_recall', sa.Float(), nullable=True),
        sa.Column('final_false_hit_rate', sa.Float(), nullable=True),
        sa.Column('final_drift_score', sa.Float(), nullable=True),

        # Validation
        sa.Column('validation_passed', sa.String(length=50), nullable=True),
        sa.Column('validation_details', JSON, nullable=True),

        # Status
        sa.Column('final_status', sa.String(length=50), nullable=False),
        sa.Column('status_reason', sa.Text(), nullable=True),

        # Report
        sa.Column('report_summary', sa.Text(), nullable=True),
        sa.Column('recommendations', JSON, nullable=True),

        # Execution metrics
        sa.Column('total_execution_time_ms', sa.Float(), nullable=True),
        sa.Column('agents_invoked_count', sa.Integer(), nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_supervisor_runs_run_id', 'supervisor_runs', ['run_id'])
    op.create_index('ix_supervisor_runs_final_status', 'supervisor_runs', ['final_status'])
    op.create_index('ix_supervisor_runs_tenant_id', 'supervisor_runs', ['tenant_id'])
    op.create_index('ix_supervisor_runs_created_at', 'supervisor_runs', ['created_at'])


def downgrade():
    """Remove supervisor_runs table"""

    op.drop_index('ix_supervisor_runs_created_at', table_name='supervisor_runs')
    op.drop_index('ix_supervisor_runs_tenant_id', table_name='supervisor_runs')
    op.drop_index('ix_supervisor_runs_final_status', table_name='supervisor_runs')
    op.drop_index('ix_supervisor_runs_run_id', table_name='supervisor_runs')
    op.drop_table('supervisor_runs')
