"""add evaluation results table

Revision ID: 004
Revises: 003
Create Date: 2024-06-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Create evaluation_results table"""
    op.create_table(
        'evaluation_results',
        sa.Column('id', sa.Integer(), nullable=False),

        # Evaluation metadata
        sa.Column('evaluation_run_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('dataset_name', sa.String(length=100), nullable=False),
        sa.Column('dataset_size', sa.Integer(), nullable=False),

        # Cache configuration at time of evaluation
        sa.Column('threshold_used', sa.Float(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('index_version', sa.String(length=100), nullable=True),

        # Core metrics
        sa.Column('precision', sa.Float(), nullable=False),
        sa.Column('recall', sa.Float(), nullable=False),
        sa.Column('f1_score', sa.Float(), nullable=False),

        # Error rates
        sa.Column('false_hit_rate', sa.Float(), nullable=False),
        sa.Column('false_miss_rate', sa.Float(), nullable=False),

        # Detailed counts
        sa.Column('total_test_cases', sa.Integer(), nullable=False),
        sa.Column('true_positives', sa.Integer(), nullable=False),
        sa.Column('true_negatives', sa.Integer(), nullable=False),
        sa.Column('false_positives', sa.Integer(), nullable=False),
        sa.Column('false_negatives', sa.Integer(), nullable=False),

        # Hit quality metrics
        sa.Column('avg_hit_margin', sa.Float(), nullable=True),
        sa.Column('avg_hit_similarity', sa.Float(), nullable=True),
        sa.Column('min_hit_similarity', sa.Float(), nullable=True),
        sa.Column('max_hit_similarity', sa.Float(), nullable=True),

        # Miss analysis
        sa.Column('avg_miss_similarity', sa.Float(), nullable=True),
        sa.Column('near_miss_count', sa.Integer(), nullable=True),

        # Recommendation
        sa.Column('recommended_action', sa.String(length=100), nullable=True),
        sa.Column('recommendation_confidence', sa.Float(), nullable=True),
        sa.Column('recommendation_details', sa.Text(), nullable=True),

        # Performance impact estimates
        sa.Column('estimated_cost_impact', sa.Float(), nullable=True),
        sa.Column('estimated_quality_impact', sa.Float(), nullable=True),

        # Evaluation execution
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('evaluation_type', sa.String(length=50), nullable=False, server_default='rule_based'),

        # Status
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),

        # Tenant isolation
        sa.Column('tenant_id', sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_evaluation_results_evaluation_run_id', 'evaluation_results', ['evaluation_run_id'])
    op.create_index('ix_evaluation_results_dataset_name', 'evaluation_results', ['dataset_name'])
    op.create_index('ix_evaluation_results_threshold_used', 'evaluation_results', ['threshold_used'])
    op.create_index('ix_evaluation_results_tenant_id', 'evaluation_results', ['tenant_id'])
    op.create_index('ix_evaluation_results_created_at', 'evaluation_results', ['created_at'])


def downgrade():
    """Drop evaluation_results table"""
    op.drop_index('ix_evaluation_results_created_at', table_name='evaluation_results')
    op.drop_index('ix_evaluation_results_tenant_id', table_name='evaluation_results')
    op.drop_index('ix_evaluation_results_threshold_used', table_name='evaluation_results')
    op.drop_index('ix_evaluation_results_dataset_name', table_name='evaluation_results')
    op.drop_index('ix_evaluation_results_evaluation_run_id', table_name='evaluation_results')
    op.drop_table('evaluation_results')
