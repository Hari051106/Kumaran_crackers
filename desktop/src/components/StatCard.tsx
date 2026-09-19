/**
 * A headline figure.
 *
 * A single number is a stat tile, not a chart - there is no magnitude to
 * compare, so a plot would add ink without adding meaning.
 */
import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string;
  sublabel?: string;
  icon?: ReactNode;
  /** Optional status accent. Always accompanied by the label text below. */
  tone?: 'neutral' | 'good' | 'warning' | 'critical';
  testId?: string;
}

// Status steps are fixed and never themed. They are paired with an icon and a
// text label wherever they appear, because red and green are close to
// indistinguishable under deuteranopia (measured ΔE 4.1).
const TONES = {
  neutral: { ring: 'ring-shell-200', icon: 'bg-shell-100 text-shell-500', value: 'text-shell-900' },
  good: { ring: 'ring-shell-200', icon: 'bg-[#0ca30c]/10 text-[#0a7d0a]', value: 'text-shell-900' },
  warning: { ring: 'ring-amber-200', icon: 'bg-[#fab219]/15 text-[#8a5e00]', value: 'text-shell-900' },
  critical: { ring: 'ring-rose-200', icon: 'bg-[#d03b3b]/10 text-[#d03b3b]', value: 'text-shell-900' },
} as const;

export function StatCard({ label, value, sublabel, icon, tone = 'neutral', testId }: StatCardProps) {
  const style = TONES[tone];
  return (
    <div
      data-testid={testId}
      className={`rounded-xl bg-white p-5 shadow-card ring-1 ${style.ring}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-shell-500">{label}</p>
        {icon && (
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${style.icon}`}>
            {icon}
          </span>
        )}
      </div>
      <p className={`tabular mt-3 text-3xl font-semibold tracking-tight ${style.value}`}>{value}</p>
      {sublabel && <p className="mt-1 text-xs text-shell-500">{sublabel}</p>}
    </div>
  );
}
