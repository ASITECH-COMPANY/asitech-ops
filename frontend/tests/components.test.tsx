import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../src/App";
import { ConfirmDialog } from "../src/components/ui/Dialog";
import { LoginPage } from "../src/pages/LoginPage";
import { usePreferences } from "../src/stores/preferences";

afterEach(() => vi.unstubAllGlobals());

describe("ConfirmDialog", () => {
  it("requires typing the confirmation text before confirming", async () => {
    usePreferences.setState({ language: "en" });
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={() => {}}
        onConfirm={onConfirm}
        title="Delete Acme?"
        description="This cannot be undone."
        confirmLabel="Delete organization"
        confirmText="acme"
      />,
    );
    const confirm = screen.getByRole("button", { name: "Delete organization" });
    expect(screen.getByRole("dialog", { name: "Delete Acme?" })).toBeInTheDocument();
    expect(confirm).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Confirm"), "acme");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <ConfirmDialog open onClose={onClose} onConfirm={() => {}} title="T" description="D" confirmLabel="Go" />,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("LoginPage", () => {
  function renderLogin() {
    const router = createMemoryRouter(
      [
        { path: "/login", element: <LoginPage /> },
        { path: "/orgs/acme", element: <p>Dashboard reached</p> },
      ],
      { initialEntries: ["/login?next=%2Forgs%2Facme"] },
    );
    render(
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
  }

  it("shows the server error message on invalid credentials", async () => {
    usePreferences.setState({ language: "en" });
    document.cookie = "asitech_csrftoken=tok; path=/";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "invalid",
              message: "Invalid input.",
              details: { non_field_errors: ["Invalid e-mail address or password."] },
            },
          }),
          { status: 400 },
        ),
      ),
    );
    renderLogin();
    await userEvent.type(screen.getByLabelText("E-mail address"), "jane@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid e-mail address or password.");
  });

  it("redirects to the requested page after signing in, in the user's language", async () => {
    usePreferences.setState({ language: "en" });
    document.cookie = "asitech_csrftoken=tok; path=/";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            id: "1",
            email: "jane@example.test",
            full_name: "Jane",
            language: "fr",
            is_staff: false,
            date_joined: "2026-01-01T00:00:00Z",
            can_create_organizations: false,
          }),
          { status: 200 },
        ),
      ),
    );
    renderLogin();
    await userEvent.type(screen.getByLabelText("E-mail address"), "jane@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "a-good-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Dashboard reached")).toBeInTheDocument();
    await waitFor(() => expect(usePreferences.getState().language).toBe("fr"));
  });
});
