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
