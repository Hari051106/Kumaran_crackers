/**
 * Preload bridge.
 *
 * This is the ONLY channel between the renderer and privileged code. Node's
 * globals are never handed across: `contextBridge` copies a small set of
 * async functions into the isolated world, so the React code can ask the main
 * process to do things but can never reach `fs`, `child_process` or
 * `ipcRenderer` itself.
 *
 * Adding a capability here widens the attack surface. Keep it small.
 */
import { contextBridge, ipcRenderer } from 'electron';

export type StoredSession = { accessToken: string; refreshToken: string };

export type AppInfo = {
  /** The renderer's own origin, which the API must allowlist for CORS. */
  origin: string;
  version: string;
  platform: string;
  isDev: boolean;
  encryptionAvailable: boolean;
};

const api = {
  session: {
    /** Read the stored session, or null when signed out. */
    get: (): Promise<StoredSession | null> => ipcRenderer.invoke('session:get'),
    /** Persist tokens via the OS keychain in the main process. */
    set: (session: StoredSession): Promise<boolean> =>
      ipcRenderer.invoke('session:set', session),
    /** Forget the stored session. */
    clear: (): Promise<boolean> => ipcRenderer.invoke('session:clear'),
  },
  settings: {
    get: (): Promise<{ apiBaseUrl: string }> => ipcRenderer.invoke('settings:get'),
    setApiBaseUrl: (url: string): Promise<boolean> =>
      ipcRenderer.invoke('settings:setApiBaseUrl', url),
  },
  app: {
    info: (): Promise<AppInfo> => ipcRenderer.invoke('app:info'),
  },
};

export type KumaranBridge = typeof api;

contextBridge.exposeInMainWorld('kumaran', api);
