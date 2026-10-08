"""Remove the retired simulated index-rebuild job schema.

Revision ID: 010
Revises: 009
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    """Drop the unused rebuild table and its orphaned references."""
    with op.batch_alter_table("supervisor_runs") as batch_op:
        batch_op.drop_column("index_rebuild_job_id")

    with op.batch_alter_table("index_versions") as batch_op:
        batch_op.drop_column("rebuild_job_id")

    op.drop_table("index_rebuild_jobs")


def downgrade():
    """Restore the retired schema for migration rollback."""
    op.create_table(
        "index_rebuild_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("trigger_source", sa.String(length=50), nullable=False),
        sa.Column("old_index_version_id", sa.Integer(), nullable=True),
        sa.Column("new_index_version_id", sa.Integer(), nullable=True),
        sa.Column("old_index_version", sa.String(length=100), nullable=True),
        sa.Column("new_index_version", sa.String(length=100), nullable=True),
        sa.Column("old_vector_count", sa.Integer(), nullable=True),
        sa.Column("active_cache_count", sa.Integer(), nullable=True),
        sa.Column("stale_vector_ratio", sa.Float(), nullable=True),
        sa.Column("avg_search_latency_ms", sa.Float(), nullable=True),
        sa.Column("index_age_hours", sa.Float(), nullable=True),
        sa.Column("new_vector_count", sa.Integer(), nullable=True),
        sa.Column("vectors_added", sa.Integer(), nullable=True),
        sa.Column("vectors_removed", sa.Integer(), nullable=True),
        sa.Column("rebuild_duration_ms", sa.Float(), nullable=True),
        sa.Column("validation_passed", sa.String(length=50), nullable=True),
        sa.Column("validation_details", sa.JSON(), nullable=True),
        sa.Column("search_latency_after_ms", sa.Float(), nullable=True),
        sa.Column("search_quality_score", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("old_index_path", sa.String(length=500), nullable=True),
        sa.Column("new_index_path", sa.String(length=500), nullable=True),
        sa.Column("backup_path", sa.String(length=500), nullable=True),
        sa.Column("tenant_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_index_rebuild_jobs_job_id", "index_rebuild_jobs", ["job_id"])
    op.create_index("ix_index_rebuild_jobs_status", "index_rebuild_jobs", ["status"])
    op.create_index("ix_index_rebuild_jobs_tenant_id", "index_rebuild_jobs", ["tenant_id"])
    op.create_index("ix_index_rebuild_jobs_created_at", "index_rebuild_jobs", ["created_at"])

    with op.batch_alter_table("index_versions") as batch_op:
        batch_op.add_column(sa.Column("rebuild_job_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("supervisor_runs") as batch_op:
        batch_op.add_column(sa.Column("index_rebuild_job_id", sa.Integer(), nullable=True))
