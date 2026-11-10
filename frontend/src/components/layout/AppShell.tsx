import { X } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { LiveStatus } from "../../hooks/useOrgEvents";
import { useT } from "../../i18n";
import type { Organization } from "../../lib/types";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ org, live, children }: { org?: Organization; live?: LiveStatus; children: ReactNode }) {
  const t = useT();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-full">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-surface lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar org={org} />
        </div>
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/50" aria-hidden onClick={() => setMobileOpen(false)} />
          <div className="relative h-full w-72 max-w-[85%] border-r border-line bg-surface">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 rounded-lg p-2 text-muted hover:bg-surface-2"
              aria-label={t("nav.closeMenu")}
            >
              <X className="size-5" aria-hidden />
            </button>
            <Sidebar org={org} onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar org={org} live={live} onOpenMenu={() => setMobileOpen(true)} />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
