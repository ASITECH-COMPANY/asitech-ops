import { AppWindow, GitBranch, Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router";

import { ApplicationForm } from "../components/apps/ApplicationForm";
import { DeploymentStatusBadge } from "../components/apps/DeploymentStatusBadge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Modal } from "../components/ui/Dialog";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useApplications, useServers } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { formatRelative } from "../lib/format";
import { can } from "../lib/permissions";
import type { OrgContext } from "./OrgLayout";

export function repoLabel(url: string): string {
  return url.replace(/^https:\/\//, "").replace(/\.git$/, "");
}

export function ApplicationsPage() {
  const t = useT();
  const language = useLanguage();
  const navigate = useNavigate();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("apps.title"), org.name);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const apps = useApplications(org.slug, search);
  const servers = useServers(org.slug, { search: "", status: "", page: 1 });
  const canManage = can(org, "applications.manage");
  const hasServer = (servers.data?.count ?? 0) > 0;

  return (
    <>
      <PageHeader
        title={t("apps.title")}
        description={t("apps.subtitle", { org: org.name })}
        actions={
          canManage && hasServer ? (
            <Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
              {t("apps.new")}
            </Button>
          ) : null
        }
      />
      <Card>
        <div className="border-b border-line px-5 py-3">
          <label className="relative block max-w-sm">
            <span className="sr-only">{t("common.search")}</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("apps.search")}
              className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
            />
          </label>
        </div>
        {apps.isPending ? (
          <Spinner />
        ) : apps.error ? (
          <ErrorState error={apps.error} onRetry={() => apps.refetch()} />
        ) : apps.data.results.length === 0 ? (
          <EmptyState title={t("apps.empty")} icon={<AppWindow className="size-6" aria-hidden />}>
            <p>{hasServer ? t("apps.emptyHelp") : t("apps.noServer")}</p>
            {!canManage ? <p className="mt-2">{t("apps.readOnly")}</p> : null}
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {apps.data.results.map((app) => {
              const last = app.last_deployment;
              return (
                <li key={app.id} className="flex flex-wrap items-center gap-4 px-5 py-4 hover:bg-surface-2/60">
                  <div className="min-w-0 flex-1">
                    <Link to={app.id} className="font-medium text-fg hover:text-primary hover:underline">
                      {app.name}
                    </Link>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      <span className="flex items-center gap-1">
                        <GitBranch className="size-3.5" aria-hidden />
                        {repoLabel(app.repo_url)} · {app.branch}
                      </span>
                      <span>{app.server.name}</span>
                    </p>
                  </div>
                  <div className="text-right text-xs text-muted">
                    {last ? (
                      <>
                        <DeploymentStatusBadge status={last.status} />
                        <p className="mt-1">
                          #{last.number} · {formatRelative(last.created_at, language)}
                        </p>
                      </>
                    ) : (
                      t("apps.noRelease")
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
      {creating ? (
        <Modal
          open
          onClose={() => setCreating(false)}
          title={t("apps.form.title")}
          footer={
            <>
              <Button variant="secondary" onClick={() => setCreating(false)}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" form="new-app">
                {t("apps.form.create")}
              </Button>
            </>
          }
        >
          <div className="max-h-[65vh] overflow-y-auto pr-1">
            <ApplicationForm
              slug={org.slug}
              formId="new-app"
              showSubmit={false}
              onSaved={(app) => {
                setCreating(false);
                navigate(app.id);
              }}
            />
          </div>
        </Modal>
      ) : null}
    </>
  );
}
