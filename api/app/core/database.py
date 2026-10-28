from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, autoflush=False, expire_on_commit=False)
# Plain libpq DSN of the same database, for raw psycopg connections (LISTEN/NOTIFY).
PG_DSN = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
