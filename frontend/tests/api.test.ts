import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, CSRF_COOKIE } from "../src/lib/api";

function jsonResponse(status: number, body: unknown) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the CSRF token on unsafe requests, fetching the cookie first when missing", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/csrf/")) {
        document.cookie = `${CSRF_COOKIE}=tok123; path=/`;
        return jsonResponse(200, { csrf_token: "tok123" });
      }
      return jsonResponse(200, { ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    await api("/organizations/", { method: "POST", body: { name: "Acme" } });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, init] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/organizations/");
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
    expect(init.credentials).toBe("same-origin");
    expect(init.body).toBe(JSON.stringify({ name: "Acme" }));
  });

  it("does not send a CSRF token on GET and builds query strings", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);
    await api("/organizations/acme/members/", { query: { search: "ama", page: 2, empty: "" } });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/organizations/acme/members/?search=ama&page=2");
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBeUndefined();
  });

  it("maps the error envelope to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(400, {
          error: { code: "invalid", message: "Invalid input.", details: { email: ["Enter a valid e-mail."] } },
        }),
      ),
    );
    const error = await api("/auth/me/").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).fieldError("email")).toBe("Enter a valid e-mail.");
  });

  it("reports network failures with status 0", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const error = (await api("/auth/me/").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.code).toBe("network_error");
  });

  it("returns undefined for 204 responses", async () => {
    document.cookie = `${CSRF_COOKIE}=tok; path=/`;
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    await expect(api("/auth/logout/", { method: "POST" })).resolves.toBeUndefined();
  });
});
