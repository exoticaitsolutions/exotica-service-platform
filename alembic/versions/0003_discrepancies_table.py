"""Add discrepancies table for Step 3 (matching and analysis).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create discrepancies table."""
    op.create_table(
        "discrepancies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("st_invoice_id", sa.String(), nullable=True),
        sa.Column("qb_invoice_id", sa.String(), nullable=True),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("st_amount", sa.Numeric(), nullable=True),
        sa.Column("qb_amount", sa.Numeric(), nullable=True),
        sa.Column("difference", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_discrepancies"),
        sa.Index("idx_discrepancies_tenant_id", "tenant_id"),
        sa.Index("idx_discrepancies_run_id", "run_id"),
        sa.Index("idx_discrepancies_status", "status"),
        sa.Index("idx_discrepancies_type", "type"),
        sa.Index("idx_discrepancies_severity", "severity"),
    )


def downgrade() -> None:
    """Drop discrepancies table."""
    op.drop_table("discrepancies")
