import { AlertTriangle, CircleCheck, OctagonAlert } from "lucide-react";
import { Link, useOutletContext } from "react-router";

import { containerState } from "../components/infra/InventoryPanel";
import { ServerStatusBadge } from "../components/servers/ServerStatusBadge";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { cn } from "../components/ui/cn";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useMonitoring } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT, type MessageKey } from "../i18n";
import { formatPercent, formatRelative } from "../lib/format";
import type { Language, MonitoringAlert } from "../lib/types";
import type { OrgContext } from "./OrgLayout";

export function alertText(t: ReturnType<typeof useT>, language: Language, alert: MonitoringAlert): string {
  const params: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(alert.params)) params[key] = value ?? "—";
  if (alert.kind === "server_offline") {
    params.since = alert.params.since ? formatRelative(String(alert.params.since), language) : t("common.never");
  }
  if (typeof alert.params.percent === "number") {
    params.percent = new Intl.NumberFormat(language === "fr" ? "fr-FR" : "en-GB", { maximumFractionDigits: 1 }).format(
      alert.params.percent,
    );
  }
  if (typeof alert.params.state === "string") params.state = containerState(t, alert.params.state);
  params.server = alert.server?.name ?? "";
  params.application = alert.application?.name ?? "";
  return t(`alert.${alert.kind}` as MessageKey, params);
}

export function alertLink(slug: string, alert: MonitoringAlert): string {
  if (alert.kind === "deployment_failed") return `/orgs/${slug}/deployments/${alert.params.deployment_id}`;
  return alert.server ? `/orgs/${slug}/servers/${alert.server.id}` : `/orgs/${slug}/monitoring`;
}

export function AlertRow({ slug, alert }: { slug: string; alert: MonitoringAlert }) {
  const t = useT();
  const language = useLanguage();
  const critical = alert.severity === "critical";
  const Icon = critical ? OctagonAlert : AlertTriangle;
  return (
    <li>
      <Link to={alertLink(slug, alert)} className="flex items-start gap-3 px-5 py-3 hover:bg-surface-2/60">
        <Icon className={cn("mt-0.5 size-4 shrink-0", critical ? "text-danger" : "text-warning")} aria-hidden />
        <span className="flex-1 text-sm text-fg">{alertText(t, language, alert)}</span>
        <span className={cn("text-xs font-medium", critical ? "text-danger" : "text-warning")}>
          {t(`monitoring.severity.${alert.severity}`)}
        </span>
      </Link>
    </li>
  );
}

function Meter({ value }: { value: number | null }) {
  const language = useLanguage();
  if (value === null) return <span className="text-muted">—</span>;
  const tone = value >= 95 ? "bg-danger" : value >= 90 ? "bg-warning" : "bg-primary";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="tabular-nums text-xs text-fg">{formatPercent(value, language)}</span>
    </div>
  );
}

export function MonitoringPage() {
  const t = useT();
  const language = useLanguage();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("monitoring.title"), org.name);
  const { data, error, isPending, refetch } = useMonitoring(org.slug);

  if (isPending) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <>
      <PageHeader
        title={t("monitoring.title")}
        description={t("monitoring.subtitle", { org: org.name })}
        actions={<span className="text-xs text-muted">{t("monitoring.updated", { time: formatRelative(data.generated_at, language) })}</span>}
      />
      <Card className="mb-6">
        <CardHeader title={`${t("monitoring.alerts")} (${data.alerts.length})`} />
        {data.alerts.length === 0 ? (
          <EmptyState title={t("monitoring.noAlerts")} icon={<CircleCheck className="size-6 text-success" aria-hidden />} />
        ) : (
          <ul className="divide-y divide-line">
            {data.alerts.map((alert, index) => (
              <AlertRow key={index} slug={org.slug} alert={alert} />
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <CardHeader title={t("monitoring.servers")} />
        {data.servers.length === 0 ? (
          <EmptyState title={t("servers.empty")} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("servers.name")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("servers.status")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("monitoring.cpu")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("monitoring.memory")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("monitoring.disk")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("monitoring.containers")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.servers.map((s) => (
                  <tr key={s.server.id} className="align-middle">
                    <td className="px-5 py-3">
                      <Link to={`/orgs/${org.slug}/servers/${s.server.id}`} className="font-medium text-fg hover:text-primary hover:underline">
                        {s.server.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3"><ServerStatusBadge status={s.status} /></td>
                    <td className="px-5 py-3"><Meter value={s.cpu_percent} /></td>
                    <td className="px-5 py-3"><Meter value={s.memory_percent} /></td>
                    <td className="px-5 py-3"><Meter value={s.disk_percent} /></td>
                    <td className="px-5 py-3 tabular-nums text-muted">
                      {s.containers_total !== null ? `${s.containers_running} / ${s.containers_total}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
