# Kumaran Crackers

> *Celebrate Every Moment with Kumaran Crackers*

A quick-commerce platform for Kumaran Crackers, built as three components around
a single authoritative backend.

| Component | Name | Stack | Status |
|---|---|---|---|
| 📱 Customer mobile | Kumaran Crackers | Flutter · Riverpod · GoRouter · Dio | ⬜ Planned (M4) |
| 🖥️ Admin desktop | Kumaran Crackers Admin | Electron · React · Vite · Tailwind | 🟢 Milestone 3 complete |
| ⚙️ Backend API | — | FastAPI · SQLAlchemy 2.x · PostgreSQL · Alembic | 🟢 Milestones 1–3 complete |

---

## Architecture

```
          ┌─────────────────────────┐
          │   Customer Mobile App   │
          │      Flutter / Dart     │
          └────────────┬────────────┘
                       │ REST
                       ▼
          ┌─────────────────────────┐
          │     FastAPI Backend     │
          │                         │
          │  Auth · Products        │
          │  Categories · Cart      │
          │  Orders · Customers     │
          │  Inventory · Delivery   │
          │  Reports                │
          └────────────┬────────────┘
                       │ SQLAlchemy
                       ▼
          ┌─────────────────────────┐
          │       PostgreSQL        │
          └─────────────────────────┘
                       ▲
                       │ REST
          ┌────────────┴────────────┐
          │     Admin Desktop       │
          │    Electron + React     │
          └─────────────────────────┘
```

**The backend is the single source of truth.** Pricing, discounts, stock
validation, order totals and authorisation are computed server-side only.
Business logic is never duplicated into the mobile or desktop clients, and
client-supplied prices and stock figures are never trusted.

---

## Repository layout

```
.
├── backend/     FastAPI service + PostgreSQL migrations   (see backend/README.md)
├── mobile/      Flutter customer application              (Milestone 4)
└── desktop/     Electron + React admin application        (Milestone 3)
```

---

## Quick start

Full instructions are in **[`backend/README.md`](backend/README.md)**.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then edit: SECRET_KEY, POSTGRES_PASSWORD, FIRST_ADMIN_PASSWORD
alembic upgrade head
python -m app.initial_data
uvicorn app.main:app --reload
```

API documentation: http://127.0.0.1:8000/docs

---

## Milestones

| # | Scope | Status |
|---|---|---|
| **1** | **Backend foundation** — config, database, migrations, auth, roles | ✅ **Complete** |
| **2** | **Categories, products, product images, catalogue APIs** | ✅ **Complete** |
| **3** | **Admin desktop — login, dashboard, products, categories, inventory** | ✅ **Complete** |
| 4 | Customer mobile — login, home, categories, products, details | ⬜ Next |
| 5 | Cart, addresses, checkout | ⬜ |
| 6 | Orders — creation, history, tracking, admin management | ⬜ |
| 7 | Delivery assignment and status | ⬜ |
| 8 | Reports and analytics | ⬜ |
| 9 | Payments | ⬜ |
| 10 | AI features — recommendations, budget planning, forecasting | ⬜ |

### Milestone 1 delivered

- Modular FastAPI service with a strict router → service → repository → model layering
- PostgreSQL schema managed by Alembic, with seeded role reference data
- JWT access + refresh tokens with type separation
- bcrypt password hashing
- Role-based access control (ADMIN / STAFF / CUSTOMER) enforced server-side
- Separate customer and back-office login paths

### Milestone 2 delivered

- Categories, products and product images, with the shop's eight opening
  categories seeded and fully admin-editable
- Public catalogue API: search, category filter, price range, in-stock,
  featured and discounted filters, six sort orders, pagination
- Money as `Decimal` / `Numeric(10,2)` end to end — never `float`
- Discount and stock status derived on read, so they cannot drift from prices
- Atomic stock adjustment, verified to lose no updates under 40 concurrent writes
- Catalogue visibility enforced server-side: a product is public only when it
  *and* its category are active, and `include_inactive` is staff-only
- Five database-level invariants (CHECK constraints, a partial unique index,
  and FK `RESTRICT`/`CASCADE` rules)

**187 tests passing** against a real PostgreSQL database, 95% coverage.

### Milestone 3 delivered

- **Kumaran Crackers Admin** desktop app: Electron + React + Vite + Tailwind
- Login, dashboard, product management, categories and inventory, all against
  the live API — no mocked data anywhere in the application
- Secure Electron architecture: `nodeIntegration: false`,
  `contextIsolation: true`, `sandbox: true`, and a preload bridge exposing
  exactly three namespaces
- Tokens held by the main process and encrypted with the OS keychain, never in
  `localStorage`
- The renderer is served over a registered `app://` scheme rather than
  `file://`, so it has a real origin the API can allowlist
- A real dashboard stats endpoint that reports only what the system can
  measure, and says so when it cannot
- Atomic stock adjustment surfaced in the inventory screen, with the server's
  guard rails shown to the user rather than swallowed

**224 tests passing**: 201 backend (pytest, real PostgreSQL) and 23 end-to-end
(Playwright — 11 auditing the real Electron binary, 12 driving the UI against a
live backend).

---

## Regulatory note

This platform sells fireworks, which are age-restricted and subject to local
sale, storage and delivery regulations. The data model and configuration carry
extension points for age and eligibility verification (see
`backend/README.md`), but the applicable rules must be confirmed against local
law before any production launch. Nothing here is designed to circumvent those
requirements.

---

## Development conventions

- Business rules belong in `backend/app/services/`. Not in routers, not in clients.
- Money is `Decimal` everywhere and crosses the wire as a string. Never `float`.
- Clients render what the server computes. No business rule is reimplemented in a client.
- No mocked data once a real endpoint exists. A screen with nothing to show says so.
- Every schema change is an Alembic migration. `create_all()` is not a migration strategy.
- API responses always go through a Pydantic schema — ORM models are never returned directly.
- `.env` is never committed. `.env.example` documents every variable.
- Run tests and linting before committing.
