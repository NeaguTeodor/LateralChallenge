from fastapi import FastAPI
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.project_name,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/api/health", tags=["health"])
def health(db: SessionDep) -> dict[str, str]:
    """Also checks the database, so it's usable as a readiness probe."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
