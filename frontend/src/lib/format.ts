import type { Language } from "./types";

const locales: Record<Language, string> = { en: "en-GB", fr: "fr-FR" };

export function formatDate(value: string | Date, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], { dateStyle: "medium" }).format(new Date(value));
}

export function formatDateTime(value: string | Date, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

export function formatRelative(value: string | Date, language: Language, now: Date = new Date()): string {
  const seconds = Math.round((new Date(value).getTime() - now.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locales[language], { numeric: "auto" });
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(seconds, "second");
}

export function initials(nameOrEmail: string): string {
  const base = nameOrEmail.includes("@") ? nameOrEmail.split("@")[0] : nameOrEmail;
  const parts = base.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : base.slice(0, 2);
  return letters.toUpperCase();
}

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"];

/** Binary sizes with 1024 steps, shown with the usual short units (GB, not GiB). */
export function formatBytes(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  let size = Math.abs(value);
  let unit = 0;
  while (size >= 1024 && unit < BYTE_UNITS.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const rounded = unit === 0 ? Math.round(size) : Number(size.toFixed(digits));
  return `${value < 0 ? "-" : ""}${rounded} ${BYTE_UNITS[unit]}`;
}

export function formatRate(bytesPerSecond: number | null | undefined): string {
  return bytesPerSecond === null || bytesPerSecond === undefined ? "—" : `${formatBytes(bytesPerSecond)}/s`;
}

export function percent(used: number | null | undefined, total: number | null | undefined): number | null {
  if (used === null || used === undefined || !total) return null;
  return Math.round((used / total) * 1000) / 10;
}

export function formatPercent(value: number | null | undefined, language: Language): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${new Intl.NumberFormat(locales[language], { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value)} %`;
}
