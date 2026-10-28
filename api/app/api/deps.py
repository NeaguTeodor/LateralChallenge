from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models import User

# auto_error=False so public routes can still tell admins apart from anonymous visitors.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


SessionDep = Annotated[Session, Depends(get_db)]


def get_optional_user(
    db: SessionDep, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User | None:
    subject = decode_access_token(token) if token else None
    return db.get(User, int(subject)) if subject and subject.isdigit() else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_customer(user: CurrentUser) -> User:
    if user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff accounts can't place orders")
    return user


CustomerUser = Annotated[User, Depends(require_customer)]
