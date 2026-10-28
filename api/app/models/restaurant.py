from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Restaurant(TimestampMixin, Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    menu_items: Mapped[list["MenuItem"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan", order_by="MenuItem.id"
    )


class MenuItem(TimestampMixin, Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(default=True)

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")
