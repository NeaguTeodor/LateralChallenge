from collections.abc import AsyncIterator

import psycopg
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import PG_DSN
from app.models import MenuItem, Order, OrderItem, OrderStatus, Restaurant, User
from app.schemas.order import OrderCreate

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.ACCEPTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


# Postgres NOTIFY channel; payload is "<order_id>:<status>". Delivered only on commit.
STATUS_CHANNEL = "order_status"
FINAL_STATUSES = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}
KEEPALIVE_SECONDS = 15


def _order_by_key(db: Session, customer: User, key: str) -> Order | None:
    return db.scalar(
        select(Order).where(Order.customer_id == customer.id, Order.idempotency_key == key)
    )


def place_order(
    db: Session, customer: User, payload: OrderCreate, idempotency_key: str | None = None
) -> Order:
    """Idempotent when a key is given: a retry returns the order the first attempt created."""
    if idempotency_key and (existing := _order_by_key(db, customer, idempotency_key)):
        return existing

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
        idempotency_key=idempotency_key,
    )
    order.set_status(OrderStatus.PENDING)
    db.add(order)
    try:
        db.commit()
    except IntegrityError:  # a concurrent retry with the same key won the race
        db.rollback()
        return _order_by_key(db, customer, idempotency_key)
    db.refresh(order)
    return order


def change_status(db: Session, order: Order, new_status: OrderStatus) -> Order:
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change order status from '{order.status}' to '{new_status}'",
        )
    order.set_status(new_status)
    db.execute(select(func.pg_notify(STATUS_CHANNEL, f"{order.id}:{new_status}")))
    db.commit()
    db.refresh(order)
    return order


async def status_stream(order_id: int) -> AsyncIterator[str]:
    """Server-Sent Events: the current status, then every change until the order is final.

    Each stream LISTENs on its own connection. Fine at this scale; with many clients one
    shared listener per worker would fan notifications out instead.
    """
    async with await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True) as conn:
        await conn.execute(f"LISTEN {STATUS_CHANNEL}")
        # Read the status only after LISTEN, so a change in between can't be missed.
        cur = await conn.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        current = OrderStatus((await cur.fetchone())[0])
        yield f"data: {current}\n\n"

        while current not in FINAL_STATUSES:
            async for note in conn.notifies(timeout=KEEPALIVE_SECONDS):
                note_order_id, _, new_status = note.payload.partition(":")
                if int(note_order_id) == order_id:
                    current = OrderStatus(new_status)
                    yield f"data: {current}\n\n"
                    if current in FINAL_STATUSES:
                        break
            else:
                yield ": keepalive\n\n"  # stops proxies from closing an idle stream
