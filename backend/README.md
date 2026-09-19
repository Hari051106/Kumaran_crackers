# Kumaran Crackers — Backend API

> *Celebrate Every Moment with Kumaran Crackers*

The FastAPI service that powers both the **Kumaran Crackers** customer mobile app
and the **Kumaran Crackers Admin** desktop application.

This service is the **single source of truth**. Prices, stock levels, order
totals and authorisation are decided here and nowhere else — the clients are
presentation layers only.

---

## Status

| Milestone | Scope | State |
|---|---|---|
| **1** | Backend foundation — config, database, auth, roles | ✅ Complete |
| 2 | Categories, products, product images | ⬜ Not started |
| 3 | Admin desktop — login, dashboard, catalogue, inventory | ⬜ Not started |
| 4 | Customer mobile — login, home, catalogue | ⬜ Not started |
| 5 | Cart, addresses, checkout | ⬜ Not started |
| 6 | Orders and tracking | ⬜ Not started |
| 7 | Delivery | ⬜ Not started |
| 8 | Reports | ⬜ Not started |
| 9 | Payments | ⬜ Not started |
| 10 | AI features | ⬜ Not started |

---

## Architecture

Requests flow strictly in one direction. Each layer may only call the one below it:

```
router      HTTP only — parse, delegate, serialise. No business rules.
  ↓
service     All business rules live here. No framework imports.
  ↓
repository  Data access only. No business rules, no HTTP.
  ↓
model       SQLAlchemy ORM.
```

Two consequences worth stating explicitly:

- **Services never raise `HTTPException`.** They raise domain errors from
  `app/utils/errors.py`, which `app/main.py` renders into one consistent JSON
  envelope. This keeps the business layer reusable outside a web request.
- **ORM objects are never returned from a route.** Every response passes through
  a Pydantic schema, so a password digest cannot leak by accident.

### Project layout

```
backend/
├── app/
│   ├── main.py            FastAPI app factory, CORS, exception handlers
│   ├── config.py          Environment-driven settings (pydantic-settings)
│   ├── database.py        Engine, session factory, declarative Base
│   ├── enums.py           Shared domain vocabulary (RoleName, TokenType)
│   ├── initial_data.py    One-off first-admin bootstrap
│   ├── models/            SQLAlchemy 2.x ORM models
│   ├── schemas/           Pydantic request/response models
│   ├── repositories/      Data access
│   ├── services/          Business logic
│   ├── routers/v1/        Versioned HTTP endpoints
│   ├── dependencies/      Auth + RBAC dependencies
│   └── utils/             Hashing, JWT, domain errors
├── alembic/               Migrations (the only way the schema changes)
├── tests/                 pytest suite, runs against real PostgreSQL
└── requirements.txt
```

---

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (developed against 16)

### 1. Create the database

```bash
sudo -u postgres psql -c "CREATE ROLE kumaran LOGIN PASSWORD 'your-password' CREATEDB;"
sudo -u postgres createdb -O kumaran kumaran_crackers
sudo -u postgres createdb -O kumaran kumaran_crackers_test
```

### 2. Install dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. Configure the environment

```bash
cp .env.example .env
```

Then edit `.env`. At minimum set `SECRET_KEY`, `POSTGRES_PASSWORD` and
`FIRST_ADMIN_PASSWORD`. Generate a real secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

> `.env` is git-ignored and must never be committed.

### 4. Apply migrations and create the first admin

```bash
alembic upgrade head
python -m app.initial_data
```

`alembic upgrade head` also seeds the three system roles (ADMIN, STAFF,
CUSTOMER). The bootstrap script is idempotent and will not reset an existing
account's password.

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

| URL | What |
|---|---|
| http://127.0.0.1:8000/docs | Interactive API documentation |
| http://127.0.0.1:8000/health | Liveness probe |

Documentation routes are disabled automatically when `APP_ENV=production`.

---

## API (v1)

Base path: `/api/v1`

### Authentication — `/auth`

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public | Register a customer; always assigns CUSTOMER |
| POST | `/auth/login` | Public | Customer sign-in |
| POST | `/auth/admin/login` | Public | Back-office sign-in; rejects customers |
| POST | `/auth/refresh` | Public | Exchange a refresh token for a new pair |
| GET | `/auth/me` | Any signed-in | Current user |
| POST | `/auth/logout` | Any signed-in | Acknowledge logout |

