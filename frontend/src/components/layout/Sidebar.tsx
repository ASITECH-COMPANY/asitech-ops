import {
  Activity,
  AppWindow,
  LayoutDashboard,
  Rocket,
  ScrollText,
  Server,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router";

import { useT, type MessageKey } from "../../i18n";
import { can } from "../../lib/permissions";
import type { Organization } from "../../lib/types";
import { Logo } from "../Logo";
import { cn } from "../ui/cn";

interface Item {
  to: string;
  label: MessageKey;
  icon: LucideIcon;
  soon?: boolean;
  end?: boolean;
}

function NavItem({ item, onNavigate }: { item: Item; onNavigate?: () => void }) {
  const t = useT();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
          isActive ? "bg-primary-soft font-medium text-primary" : "text-muted hover:bg-surface-2 hover:text-fg",
        )
      }
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span className="flex-1 truncate">{t(item.label)}</span>
      {item.soon ? (
        <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">
          {t("nav.soon")}
        </span>
      ) : null}
    </NavLink>
  );
}

function Section({ title, items, onNavigate }: { title?: string; items: Item[]; onNavigate?: () => void }) {
  return (
    <div className="space-y-0.5">
      {title ? (
        <p className="px-2.5 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-muted/80">{title}</p>
      ) : null}
      {items.map((item) => (
        <NavItem key={item.to} item={item} onNavigate={onNavigate} />
      ))}
    </div>
  );
}

export function Sidebar({ org, onNavigate }: { org?: Organization; onNavigate?: () => void }) {
  const t = useT();
  const base = org ? `/orgs/${org.slug}` : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-4">
        <Logo />
      </div>
      <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main">
        {base ? (
          <>
            <Section items={[{ to: base, label: "nav.overview", icon: LayoutDashboard, end: true }]} onNavigate={onNavigate} />
            <Section
              title={t("nav.infrastructure")}
              onNavigate={onNavigate}
              items={[
                { to: `${base}/servers`, label: "nav.servers", icon: Server },
                { to: `${base}/applications`, label: "nav.applications", icon: AppWindow },
                { to: `${base}/deployments`, label: "nav.deployments", icon: Rocket },
                { to: `${base}/monitoring`, label: "nav.monitoring", icon: Activity },
              ]}
            />
            <Section
              title={t("nav.organization")}
              onNavigate={onNavigate}
              items={[
                { to: `${base}/members`, label: "nav.members", icon: Users },
                ...(can(org, "audit.view") ? [{ to: `${base}/audit`, label: "nav.audit" as const, icon: ScrollText }] : []),
                { to: `${base}/settings`, label: "nav.settings", icon: Settings },
              ]}
            />
          </>
        ) : null}
      </nav>
      <div className="border-t border-line px-4 py-3 text-xs text-muted">
        v0.1.0-dev ·{" "}
        <a className="hover:text-fg" href="/api/docs/" target="_blank" rel="noopener noreferrer">
          {t("nav.apiDocs")}
        </a>
      </div>
    </div>
  );
}
