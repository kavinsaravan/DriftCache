"""add drift alerts table

Revision ID: 003
Revises: 002
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Create drift_alerts table"""
    op.create_table(
        'drift_alerts',
        sa.Column('id', sa.Integer(), nullable=False),

        # Overall drift assessment
        sa.Column('drift_score', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),

        # Statistical signals
        sa.Column('centroid_shift', sa.Float(), nullable=False),
        sa.Column('variance_shift', sa.Float(), nullable=False),
        sa.Column('ks_p_value', sa.Float(), nullable=True),

        # Similarity metrics
        sa.Column('avg_similarity_recent', sa.Float(), nullable=True),
        sa.Column('avg_similarity_reference', sa.Float(), nullable=True),
        sa.Column('similarity_drop', sa.Float(), nullable=True),

        # Cache performance correlation
        sa.Column('cache_hit_rate_recent', sa.Float(), nullable=True),
        sa.Column('cache_hit_rate_reference', sa.Float(), nullable=True),
        sa.Column('hit_rate_drop', sa.Float(), nullable=True),

        # Window metadata
        sa.Column('reference_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reference_window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reference_sample_size', sa.Integer(), nullable=False),
        sa.Column('recent_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recent_window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recent_sample_size', sa.Integer(), nullable=False),

        # Recommendations
        sa.Column('recommended_action', sa.String(length=100), nullable=True),
        sa.Column('action_details', sa.Text(), nullable=True),

        # Alert lifecycle
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_drift_alerts_drift_score', 'drift_alerts', ['drift_score'])
    op.create_index('ix_drift_alerts_severity', 'drift_alerts', ['severity'])
    op.create_index('ix_drift_alerts_is_resolved', 'drift_alerts', ['is_resolved'])
    op.create_index('ix_drift_alerts_tenant_id', 'drift_alerts', ['tenant_id'])
    op.create_index('ix_drift_alerts_created_at', 'drift_alerts', ['created_at'])


def downgrade():
    """Drop drift_alerts table"""
    op.drop_index('ix_drift_alerts_created_at', table_name='drift_alerts')
    op.drop_index('ix_drift_alerts_tenant_id', table_name='drift_alerts')
    op.drop_index('ix_drift_alerts_is_resolved', table_name='drift_alerts')
    op.drop_index('ix_drift_alerts_severity', table_name='drift_alerts')
    op.drop_index('ix_drift_alerts_drift_score', table_name='drift_alerts')
    op.drop_table('drift_alerts')
