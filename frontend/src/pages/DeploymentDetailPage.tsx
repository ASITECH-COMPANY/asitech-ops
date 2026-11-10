import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import { DeploymentStatusBadge } from "../components/apps/DeploymentStatusBadge";
import { duration, stepLabel } from "../components/apps/DeploymentsTable";
import { LogViewer } from "../components/apps/LogViewer";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Field";
import { ErrorState, Spinner } from "../components/ui/States";
import { useDeployment } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { ApiError } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { NotFoundContent } from "./NotFoundPage";
import type { OrgContext } from "./OrgLayout";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 break-all text-sm text-fg">{children}</dd>
    </div>
  );
}

export function DeploymentDetailPage() {
  const t = useT();
  const language = useLanguage();
  const { org } = useOutletContext<OrgContext>();
  const { deploymentId = "" } = useParams();
  const { data, error, isPending, refetch } = useDeployment(org.slug, deploymentId);
  useDocumentTitle(data ? `${data.application.name} #${data.number}` : undefined, org.name);

  if (isPending) return <Spinner />;
  if (error instanceof ApiError && error.status === 404) return <NotFoundContent />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <>
      <Link to={`/orgs/${org.slug}/applications/${data.application.id}`} className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" aria-hidden />
        {data.application.name}
      </Link>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-fg sm:text-2xl">
          {data.application.name} #{data.number}
        </h1>
        <DeploymentStatusBadge status={data.status} />
        {data.is_current ? <Badge tone="success">{t("deployments.current")}</Badge> : null}
        {data.rollback_of_number ? <Badge>{t("deployments.rollbackOf", { number: data.rollback_of_number })}</Badge> : null}
      </div>
      {data.status === "failed" && data.error ? (
        <div className="mb-6">
          <Alert>
            <strong>{t("deployments.error")} : </strong>
            {data.error}
          </Alert>
        </div>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
          <LogViewer key={data.id} slug={org.slug} deploymentId={data.id} status={data.status} />
        </div>
        <Card className="p-5">
          <dl className="space-y-4">
            <Item label={t("deployments.step")}>{stepLabel(t, data.step)}</Item>
            <Item label={t("apps.form.branch")}>{data.branch || "—"}</Item>
            <Item label={t("deployments.commit")}>
              <span className="font-mono text-xs">{data.commit_sha || "—"}</span>
            </Item>
            <Item label={t("deployments.image")}>
              <span className="font-mono text-xs">{data.image || "—"}</span>
            </Item>
            <Item label={t("deployments.by")}>{data.triggered_by ?? "—"}</Item>
            <Item label={t("deployments.started")}>{formatDateTime(data.created_at, language)}</Item>
            <Item label={t("deployments.duration")}>{duration(data)}</Item>
          </dl>
        </Card>
      </div>
      <Link to={`/orgs/${org.slug}/deployments`} className="mt-6 inline-block text-sm text-muted hover:text-fg">
        {t("deployments.back")}
      </Link>
    </>
  );
}
