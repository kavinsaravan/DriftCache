"""add training and model versioning tables

Revision ID: 009
Revises: 008
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    """Add training_pairs, training_jobs, and model_versions tables"""

    # Create training_pairs table
    op.create_table(
        'training_pairs',
        sa.Column('id', sa.Integer(), nullable=False),

        # Texts
        sa.Column('anchor_text', sa.Text(), nullable=False),
        sa.Column('comparison_text', sa.Text(), nullable=False),

        # Pair metadata
        sa.Column('pair_type', sa.String(length=50), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),

        # Source information
        sa.Column('anchor_cache_id', sa.String(length=36), nullable=True),
        sa.Column('comparison_cache_id', sa.String(length=36), nullable=True),

        # Data quality
        sa.Column('is_validated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quality_score', sa.Float(), nullable=True),

        # Training metadata
        sa.Column('used_in_training', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Constraints
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_training_pairs_pair_type', 'training_pairs', ['pair_type'])
    op.create_index('ix_training_pairs_anchor_cache_id', 'training_pairs', ['anchor_cache_id'])
    op.create_index('ix_training_pairs_comparison_cache_id', 'training_pairs', ['comparison_cache_id'])

    # Create training_jobs table
    op.create_table(
        'training_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False, unique=True),

        # Job metadata
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('base_model', sa.String(length=100), nullable=False),
        sa.Column('output_model_name', sa.String(length=100), nullable=True),

        # Training configuration
        sa.Column('training_config', JSON, nullable=True),

        # Dataset info
        sa.Column('num_training_pairs', sa.Integer(), nullable=True),
        sa.Column('num_positive_pairs', sa.Integer(), nullable=True),
        sa.Column('num_negative_pairs', sa.Integer(), nullable=True),

        # Training metrics
        sa.Column('final_loss', sa.Float(), nullable=True),
        sa.Column('num_epochs_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('training_time_seconds', sa.Float(), nullable=True),

        # Evaluation metrics
        sa.Column('eval_metrics', JSON, nullable=True),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_training_jobs_job_id', 'training_jobs', ['job_id'])
    op.create_index('ix_training_jobs_status', 'training_jobs', ['status'])

    # Create model_versions table
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.String(length=50), nullable=False, unique=True),

        # Model identification
        sa.Column('model_name', sa.String(length=200), nullable=False),
        sa.Column('base_model', sa.String(length=100), nullable=False),
        sa.Column('is_finetuned', sa.Boolean(), nullable=False, server_default='0'),

        # Training info
        sa.Column('training_job_id', sa.String(length=36), nullable=True),
        sa.Column('huggingface_url', sa.String(length=500), nullable=True),

        # Performance metrics
        sa.Column('performance_metrics', JSON, nullable=True),

        # A/B testing
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('traffic_percentage', sa.Float(), nullable=False, server_default='0.0'),

        # Model metadata
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('model_size_mb', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),

        # Deployment info
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Constraints
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_model_versions_version_id', 'model_versions', ['version_id'])
    op.create_index('ix_model_versions_training_job_id', 'model_versions', ['training_job_id'])


def downgrade():
    """Remove training tables"""

    # Drop indexes
    op.drop_index('ix_model_versions_training_job_id', 'model_versions')
    op.drop_index('ix_model_versions_version_id', 'model_versions')
    op.drop_index('ix_training_jobs_status', 'training_jobs')
    op.drop_index('ix_training_jobs_job_id', 'training_jobs')
    op.drop_index('ix_training_pairs_comparison_cache_id', 'training_pairs')
    op.drop_index('ix_training_pairs_anchor_cache_id', 'training_pairs')
    op.drop_index('ix_training_pairs_pair_type', 'training_pairs')

    # Drop tables
    op.drop_table('model_versions')
    op.drop_table('training_jobs')
    op.drop_table('training_pairs')
