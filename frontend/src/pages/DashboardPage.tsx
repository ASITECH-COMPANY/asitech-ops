import { AppWindow, ArrowRight, CheckCircle2, CircleDashed, Server, ShieldCheck, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useOutletContext } from "react-router";

import { Badge } from "../components/ui/Badge";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useDashboard } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { actionKey, useLanguage, useT, type MessageKey } from "../i18n";
import { formatRelative } from "../lib/format";
import type { AuditEntry } from "../lib/types";
import type { OrgContext } from "./OrgLayout";

function StatCard({ label, value, icon, hint }: { label: string; value: ReactNode; icon: ReactNode; hint?: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">{label}</p>
        <span className="text-muted">{icon}</span>
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-fg">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}

export function ActivityItem({ entry }: { entry: AuditEntry }) {
  const t = useT();
  const language = useLanguage();
  const key = actionKey(entry.action);
  return (
    <li className="flex items-start gap-3 px-5 py-3">
      <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-fg">
          <span className="font-medium">{entry.actor.email || t("audit.system")}</span>{" "}
          <span className="text-muted">{key ? t(key).toLowerCase() : entry.action}</span>
          {entry.target_repr ? <span className="font-medium"> · {entry.target_repr}</span> : null}
        </p>
        <p className="mt-0.5 text-xs text-muted">
          <time dateTime={entry.created_at}>{formatRelative(entry.created_at, language)}</time>
        </p>
      </div>
    </li>
  );
}

const MODULES: { key: MessageKey; phase: string | null }[] = [
  { key: "dashboard.module.organizations", phase: null },
  { key: "dashboard.module.servers", phase: null },
  { key: "dashboard.module.deployments", phase: null },
  { key: "dashboard.module.infrastructure", phase: "Phase 4" },
  { key: "dashboard.module.production", phase: "Phase 5" },
];

export function DashboardPage() {
  const t = useT();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("dashboard.title"), org.name);
  const { data, error, isPending, refetch } = useDashboard(org.slug);

  if (isPending) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  const admins = data.members_by_role.owner + data.members_by_role.admin;

  return (
    <>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.subtitle", { org: org.name })} />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label={t("dashboard.servers")}
          value={data.stats.servers}
          icon={<Server className="size-4" />}
          hint={t("dashboard.serversDetail", {
            online: data.servers_by_status.online,
            offline: data.servers_by_status.offline,
          })}
        />
        <StatCard
          label={t("dashboard.members")}
          value={data.stats.members}
          icon={<Users className="size-4" />}
          hint={`${admins} ${t("dashboard.admins").toLowerCase()} · ${t("dashboard.pendingInvites").toLowerCase()} : ${data.stats.pending_invitations ?? "—"}`}
        />
        <StatCard
          label={t("dashboard.applications")}
          value={data.stats.applications}
          icon={<AppWindow className="size-4" />}
          hint={t("dashboard.deploymentsWeek", { count: data.stats.deployments_last_7d })}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title={t("dashboard.recentActivity")}
            actions={
              data.recent_activity ? (
                <Link to="audit" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                  {t("dashboard.viewAudit")}
                  <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              ) : null
            }
          />
          {data.recent_activity === null ? (
            <EmptyState title={t("dashboard.activityRestricted")} icon={<ShieldCheck className="size-6" aria-hidden />} />
          ) : data.recent_activity.length === 0 ? (
            <EmptyState title={t("dashboard.noActivity")} />
          ) : (
            <ul className="divide-y divide-line">
              {data.recent_activity.map((entry) => (
                <ActivityItem key={entry.id} entry={entry} />
              ))}
            </ul>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title={t("dashboard.modules")} description={t("dashboard.modulesHelp")} />
          <ul className="divide-y divide-line">
            {MODULES.map((module) => (
              <li key={module.key} className="flex items-center gap-3 px-5 py-3">
                {module.phase ? (
                  <CircleDashed className="size-4 shrink-0 text-muted" aria-hidden />
                ) : (
                  <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
                )}
                <span className="min-w-0 flex-1 text-sm text-fg">{t(module.key)}</span>
                {module.phase ? (
                  <Badge>{t("dashboard.status.planned", { phase: module.phase })}</Badge>
                ) : (
                  <Badge tone="success">{t("dashboard.status.available")}</Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
