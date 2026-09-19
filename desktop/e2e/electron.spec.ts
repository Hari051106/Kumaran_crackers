/**
 * Security audit of the real Electron application.
 *
 * This launches the actual packaged main process, not a simulation, and
 * verifies the renderer it creates cannot reach Node. These assertions are the
 * difference between "we set contextIsolation" and "the renderer genuinely has
 * no filesystem access".
 */
import { test, expect, _electron as electron, type ElectronApplication } from '@playwright/test';

// Supplied by the environment so no working credential is committed.
// Defaults match the local development admin created by
// `python -m app.initial_data`.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@kumarancrackers.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'Admin@12345';

let app: ElectronApplication;

test.beforeAll(async () => {
  app = await electron.launch({
    args: [
      '.',
      // Required only because the CI container runs as root; the application
      // itself never disables the sandbox.
      '--no-sandbox',
    ],
    cwd: process.cwd(),
  });
});

test.afterAll(async () => {
  await app?.close();
});

test('the application window opens', async () => {
  const window = await app.firstWindow();
  await expect.poll(() => window.title(), { timeout: 20_000 }).toContain('Kumaran Crackers');
});

test('the renderer has no access to Node', async () => {
  const window = await app.firstWindow();

  const leaks = await window.evaluate(() => ({
    require: typeof (globalThis as Record<string, unknown>).require,
    process: typeof (globalThis as Record<string, unknown>).process,
    module: typeof (globalThis as Record<string, unknown>).module,
    Buffer: typeof (globalThis as Record<string, unknown>).Buffer,
    global: typeof (globalThis as Record<string, unknown>).global,
  }));

  // If any of these were 'object' or 'function', a cross-site script in the
  // renderer could read and write the user's filesystem.
  expect(leaks.require).toBe('undefined');
  expect(leaks.process).toBe('undefined');
  expect(leaks.module).toBe('undefined');
  expect(leaks.Buffer).toBe('undefined');
  expect(leaks.global).toBe('undefined');
});

test('the preload bridge exposes only the intended surface', async () => {
  const window = await app.firstWindow();

  const shape = await window.evaluate(() => {
    const bridge = (window as unknown as { kumaran?: Record<string, Record<string, unknown>> })
      .kumaran;
    if (!bridge) return null;
    return Object.fromEntries(
      Object.entries(bridge).map(([namespace, members]) => [namespace, Object.keys(members).sort()]),
    );
  });

  expect(shape).toEqual({
    app: ['info'],
    session: ['clear', 'get', 'set'],
    settings: ['get', 'setApiBaseUrl'],
  });
});

test('ipcRenderer itself is not reachable from the renderer', async () => {
  const window = await app.firstWindow();
  const exposed = await window.evaluate(
    () => typeof (window as Record<string, unknown>).ipcRenderer,
  );
  // Exposing ipcRenderer would let renderer code invoke arbitrary IPC channels.
  expect(exposed).toBe('undefined');
});

test('web preferences are locked down', async () => {
  const preferences = await app.evaluate(async ({ BrowserWindow }) => {
    const [first] = BrowserWindow.getAllWindows();
    return first?.webContents.getLastWebPreferences() ?? null;
  });

  expect(preferences).not.toBeNull();
  expect(preferences?.nodeIntegration).toBeFalsy();
  expect(preferences?.contextIsolation).not.toBe(false);
  expect(preferences?.sandbox).not.toBe(false);
  expect(preferences?.webSecurity).not.toBe(false);
});

