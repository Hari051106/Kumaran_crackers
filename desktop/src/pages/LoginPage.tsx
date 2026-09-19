/**
 * Back-office sign-in.
 *
 * The backend rejects customer accounts at this endpoint even with correct
 * credentials, so a stolen shopper password cannot open the admin console.
 */
import { useState, type FormEvent } from 'react';

import { useAuth } from '../auth/AuthContext';
import { Button, Field, TextInput } from '../components/ui';

export function LoginPage() {
  const { login, signingIn, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState(false);

  const emailInvalid = touched && !email.trim();
  const passwordInvalid = touched && !password;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!email.trim() || !password) return;
    try {
      await login(email.trim(), password);
    } catch {
      // The provider already surfaced the message; nothing further to do here.
    }
  }

  return (
    <div className="flex h-full">
      {/* ---- Brand panel ---- */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-shell-900 p-12 lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500 text-xl font-bold text-white">
            K
          </div>
          <div>
            <p className="text-base font-semibold text-white">Kumaran Crackers</p>
            <p className="text-sm text-shell-400">Admin Console</p>
          </div>
        </div>

        <div>
          <h2 className="max-w-md text-3xl font-semibold leading-tight text-white">
            Celebrate Every Moment with Kumaran Crackers
          </h2>
          <p className="mt-4 max-w-md text-sm leading-6 text-shell-400">
            Manage your catalogue, stock and orders from one place.
          </p>
        </div>

        <p className="text-xs text-shell-500">
          Authorised staff only. All activity is recorded.
        </p>
      </div>

      {/* ---- Form ---- */}
      <div className="flex w-full items-center justify-center bg-shell-50 px-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500 text-xl font-bold text-white">
              K
            </div>
            <p className="text-base font-semibold text-shell-900">Kumaran Crackers Admin</p>
          </div>

          <h1 className="text-2xl font-semibold text-shell-900">Sign in</h1>
          <p className="mt-1 text-sm text-shell-500">
            Use your staff or administrator account.
          </p>

          <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5" noValidate>
            {error && (
              <div
                role="alert"
                data-testid="login-error"
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800"
              >
                {error}
              </div>
            )}

            <Field label="Email address" htmlFor="email" required
                   error={emailInvalid ? 'Enter your email address.' : undefined}>
              <TextInput
                id="email"
                name="email"
                required
                aria-required="true"
                type="email"
                autoComplete="username"
                autoFocus
                value={email}
                invalid={emailInvalid}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (error) clearError();
                }}
                placeholder="you@kumarancrackers.com"
              />
            </Field>

            <Field label="Password" htmlFor="password" required
                   error={passwordInvalid ? 'Enter your password.' : undefined}>
              <div className="relative">
                <TextInput
                  id="password"
                  name="password"
                  required
                  aria-required="true"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  invalid={passwordInvalid}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) clearError();
                  }}
                  className="pr-16"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="focus-ring absolute inset-y-0 right-0 rounded-r-lg px-3 text-xs font-semibold text-shell-500 hover:text-shell-700"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </Field>

            <Button type="submit" loading={signingIn} data-testid="login-submit" className="mt-2 w-full">
              {signingIn ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
