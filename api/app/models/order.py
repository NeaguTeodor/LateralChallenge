from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.user import User


class OrderStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    # A retried POST with the same Idempotency-Key returns the original order.
    __table_args__ = (UniqueConstraint("customer_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"), default=OrderStatus.PENDING, index=True
    )
    delivery_address: Mapped[str] = mapped_column(String(255))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    # selectin: one extra query per list (no N+1), and unlike a JOIN it doesn't extend
    # the order's FOR UPDATE lock to the customer's row.
    customer: Mapped["User"] = relationship(lazy="selectin")
    events: Mapped[list["OrderStatusEvent"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="OrderStatusEvent.id"
    )

    @property
    def customer_name(self) -> str:
        return self.customer.full_name

    def set_status(self, status: OrderStatus) -> None:
        """Change status and record it, so tracking can show when each step happened."""
        self.status = status
        self.events.append(OrderStatusEvent(status=status))


class OrderItem(Base):
    """A line in an order.

    Name and price are snapshotted so later menu edits don't rewrite order history.
    """

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    menu_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_items.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int]

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusEvent(Base):
    """Append-only history of an order's status changes."""

    __tablename__ = "order_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status", create_type=False)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
