/**
 * Kumaran Crackers Admin - Electron main process.
 *
 * Security posture: the renderer is treated as untrusted. It runs sandboxed,
 * with context isolation on and Node integration off, and reaches privileged
 * capability only through the narrow, explicitly enumerated IPC surface
 * declared in `preload.ts`.
 */
import { app, BrowserWindow, ipcMain, net, protocol, safeStorage, shell } from 'electron';
import { join, normalize, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';

/**
 * The dev server URL is passed explicitly by `npm run dev`. Deciding from
 * `app.isPackaged` alone would be wrong: an unpackaged *production* build has
 * no dev server to talk to and must load the built renderer from disk.
 */
const DEV_SERVER_URL = process.env.ELECTRON_RENDERER_URL ?? null;
const IS_DEV = DEV_SERVER_URL !== null;
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

/**
 * The built renderer is served over a registered `app://` scheme rather than
 * `file://`.
 *
 * A file:// page has an opaque origin, which the browser sends as
 * `Origin: null`. A correctly-configured API rejects that, so the packaged
 * application could never authenticate - and the alternative, allowing
 * `null` server-side, would let any local HTML file call the API. A custom
 * scheme gives the renderer a real, stable origin the backend can allowlist.
 */
const APP_SCHEME = 'app';
const APP_ORIGIN = `${APP_SCHEME}://kumaran`;

/** Origins the renderer may navigate to. */
const ALLOWED_ORIGINS = new Set(
  DEV_SERVER_URL ? [new URL(DEV_SERVER_URL).origin] : [APP_ORIGIN],
);

// Must be declared before `app.whenReady()`.
protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
    },
  },
]);

/** Serve the built renderer, refusing anything outside the bundle directory. */
function registerAppProtocol(): void {
  const rendererRoot = join(__dirname, '..', 'dist');

  protocol.handle(APP_SCHEME, (request) => {
    const { pathname } = new URL(request.url);
    const relative = decodeURIComponent(pathname === '/' ? '/index.html' : pathname);

    // Resolve, then verify the result is still inside the bundle. Without this
    // check, `app://kumaran/../../etc/passwd` would escape the directory.
    const resolved = normalize(join(rendererRoot, relative));
    if (resolved !== rendererRoot && !resolved.startsWith(rendererRoot + sep)) {
      return new Response('Forbidden', { status: 403 });
    }
    if (!existsSync(resolved)) {
      // Unknown paths fall back to the SPA entry point.
      return net.fetch(pathToFileURL(join(rendererRoot, 'index.html')).toString());
    }
    return net.fetch(pathToFileURL(resolved).toString());
  });
}

let mainWindow: BrowserWindow | null = null;

// ---------------------------------------------------------------------------
// Credential storage
//
// Tokens live in the main process, never in renderer-accessible storage such
// as localStorage. They are encrypted at rest with the OS keychain where one
// is available (DPAPI on Windows, Keychain on macOS, libsecret on Linux).
// ---------------------------------------------------------------------------
type StoredSession = { accessToken: string; refreshToken: string };

function sessionFile(): string {
  return join(app.getPath('userData'), 'session.bin');
}

function settingsFile(): string {
  return join(app.getPath('userData'), 'settings.json');
}

function writeSecret(value: string): void {
  if (safeStorage.isEncryptionAvailable()) {
    writeFileSync(sessionFile(), safeStorage.encryptString(value));
    return;
  }
  // No OS keyring (common on a bare Linux CI box). Refuse to pretend this is
  // encrypted - mark the payload plainly so it is never mistaken for a
  // protected blob, and warn loudly.
  console.warn(
    '[kumaran] OS credential encryption is unavailable; the session token is ' +
      'being stored unencrypted. Do not use this machine for production data.',
  );
  writeFileSync(sessionFile(), `PLAINTEXT:${value}`, 'utf8');
}

