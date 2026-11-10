import { useState } from "react";
import { Navigate, useOutletContext } from "react-router";

import { Badge } from "../components/ui/Badge";
import { Card, PageHeader } from "../components/ui/Card";
import { Select } from "../components/ui/Field";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useAuditLog } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { actionKey, useLanguage, useT } from "../i18n";
import { en } from "../i18n/en";
import { formatDateTime } from "../lib/format";
import { can } from "../lib/permissions";
import type { OrgContext } from "./OrgLayout";

const ACTIONS = Object.keys(en)
  .filter((key) => key.startsWith("action."))
  .map((key) => key.slice("action.".length))
  // Account-level events are not attached to an organization.
  .filter((action) => !action.startsWith("auth.") && !action.startsWith("user."));

function actionTone(action: string) {
  if (action.endsWith("deleted") || action.endsWith("removed") || action.endsWith("revoked")) return "danger" as const;
  if (action.endsWith("created") || action.endsWith("accepted")) return "success" as const;
  return "primary" as const;
}

function formatMetadata(metadata: Record<string, unknown>): string {
  return Object.entries(metadata)
    .map(([key, value]) => {
      if (value && typeof value === "object" && "from" in value && "to" in value) {
        const change = value as { from: unknown; to: unknown };
        return `${key}: ${String(change.from)} → ${String(change.to)}`;
      }
      return `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`;
    })
    .join(" · ");
}

export function AuditPage() {
  const t = useT();
  const language = useLanguage();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("audit.title"), org.name);
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const allowed = can(org, "audit.view");
  const log = useAuditLog(org.slug, { action: action || undefined, page });

  if (!allowed) return <Navigate to={`/orgs/${org.slug}`} replace />;

  return (
    <>
      <PageHeader title={t("audit.title")} description={t("audit.subtitle", { org: org.name })} />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <Select
            aria-label={t("audit.action")}
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          >
            <option value="">{t("audit.allActions")}</option>
            {ACTIONS.map((value) => {
              const key = actionKey(value);
              return (
                <option key={value} value={value}>
                  {key ? t(key) : value}
                </option>
              );
            })}
          </Select>
        </div>
        {log.isPending ? (
          <Spinner />
        ) : log.error ? (
          <ErrorState error={log.error} onRetry={() => log.refetch()} />
        ) : log.data.results.length === 0 ? (
          <EmptyState title={t("audit.empty")} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[48rem] text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("audit.when")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("audit.actor")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("audit.action")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("audit.target")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("audit.ip")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {log.data.results.map((entry) => {
                  const key = actionKey(entry.action);
                  return (
                    <tr key={entry.id} className="align-top">
                      <td className="whitespace-nowrap px-5 py-3 text-muted">
                        <time dateTime={entry.created_at}>{formatDateTime(entry.created_at, language)}</time>
                      </td>
                      <td className="px-5 py-3 text-fg">{entry.actor.email || t("audit.system")}</td>
                      <td className="px-5 py-3">
                        <Badge tone={actionTone(entry.action)}>{key ? t(key) : entry.action}</Badge>
                      </td>
                      <td className="px-5 py-3">
                        <p className="text-fg">{entry.target_repr || "—"}</p>
                        {Object.keys(entry.metadata).length > 0 ? (
                          <p className="mt-0.5 font-mono text-xs text-muted">{formatMetadata(entry.metadata)}</p>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-muted">{entry.ip_address ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {log.data ? <Pagination page={page} count={log.data.count} onPage={setPage} /> : null}
      </Card>
    </>
  );
}
