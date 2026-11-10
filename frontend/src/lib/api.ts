/**
 * Minimal API client for the Control Plane.
 *
 * Authentication uses the Django session cookie (HttpOnly). Unsafe requests
 * carry the CSRF token read from the CSRF cookie, as Django expects.
 */

export const CSRF_COOKIE = "asitech_csrftoken";
const API_PREFIX = "/api/v1";

export type ErrorDetails = Record<string, string[] | unknown> | unknown[] | null;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetails;

  constructor(status: number, code: string, message: string, details: ErrorDetails = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** First validation message for a field, if any. */
  fieldError(field: string): string | undefined {
    if (!this.details || Array.isArray(this.details)) return undefined;
    const value = (this.details as Record<string, unknown>)[field];
    return Array.isArray(value) && typeof value[0] === "string" ? value[0] : undefined;
  }

  /** A human-readable message, preferring non-field validation errors. */
  get displayMessage(): string {
    return this.fieldError("non_field_errors") ?? this.message;
  }
}

export function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) return decodeURIComponent(item.slice(prefix.length));
  }
  return null;
}

let csrfRequest: Promise<void> | null = null;

async function ensureCsrfCookie(): Promise<void> {
  if (readCookie(CSRF_COOKIE)) return;
  csrfRequest ??= fetch(`${API_PREFIX}/auth/csrf/`, { credentials: "same-origin" })
    .then(() => undefined)
    .finally(() => {
      csrfRequest = null;
    });
  await csrfRequest;
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface RequestOptions {
  method?: Method;
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (method !== "GET") {
    await ensureCsrfCookie();
    const token = readCookie(CSRF_COOKIE);
    if (token) headers["X-CSRFToken"] = token;
  }
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let url = `${API_PREFIX}${path}`;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      credentials: "same-origin",
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "The server could not be reached.");
  }

  if (response.status === 204) return undefined as T;

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const envelope = (data as { error?: { code?: string; message?: string; details?: ErrorDetails } } | null)
      ?.error;
    throw new ApiError(
      response.status,
      envelope?.code ?? "http_error",
      envelope?.message ?? (response.statusText || "Request failed."),
      envelope?.details ?? null,
    );
  }
  return data as T;
}

export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403) &&
    (error.code === "not_authenticated" || error.code === "authentication_failed");
}
