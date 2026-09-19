/**
 * Axios instance for the Kumaran Crackers API.
 *
 * Responsibilities:
 *  - attach the bearer token to every request
 *  - refresh a single time on a 401 and replay the original request
 *  - normalise the backend's error envelope into a predictable `ApiError`
 */
import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

import { bridge } from '../lib/bridge';
import type { ApiErrorBody, TokenPair } from '../types/api';
import type { StoredSession } from '../types/session';

/** A failure the UI can render without inspecting axios internals. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, string>;

  constructor(message: string, status: number, code: string, details: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }

  get isPermissionError(): boolean {
    return this.status === 403;
  }
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

let onSessionExpired: (() => void) | null = null;

/** Registered by the auth provider so an unrecoverable 401 logs the user out. */
export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

export const api: AxiosInstance = axios.create({
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

/** Resolve the API base URL from the main process (or the dev fallback). */
export async function resolveBaseUrl(): Promise<string> {
  const { apiBaseUrl } = await bridge().settings.get();
  return apiBaseUrl;
}

export async function applyBaseUrl(): Promise<void> {
  api.defaults.baseURL = await resolveBaseUrl();
}

// ---- Request: attach the access token --------------------------------------
api.interceptors.request.use(async (config) => {
  if (!config.baseURL) config.baseURL = await resolveBaseUrl();

  const session = await bridge().session.get();
  if (session?.accessToken) {
    config.headers.set('Authorization', `Bearer ${session.accessToken}`);
  }
  return config;
});

// ---- Response: refresh once on 401, then normalise errors -------------------
// A single in-flight refresh is shared, so a burst of concurrent 401s does not
// fire N refresh calls and invalidate each other's tokens.
let refreshInFlight: Promise<StoredSession | null> | null = null;

async function refreshSession(): Promise<StoredSession | null> {
  const current = await bridge().session.get();
  if (!current?.refreshToken) return null;

  try {
    const baseURL = await resolveBaseUrl();
    // A bare axios call: using `api` here would recurse through this very
    // interceptor.
    const response = await axios.post<{ tokens: TokenPair }>(
      `${baseURL}/auth/refresh`,
      { refresh_token: current.refreshToken },
      { headers: { 'Content-Type': 'application/json' }, timeout: 15_000 },
    );
    const next: StoredSession = {
      accessToken: response.data.tokens.access_token,
      refreshToken: response.data.tokens.refresh_token,
    };
    await bridge().session.set(next);
    return next;
  } catch {
    await bridge().session.clear();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const config = error.config as RetriableConfig | undefined;
    const status = error.response?.status ?? 0;

    // Never try to refresh the refresh call itself, and only ever retry once.
    const isAuthEndpoint = config?.url?.includes('/auth/');
    if (status === 401 && config && !config._retried && !isAuthEndpoint) {
      config._retried = true;

      refreshInFlight ??= refreshSession().finally(() => {
        refreshInFlight = null;
      });
      const session = await refreshInFlight;

      if (session) {
        config.headers.set('Authorization', `Bearer ${session.accessToken}`);
        return api.request(config);
      }
      onSessionExpired?.();
    }

    if (!error.response) {
      throw new ApiError(
        'Cannot reach the Kumaran Crackers server. Check that it is running and try again.',
        0,
        'network_error',
      );
    }

    const body = error.response.data;
    throw new ApiError(
      body?.error?.message ?? 'Something went wrong. Please try again.',
      status,
      body?.error?.code ?? 'unknown_error',
      body?.error?.details ?? {},
    );
  },
);
