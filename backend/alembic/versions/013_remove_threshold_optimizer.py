"""Remove the disconnected threshold optimizer.

Revision ID: 013
Revises: 012
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("threshold_versions", "optimization_run_id")
    op.drop_table("optimization_runs")


def downgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("trigger_source", sa.String(length=50), nullable=False),
        sa.Column("old_threshold", sa.Float(), nullable=False),
        sa.Column("precision_before", sa.Float(), nullable=True),
        sa.Column("recall_before", sa.Float(), nullable=True),
        sa.Column("false_hit_rate_before", sa.Float(), nullable=True),
        sa.Column("false_miss_rate_before", sa.Float(), nullable=True),
        sa.Column("f1_score_before", sa.Float(), nullable=True),
        sa.Column("new_threshold", sa.Float(), nullable=False),
        sa.Column("precision_after_estimate", sa.Float(), nullable=True),
        sa.Column("recall_after_estimate", sa.Float(), nullable=True),
        sa.Column("false_hit_rate_after_estimate", sa.Float(), nullable=True),
        sa.Column("false_miss_rate_after_estimate", sa.Float(), nullable=True),
        sa.Column("f1_score_after_estimate", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("optimization_score", sa.Float(), nullable=True),
        sa.Column("candidates_tested", sa.JSON(), nullable=True),
        sa.Column("candidate_scores", sa.JSON(), nullable=True),
        sa.Column("precision_weight", sa.Float(), nullable=True),
        sa.Column("recall_weight", sa.Float(), nullable=True),
        sa.Column("cost_weight", sa.Float(), nullable=True),
        sa.Column("latency_weight", sa.Float(), nullable=True),
        sa.Column("dataset_name", sa.String(length=100), nullable=True),
        sa.Column("dataset_size", sa.Integer(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        sa.Column("constraints_applied", sa.JSON(), nullable=True),
        sa.Column("tenant_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_runs_run_id", "optimization_runs", ["run_id"])
    op.create_index("ix_optimization_runs_tenant_id", "optimization_runs", ["tenant_id"])
    op.create_index("ix_optimization_runs_created_at", "optimization_runs", ["created_at"])
    op.add_column(
        "threshold_versions",
        sa.Column("optimization_run_id", sa.Integer(), nullable=True),
    )