function readSecret(): string | null {
  const path = sessionFile();
  if (!existsSync(path)) return null;
  try {
    const raw = readFileSync(path);
    const asText = raw.toString('utf8');
    if (asText.startsWith('PLAINTEXT:')) return asText.slice('PLAINTEXT:'.length);
    if (!safeStorage.isEncryptionAvailable()) return null;
    return safeStorage.decryptString(raw);
  } catch {
    // A corrupt or undecryptable blob must log the user out, not crash the app.
    return null;
  }
}

function readSettings(): { apiBaseUrl: string } {
  try {
    const path = settingsFile();
    if (!existsSync(path)) return { apiBaseUrl: DEFAULT_API_BASE_URL };
    const parsed = JSON.parse(readFileSync(path, 'utf8')) as { apiBaseUrl?: unknown };
    return {
      apiBaseUrl:
        typeof parsed.apiBaseUrl === 'string' && parsed.apiBaseUrl
          ? parsed.apiBaseUrl
          : DEFAULT_API_BASE_URL,
    };
  } catch {
    return { apiBaseUrl: DEFAULT_API_BASE_URL };
  }
}

// ---------------------------------------------------------------------------
// IPC surface
// ---------------------------------------------------------------------------
function registerIpcHandlers(): void {
  ipcMain.handle('session:get', (): StoredSession | null => {
    const raw = readSecret();
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as Partial<StoredSession>;
      if (typeof parsed.accessToken !== 'string' || typeof parsed.refreshToken !== 'string') {
        return null;
      }
      return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken };
    } catch {
      return null;
    }
  });

  ipcMain.handle('session:set', (_event, session: unknown): boolean => {
    // Never trust the shape coming from the renderer.
    const candidate = session as Partial<StoredSession> | null;
    if (
      !candidate ||
      typeof candidate.accessToken !== 'string' ||
      typeof candidate.refreshToken !== 'string'
    ) {
      return false;
    }
    writeSecret(
      JSON.stringify({
        accessToken: candidate.accessToken,
        refreshToken: candidate.refreshToken,
      }),
    );
    return true;
  });

  ipcMain.handle('session:clear', (): boolean => {
    try {
      rmSync(sessionFile(), { force: true });
    } catch {
      /* already gone */
    }
    return true;
  });

  ipcMain.handle('settings:get', () => readSettings());

  ipcMain.handle('settings:setApiBaseUrl', (_event, url: unknown): boolean => {
    if (typeof url !== 'string') return false;
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return false;
    }
    // Only ever speak HTTP(S) - no file:, no custom schemes.
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    writeFileSync(
      settingsFile(),
      JSON.stringify({ apiBaseUrl: url.replace(/\/+$/, '') }, null, 2),
      'utf8',
    );
    return true;
  });

  ipcMain.handle('app:info', () => ({
    origin: DEV_SERVER_URL ? new URL(DEV_SERVER_URL).origin : APP_ORIGIN,
    version: app.getVersion(),
    platform: process.platform,
    isDev: IS_DEV,
    encryptionAvailable: safeStorage.isEncryptionAvailable(),
  }));
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------
function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 680,
    show: false,
    backgroundColor: '#0c111b',
    title: 'Kumaran Crackers Admin',
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      // The three settings that matter most: the renderer gets no Node, no
      // shared context with the preload, and runs inside the OS sandbox.
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow?.show());

  // A compromised renderer must not be able to navigate itself somewhere else.
  mainWindow.webContents.on('will-navigate', (event, url) => {
    let target: URL;
    try {
      target = new URL(url);
    } catch {
      event.preventDefault();
      return;
    }
    if (!ALLOWED_ORIGINS.has(target.origin)) event.preventDefault();
  });

  // External links open in the user's browser; the app never spawns windows.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) void shell.openExternal(url);
    return { action: 'deny' };
  });

  if (DEV_SERVER_URL) {
    void mainWindow.loadURL(DEV_SERVER_URL);
  } else {
    void mainWindow.loadURL(`${APP_ORIGIN}/index.html`);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  if (!DEV_SERVER_URL) registerAppProtocol();
  registerIpcHandlers();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Refuse to create additional renderers with unsafe preferences.
app.on('web-contents-created', (_event, contents) => {
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
});
