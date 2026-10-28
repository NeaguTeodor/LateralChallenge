from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class OrderStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"), default=OrderStatus.PENDING, index=True
    )
    delivery_address: Mapped[str] = mapped_column(String(255))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


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
