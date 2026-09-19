# Kumaran Crackers Admin

> *Celebrate Every Moment with Kumaran Crackers*

The back-office desktop application: Electron + React + Vite + Tailwind, talking
to the Kumaran Crackers FastAPI backend.

It holds **no business logic**. Prices, discounts, stock status and permissions
are all decided by the server; this application renders them and sends back
intent.

---

## Security posture

The renderer is treated as untrusted code. Three settings do most of the work:

```ts
nodeIntegration: false,   // no require(), no fs, no child_process
contextIsolation: true,   // preload and page cannot share globals
sandbox: true,            // the renderer runs in the OS sandbox
```

Everything privileged goes through the preload bridge in `electron/preload.ts`,
which exposes exactly three namespaces and nothing else:

| Namespace | Members | Purpose |
|---|---|---|
| `session` | `get`, `set`, `clear` | Tokens, held by the main process |
| `settings` | `get`, `setApiBaseUrl` | Which server to talk to |
| `app` | `info` | Version, platform, encryption status |

`ipcRenderer` itself is never exposed — otherwise renderer code could invoke
arbitrary IPC channels.

### Credential storage

Tokens are **never** placed in `localStorage`, which any injected script can
read. They live in the main process, encrypted at rest with the OS keychain
(DPAPI on Windows, Keychain on macOS, libsecret on Linux) via Electron's
`safeStorage`.

Where no keychain exists — a bare Linux CI box, for instance — the app refuses
to pretend: it marks the payload as plaintext, logs a warning, and the Settings
screen shows an **Unencrypted** badge.

### Why `app://` and not `file://`

The packaged renderer is served over a registered `app://kumaran` scheme rather
than loaded from `file://`.

A `file://` page has an *opaque* origin, which the browser transmits as
`Origin: null`. A correctly configured API rejects that, so the packaged
application would reach the login screen and then fail every request. The
alternative — allowing `null` server-side — would let any local HTML file call
the API. A custom scheme gives the renderer a real, stable origin the backend
can allowlist, and the handler refuses to serve anything outside the bundle.

The backend must therefore include `app://kumaran` in `CORS_ORIGINS`.

### Other hardening

- A Content-Security-Policy meta tag: no inline scripts, no remote code,
  connections only to the local API.
- `will-navigate` is blocked for any origin but the app's own.
- New windows are denied; `https://` links open in the user's browser instead.

---

## Getting started

Requires the backend running on `http://127.0.0.1:8000`.

```bash
cd desktop
npm install

npm run dev          # Vite dev server + Electron, with hot reload
npm run build        # typecheck, build the renderer, bundle main + preload
npm run package:win  # produce a Windows installer
```

| Script | What it does |
|---|---|
| `npm run dev` | Development, with the renderer hot-reloading |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | Typecheck, then build renderer and Electron bundles |
| `npm run preview` | Serve the built renderer in a browser on :4173 |
| `npm run package:win` | Windows installer via electron-builder |

---

## Project layout

```
desktop/
├── electron/
│   ├── main.ts        Window, app:// protocol, IPC, credential storage
│   └── preload.ts     The context bridge - the only privileged surface
├── src/
│   ├── api/           Axios client (token refresh) + typed endpoints
│   ├── auth/          Session restore, login, logout
│   ├── components/    Buttons, fields, tables, modals, toasts, stat cards
│   ├── layouts/       AppShell - sidebar, header, routed outlet
│   ├── lib/           Money formatting, the bridge accessor
│   ├── pages/         Login, Dashboard, Products, Categories, Inventory…
│   └── types/         Mirrors of the backend schemas
├── e2e/               Playwright: Electron security + admin workflow
└── scripts/           esbuild bundling for main and preload
```

---

## Money on the client

The API sends money as an exact decimal **string** (`"1874.25"`). The client
keeps it a string from the API response, through the form inputs, and back into
the request body.

```ts
// Correct - formatting operates on the string
formatMoney('1874.25');   // "₹1,874.25"

// Wrong - reintroduces the error the Decimal column exists to prevent
Number('1874.25')
```

`src/lib/money.ts` formats and compares decimal strings without ever going
through a float, including Indian digit grouping (`₹1,40,568.75`).

---

## What the dashboard shows — and does not

Every figure comes from the live database. Sales, revenue and order counts do
not exist until the order system lands, so the backend returns
`sales_metrics_available: false` and the dashboard states that plainly.

Nothing on any screen is mocked. The Orders, Customers, Delivery and Reports
screens say which milestone brings them rather than displaying invented rows — a
screen of fake data is worse than an honest empty one, because it looks like it
works.

---

## Testing

```bash
npx playwright test                      # everything
npx playwright test e2e/electron.spec.ts # security audit of the real binary
npx playwright test e2e/admin-flow.spec.ts
```

Both suites need the backend running. They sign in with `E2E_ADMIN_EMAIL` /
`E2E_ADMIN_PASSWORD`, defaulting to the local development admin that
`python -m app.initial_data` creates. Set them to match your own environment
if you changed `FIRST_ADMIN_PASSWORD`.

**`electron.spec.ts`** launches the real Electron binary and asserts the
renderer genuinely cannot reach Node (`require`, `process`, `module`, `Buffer`
and `global` are all `undefined`), that the bridge exposes only the intended
members, that the `app://` handler will not serve files outside the bundle, and
that the packaged app can actually authenticate against the live API.

**`admin-flow.spec.ts`** drives the built renderer in Chromium against a live
backend and a real PostgreSQL database: sign in, create a category, add a
product with a price and stock, confirm the price survives the round trip
exactly, adjust inventory, and check that server-side rules (stock floor, MRP
ceiling, category-with-products) surface properly in the UI.

On a machine without a display, prefix with `xvfb-run -a`.

### Chromium

The config points at a Chromium already present in the environment. Override
with `CHROMIUM_PATH` if yours lives elsewhere.
