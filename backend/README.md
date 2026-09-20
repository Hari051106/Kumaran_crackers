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
| **2** | Categories, products, product images, catalogue APIs | ✅ Complete |
| **3** | Admin desktop — login, dashboard, catalogue, inventory | ✅ Complete |
| **4** | Customer mobile — login, home, catalogue | ✅ Complete |
| **5** | Cart, addresses, checkout | ✅ Complete |
| **6** | Orders, tracking and back-office order management | ✅ Complete |
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
│   ├── enums.py           Shared vocabulary: roles, tokens, stock, sort,
│   │                      order statuses and the transitions between them
│   ├── initial_data.py    One-off first-admin bootstrap
│   ├── models/            SQLAlchemy 2.x ORM models
│   ├── schemas/           Pydantic request/response models
│   ├── repositories/      Data access
│   ├── services/          Business logic
│   ├── routers/v1/        Versioned HTTP endpoints
│   ├── dependencies/      Auth + RBAC dependencies
│   └── utils/             Hashing, JWT, slugs, domain errors
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

### Categories — `/categories`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/categories` | **Public** | List categories with live product counts |
| GET | `/categories/{slug}` | **Public** | One category by slug |
| POST | `/categories` | **ADMIN** | Create (slug derived server-side) |
| PATCH | `/categories/{id}` | **ADMIN** | Update; renaming re-slugs |
| DELETE | `/categories/{id}` | **ADMIN** | Delete; refused if it holds products |

### Admin — `/admin`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/admin/dashboard` | STAFF | Catalogue, inventory, customer and trading figures |
| GET | `/admin/orders` | STAFF | All orders, searchable and filterable by status |
| GET | `/admin/orders/{order_number}` | STAFF | Full order, audit trail and remaining moves |
| POST | `/admin/orders/{order_number}/status` | STAFF | Advance an order through the workflow |
| GET | `/admin/customers` | STAFF | Customers with their real order count and spend |

The dashboard reports **only figures the system can actually measure**. Before
the first order exists it carries `sales_metrics_available: false` so the
desktop client can say so plainly rather than rendering a zero that reads like
a quiet trading day. Cancelled orders are excluded from every revenue figure,
from best sellers, and from customer spend — a withdrawn order was never a
sale — but they still appear in `orders_by_status`, because the operator needs
to see them.

`/admin/customers` is staff-visible and read-only: whoever is working an order
needs to be able to look the customer up, and it exposes nothing the order
screens do not already show. Changing an account still requires ADMIN through
`/users`.

### Products — `/products`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/products` | **Public** | Catalogue search, filter, sort, paginate |
| GET | `/products/{slug}` | **Public** | Product detail with images |
| GET | `/products/low-stock` | STAFF | At or below the low-stock threshold |
| GET | `/products/out-of-stock` | STAFF | Nothing left in stock |
| POST | `/products` | **ADMIN** | Create (SKU auto-generated if omitted) |
| GET | `/products/id/{id}` | STAFF | Admin view, including operational fields |
| PATCH | `/products/id/{id}` | **ADMIN** | Update |
| DELETE | `/products/id/{id}` | **ADMIN** | Delete, cascading to its images |
| POST | `/products/id/{id}/activate` | **ADMIN** | Show in the catalogue |
| POST | `/products/id/{id}/deactivate` | **ADMIN** | Hide without destroying history |
| POST | `/products/id/{id}/stock` | STAFF | Set (`set_to`) or adjust (`delta`) stock |
| POST | `/products/id/{id}/images` | **ADMIN** | Add an image |
| DELETE | `/products/id/{id}/images/{image_id}` | **ADMIN** | Remove an image |

Catalogue query parameters: `query`, `category_id`, `category` (slug),
`min_price`, `max_price`, `in_stock`, `featured`, `discounted`, `sort`, `page`,
`page_size`.

Sort values: `newest`, `price_asc`, `price_desc`, `name_asc`, `discount`,
`popularity`.

---

## Money, discounts and stock

**Money is `Numeric(10, 2)` in the database and `Decimal` in Python — never
`float`.** Binary floating point cannot represent values such as `0.10`
exactly, and the error compounds across order totals.

Consequently the API sends money as an exact JSON **string**:

```json
{ "mrp": "2499.00", "selling_price": "1874.25", "discount_percentage": "25.0" }
```

Clients must parse these into a decimal type. Parsing into a Dart `double` or a
JS `number` reintroduces exactly the error the Decimal column exists to avoid.

**The discount is derived, never stored.** `discount_percentage` and
`discount_amount` are computed from `mrp` and `selling_price` on read, so they
cannot drift out of step with the prices the way a cached column would.

**Stock status is likewise derived** from `stock_quantity` against
`low_stock_threshold`:

| Condition | Status |
|---|---|
| `stock_quantity <= 0` | `OUT_OF_STOCK` |
| `stock_quantity <= low_stock_threshold` | `LOW_STOCK` |
| otherwise | `IN_STOCK` |

