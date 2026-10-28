from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas.user import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: SessionDep) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # unique email; also covers two concurrent sign-ups
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: SessionDep) -> Token:
    """OAuth2 password flow: send `username` (the email) and `password` as form data."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    # Hash even for unknown emails so response time doesn't reveal which accounts exist.
    password_ok = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    return user


# --- Local demo helpers: switch between accounts without typing passwords ---


def _require_demo() -> None:
    if not settings.demo_logins:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


@router.get("/demo-accounts", response_model=list[UserRead])
def demo_accounts(db: SessionDep) -> Sequence[User]:
    """Every account, customers first, for the demo switcher (404 outside local)."""
    _require_demo()
    return db.scalars(select(User).order_by(User.role, User.id).limit(100)).all()


@router.post("/demo-login/{user_id}", response_model=Token)
def demo_login(user_id: int, db: SessionDep) -> Token:
    _require_demo()
    if db.get(User, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return Token(access_token=create_access_token(user_id))
