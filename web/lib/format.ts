// Display formatting. Times are shown in UTC: alert and replay timestamps come from
// the backend in UTC, and operators comparing them need one clock, not local time.

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-09-23 08:12:30" (UTC). */
export function formatUtc(iso: string | null | undefined, withSeconds = true): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}${withSeconds ? `:${pad(d.getUTCSeconds())}` : ""}`;
  return `${date} ${time}`;
}

/** "08:12:30" (UTC). */
export function formatUtcTime(d: Date): string {
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

export function fixed(value: number | null | undefined, digits = 3): string {
  return value == null ? "–" : value.toFixed(digits);
}
