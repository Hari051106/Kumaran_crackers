/**
 * Typed access to the Electron preload bridge.
 *
 * In the packaged desktop application `window.kumaran` is always present and
 * tokens are held by the main process, encrypted by the OS keychain.
 *
 * When the same renderer is opened in a plain browser - which is how the UI is
 * exercised in automated tests - there is no main process to talk to, so a
 * clearly-labelled `sessionStorage` fallback stands in. It is dev/test only:
 * shipping builds always run inside Electron and take the secure path.
 */
import type { StoredSession } from '../types/session';

type SettingsShape = { apiBaseUrl: string };

interface KumaranBridge {
  session: {
    get(): Promise<StoredSession | null>;
    set(session: StoredSession): Promise<boolean>;
    clear(): Promise<boolean>;
  };
  settings: {
    get(): Promise<SettingsShape>;
    setApiBaseUrl(url: string): Promise<boolean>;
  };
  app: {
    info(): Promise<{
      origin: string;
      version: string;
      platform: string;
      isDev: boolean;
      encryptionAvailable: boolean;
    }>;
  };
}

declare global {
  interface Window {
    kumaran?: KumaranBridge;
  }
}

const FALLBACK_SESSION_KEY = 'kumaran.dev.session';
const FALLBACK_SETTINGS_KEY = 'kumaran.dev.apiBaseUrl';
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export const isElectron = (): boolean => typeof window !== 'undefined' && !!window.kumaran;

function safeRead(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    /* storage blocked - the session simply will not persist */
  }
}

const browserFallback: KumaranBridge = {
  session: {
    async get() {
      const raw = safeRead(FALLBACK_SESSION_KEY);
      if (!raw) return null;
      try {
        return JSON.parse(raw) as StoredSession;
      } catch {
        return null;
      }
    },
    async set(session) {
      safeWrite(FALLBACK_SESSION_KEY, JSON.stringify(session));
      return true;
    },
    async clear() {
      try {
        window.sessionStorage.removeItem(FALLBACK_SESSION_KEY);
      } catch {
        /* nothing to clear */
      }
      return true;
    },
  },
  settings: {
    async get() {
      return { apiBaseUrl: safeRead(FALLBACK_SETTINGS_KEY) ?? DEFAULT_API_BASE_URL };
    },
    async setApiBaseUrl(url) {
      safeWrite(FALLBACK_SETTINGS_KEY, url);
      return true;
    },
  },
  app: {
    async info() {
      return {
        origin: window.location.origin,
        version: 'dev',
        platform: 'browser',
        isDev: true,
        encryptionAvailable: false,
      };
    },
  },
};

export function bridge(): KumaranBridge {
  return window.kumaran ?? browserFallback;
}
