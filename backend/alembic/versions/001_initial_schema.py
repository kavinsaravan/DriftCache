"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create requests table
    op.create_table(
        'requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('stream', sa.Boolean(), nullable=True),
        sa.Column('messages_json', sa.JSON(), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('prompt_hash', sa.String(length=64), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requests_request_id'), 'requests', ['request_id'], unique=True)
    op.create_index(op.f('ix_requests_tenant_id'), 'requests', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_requests_model'), 'requests', ['model'], unique=False)
    op.create_index(op.f('ix_requests_prompt_hash'), 'requests', ['prompt_hash'], unique=False)
    op.create_index(op.f('ix_requests_user_id'), 'requests', ['user_id'], unique=False)

    # Create cache_entries table
    op.create_table(
        'cache_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_id', sa.String(length=36), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('prompt_hash', sa.String(length=64), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('system_prompt_hash', sa.String(length=64), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('tenant_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('request_params', sa.JSON(), nullable=True),
        sa.Column('cache_hits', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cache_entries_cache_id'), 'cache_entries', ['cache_id'], unique=True)
    op.create_index(op.f('ix_cache_entries_prompt_hash'), 'cache_entries', ['prompt_hash'], unique=False)
    op.create_index(op.f('ix_cache_entries_system_prompt_hash'), 'cache_entries', ['system_prompt_hash'], unique=False)
    op.create_index(op.f('ix_cache_entries_model'), 'cache_entries', ['model'], unique=False)
    op.create_index(op.f('ix_cache_entries_tenant_id'), 'cache_entries', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_cache_entries_user_id'), 'cache_entries', ['user_id'], unique=False)

    # Create cache_events table
    op.create_table(
        'cache_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('cache_status', sa.Enum('HIT', 'MISS', 'EXPIRED', 'THRESHOLD_NOT_MET', 'MODEL_MISMATCH', 'SYSTEM_MISMATCH', 'BYPASS', 'ERROR', name='cachestatus'), nullable=False),
        sa.Column('matched_cache_id', sa.String(length=36), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('threshold_used', sa.Float(), nullable=False),
        sa.Column('threshold_version_id', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('retrieval_source', sa.String(length=20), nullable=True),
        sa.Column('tenant_id', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cache_events_request_id'), 'cache_events', ['request_id'], unique=False)
    op.create_index(op.f('ix_cache_events_cache_status'), 'cache_events', ['cache_status'], unique=False)
    op.create_index(op.f('ix_cache_events_matched_cache_id'), 'cache_events', ['matched_cache_id'], unique=False)
    op.create_index(op.f('ix_cache_events_tenant_id'), 'cache_events', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_cache_events_model'), 'cache_events', ['model'], unique=False)
    op.create_index(op.f('ix_cache_events_created_at'), 'cache_events', ['created_at'], unique=False)

    # Create embedding_records table
    op.create_table(
        'embedding_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_id', sa.String(length=36), nullable=False),
        sa.Column('faiss_vector_id', sa.Integer(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_embedding_records_cache_id'), 'embedding_records', ['cache_id'], unique=False)
    op.create_index(op.f('ix_embedding_records_faiss_vector_id'), 'embedding_records', ['faiss_vector_id'], unique=True)

    # Create provider_calls table
    op.create_table(
        'provider_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('cost_currency', sa.String(length=3), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('tenant_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_calls_request_id'), 'provider_calls', ['request_id'], unique=False)
    op.create_index(op.f('ix_provider_calls_provider'), 'provider_calls', ['provider'], unique=False)
    op.create_index(op.f('ix_provider_calls_model'), 'provider_calls', ['model'], unique=False)
    op.create_index(op.f('ix_provider_calls_tenant_id'), 'provider_calls', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_provider_calls_user_id'), 'provider_calls', ['user_id'], unique=False)
    op.create_index(op.f('ix_provider_calls_created_at'), 'provider_calls', ['created_at'], unique=False)

    # Create threshold_versions table
    op.create_table(
        'threshold_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('active_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_threshold_versions_threshold_value'), 'threshold_versions', ['threshold_value'], unique=False)
    op.create_index(op.f('ix_threshold_versions_active_from'), 'threshold_versions', ['active_from'], unique=False)
    op.create_index(op.f('ix_threshold_versions_active_until'), 'threshold_versions', ['active_until'], unique=False)


def downgrade() -> None:
    op.drop_table('threshold_versions')
    op.drop_table('provider_calls')
    op.drop_table('embedding_records')
    op.drop_table('cache_events')
    op.drop_table('cache_entries')
    op.drop_table('requests')