**Relative stock changes are atomic.** A `delta` adjustment is applied as a
single `UPDATE ... SET stock_quantity = stock_quantity + :delta WHERE
stock_quantity + :delta >= 0`, so two concurrent adjustments cannot lose one
another, and stock can never be driven negative. Verified under 40 concurrent
requests. Checkout in Milestones 5 and 6 builds on this same primitive.

---

## Catalogue visibility

A product is publicly visible only when **the product and its category are both
active**. An active product inside a deactivated category stays hidden.

The `include_inactive` query parameter is honoured **only for signed-in staff**.
A customer or anonymous caller who sends it still receives the active catalogue,
so a deactivated item cannot be discovered by guessing a query parameter.

---

### Cart — `/cart`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/cart` | Signed in | The basket, priced from the live catalogue |
| POST | `/cart/items` | Signed in | Add a product, or top up an existing line |
| PATCH | `/cart/items/{id}` | Signed in | Set an absolute quantity |
| DELETE | `/cart/items/{id}` | Signed in | Remove a line |
| DELETE | `/cart` | Signed in | Empty the basket |

### Addresses — `/addresses`

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/addresses` | Signed in | My addresses, default first |
| POST | `/addresses` | Signed in | Save one; the first becomes the default |
| GET | `/addresses/{id}` | Signed in | One address |
| PATCH | `/addresses/{id}` | Signed in | Update |
| POST | `/addresses/{id}/default` | Signed in | Make it the default |
| DELETE | `/addresses/{id}` | Signed in | Delete; promotes another if it was default |

### Checkout — `/checkout`

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/checkout/quote` | Signed in | Authoritative cost for this basket and address |

### Orders — `/orders`

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/orders` | Signed in | Turn the basket into an order |
| GET | `/orders` | Signed in | My order history, newest first |
| GET | `/orders/{order_number}` | Signed in | One of my orders, with its tracking timeline |
| POST | `/orders/{order_number}/cancel` | Signed in | Withdraw an order before it is packed |

The request body for `POST /orders` is an address id and nothing else. The
basket is already on the server and the price is the server's to decide.

---

## How a basket is priced

`app/services/pricing.py` is the single authority on what a basket costs. The
checkout quote calls it, and order creation calls the same function, so a
customer can never be quoted one figure and charged another.

```
subtotal      = Σ (mrp           × quantity)   total at MRP
discount      = Σ ((mrp - price) × quantity)   the saving
items_total   = subtotal - discount            what the goods cost
delivery      = 0 when items_total >= FREE_DELIVERY_THRESHOLD, else DELIVERY_CHARGE
total         = items_total + delivery         amount payable
```

**No rounding happens anywhere.** Every amount is a `Decimal` from a
`Numeric(10, 2)` column. A two-decimal price multiplied by an integer is still
exactly two decimals, and adding such values is exact, so the sum of the lines
always equals the total — there is no drift to reconcile.

### A cart item stores no price

`cart_items` records a product and a quantity, and nothing about cost. Totals
are recomputed from the live `products` row on every read, so a price change or
a sell-out between adding an item and checking out shows up immediately rather
than as a surprise at the till. Price is only frozen when an order is placed.

### Nothing about money is read from the client

A request carries product ids, quantities and an address id. Anything else it
sends — `unit_price`, `total`, `discount` — is ignored. There is a test that
posts a basket claiming an item costs ₹0.01 and asserts the server charges the
catalogue price.

### Stock is checked twice

Once when an item is added, and again when the basket is read or quoted,
because the shelf can empty in between. A basket with a problem is still
priced and returned in full, with a message per offending line, so the shopper
can see exactly which item to fix rather than facing a bare refusal.

---

## How an order is placed

`POST /orders` is the one operation in this system that must be all-or-nothing.
It writes an order and its lines, takes stock off the shelf, records the first
audit entry, and empties the basket. `app/services/order_service.py` does all
of that inside a **single transaction with one commit at the end**, so there is
no half-written order and no stock taken for an order that was never created.

Before anything is written, every checkout rule is re-run and the basket is
re-priced. The quote the customer saw may be seconds old, and the shelf can
empty in that time.

### Stock moves atomically

```python
UPDATE products
   SET stock_quantity = stock_quantity - :qty,
       sold_quantity  = sold_quantity  + :qty
 WHERE id = :id AND stock_quantity >= :qty
