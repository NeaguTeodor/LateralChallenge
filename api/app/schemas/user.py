from pydantic import BaseModel, ConfigDict, EmailStr

from app.models import UserRole
from app.schemas.types import Password, ShortStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: ShortStr
    password: Password


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
