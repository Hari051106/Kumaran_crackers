/**
 * Money formatting that never converts through a float.
 *
 * The API sends money as exact decimal strings ("1874.25"). Parsing those into
 * a JS `number` would reintroduce binary floating-point error - the very thing
 * the backend's Numeric(10,2) columns exist to prevent. Everything here works
 * on the string.
 */

const INR = '₹';

/** Split "1874.25" into its sign, integer and fractional parts. */
function parts(value: string): { negative: boolean; whole: string; fraction: string } {
  const trimmed = (value ?? '').trim();
  const negative = trimmed.startsWith('-');
  const unsigned = negative ? trimmed.slice(1) : trimmed;
  const [whole = '0', fraction = ''] = unsigned.split('.');
  return { negative, whole: whole || '0', fraction };
}

/**
 * Group digits the Indian way: the last three, then pairs.
 * 1234567 -> "12,34,567"
 */
function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits;
  const last3 = digits.slice(-3);
  const rest = digits.slice(0, -3);
  return `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${last3}`;
}

/** Format a decimal string as "₹1,874.25". */
export function formatMoney(value: string | null | undefined, showSymbol = true): string {
  if (value === null || value === undefined || value === '') return showSymbol ? `${INR}0.00` : '0.00';
  const { negative, whole, fraction } = parts(value);
  const paise = (fraction + '00').slice(0, 2);
  const body = `${groupIndian(whole)}.${paise}`;
  return `${negative ? '-' : ''}${showSymbol ? INR : ''}${body}`;
}

/** Format a decimal string as a compact whole-rupee figure, e.g. "₹1,874". */
export function formatMoneyShort(value: string | null | undefined): string {
  if (!value) return `${INR}0`;
  const { negative, whole } = parts(value);
  return `${negative ? '-' : ''}${INR}${groupIndian(whole)}`;
}

/** Format "25.0" as "25%", dropping a pointless trailing ".0". */
export function formatPercent(value: string | null | undefined): string {
  if (!value) return '0%';
  const cleaned = value.replace(/\.0$/, '');
  return `${cleaned}%`;
}

/** Group a plain integer count, e.g. 12345 -> "12,345". */
export function formatCount(value: number): string {
  return groupIndian(String(Math.trunc(Math.abs(value)))).replace(/^/, value < 0 ? '-' : '');
}

/**
 * Compare two decimal strings without floating point.
 * Returns a negative number, zero, or a positive number like a comparator.
 */
export function compareMoney(a: string, b: string): number {
  const pa = parts(a);
  const pb = parts(b);
  if (pa.negative !== pb.negative) return pa.negative ? -1 : 1;
  const scale = (p: { whole: string; fraction: string }) =>
    BigInt(p.whole + (p.fraction + '00').slice(0, 2));
  const diff = scale(pa) - scale(pb);
  const magnitude = diff === 0n ? 0 : diff > 0n ? 1 : -1;
  return pa.negative ? -magnitude : magnitude;
}

/** True when the string is a well-formed money amount with at most 2 decimals. */
export function isValidMoney(value: string): boolean {
  return /^\d{1,8}(\.\d{1,2})?$/.test(value.trim());
}
