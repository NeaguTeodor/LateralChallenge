from pydantic import BaseModel, ConfigDict

from app.schemas.types import Price, ShortStr


class RestaurantBase(BaseModel):
    name: ShortStr
    description: str = ""
    address: ShortStr
    is_active: bool = True


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(BaseModel):
    name: ShortStr | None = None
    description: str | None = None
    address: ShortStr | None = None
    is_active: bool | None = None


class RestaurantRead(RestaurantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MenuItemBase(BaseModel):
    name: ShortStr
    description: str = ""
    price: Price
    is_available: bool = True


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: ShortStr | None = None
    description: str | None = None
    price: Price | None = None
    is_available: bool | None = None


class MenuItemRead(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
