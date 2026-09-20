/**
 * Date and time formatting for the back office.
 *
 * The API sends UTC ISO timestamps; staff read them in the machine's local
 * time. Deliberately hand-rolled rather than pulling in a date library for
 * three fixed formats.
 */

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function two(value: number): string {
  return String(value).padStart(2, '0');
}

/** "20 Sep 2026" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '—';
  return `${when.getDate()} ${MONTHS[when.getMonth()]} ${when.getFullYear()}`;
}

/** "15:04" - a 24-hour clock, because operations logs read better that way. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '';
  return `${two(when.getHours())}:${two(when.getMinutes())}`;
}

/** "20 Sep 2026, 15:04" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = formatDate(iso);
  const time = formatTime(iso);
  return time ? `${date}, ${time}` : date;
}
