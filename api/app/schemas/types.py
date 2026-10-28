"""Field types shared across request schemas, so each constraint is defined once."""

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, Field

ShortStr = Annotated[str, Field(min_length=1, max_length=255)]
# Capped so an order total always fits Numeric(10, 2).
Price = Annotated[Decimal, Field(gt=0, le=10_000, max_digits=10, decimal_places=2)]


def _fits_bcrypt(password: str) -> str:
    # bcrypt only accepts 72 *bytes*; a character limit lets multibyte passwords through.
    if len(password.encode()) > 72:
        raise ValueError("must be at most 72 bytes")
    return password


Password = Annotated[str, Field(min_length=8), AfterValidator(_fits_bcrypt)]
