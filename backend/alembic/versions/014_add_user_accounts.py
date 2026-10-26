"""Add user accounts, expiring sessions and project ownership.

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("user_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_table("auth_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_attempts_client_hash", "auth_attempts", ["client_hash"])
    op.create_index("ix_auth_attempts_created_at", "auth_attempts", ["created_at"])
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_projects_owner_id", "users", ["owner_id"], ["id"])
        batch.create_index("ix_projects_owner_id", ["owner_id"])


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_index("ix_projects_owner_id")
        batch.drop_constraint("fk_projects_owner_id", type_="foreignkey")
        batch.drop_column("owner_id")
    op.drop_table("auth_attempts")
    op.drop_table("user_sessions")
    op.drop_table("users")