test('the session store starts empty and round-trips through the main process', async () => {
  const window = await app.firstWindow();

  const result = await window.evaluate(async () => {
    const bridge = (window as unknown as {
      kumaran: {
        session: {
          get(): Promise<unknown>;
          set(value: unknown): Promise<boolean>;
          clear(): Promise<boolean>;
        };
      };
    }).kumaran;

    await bridge.session.clear();
    const empty = await bridge.session.get();

    const accepted = await bridge.session.set({ accessToken: 'a.b.c', refreshToken: 'd.e.f' });
    const stored = await bridge.session.get();

    // A malformed payload must be rejected rather than persisted.
    const rejected = await bridge.session.set({ nonsense: true });

    await bridge.session.clear();
    const cleared = await bridge.session.get();

    return { empty, accepted, stored, rejected, cleared };
  });

  expect(result.empty).toBeNull();
  expect(result.accepted).toBe(true);
  expect(result.stored).toEqual({ accessToken: 'a.b.c', refreshToken: 'd.e.f' });
  expect(result.rejected).toBe(false);
  expect(result.cleared).toBeNull();
});

test('the main process rejects a non-http API address', async () => {
  const window = await app.firstWindow();

  const outcome = await window.evaluate(async () => {
    const bridge = (window as unknown as {
      kumaran: { settings: { setApiBaseUrl(url: string): Promise<boolean> } };
    }).kumaran;
    return {
      fileScheme: await bridge.settings.setApiBaseUrl('file:///etc/passwd'),
      garbage: await bridge.settings.setApiBaseUrl('not-a-url'),
      valid: await bridge.settings.setApiBaseUrl('http://127.0.0.1:8000/api/v1'),
    };
  });

  expect(outcome.fileScheme).toBe(false);
  expect(outcome.garbage).toBe(false);
  expect(outcome.valid).toBe(true);
});


test('the renderer is served from the app:// origin, not file://', async () => {
  const window = await app.firstWindow();
  const origin = await window.evaluate(() => window.location.origin);

  // A file:// page has an opaque origin that is sent as `Origin: null`, which
  // the API refuses - so the packaged app could never sign in.
  expect(origin).toBe('app://kumaran');
  expect(origin.startsWith('file://')).toBe(false);
});

test('the app:// handler never serves files outside the bundle', async () => {
  const window = await app.firstWindow();

  const attempts = await window.evaluate(async () => {
    const urls = [
      'app://kumaran/../../../../etc/passwd',
      'app://kumaran/etc/passwd',
      'app://kumaran/%2e%2e/%2e%2e/%2e%2e/etc/passwd',
    ];
    return Promise.all(
      urls.map(async (url) => {
        try {
          const response = await fetch(url);
          return { url, status: response.status, body: await response.text() };
        } catch {
          return { url, status: 0, body: '' };
        }
      }),
    );
  });

  for (const attempt of attempts) {
    // Chromium normalises the path for a standard scheme before the handler
    // sees it, so these resolve inside the bundle, miss, and fall back to the
    // SPA shell. What matters is that no system file is ever returned.
    expect(attempt.body).not.toContain('root:');
    expect(attempt.body).not.toContain('/bin/bash');
    if (attempt.status === 200) {
      expect(attempt.body).toContain('<!doctype html>');
    }
  }
});

test('the packaged application can actually sign in against the live API', async () => {
  const window = await app.firstWindow();

  // Start from a known signed-out state: a stored session from an earlier run
  // would (correctly) take the app straight to the dashboard.
  await window.evaluate(async () => {
    await (window as unknown as { kumaran: { session: { clear(): Promise<boolean> } } })
      .kumaran.session.clear();
  });
  await window.reload();

  // This is the assertion that catches the CORS trap: a renderer on an opaque
  // origin reaches the login screen perfectly well and then fails every
  // request. Only a real round trip proves the wiring.
  await window.waitForSelector('[data-testid="login-submit"]', { timeout: 20_000 });

  await window.getByLabel('Email address').fill(ADMIN_EMAIL);
  await window.getByLabel('Password').fill(ADMIN_PASSWORD);
  await window.getByTestId('login-submit').click();

  await expect(window.getByTestId('dashboard')).toBeVisible({ timeout: 20_000 });
  await expect(window.getByTestId('stat-products')).toBeVisible();
});

test('the session survives a reload, having been stored by the main process', async () => {
  const window = await app.firstWindow();

  await window.reload();
  // No second sign-in: the token was read back from the OS-protected store.
  await expect(window.getByTestId('dashboard')).toBeVisible({ timeout: 20_000 });
});
