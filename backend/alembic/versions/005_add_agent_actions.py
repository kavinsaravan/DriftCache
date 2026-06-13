"""add agent actions table

Revision ID: 005
Revises: 004
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """Create agent_actions table for autonomous workflow tracking"""
    op.create_table(
        'agent_actions',
        sa.Column('id', sa.Integer(), nullable=False),

        # Workflow metadata
        sa.Column('workflow_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('workflow_status', sa.String(length=50), nullable=False),
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),

        # System state at decision time
        sa.Column('current_threshold', sa.Float(), nullable=True),
        sa.Column('cache_hit_rate', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('recall', sa.Float(), nullable=True),
        sa.Column('false_hit_rate', sa.Float(), nullable=True),
        sa.Column('false_miss_rate', sa.Float(), nullable=True),

        # Analysis results
        sa.Column('drift_severity', sa.String(length=50), nullable=True),
        sa.Column('drift_score', sa.Float(), nullable=True),
        sa.Column('quality_acceptable', sa.Boolean(), nullable=True),

        # Decision
        sa.Column('decision', sa.String(length=100), nullable=False),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('decision_confidence', sa.Float(), nullable=True),

        # Action taken
        sa.Column('action_taken', sa.String(length=200), nullable=True),
        sa.Column('old_threshold', sa.Float(), nullable=True),
        sa.Column('new_threshold', sa.Float(), nullable=True),
        sa.Column('action_result', JSON, nullable=True),

        # Validation
        sa.Column('validation_passed', sa.Boolean(), nullable=True),
        sa.Column('validation_summary', sa.Text(), nullable=True),
        sa.Column('validation_result', JSON, nullable=True),

        # Report
        sa.Column('report_summary', sa.Text(), nullable=True),
        sa.Column('errors', JSON, nullable=True),
        sa.Column('warnings', JSON, nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index('ix_agent_actions_workflow_id', 'agent_actions', ['workflow_id'])
    op.create_index('ix_agent_actions_workflow_status', 'agent_actions', ['workflow_status'])
    op.create_index('ix_agent_actions_trigger_type', 'agent_actions', ['trigger_type'])
    op.create_index('ix_agent_actions_drift_severity', 'agent_actions', ['drift_severity'])
    op.create_index('ix_agent_actions_decision', 'agent_actions', ['decision'])
    op.create_index('ix_agent_actions_tenant_id', 'agent_actions', ['tenant_id'])
    op.create_index('ix_agent_actions_created_at', 'agent_actions', ['created_at'])


def downgrade():
    """Drop agent_actions table"""
    op.drop_index('ix_agent_actions_created_at', table_name='agent_actions')
    op.drop_index('ix_agent_actions_tenant_id', table_name='agent_actions')
    op.drop_index('ix_agent_actions_decision', table_name='agent_actions')
    op.drop_index('ix_agent_actions_drift_severity', table_name='agent_actions')
    op.drop_index('ix_agent_actions_trigger_type', table_name='agent_actions')
    op.drop_index('ix_agent_actions_workflow_status', table_name='agent_actions')
    op.drop_index('ix_agent_actions_workflow_id', table_name='agent_actions')
    op.drop_table('agent_actions')
