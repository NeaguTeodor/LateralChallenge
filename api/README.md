# api

FastAPI backend for the takeaway platform.

## Layout

```
app/
├── main.py            # FastAPI app factory: mounts routers, docs, health check
├── initial_data.py    # idempotent seed (admin user + demo restaurants)
├── core/              # settings, DB engine/session, password hashing & JWT
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic request/response models (shared field types in types.py)
├── services/          # business logic that is more than CRUD (order placement & status rules)
└── api/
    ├── deps.py        # DB session, current user, admin guard
    ├── router.py      # aggregates all routers under /api/v1
    └── routes/        # one module per resource: auth, restaurants, orders
alembic/               # migrations
tests/                 # pytest suite, runs against Postgres via the real migrations
```

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # install deps into .venv
docker compose up -d db                   # from repo root: Postgres only
uv run alembic upgrade head
uv run python -m app.initial_data
uv run uvicorn app.main:app --reload      # http://localhost:8000/api/docs
```

Set `DATABASE_URL` (or an `api/.env` file) if Postgres isn't on `localhost:5432`.

```bash
uv run pytest                             # tests (needs the compose `db`; uses a `takeaway_test` DB)
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "describe change"
```