RETURNING stock_quantity
```

The guard and the arithmetic are in the same statement, so two customers
checking out the last unit cannot both succeed: one matches the row, the other
matches nothing and gets `None`. There is no read-modify-write window to lose.

Multi-line orders reserve stock **in product id order**, so two orders holding
the same two products lock them in the same sequence and cannot deadlock. If
any line fails, the exception rolls back the order, its lines, and the stock
already taken for earlier lines.

### An order is an immutable record

Prices, product names, SKUs, image URLs and the whole delivery address are
snapshotted onto the order. Editing a product or an address afterwards does
not rewrite what was bought, and the database's CHECK constraints keep the
invoice arithmetic true even if the service layer is wrong.

### The status workflow

```
PLACED ──► CONFIRMED ──► PACKING ──► OUT_FOR_DELIVERY ──► DELIVERED
   │            │            │               │
   └────────────┴────────────┴───────────────┴──────────► CANCELLED
```

`ALLOWED_STATUS_TRANSITIONS` in `app/enums.py` is the whole rule. An order
never moves backwards, never skips a stage, and `DELIVERED` and `CANCELLED`
are terminal. Every move is appended to `order_status_history` with who made
it. `/admin/orders/{n}` publishes the moves that remain open so the desktop
client offers only those — and the server re-checks every one regardless.

Customers may cancel only while the order is `PLACED` or `CONFIRMED`; after
that it is a phone call. Cancelling returns the stock and decrements
`sold_quantity`, because a withdrawn order was never a sale.

---

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

**categories** — `id`, `name` (unique), `slug` (unique), `description`,
`image_url`, `display_order`, `is_active`, timestamps. Seeded with the shop's
eight opening categories, all editable by an admin afterwards.

**products** — `id`, `name`, `slug` (unique), `sku` (unique), `description`,
`category_id` → `categories.id` (`RESTRICT`), `mrp`, `selling_price`,
`stock_quantity`, `low_stock_threshold`, `sold_quantity`, `is_active`,
`is_featured`, timestamps.

**product_images** — `id`, `product_id` → `products.id` (`CASCADE`),
`image_url`, `alt_text`, `display_order`, `is_primary`, timestamps.

**addresses** — `id`, `user_id` → `users.id` (`CASCADE`), recipient name and
phone, `house_number`, `street`, `area`, `city`, `state`, `pincode`,
`delivery_instructions`, `is_default`, timestamps.

**carts** — `id`, `user_id` → `users.id` (`CASCADE`, unique: one basket per
customer), timestamps.

**cart_items** — `id`, `cart_id` → `carts.id` (`CASCADE`), `product_id` →
`products.id` (`RESTRICT`), `quantity`, timestamps. Deliberately no price.

**orders** — `id`, `order_number` (unique, `KC-000123`), `user_id` →
`users.id` (`RESTRICT`), `status`, `subtotal`, `discount`, `items_total`,
`delivery_charge`, `total`, `currency`, the delivery address **snapshotted**
field by field, `placed_at`, `delivered_at`, `cancelled_at`,
`cancellation_reason`, timestamps.

**order_items** — `id`, `order_id` → `orders.id` (`CASCADE`), `product_id` →
`products.id` (`RESTRICT`), and a snapshot of what was bought:
`product_name`, `product_sku`, `product_image_url`, `quantity`, `unit_mrp`,
`unit_price`, `line_total`, `line_discount`.

**order_status_history** — `id`, `order_id` → `orders.id` (`CASCADE`),
`from_status`, `to_status`, `changed_by_user_id` → `users.id` (`SET NULL`),
`changed_by_name` (snapshotted), `note`, `created_at`. Append-only.

Orders snapshot everything for one reason: an order is a record of what was
actually bought. Renaming a product or editing a saved address must not
rewrite history. `user_id` is `RESTRICT` so a customer with orders cannot be
deleted out from under them, and `changed_by_user_id` is `SET NULL` with the
name kept, so removing a staff account does not erase who did what.

`RESTRICT` is deliberate: deleting a role that still has users, or a category
that still has products, must fail rather than cascade-delete live data.
Product images use `CASCADE` because an image has no meaning without its
product.

### Database-enforced invariants

These hold even if a bug slips past the service layer:

| Guarantee | Mechanism |
|---|---|
| `selling_price <= mrp` | CHECK constraint |
| Prices and quantities are non-negative | CHECK constraints |
| At most one primary image per product | Partial unique index |
| A category with products cannot be deleted | FK `ON DELETE RESTRICT` |
| Deleting a product removes its images | FK `ON DELETE CASCADE` |
| At most one default address per customer | Partial unique index |
| A PIN code is six digits, never starting with zero | CHECK constraint |
| `items_total = subtotal − discount` on every order | CHECK constraint |
| `total = items_total + delivery_charge` on every order | CHECK constraint |
| Order money and quantities are non-negative | CHECK constraints |
| Order numbers are unique | Unique index |
| A customer with orders cannot be deleted | FK `ON DELETE RESTRICT` |
| A product that has been ordered cannot be deleted | FK `ON DELETE RESTRICT` |
| One line per product in a basket | Composite unique constraint |
| A basket quantity is always positive | CHECK constraint |
| A product in someone's basket cannot be deleted | FK `ON DELETE RESTRICT` |

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
