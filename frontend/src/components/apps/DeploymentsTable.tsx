import { History } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useRollback } from "../../hooks/queries";
import { useLanguage, useT, type MessageKey } from "../../i18n";
import { ApiError } from "../../lib/api";
import { formatRelative } from "../../lib/format";
import type { Deployment } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/Dialog";
import { DeploymentStatusBadge } from "./DeploymentStatusBadge";

export function duration(d: Pick<Deployment, "started_at" | "finished_at">): string {
  if (!d.started_at) return "—";
  const end = d.finished_at ? new Date(d.finished_at) : new Date();
  const seconds = Math.max(0, Math.round((end.getTime() - new Date(d.started_at).getTime()) / 1000));
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

export function stepLabel(t: ReturnType<typeof useT>, step: string): string {
  const key = `deployments.step.${step}` as MessageKey;
  return step ? t(key) === key ? step : t(key) : "—";
}

export function DeploymentsTable({
  slug,
  deployments,
  showApplication,
  canDeploy,
}: {
  slug: string;
  deployments: Deployment[];
  showApplication: boolean;
  canDeploy: boolean;
}) {
  const t = useT();
  const language = useLanguage();
  const rollback = useRollback(slug);
  const [target, setTarget] = useState<Deployment | null>(null);
  const busy = deployments.some((d) => d.status === "queued" || d.status === "running");

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className="px-5 py-2.5 font-medium">{t("deployments.number")}</th>
            {showApplication ? <th scope="col" className="px-5 py-2.5 font-medium">{t("deployments.application")}</th> : null}
            <th scope="col" className="px-5 py-2.5 font-medium">{t("deployments.status")}</th>
            <th scope="col" className="hidden px-5 py-2.5 font-medium md:table-cell">{t("deployments.commit")}</th>
            <th scope="col" className="hidden px-5 py-2.5 font-medium lg:table-cell">{t("deployments.by")}</th>
            <th scope="col" className="px-5 py-2.5 font-medium">{t("deployments.started")}</th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {deployments.map((d) => (
            <tr key={d.id} className="align-middle hover:bg-surface-2/60">
              <td className="px-5 py-3">
                <Link to={`/orgs/${slug}/deployments/${d.id}`} className="font-medium text-fg hover:text-primary hover:underline">
                  #{d.number}
                </Link>
                <div className="mt-1 flex flex-wrap gap-1">
                  {d.is_current ? <Badge tone="success">{t("deployments.current")}</Badge> : null}
                  {d.rollback_of_number ? <Badge>{t("deployments.rollbackOf", { number: d.rollback_of_number })}</Badge> : null}
                </div>
              </td>
              {showApplication ? (
                <td className="px-5 py-3">
                  <Link to={`/orgs/${slug}/applications/${d.application.id}`} className="text-fg hover:text-primary hover:underline">
                    {d.application.name}
                  </Link>
                </td>
              ) : null}
              <td className="px-5 py-3">
                <DeploymentStatusBadge status={d.status} />
                {d.status === "running" ? <p className="mt-1 text-xs text-muted">{stepLabel(t, d.step)}</p> : null}
              </td>
              <td className="hidden px-5 py-3 font-mono text-xs text-muted md:table-cell">
                {d.commit_sha ? d.commit_sha.slice(0, 10) : "—"}
              </td>
              <td className="hidden px-5 py-3 text-muted lg:table-cell">{d.triggered_by ?? "—"}</td>
              <td className="px-5 py-3 text-muted">
                <time dateTime={d.created_at}>{formatRelative(d.created_at, language)}</time>
                <span className="block text-xs">{duration(d)}</span>
              </td>
              <td className="px-5 py-3 text-right">
                {canDeploy && d.status === "succeeded" && !d.is_current && d.image ? (
                  <Button variant="ghost" size="sm" icon={<History className="size-4" />} disabled={busy} onClick={() => setTarget(d)}>
                    {t("deployments.rollback")}
                  </Button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ConfirmDialog
        open={target !== null}
        onClose={() => {
          setTarget(null);
          rollback.reset();
        }}
        onConfirm={() => target && rollback.mutate(target.id, { onSuccess: () => setTarget(null) })}
        title={t("deployments.rollbackTitle", { app: target?.application.name ?? "", number: target?.number ?? "" })}
        description={t("deployments.rollbackBody", { number: target?.number ?? "" })}
        confirmLabel={t("deployments.rollback")}
        loading={rollback.isPending}
        error={rollback.error instanceof ApiError ? rollback.error.displayMessage : null}
      />
    </div>
  );
}
