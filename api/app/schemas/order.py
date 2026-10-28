from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import OrderStatus
from app.schemas.types import ShortStr


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    restaurant_id: int
    delivery_address: ShortStr | None = None  # defaults to the customer's saved address
    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def _one_line_per_item(cls, items: list[OrderItemCreate]) -> list[OrderItemCreate]:
        # Otherwise two lines of the same item would get around the per-item quantity cap.
        if len({line.menu_item_id for line in items}) != len(items):
            raise ValueError("each menu item may appear only once; use quantity instead")
        return items


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int | None
    name: str
    unit_price: Decimal
    quantity: int


class OrderStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: OrderStatus
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    customer_name: str
    restaurant_id: int
    restaurant_name: str
    status: OrderStatus
    delivery_address: str
    total: Decimal
    items: list[OrderItemRead]
    events: list[OrderStatusEventRead]
    created_at: datetime
    updated_at: datetime


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
