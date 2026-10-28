from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MenuItem, Order, OrderItem, OrderStatus, Restaurant, User
from app.schemas.order import OrderCreate

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.ACCEPTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def place_order(db: Session, customer: User, payload: OrderCreate) -> Order:
    restaurant = db.get(Restaurant, payload.restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found")

    requested_ids = {line.menu_item_id for line in payload.items}
    menu_items = {
        item.id: item
        for item in db.scalars(
            select(MenuItem).where(
                MenuItem.id.in_(requested_ids), MenuItem.restaurant_id == restaurant.id
            )
        )
    }

    if missing := requested_ids - menu_items.keys():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Menu items not found in this restaurant: {sorted(missing)}",
        )
    if unavailable := sorted(i.id for i in menu_items.values() if not i.is_available):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Menu items currently unavailable: {unavailable}"
        )

    items = [
        OrderItem(
            menu_item_id=line.menu_item_id,
            name=menu_items[line.menu_item_id].name,
            unit_price=menu_items[line.menu_item_id].price,
            quantity=line.quantity,
        )
        for line in payload.items
    ]
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        delivery_address=payload.delivery_address,
        items=items,
        total=sum(item.unit_price * item.quantity for item in items),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def change_status(db: Session, order: Order, new_status: OrderStatus) -> Order:
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change order status from '{order.status}' to '{new_status}'",
        )
    order.status = new_status
    db.commit()
    db.refresh(order)
    return order
