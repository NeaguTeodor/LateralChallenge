from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AdminUser, OptionalUser, SessionDep
from app.models import MenuItem, Restaurant, User
from app.schemas.restaurant import (
    MenuItemCreate,
    MenuItemRead,
    MenuItemUpdate,
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def get_restaurant_or_404(db: SessionDep, restaurant_id: int, user: User | None) -> Restaurant:
    """Inactive restaurants exist only for admins; everyone else gets 404."""
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None or not (restaurant.is_active or (user and user.is_admin)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found")
    return restaurant


def get_menu_item_or_404(db: SessionDep, restaurant_id: int, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None or item.restaurant_id != restaurant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    return item


def apply_update[T](db: SessionDep, obj: T, payload: BaseModel) -> T:
    """PATCH semantics: only fields the client actually sent are changed."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


# --- Public browsing (admins also see inactive restaurants) ---


@router.get("", response_model=list[RestaurantRead])
def list_restaurants(
    db: SessionDep,
    user: OptionalUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Restaurant]:
    stmt = select(Restaurant).order_by(Restaurant.name).limit(limit).offset(offset)
    if not (user and user.is_admin):
        stmt = stmt.where(Restaurant.is_active)
    return db.scalars(stmt).all()


@router.get("/{restaurant_id}", response_model=RestaurantRead)
def get_restaurant(restaurant_id: int, db: SessionDep, user: OptionalUser) -> Restaurant:
    return get_restaurant_or_404(db, restaurant_id, user)


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemRead])
def get_menu(restaurant_id: int, db: SessionDep, user: OptionalUser) -> list[MenuItem]:
    return get_restaurant_or_404(db, restaurant_id, user).menu_items


# --- Admin management ---


@router.post("", response_model=RestaurantRead, status_code=status.HTTP_201_CREATED)
def create_restaurant(payload: RestaurantCreate, db: SessionDep, _: AdminUser) -> Restaurant:
    restaurant = Restaurant(**payload.model_dump())
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.patch("/{restaurant_id}", response_model=RestaurantRead)
def update_restaurant(
    restaurant_id: int, payload: RestaurantUpdate, db: SessionDep, admin: AdminUser
) -> Restaurant:
    return apply_update(db, get_restaurant_or_404(db, restaurant_id, admin), payload)


@router.post(
    "/{restaurant_id}/menu", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED
)
def create_menu_item(
    restaurant_id: int, payload: MenuItemCreate, db: SessionDep, admin: AdminUser
) -> MenuItem:
    restaurant = get_restaurant_or_404(db, restaurant_id, admin)
    item = MenuItem(restaurant_id=restaurant.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{restaurant_id}/menu/{item_id}", response_model=MenuItemRead)
def update_menu_item(
    restaurant_id: int, item_id: int, payload: MenuItemUpdate, db: SessionDep, _: AdminUser
) -> MenuItem:
    return apply_update(db, get_menu_item_or_404(db, restaurant_id, item_id), payload)


@router.delete("/{restaurant_id}/menu/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(restaurant_id: int, item_id: int, db: SessionDep, _: AdminUser) -> None:
    db.delete(get_menu_item_or_404(db, restaurant_id, item_id))
    db.commit()
