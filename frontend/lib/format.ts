// Centralized formatters. Pages MUST use these instead of ad-hoc
// `toLocaleString` calls so locale handling stays consistent.

export function formatCurrency(
  amount: number | null | undefined,
  currency: string | null | undefined,
  locale: string = "en-US",
): string {
  if (amount == null || !currency) return "—";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Unknown currency code — fall back to plain number with the code suffixed.
    return `${amount.toFixed(2)} ${currency}`;
  }
}

export function formatDateTime(
  iso: string | Date | null | undefined,
  timezone?: string,
  locale: string = "en-US",
): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
  }).format(d);
}

const RELATIVE_THRESHOLDS: Array<[number, Intl.RelativeTimeFormatUnit]> = [
  [60, "second"],
  [3600, "minute"],
  [86400, "hour"],
  [604800, "day"],
  [2592000, "week"],
  [31536000, "month"],
];

export function formatRelative(
  iso: string | Date | null | undefined,
  locale: string = "en-US",
): string {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) return "—";
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const diffSec = Math.round((d.getTime() - Date.now()) / 1000);
  const absSec = Math.abs(diffSec);
  for (const [limit, unit] of RELATIVE_THRESHOLDS) {
    if (absSec < limit) {
      const divisor = limit === 60 ? 1 : limit / 60;
      const inUnit =
        unit === "second"
          ? diffSec
          : Math.round(diffSec / (divisor * (unit === "minute" ? 1 : 60)));
      return rtf.format(inUnit, unit);
    }
  }
  return rtf.format(Math.round(diffSec / 31536000), "year");
}

export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, Math.max(0, max - 1)) + "…";
}
