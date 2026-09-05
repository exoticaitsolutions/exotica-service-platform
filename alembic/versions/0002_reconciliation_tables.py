"""Add reconciliation tables for Step 2 (ST and QB data + runs).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reconciliation tables."""
    # reconciliation_runs table
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
        sa.Column("date_from", sa.String(), nullable=False),
        sa.Column("date_to", sa.String(), nullable=False),
        sa.Column("trigger_source", sa.String(), nullable=False, server_default="api"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("servicetitan_invoice_count", sa.Integer(), nullable=True),
        sa.Column("quickbooks_invoice_count", sa.Integer(), nullable=True),
        sa.Column("matched_count", sa.Integer(), nullable=True),
        sa.Column("discrepancy_count", sa.Integer(), nullable=True),
        sa.Column("health_score", sa.Numeric(), nullable=True),
        sa.Column("source_errors", sa.JSON(), nullable=False, server_default="[]"),
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
        sa.PrimaryKeyConstraint("id", name="pk_reconciliation_runs"),
        sa.Index("idx_reconciliation_runs_tenant_id", "tenant_id"),
        sa.Index("idx_reconciliation_runs_status", "status"),
        sa.Index("idx_reconciliation_runs_started_at", "started_at"),
    )

    # st_invoices table (ServiceTitan normalized data)
    op.create_table(
        "st_invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("servicetitan_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("invoice_date", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("paid_amount", sa.Numeric(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_st_invoices"),
        sa.Index("idx_st_invoices_tenant_id", "tenant_id"),
        sa.Index("idx_st_invoices_run_id", "run_id"),
    )

    # qb_invoices table (QuickBooks normalized data)
    op.create_table(
        "qb_invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("quickbooks_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("invoice_date", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("paid_amount", sa.Numeric(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_qb_invoices"),
        sa.Index("idx_qb_invoices_tenant_id", "tenant_id"),
        sa.Index("idx_qb_invoices_run_id", "run_id"),
    )


def downgrade() -> None:
    """Drop reconciliation tables."""
    op.drop_table("qb_invoices")
    op.drop_table("st_invoices")
    op.drop_table("reconciliation_runs")
