"""Replace autonomous agent orchestration with similarity drift monitoring.

Revision ID: 011
Revises: 010
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drift_alerts") as batch_op:
        batch_op.add_column(sa.Column("wasserstein_distance", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "drift_detected",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("reasons", sa.JSON(), nullable=True))
        batch_op.create_index("ix_drift_alerts_drift_detected", ["drift_detected"])

    op.execute(
        sa.text(
            "UPDATE drift_alerts SET drift_detected = "
            "CASE WHEN drift_score >= 0.5 THEN true ELSE false END"
        )
    )

    op.drop_table("supervisor_runs")
    op.drop_table("agent_actions")


def downgrade():
    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("workflow_status", sa.String(length=50), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        sa.Column("current_threshold", sa.Float(), nullable=True),
        sa.Column("cache_hit_rate", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("false_hit_rate", sa.Float(), nullable=True),
        sa.Column("false_miss_rate", sa.Float(), nullable=True),
        sa.Column("drift_severity", sa.String(length=50), nullable=True),
        sa.Column("drift_score", sa.Float(), nullable=True),
        sa.Column("quality_acceptable", sa.Boolean(), nullable=True),
        sa.Column("decision", sa.String(length=100), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decision_confidence", sa.Float(), nullable=True),
        sa.Column("action_taken", sa.String(length=200), nullable=True),
        sa.Column("old_threshold", sa.Float(), nullable=True),
        sa.Column("new_threshold", sa.Float(), nullable=True),
        sa.Column("action_result", sa.JSON(), nullable=True),
        sa.Column("validation_passed", sa.Boolean(), nullable=True),
        sa.Column("validation_summary", sa.Text(), nullable=True),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("report_summary", sa.Text(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("tenant_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_agent_actions_workflow_id", "workflow_id"),
        ("ix_agent_actions_workflow_status", "workflow_status"),
        ("ix_agent_actions_trigger_type", "trigger_type"),
        ("ix_agent_actions_drift_severity", "drift_severity"),
        ("ix_agent_actions_decision", "decision"),
        ("ix_agent_actions_tenant_id", "tenant_id"),
        ("ix_agent_actions_created_at", "created_at"),
    ):
        op.create_index(name, "agent_actions", [column])

    op.create_table(
        "supervisor_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("trigger_source", sa.String(length=50), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("initial_drift_score", sa.Float(), nullable=True),
        sa.Column("initial_drift_severity", sa.String(length=50), nullable=True),
        sa.Column("initial_precision", sa.Float(), nullable=True),
        sa.Column("initial_recall", sa.Float(), nullable=True),
        sa.Column("initial_false_hit_rate", sa.Float(), nullable=True),
        sa.Column("initial_cache_hit_rate", sa.Float(), nullable=True),
        sa.Column("initial_stale_vector_ratio", sa.Float(), nullable=True),
        sa.Column("diagnosis", sa.String(length=100), nullable=False),
        sa.Column("diagnosis_details", sa.JSON(), nullable=True),
        sa.Column("decision_path", sa.JSON(), nullable=True),
        sa.Column("actions_taken", sa.JSON(), nullable=True),
        sa.Column("threshold_optimizer_run_id", sa.Integer(), nullable=True),
        sa.Column("cache_invalidation_count", sa.Integer(), nullable=True),
        sa.Column("final_precision", sa.Float(), nullable=True),
        sa.Column("final_recall", sa.Float(), nullable=True),
        sa.Column("final_false_hit_rate", sa.Float(), nullable=True),
        sa.Column("final_drift_score", sa.Float(), nullable=True),
        sa.Column("validation_passed", sa.String(length=50), nullable=True),
        sa.Column("validation_details", sa.JSON(), nullable=True),
        sa.Column("final_status", sa.String(length=50), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("report_summary", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("total_execution_time_ms", sa.Float(), nullable=True),
        sa.Column("agents_invoked_count", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_supervisor_runs_run_id", "run_id"),
        ("ix_supervisor_runs_final_status", "final_status"),
        ("ix_supervisor_runs_tenant_id", "tenant_id"),
        ("ix_supervisor_runs_created_at", "created_at"),
    ):
        op.create_index(name, "supervisor_runs", [column])

    with op.batch_alter_table("drift_alerts") as batch_op:
        batch_op.drop_index("ix_drift_alerts_drift_detected")
        batch_op.drop_column("reasons")
        batch_op.drop_column("drift_detected")
        batch_op.drop_column("wasserstein_distance")
