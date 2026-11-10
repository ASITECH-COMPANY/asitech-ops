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

describe("formatting", () => {
  it("formats sizes, rates and percentages", async () => {
    const { formatBytes, formatPercent, formatRate, percent } = await import("../src/lib/format");
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(12_411_666_432)).toBe("11.6 GB");
    expect(formatBytes(null)).toBe("—");
    expect(formatRate(2048)).toBe("2 KB/s");
    expect(percent(1, 4)).toBe(25);
    expect(percent(1, 0)).toBeNull();
    expect(formatPercent(41, "en")).toBe("41.0 %");
    expect(formatPercent(41, "fr")).toMatch(/^41,0\s%$/);
  });
});

describe("monitoring alerts", () => {
  it("renders localized alert messages", async () => {
    const { translate } = await import("../src/i18n");
    const { alertText } = await import("../src/pages/MonitoringPage");
    const t = (key: Parameters<typeof translate>[1], params?: Record<string, string | number>) =>
      translate("fr", key, params);
    const text = alertText(t, "fr", {
      severity: "warning",
      kind: "disk_high",
      server: { id: "1", name: "web-01" },
      params: { percent: 90.1 },
    });
    expect(text).toBe("Le disque de web-01 est plein à 90,1 %.");
    const down = alertText(t, "fr", {
      severity: "warning",
      kind: "container_down",
      server: { id: "1", name: "web-01" },
      params: { container: "api", state: "restarting" },
    });
    expect(down).toBe("Le conteneur api sur web-01 est en redémarrage.");
  });
});
