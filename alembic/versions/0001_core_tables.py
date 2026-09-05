"""Create core tables (tenants, audit_events, idempotency_records).

Revision ID: 0001
Revises:
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial core tables."""
    # tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
    )

    # audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_display_name", sa.String(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("actor_channel", sa.String(), nullable=True),
        sa.Column("target_system", sa.String(), nullable=True),
        sa.Column("target_ref", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("discrepancy_id", sa.String(), nullable=True),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.Index("idx_audit_events_tenant_id", "tenant_id"),
        sa.Index("idx_audit_events_occurred_at", "occurred_at"),
    )

    # Append-only trigger: prevent UPDATE and DELETE on audit_events
    op.execute("""
        CREATE OR REPLACE RULE audit_events_no_update AS
        ON UPDATE TO audit_events DO INSTEAD NOTHING;
        """)
    op.execute("""
        CREATE OR REPLACE RULE audit_events_no_delete AS
        ON DELETE TO audit_events DO INSTEAD NOTHING;
        """)

    # idempotency_records table
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "tenant_id",
            "endpoint",
            "key",
            name="uq_idempotency_records_tenant_id_endpoint_key",
        ),
        sa.Index("idx_idempotency_records_tenant_id", "tenant_id"),
        sa.Index("idx_idempotency_records_expires_at", "expires_at"),
    )


def downgrade() -> None:
    """Drop all core tables."""
    # Drop audit_events rules first
    op.execute("DROP RULE IF EXISTS audit_events_no_update ON audit_events")
    op.execute("DROP RULE IF EXISTS audit_events_no_delete ON audit_events")

    # Drop tables
    op.drop_table("idempotency_records")
    op.drop_table("audit_events")
    op.drop_table("tenants")
