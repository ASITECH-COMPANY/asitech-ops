import { describe, expect, it } from "vitest";

import { assignableRoles, can, canAssignRole } from "../src/lib/permissions";
import { safeNext } from "../src/lib/redirect";

describe("permissions", () => {
  it("checks organization permissions", () => {
    expect(can({ permissions: ["audit.view"] }, "audit.view")).toBe(true);
    expect(can({ permissions: ["organization.view"] }, "audit.view")).toBe(false);
    expect(can(undefined, "organization.view")).toBe(false);
  });

  it("mirrors the backend role hierarchy", () => {
    expect(canAssignRole("owner", "owner", "viewer")).toBe(true);
    expect(canAssignRole("admin", "member", "admin")).toBe(true);
    expect(canAssignRole("admin", "member", "owner")).toBe(false);
    expect(canAssignRole("admin", "owner", "member")).toBe(false);
    expect(canAssignRole("member", "viewer", "member")).toBe(false);
    expect(assignableRoles("admin")).not.toContain("owner");
    expect(assignableRoles("viewer")).toEqual([]);
  });
});

describe("safeNext", () => {
  it("only accepts same-site relative paths", () => {
    expect(safeNext("/orgs/acme")).toBe("/orgs/acme");
    expect(safeNext("/invite#token")).toBe("/invite#token");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("/\\evil.example")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});
