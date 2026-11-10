import { ArrowLeft, ExternalLink, GitBranch, Rocket, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router";

import { ApplicationForm } from "../components/apps/ApplicationForm";
import { DeploymentsTable } from "../components/apps/DeploymentsTable";
import { DeploymentStatusBadge } from "../components/apps/DeploymentStatusBadge";
import { EnvironmentEditor } from "../components/apps/EnvironmentEditor";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/Dialog";
import { Alert } from "../components/ui/Field";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { cn } from "../components/ui/cn";
import { useAppDeployments, useApplication, useDeleteApplication, useDeploy } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { ApiError } from "../lib/api";
import { formatRelative } from "../lib/format";
import { can } from "../lib/permissions";
import { NotFoundContent } from "./NotFoundPage";
import { repoLabel } from "./ApplicationsPage";
import type { OrgContext } from "./OrgLayout";

type Tab = "history" | "environment" | "settings";

export function ApplicationDetailPage() {
  const t = useT();
  const language = useLanguage();
  const navigate = useNavigate();
  const { org } = useOutletContext<OrgContext>();
  const { appId = "" } = useParams();
  const app = useApplication(org.slug, appId);
  const [tab, setTab] = useState<Tab>("history");
  const [page, setPage] = useState(1);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deployments = useAppDeployments(org.slug, appId, page);
  const deploy = useDeploy(org.slug);
  const remove = useDeleteApplication(org.slug, appId);
  useDocumentTitle(app.data?.name, org.name);

  if (app.isPending) return <Spinner />;
  if (app.error instanceof ApiError && app.error.status === 404) return <NotFoundContent />;
  if (app.error || !app.data) return <ErrorState error={app.error} onRetry={() => app.refetch()} />;
  const data = app.data;
  const canManage = can(org, "applications.manage");
  const canDeploy = can(org, "applications.deploy");
  const busy = data.last_deployment?.status === "queued" || data.last_deployment?.status === "running";
  const serverReady = data.server.status === "online";
  const address = data.host_port ? `http://${data.bind_address === "0.0.0.0" ? "<server>" : "127.0.0.1"}:${data.host_port}` : null;

  return (
    <>
      <Link to=".." relative="path" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" aria-hidden />
        {t("apps.title")}
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight text-fg sm:text-2xl">{data.name}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            <a href={data.repo_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-fg">
              <GitBranch className="size-4" aria-hidden />
              {repoLabel(data.repo_url)} · {data.branch}
              <ExternalLink className="size-3" aria-hidden />
            </a>
            <Link to={`/orgs/${org.slug}/servers/${data.server.id}`} className="hover:text-fg">
              {data.server.name}
            </Link>
          </p>
        </div>
        {canDeploy ? (
          <div className="text-right">
            <Button
              icon={<Rocket className="size-4" />}
              loading={deploy.isPending}
              disabled={busy || !serverReady}
              onClick={() =>
                deploy.mutate(data.id, { onSuccess: (d) => navigate(`/orgs/${org.slug}/deployments/${d.id}`) })
              }
            >
              {busy ? t("apps.deploying") : t("apps.deploy")}
            </Button>
            <p className="mt-1.5 max-w-xs text-xs text-muted">{t("apps.deployHelp", { branch: data.branch })}</p>
          </div>
        ) : null}
      </div>

      {!serverReady ? (
        <div className="mb-6">
          <Alert tone="info">
            {t("apps.serverOffline", { server: data.server.name, status: t(`servers.status.${data.server.status}`) })}
          </Alert>
        </div>
      ) : null}
      {deploy.error instanceof ApiError ? (
        <div className="mb-6">
          <Alert>{deploy.error.displayMessage}</Alert>
        </div>
      ) : null}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-sm text-muted">{t("apps.release")}</p>
          {data.current_deployment ? (
            <p className="mt-2 text-lg font-semibold text-fg">
              #{data.current_deployment.number}{" "}
              <span className="font-mono text-xs font-normal text-muted">{data.current_deployment.commit_sha.slice(0, 10)}</span>
            </p>
          ) : (
            <p className="mt-2 text-sm text-muted">{t("apps.noRelease")}</p>
          )}
        </Card>
        <Card className="p-5">
          <p className="text-sm text-muted">{t("deployments.title")}</p>
          {data.last_deployment ? (
            <div className="mt-2 flex items-center gap-2">
              <DeploymentStatusBadge status={data.last_deployment.status} />
              <span className="text-xs text-muted">{formatRelative(data.last_deployment.created_at, language)}</span>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">—</p>
          )}
        </Card>
        <Card className="p-5">
          <p className="text-sm text-muted">{t("apps.url")}</p>
          <p className="mt-2 truncate font-mono text-sm text-fg">{address ?? "—"}</p>
        </Card>
      </div>

      <div role="tablist" className="mb-4 flex gap-1 border-b border-line">
        {(["history", "environment", "settings"] as const).map((value) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
              tab === value ? "border-primary text-primary" : "border-transparent text-muted hover:text-fg",
            )}
          >
            {t(value === "history" ? "apps.history" : value === "environment" ? "apps.environment" : "apps.settings")}
          </button>
        ))}
      </div>

      {tab === "history" ? (
        <Card>
          {deployments.isPending ? (
            <Spinner />
          ) : deployments.error ? (
            <ErrorState error={deployments.error} onRetry={() => deployments.refetch()} />
          ) : deployments.data.results.length === 0 ? (
            <EmptyState title={t("deployments.empty")} />
          ) : (
            <>
              <DeploymentsTable slug={org.slug} deployments={deployments.data.results} showApplication={false} canDeploy={canDeploy} />
              <Pagination page={page} count={deployments.data.count} onPage={setPage} />
            </>
          )}
        </Card>
      ) : tab === "environment" ? (
        <Card>
          <CardHeader title={t("apps.environment")} />
          <EnvironmentEditor slug={org.slug} appId={data.id} canEdit={canManage} />
        </Card>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader title={t("apps.form.editTitle")} />
            <div className="p-5">
              {canManage ? (
                <ApplicationForm slug={org.slug} app={data} formId="edit-app" onSaved={() => app.refetch()} />
              ) : (
                <Alert tone="info">{t("apps.readOnly")}</Alert>
              )}
            </div>
          </Card>
          {canManage ? (
            <Card className="border-danger/40">
              <CardHeader title={<span className="text-danger">{t("servers.dangerZone")}</span>} />
              <div className="flex flex-wrap items-center justify-between gap-4 p-5">
                <p className="text-sm text-muted">{t("apps.deleteBody", { name: data.name })}</p>
                <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirmDelete(true)}>
                  {t("apps.delete")}
                </Button>
              </div>
            </Card>
          ) : null}
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => {
          setConfirmDelete(false);
          remove.reset();
        }}
        onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate(`/orgs/${org.slug}/applications`, { replace: true }) })}
        title={t("apps.deleteTitle", { name: data.name })}
        description={t("apps.deleteBody", { name: data.name })}
        confirmLabel={t("apps.delete")}
        confirmText={data.name}
        loading={remove.isPending}
        error={remove.error instanceof ApiError ? remove.error.displayMessage : null}
      />
    </>
  );
}
