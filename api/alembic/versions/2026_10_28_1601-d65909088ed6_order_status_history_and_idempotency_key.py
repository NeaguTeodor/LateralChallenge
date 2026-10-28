"""order status history and idempotency key

Revision ID: d65909088ed6
Revises: 4a232e6f9d8a
Create Date: 2026-10-28 16:01:48.097918

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d65909088ed6"
down_revision: str | Sequence[str] | None = "4a232e6f9d8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "order_status_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        # Reuses the enum type created by the initial migration.
        sa.Column(
            "status", postgresql.ENUM(name="order_status", create_type=False), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_events_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_events")),
    )
    op.create_index(
        op.f("ix_order_status_events_order_id"), "order_status_events", ["order_id"], unique=False
    )
    op.add_column("orders", sa.Column("idempotency_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        op.f("uq_orders_customer_id"), "orders", ["customer_id", "idempotency_key"]
    )

    # Backfill: existing orders get one event for their current status.
    op.execute(
        "INSERT INTO order_status_events (order_id, status, created_at) "
        "SELECT id, status, updated_at FROM orders"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("uq_orders_customer_id"), "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
    op.drop_index(op.f("ix_order_status_events_order_id"), table_name="order_status_events")
    op.drop_table("order_status_events")
