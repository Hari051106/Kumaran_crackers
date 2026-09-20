# Kumaran Crackers — Customer App

> *Celebrate Every Moment with Kumaran Crackers*

The shopper-facing Flutter application. Android is the primary target; the code
is written to stay iOS-compatible and also builds for web, which is how the UI
is exercised in automated checks.

It holds **no business logic**. Prices, discounts, stock status and search are
all decided by the server; this app renders them and sends back intent.

---

## Running it

Requires the backend on `http://127.0.0.1:8000`.

```bash
cd mobile
flutter pub get

# Android emulator — 10.2.2 is how the emulator reaches the host's localhost
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1

# Physical device on the same network
flutter run --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1

# Release APK
flutter build apk --release --dart-define=API_BASE_URL=https://api.example.com/api/v1
```

`API_BASE_URL` defaults to the Android emulator address, so `flutter run` works
on an emulator with no extra flags.

### Web build

```bash
flutter build web --release --no-web-resources-cdn \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1
```

`--no-web-resources-cdn` serves CanvasKit from the bundle rather than
`gstatic.com`, keeping the build self-contained and working behind a
restrictive network. Native builds do not use CanvasKit at all.

The web origin must be listed in the backend's `CORS_ORIGINS`. A real Android
or iOS build sends no `Origin` header and is unaffected by CORS.

---

## Architecture

```
lib/
├── main.dart              Entry point
├── app.dart               Theme, router, session restore
├── core/
│   ├── api_client.dart    Dio + bearer token + one-shot refresh
│   ├── api_exception.dart One failure type the UI can render
│   ├── config.dart        Build-time configuration
│   ├── dates.dart         Date and time formatting for order screens
│   ├── money.dart         Decimal-string formatting - no floats
│   ├── theme.dart         Material 3 theme
│   └── token_storage.dart Keystore / Keychain via flutter_secure_storage
├── models/                Mirrors of the backend schemas
├── repositories/          One method per endpoint
├── providers/             Riverpod wiring
├── router/                GoRouter routes
├── features/              Splash, auth, home, catalogue, cart, checkout,
│                          addresses, orders, profile
└── widgets/               Product card, stock chip, order status chip,
                           state views
```

**Packages:** `flutter_riverpod` (state), `go_router` (navigation), `dio`
(HTTP), `flutter_secure_storage` (tokens), `cached_network_image` (imagery).

---

## Money

The API sends money as an exact decimal **string** (`"1874.25"`). The app keeps
it a string from response to screen.

```dart
formatMoney('1874.25');   // ₹1,874.25
formatMoney('1234567.89') // ₹12,34,567.89  (Indian grouping)

double.parse('1874.25')   // never - reintroduces the error the
                          // backend's Decimal columns exist to prevent
```

`core/money.dart` formats and compares decimal strings without ever touching a
`double`, including `compareMoney`, which stays exact past 2^53 where a double
silently rounds.

**There is no client-side arithmetic on money at all.** The basket and checkout
screens display the subtotal, discount, delivery charge and total exactly as the
server computed them. The app never adds up a line, never applies a discount and
never decides a delivery charge — so the figure a shopper reads is by
construction the figure that will be charged.

---

## Security

| Concern | Handling |
|---|---|
| Token storage | `flutter_secure_storage` — Android Keystore via EncryptedSharedPreferences, iOS Keychain. Never `SharedPreferences`. |
| Token refresh | One shared in-flight refresh, so a burst of 401s cannot fire N refreshes that invalidate each other. |
| Refresh loops | Auth endpoints are excluded from refresh, and each request is retried at most once. |
| Authorisation | Enforced entirely by the API. The app has no admin surface to hide. |
| Corrupt keystore | Reading a damaged entry signs the user out rather than crashing on launch. |

---

## What is real, and what is not

Every screen reads live data. Nothing is mocked.

**There is no "best sellers" row.** Nothing has been sold until the order
system exists, so that row would be an arbitrary ordering presented as
popularity. The home screen instead shows Featured (admin-curated), Special
offers (priced below MRP) and New arrivals — all of which mean something today.

**No promotional banner carousel.** Banners are marketing content the backend
does not model yet; a hardcoded set of images would be exactly the mock data
this project avoids.

The basket, delivery addresses, checkout and ordering are all live. "Place
order" places a real order: the server re-prices the basket, takes the stock
and empties the cart in one transaction, and the app lands on the new order's
tracking screen.

**Order progress is never guessed.** The tracking timeline fills a stage only
when the server says it was reached, and each stage shows the timestamp it
happened. A status the app does not recognise is rendered using the server's
own label rather than being mapped to the nearest one it knows — a wrong
status would tell the shopper something untrue about their order.

**Whether an order can be cancelled is the server's answer**
(`is_cancellable_by_customer`), not a rule re-implemented here. The button
appears only when the server says it applies, and the server re-checks anyway.

---

## Testing

```bash
flutter analyze     # static analysis, strict-casts and strict-raw-types on
flutter test        # unit and widget tests
```

The suite covers money formatting exactly (including precision a `double`
cannot hold), JSON parsing that keeps money as strings, the quantity selector
capping at available stock, an unknown stock status failing closed to
out-of-stock, an unknown *order* status falling back to the server's label
rather than being guessed, date formatting at both ends of the 12-hour clock,
form validation mirroring the server's password and phone rules, and status
state always being conveyed by words and an icon rather than colour alone.

### Driving the real app

The web build served over HTTP and driven with Chromium exercises the real
widgets against the live API. That flow covers the home screen's four queries,
debounced search, filters, product detail by slug, registration writing a new
customer to PostgreSQL, and checkout placing a real order that lands on the
tracking screen with the basket emptied and the stock moved.
