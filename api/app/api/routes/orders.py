from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.models import Order, OrderStatus, User
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_for_user(db: SessionDep, user: User, order_id: int, *, lock: bool = False) -> Order:
    """Fetch an order the user may see. Customers get 404 (not 403) for others' orders."""
    order = db.get(Order, order_id, with_for_update=lock)
    if order is None or (not user.is_admin and order.customer_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def place_order(payload: OrderCreate, db: SessionDep, user: CurrentUser) -> Order:
    return order_service.place_order(db, user, payload)


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: SessionDep,
    user: CurrentUser,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Order]:
    """Customers see their own orders; admins see all orders."""
    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    if not user.is_admin:
        stmt = stmt.where(Order.customer_id == user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: SessionDep, user: CurrentUser) -> Order:
    return get_order_for_user(db, user, order_id)


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: int, payload: OrderStatusUpdate, db: SessionDep, admin: AdminUser
) -> Order:
    order = get_order_for_user(db, admin, order_id, lock=True)
    return order_service.change_status(db, order, payload.status)


@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_order(order_id: int, db: SessionDep, user: CurrentUser) -> Order:
    """Customers may cancel their own order while it is still pending."""
    order = get_order_for_user(db, user, order_id, lock=True)
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only pending orders can be cancelled")
    return order_service.change_status(db, order, OrderStatus.CANCELLED)
