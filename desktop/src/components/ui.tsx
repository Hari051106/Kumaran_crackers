/**
 * Shared presentational building blocks.
 *
 * Kept in one module because each is small and they are always imported
 * together; splitting them into a file each would add noise, not clarity.
 */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';

// ---- Button -----------------------------------------------------------------
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-300',
  secondary:
    'bg-white text-shell-700 border border-shell-300 hover:bg-shell-50 disabled:text-shell-400',
  danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
  ghost: 'text-shell-600 hover:bg-shell-100 disabled:text-shell-400',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = 'primary',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`focus-ring inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${BUTTON_VARIANTS[variant]} ${className}`}
    >
      {loading ? <Spinner className="h-4 w-4" /> : icon}
      {children}
    </button>
  );
}

// ---- Spinner ----------------------------------------------------------------
export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path
        d="M12 2a10 10 0 0110 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        className="opacity-90"
      />
    </svg>
  );
}

// ---- Form fields -------------------------------------------------------------
interface FieldProps {
  label: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

export function Field({ label, htmlFor, error, hint, required, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-shell-700">
        {label}
        {/* aria-hidden so the accessible name stays "Password" rather than
            "Password star". Required-ness is conveyed by the control's own
            aria-required attribute instead. */}
        {required && (
          <span aria-hidden="true" className="ml-0.5 text-rose-600">
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p className="text-xs font-medium text-rose-600">{error}</p>
      ) : hint ? (
        <p className="text-xs text-shell-500">{hint}</p>
      ) : null}
    </div>
  );
}

const CONTROL_CLASSES =
  'focus-ring w-full rounded-lg border border-shell-300 bg-white px-3 py-2 text-sm text-shell-900 placeholder:text-shell-400 disabled:bg-shell-100 disabled:text-shell-500';

export function TextInput({
  invalid,
  className = '',
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      {...rest}
      aria-invalid={invalid || undefined}
      className={`${CONTROL_CLASSES} ${invalid ? 'border-rose-400' : ''} ${className}`}
    />
  );
}

export function Select({
  invalid,
  className = '',
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      {...rest}
      aria-invalid={invalid || undefined}
      className={`${CONTROL_CLASSES} ${invalid ? 'border-rose-400' : ''} ${className}`}
    >
      {children}
    </select>
  );
}

export function TextArea({
  className = '',
  ...rest
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={`${CONTROL_CLASSES} min-h-[90px] ${className}`} />;
}

// ---- Badge -------------------------------------------------------------------
type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'brand';

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: 'bg-shell-100 text-shell-700 ring-shell-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
};

export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

// ---- Panel -------------------------------------------------------------------
export function Panel({
  title,
  description,
  action,
  children,
  className = '',
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-shell-200 bg-white shadow-card ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-shell-200 px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-shell-900">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-shell-500">{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

// ---- State placeholders -------------------------------------------------------
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-shell-500">
      <Spinner className="h-7 w-7 text-brand-500" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-full bg-shell-100">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-shell-400">
          <path
            d="M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4M3 17l9 4 9-4"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <p className="text-sm font-semibold text-shell-800">{title}</p>
      {description && <p className="max-w-sm text-sm text-shell-500">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center"
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-rose-50">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 text-rose-600">
          <path
            fillRule="evenodd"
            d="M18 10A8 8 0 112 10a8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
            clipRule="evenodd"
          />
        </svg>
      </div>
      <p className="max-w-md text-sm font-medium text-shell-700">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
