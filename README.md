# Takeaway Platform

A small takeaway platform: customers browse restaurants and menus, place orders and
track their status; staff (admins) manage menus and move orders through their lifecycle.

| Path      | What                                                              |
|-----------|-------------------------------------------------------------------|
| `api/`    | FastAPI + SQLAlchemy + Alembic backend ([details](api/README.md)) |
| `web/`    | React + TypeScript UI ([details](web/README.md))                  |
| `nginx/`  | Reverse proxy config                                              |

## Quick start

```bash
cp .env.example .env    # optional — defaults work out of the box
docker compose up --build
```

- Web UI: http://localhost:8080
- API docs: http://localhost:8080/api/docs
- Seeded admin: `admin@takeaway.dev` / `admin1234`
- Two demo restaurants with menus are seeded on first start.

`nginx` (port 8080, serves the built UI at `/`) → `api` (uvicorn, 2 workers) → `db` (Postgres 17). On start the API
container runs migrations and the idempotent seed script.

## API overview

All routes are under `/api/v1`. Auth is JWT bearer; get a token from `POST /auth/login`
(OAuth2 password form: `username` = email). The "Authorize" button in the docs works too.

| Method | Path                                   | Who      | Purpose                         |
|--------|----------------------------------------|----------|---------------------------------|
| POST   | `/auth/register`                       | public   | Create a customer account       |
| POST   | `/auth/login`                          | public   | Get an access token             |
| GET    | `/auth/me`                             | user     | Current user                    |
| GET    | `/restaurants`                         | public   | List active restaurants         |
| GET    | `/restaurants/{id}`                    | public   | Restaurant details              |
| GET    | `/restaurants/{id}/menu`               | public   | Menu                            |
| POST   | `/restaurants`                         | admin    | Create restaurant               |
| PATCH  | `/restaurants/{id}`                    | admin    | Update / deactivate restaurant  |
| POST   | `/restaurants/{id}/menu`               | admin    | Add menu item                   |
| PATCH  | `/restaurants/{id}/menu/{item_id}`     | admin    | Update menu item                |
| DELETE | `/restaurants/{id}/menu/{item_id}`     | admin    | Remove menu item                |
| POST   | `/orders`                              | user     | Place an order                  |
| GET    | `/orders?status=`                      | user     | Own orders (admins: all)        |
| GET    | `/orders/{id}`                         | user     | Track an order                  |
| POST   | `/orders/{id}/cancel`                  | user     | Cancel own order while pending  |
| PATCH  | `/orders/{id}/status`                  | admin    | Advance order status            |

### Order lifecycle

```
pending ──► accepted ──► out_for_delivery ──► delivered
   │            │
   └────────────┴──► cancelled
```

Invalid transitions return `409 Conflict`. Status updates lock the order row
(`SELECT … FOR UPDATE`) so concurrent updates can't skip a step.

## Design notes

- **Prices are snapshotted** on order items (name + unit price), so editing or deleting a
  menu item never rewrites order history. The total is computed server-side.
- **Restaurants are deactivated, not deleted**, because orders reference them.
- **Customers get 404 for other people's orders** rather than 403, so order IDs don't leak.
- **Money is `Decimal`** end to end and serialised as a string (`"17.00"`) to avoid float rounding.
- Admins are created by the seed script from env vars; public registration only creates customers.
- **Pessimistic locking for status changes** (`SELECT … FOR UPDATE`) rather than optimistic
  versioning: contention on a single order is rare and short, and it keeps the code obvious.
  A test holds the lock from a second transaction to prove updates wait and re-check.
- **Tests run on Postgres through the real Alembic migrations**, so locks, enums and `Numeric`
  behave exactly as in production, and migrations are exercised on every run.
- **Public endpoints accept an optional token**: anonymous users only see active restaurants,
  admins see inactive ones too (so they can reactivate them).
- **Hardening kept deliberately small**: login/register are rate-limited in nginx, Postgres is
  bound to localhost, the health check hits the DB, and `ENVIRONMENT=production` refuses to
  start with the default JWT secret or admin password.

## Trade-offs & what I'd do next

- **Live tracking** polls every 5 s. Next step: Server-Sent Events fed by Postgres
  `LISTEN/NOTIFY` (works across uvicorn workers without adding Redis).
- **Idempotency**: a double-submitted order creates two orders. An `Idempotency-Key` header
  stored on the order would fix it; it matters most once payments exist.
- **Status history**: only the current status is stored. An `order_status_events` table would
  give timestamps per step and an audit trail.
- **Migrations run on container start**, fine for one instance; with several replicas they'd
  move to a one-off deploy job.
- **Staff are global admins**; a real platform would scope staff to their restaurants.
- **Auth**: short-lived access tokens only — no refresh tokens or revocation. The web UI keeps
  the token in `localStorage`; an httpOnly cookie would be safer against XSS.
- **Services raise `HTTPException`** directly; with more business logic I'd use domain
  exceptions mapped to HTTP in one place.
- No CI pipeline or structured logging yet (uvicorn access logs only).
