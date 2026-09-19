/**
 * Authentication state for the admin application.
 *
 * Route guards here are a usability feature only. The backend enforces every
 * permission independently, so hiding a screen never stands in for authorisation.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, applyBaseUrl, setSessionExpiredHandler } from '../api/client';
import { authApi } from '../api/endpoints';
import { bridge } from '../lib/bridge';
import type { User } from '../types/api';

interface AuthState {
  user: User | null;
  /** True while the stored session is being restored on start-up. */
  initialising: boolean;
  signingIn: boolean;
  error: string | null;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  clearError(): void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initialising, setInitialising] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Restore a stored session on launch so the user is not asked to sign in
  // again every time the app opens.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      await applyBaseUrl();
      const session = await bridge().session.get();
      if (!session?.accessToken) {
        if (!cancelled) setInitialising(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        // Token expired, revoked, or the account was deactivated.
        await bridge().session.clear();
      } finally {
        if (!cancelled) setInitialising(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Signing out locally must succeed even if the server is unreachable.
    }
    await bridge().session.clear();
    setUser(null);
  }, []);

  // An unrecoverable 401 from any request drops the session.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      void bridge().session.clear();
      setUser(null);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setSigningIn(true);
    setError(null);
    try {
      const response = await authApi.adminLogin(email, password);
      await bridge().session.set({
        accessToken: response.tokens.access_token,
        refreshToken: response.tokens.refresh_token,
      });
      setUser(response.user);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Something went wrong while signing in. Please try again.';
      setError(message);
      throw caught;
    } finally {
      setSigningIn(false);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      initialising,
      signingIn,
      error,
      login,
      logout,
      clearError: () => setError(null),
    }),
    [user, initialising, signingIn, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider.');
  return context;
}
