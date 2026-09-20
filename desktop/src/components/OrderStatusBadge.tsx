/**
 * Order status as icon + word + colour, never colour alone.
 *
 * Red and green sit close enough under deuteranopia to be unreliable on their
 * own, so every badge carries the server's label and a distinct glyph.
 */
import type { OrderStatus } from '../types/api';

type Tone = 'neutral' | 'info' | 'progress' | 'success' | 'danger';

const TONES: Record<Tone, string> = {
  neutral: 'bg-shell-100 text-shell-700 ring-shell-200',
  info: 'bg-sky-50 text-sky-800 ring-sky-200',
  progress: 'bg-amber-50 text-amber-800 ring-amber-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
};

const GLYPHS: Record<OrderStatus, { tone: Tone; path: string }> = {
  PLACED: { tone: 'neutral', path: 'M7 4h10l1 16H6L7 4zM9 8a3 3 0 006 0' },
  CONFIRMED: { tone: 'info', path: 'M5 12l5 5L20 7' },
  PACKING: { tone: 'progress', path: 'M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4M3 17l9 4 9-4' },
  OUT_FOR_DELIVERY: {
    tone: 'progress',
    path: 'M3 16V7h11v9M14 10h4l3 3v3h-7M7 19a2 2 0 100-4 2 2 0 000 4zm10 0a2 2 0 100-4 2 2 0 000 4z',
  },
  DELIVERED: { tone: 'success', path: 'M5 12l5 5L20 7' },
  CANCELLED: { tone: 'danger', path: 'M6 6l12 12M18 6L6 18' },
};

export function OrderStatusBadge({ status, label }: { status: OrderStatus; label: string }) {
  // An unrecognised status still renders, using the server's own wording.
  const glyph = GLYPHS[status] ?? { tone: 'neutral' as Tone, path: 'M12 8v4m0 4h.01' };

  return (
    <span
      data-testid={`order-status-${status}`}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONES[glyph.tone]}`}
    >
      <svg viewBox="0 0 24 24" fill="none" className="h-3 w-3" aria-hidden="true">
        <path
          d={glyph.path}
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {label}
    </span>
  );
}
