from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models import Base, MenuItem, Restaurant, User, UserRole

API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Create the test database if needed and build the schema through the real migrations."""
    name = engine.url.database
    server = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}):
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    server.dispose()

    alembic_cfg = Config(Path(__file__).parents[1] / "alembic.ini")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
    tables = ", ".join(Base.metadata.tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _make_user(db: Session, email: str, role: UserRole) -> User:
    user = User(
        email=email, full_name=email, hashed_password=hash_password("password123"), role=role
    )
    db.add(user)
    db.commit()
    return user


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    res = client.post(f"{API}/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def customer_headers(client: TestClient, db: Session) -> dict[str, str]:
    _make_user(db, "customer@test.dev", UserRole.CUSTOMER)
    return _auth_headers(client, "customer@test.dev")


@pytest.fixture
def other_customer_headers(client: TestClient, db: Session) -> dict[str, str]:
    _make_user(db, "other@test.dev", UserRole.CUSTOMER)
    return _auth_headers(client, "other@test.dev")


@pytest.fixture
def admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    _make_user(db, "admin@test.dev", UserRole.ADMIN)
    return _auth_headers(client, "admin@test.dev")


@pytest.fixture
def restaurant(db: Session) -> Restaurant:
    restaurant = Restaurant(
        name="Testaurant",
        address="1 Test St",
        menu_items=[
            MenuItem(name="Burger", price=Decimal("9.50")),
            MenuItem(name="Fries", price=Decimal("3.25")),
            MenuItem(name="Sold Out Shake", price=Decimal("4.00"), is_available=False),
        ],
    )
    db.add(restaurant)
    db.commit()
    return restaurant
