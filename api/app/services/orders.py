from collections.abc import AsyncIterator

import psycopg
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
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


def _check_order_limits(db: Session, customer: User, restaurant_id: int) -> None:
    """One active order per restaurant, and a cap on orders per customer."""
    active = db.scalar(
        select(Order.id).where(
            Order.customer_id == customer.id,
            Order.restaurant_id == restaurant_id,
            Order.status.not_in(FINAL_STATUSES),
        )
    )
    if active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You already have an active order (#{active}) from this restaurant. "
            "Wait until it's delivered, or cancel it while it's still pending.",
        )
    placed = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.customer_id == customer.id, Order.status != OrderStatus.CANCELLED)
    )
    if placed >= settings.max_orders_per_customer:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Order limit reached: {settings.max_orders_per_customer} orders per customer.",
        )


def place_order(
    db: Session, customer: User, payload: OrderCreate, idempotency_key: str | None = None
) -> Order:
    """Idempotent when a key is given: a retry returns the order the first attempt created."""
    # Lock the customer's row: simultaneous checkouts (including retries with the same key)
    # run one after another, so neither the key lookup nor the limits below can be raced.
    db.execute(select(User.id).where(User.id == customer.id).with_for_update())
    if idempotency_key and (existing := _order_by_key(db, customer, idempotency_key)):
        return existing
    _check_order_limits(db, customer, payload.restaurant_id)

    if not (address := payload.delivery_address or customer.address):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "delivery_address: required (none saved yet)"
        )

    # Shared lock: concurrent checkouts don't block each other, but deactivating the
    # restaurant (exclusive lock) waits for them, and they wait for it.
    restaurant = db.get(Restaurant, payload.restaurant_id, with_for_update={"read": True})
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found")

    requested_ids = {line.menu_item_id for line in payload.items}
    menu_items = {
        item.id: item
        for item in db.scalars(
            select(MenuItem)
            .where(MenuItem.id.in_(requested_ids), MenuItem.restaurant_id == restaurant.id)
            .with_for_update(read=True)  # can't be deleted while this checkout runs
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
        delivery_address=address,
        items=items,
        total=sum(item.unit_price * item.quantity for item in items),
        idempotency_key=idempotency_key,
    )
    order.set_status(OrderStatus.PENDING)
    customer.address = address  # remembered for the next checkout
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _transition(db: Session, order: Order, new_status: OrderStatus) -> None:
    """Validate, record and announce a status change. The caller commits."""
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change order status from '{order.status}' to '{new_status}'",
        )
    order.set_status(new_status)
    db.execute(select(func.pg_notify(STATUS_CHANNEL, f"{order.id}:{new_status}")))


def change_status(db: Session, order: Order, new_status: OrderStatus) -> Order:
    _transition(db, order, new_status)
    db.commit()
    db.refresh(order)
    return order


def cancel_open_orders(db: Session, restaurant_id: int) -> None:
    """When a restaurant closes, cancel what it hasn't sent out yet. The caller commits.

    Orders already out for delivery are left to complete.
    """
    cancellable = [s for s, nxt in ALLOWED_TRANSITIONS.items() if OrderStatus.CANCELLED in nxt]
    stmt = select(Order).where(Order.restaurant_id == restaurant_id, Order.status.in_(cancellable))
    for order in db.scalars(stmt.with_for_update(of=Order)):
        _transition(db, order, OrderStatus.CANCELLED)


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
