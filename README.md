# Kumaran Crackers

> *Celebrate Every Moment with Kumaran Crackers*

A quick-commerce platform for Kumaran Crackers, built as three components around
a single authoritative backend.

| Component | Name | Stack | Status |
|---|---|---|---|
| 📱 Customer mobile | Kumaran Crackers | Flutter · Riverpod · GoRouter · Dio | 🟢 Milestones 4–5 complete |
| 🖥️ Admin desktop | Kumaran Crackers Admin | Electron · React · Vite · Tailwind | 🟢 Milestone 3 complete |
| ⚙️ Backend API | — | FastAPI · SQLAlchemy 2.x · PostgreSQL · Alembic | 🟢 Milestones 1–5 complete |

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
├── mobile/      Flutter customer application              (see mobile/README.md)
└── desktop/     Electron + React admin application        (see desktop/README.md)
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
| **4** | **Customer mobile — login, home, categories, products, details** | ✅ **Complete** |
| **5** | **Cart, addresses, checkout** | ✅ **Complete** |
| **6** | **Orders — creation, history, tracking, admin management** | ✅ **Complete** |
| 7 | Delivery assignment and status | ⬜ Next |
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

### Milestone 4 delivered

- **Kumaran Crackers** customer app in Flutter: splash with session restore,
  register, sign in, home, category browsing, catalogue and product detail
- Material 3 throughout, with Riverpod, GoRouter, Dio, secure token storage
  and cached product imagery
- Money kept as exact decimal strings end to end, formatted with Indian digit
  grouping and never parsed into a `double`
- Tokens in the Android Keystore / iOS Keychain, with a single shared
  in-flight refresh
- Catalogue search (debounced), category and price filters, five sort orders,
  infinite scroll and pull-to-refresh
- Stock state always carried by words and an icon, not colour alone

**264 tests passing** overall: 201 backend, 23 desktop end-to-end, and 40
Flutter unit and widget tests.

### Milestone 5 delivered

- Basket, delivery addresses and checkout, on both the API and the mobile app
- A single pricing authority (`backend/app/services/pricing.py`) that the
  checkout quote uses and order creation will reuse, so a customer cannot be
  quoted one figure and charged another
- Subtotal, discount, delivery and total computed entirely server-side in
  `Decimal`, with **no rounding anywhere** — the lines always sum to the total
- Cart items store **no price**: totals are recomputed from the live product
  row on every read, so a price change or a sell-out surfaces immediately
- Stock validated when an item is added *and* again at checkout, with a
  per-line message naming exactly what to fix
- Addresses scoped per customer, with exactly one default enforced by a
  partial unique index

---

### Milestone 6 delivered

- Placing an order is one transaction: the order, its lines, the stock
  reservation, the audit entry and emptying the basket all commit together or
  none of them do
- Stock moves through a single atomic `UPDATE … WHERE stock >= :qty RETURNING`,
  so two customers checking out the last unit cannot both succeed
- Every checkout rule is re-run at placement and the price is recomputed from
  the same pricing authority — the client never sends an amount
- An order is an immutable record: prices, product names, SKUs and the
  delivery address are snapshotted, and database CHECK constraints hold the
  invoice arithmetic (`items_total = subtotal − discount`,
  `total = items_total + delivery_charge`)
- A status workflow that only moves forwards, one stage at a time, with an
  append-only audit trail recording who made each change
- Customers can cancel until packing begins; cancelling returns the stock and
  never counts as a sale
- Mobile: order history, a tracking timeline, and the checkout button now
  actually places the order
- Admin desktop: order list with search and status filter, full order detail,
  status updates, and customer records with real order counts and spend
- The dashboard's sales figures are live — and still say plainly when there is
  nothing to measure rather than showing a misleading zero

**458 tests passing**: 362 backend, 28 desktop end-to-end, 68 Flutter.

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
- The server prices every basket. A client sends ids and quantities, nothing more.
- Clients render what the server computes. No business rule is reimplemented in a client.
- No mocked data once a real endpoint exists. A screen with nothing to show says so.
- Every schema change is an Alembic migration. `create_all()` is not a migration strategy.
- API responses always go through a Pydantic schema — ORM models are never returned directly.
- `.env` is never committed. `.env.example` documents every variable.
- Run tests and linting before committing.