### Users — `/users`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/users/me` | Any signed-in | My profile |
| PATCH | `/users/me` | Any signed-in | Update my name / phone / date of birth |
| POST | `/users/me/change-password` | Any signed-in | Change my password |
| GET | `/users` | **ADMIN** | Search + paginate users |
| POST | `/users` | **ADMIN** | Create a user with an explicit role |
| GET | `/users/{id}` | **ADMIN** | Read one user |
| PATCH | `/users/{id}` | **ADMIN** | Change a user's role or active state |

### Error format

Every failure — validation, auth, business rule, or unexpected — uses one shape:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to perform this action.",
    "details": { "field": "reason" }
  }
}
```

Clients can therefore parse errors with a single code path. Internal exceptions
are logged server-side and returned as a generic `internal_error`; SQL, stack
traces and table names are never sent to a client.

---

## Security notes

| Concern | How it is handled |
|---|---|
| Password storage | bcrypt with a per-password salt. Plain text is never stored. |
| Long passwords | Rejected above 72 bytes rather than silently truncated — truncation would let two different passwords authenticate each other. |
| Token confusion | Access and refresh tokens carry a `type` claim that is verified on decode, so a refresh token cannot be replayed as a session token. |
| Privilege escalation | `/auth/register` fixes the role to CUSTOMER server-side; a `role` field in the request body is ignored. |
| Revocation latency | The role and active flag are re-read from the database on every request, so deactivating or demoting a user takes effect immediately rather than at token expiry. |
| Account enumeration | An unknown e-mail and a wrong password return byte-identical 401 responses, and a dummy bcrypt verification equalises the timing. |
| Admin lockout | An admin cannot change their own role or deactivate themselves. |
| Back-office access | Customer accounts are refused at `/auth/admin/login` even with valid credentials. |
| Secrets | Sourced from the environment. A placeholder `SECRET_KEY` aborts start-up outside development. |

Authorisation is enforced **on the server**. Client-side route guards in the
mobile and desktop apps are for usability, never for security.

### Regulatory note

Fireworks are age-restricted goods. The schema carries `date_of_birth` and
`age_confirmed_at` on `users`, and `MINIMUM_PURCHASE_AGE` /
`REQUIRE_AGE_CONFIRMATION` are configurable per deployment, so eligibility
checks can be enforced at checkout without migrating a live orders table.
These are extension points — the applicable rules must be confirmed against
local law before launch.

---

## Database

Schema changes go through Alembic **only**. `Base.metadata.create_all()` is
never used to build a real database.

```bash
alembic revision --autogenerate -m "add products"   # generate
alembic upgrade head                                 # apply
alembic downgrade -1                                 # roll back one
alembic check                                        # fail if models drift
```

Always read a generated migration before applying it — autogenerate does not
detect table renames, and it cannot write your data backfills for you.

### Current entities

**roles** — `id`, `name` (unique), `description`, timestamps.
Seeded with ADMIN, STAFF, CUSTOMER by the baseline migration.

**users** — `id`, `email` (unique), `phone` (unique, nullable), `full_name`,
`hashed_password`, `role_id` → `roles.id` (`ON DELETE RESTRICT`), `is_active`,
`is_verified`, `last_login_at`, `date_of_birth`, `age_confirmed_at`, timestamps.

`RESTRICT` is deliberate: deleting a role that still has users must fail rather
than cascade-delete customer accounts.

---

## Testing

```bash
pytest                              # whole suite
pytest --cov=app --cov-report=term  # with coverage
pytest tests/test_auth.py -v        # one file
```

The suite runs against a **real PostgreSQL** database (`TEST_DATABASE_URL`),
not SQLite, so server defaults, unique constraints and foreign-key behaviour
are exercised exactly as in production. The schema is built by running the
Alembic migrations, which means every test run also proves the migrations work.

Each test executes inside a transaction that is rolled back afterwards, so
tests are isolated and order-independent without rebuilding the schema between
them.

## Linting

```bash
ruff check app alembic tests
ruff format app alembic tests
```
