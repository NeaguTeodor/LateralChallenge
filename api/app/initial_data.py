"""Idempotent seed: ensures an admin user exists and, optionally, some demo restaurants."""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import MenuItem, Restaurant, User, UserRole

logger = logging.getLogger(__name__)

DEMO_RESTAURANTS = {
    ("Napoli Express", "Wood-fired pizza", "12 Via Roma"): [
        ("Margherita", "Tomato, mozzarella, basil", "8.50"),
        ("Diavola", "Spicy salami, chilli", "10.00"),
        ("Tiramisu", "Classic, made in-house", "5.00"),
    ],
    ("Tokyo Bowl", "Ramen and rice bowls", "3 Sakura Street"): [
        ("Tonkotsu Ramen", "Pork broth, chashu, egg", "12.00"),
        ("Chicken Katsu Don", "Crispy chicken over rice", "11.00"),
        ("Gyoza (6)", "Pan-fried pork dumplings", "6.00"),
    ],
}


def seed_user(db: Session, email: str, password: str, full_name: str, role: UserRole) -> None:
    email = email.lower()  # login lowercases too
    if db.scalar(select(User).where(User.email == email)):
        return
    db.add(
        User(email=email, full_name=full_name, hashed_password=hash_password(password), role=role)
    )
    logger.info("Created %s user %s", role, email)


def seed_demo_restaurants(db: Session) -> None:
    if db.scalar(select(Restaurant.id).limit(1)):
        return
    for (name, description, address), items in DEMO_RESTAURANTS.items():
        db.add(
            Restaurant(
                name=name,
                description=description,
                address=address,
                menu_items=[MenuItem(name=n, description=d, price=Decimal(p)) for n, d, p in items],
            )
        )
    logger.info("Seeded %d demo restaurants", len(DEMO_RESTAURANTS))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        seed_user(
            db, settings.first_admin_email, settings.first_admin_password, "Admin", UserRole.ADMIN
        )
        if settings.seed_demo_data:
            seed_user(
                db,
                settings.demo_customer_email,
                settings.demo_customer_password,
                "Demo Customer",
                UserRole.CUSTOMER,
            )
            seed_demo_restaurants(db)
        db.commit()


if __name__ == "__main__":
    main()
