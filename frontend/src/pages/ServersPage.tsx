import { Plus, Search, Server as ServerIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router";

import { InstallCommand } from "../components/servers/InstallCommand";
import { ServerStatusBadge } from "../components/servers/ServerStatusBadge";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Modal } from "../components/ui/Dialog";
import { Alert, Select, TextField } from "../components/ui/Field";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useCreateServer, useServer, useServers } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { ApiError } from "../lib/api";
import { formatBytes, formatRelative } from "../lib/format";
import { can } from "../lib/permissions";
import type { CreatedServer, Organization, Server, ServerStatus } from "../lib/types";
import type { OrgContext } from "./OrgLayout";

const STATUSES: ServerStatus[] = ["online", "offline", "pending", "revoked"];

function ConnectionWatcher({ org, server }: { org: Organization; server: CreatedServer }) {
  const t = useT();
  // Status changes arrive over the organization WebSocket, which refreshes this query.
  const { data } = useServer(org.slug, server.id);
  return data?.status === "online" ? (
    <Alert tone="success">{t("servers.connected")}</Alert>
  ) : (
    <p className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="size-2 animate-pulse rounded-full bg-warning" aria-hidden />
      {t("servers.waiting")}
    </p>
  );
}

function AddServerDialog({ org, open, onClose }: { org: Organization; open: boolean; onClose: () => void }) {
  const t = useT();
  const create = useCreateServer(org.slug);
  const [name, setName] = useState("");
  const [environment, setEnvironment] = useState("");
  const [project, setProject] = useState("");
  const [created, setCreated] = useState<CreatedServer | null>(null);
  const error = create.error instanceof ApiError ? create.error : null;

  const close = () => {
    setName("");
    setEnvironment("");
    setProject("");
    setCreated(null);
    create.reset();
    onClose();
  };

  if (created) {
    return (
      <Modal
        open={open}
        onClose={close}
        title={t("servers.installTitle", { name: created.name })}
        footer={
          <>
            <Link
              to={created.id}
              onClick={close}
              className="inline-flex h-10 items-center rounded-lg border border-line px-4 text-sm font-medium text-fg hover:bg-surface-2"
            >
              {created.name}
            </Link>
            <Button onClick={close}>{t("common.close")}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <InstallCommand enrollment={created.enrollment} />
          <ConnectionWatcher org={org} server={created} />
        </div>
      </Modal>
    );
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name, environment, project }, { onSuccess: setCreated });
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={t("servers.addTitle")}
      description={t("servers.addHelp")}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form="add-server" loading={create.isPending} disabled={name.trim().length < 2}>
            {create.isPending ? t("servers.creating") : t("servers.create")}
          </Button>
        </>
      }
    >
      <form id="add-server" className="space-y-4" onSubmit={onSubmit} noValidate>
        {error && !error.fieldError("name") ? <Alert>{error.displayMessage}</Alert> : null}
        <TextField
          label={t("servers.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={error?.fieldError("name")}
          maxLength={100}
          placeholder="web-01"
          data-autofocus
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={t("servers.environment")}
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            error={error?.fieldError("environment")}
            maxLength={32}
            placeholder="production"
          />
          <TextField
            label={t("servers.project")}
            value={project}
            onChange={(e) => setProject(e.target.value)}
            error={error?.fieldError("project")}
            maxLength={64}
          />
        </div>
        <p className="text-xs text-muted">{t("servers.labelHint")}</p>
      </form>
    </Modal>
  );
}

function ServerRow({ server }: { server: Server }) {
  const t = useT();
  const language = useLanguage();
  const f = server.facts;
  const system = [f.hostname, [f.os_name, f.os_version].filter(Boolean).join(" "), f.architecture]
    .filter(Boolean)
    .join(" · ");
  const resources = [
    f.cpu_count ? t("servers.cpuCount", { count: f.cpu_count }) : null,
    f.memory_total ? formatBytes(f.memory_total) : null,
    f.disk_total ? formatBytes(f.disk_total, 0) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <tr className="align-middle hover:bg-surface-2/60">
      <td className="px-5 py-3">
        <Link to={server.id} className="font-medium text-fg hover:text-primary hover:underline">
          {server.name}
        </Link>
        <div className="mt-1 flex flex-wrap gap-1">
          {server.environment ? <Badge tone="primary">{server.environment}</Badge> : null}
          {server.project ? <Badge>{server.project}</Badge> : null}
        </div>
      </td>
      <td className="px-5 py-3">
        <ServerStatusBadge status={server.status} />
      </td>
      <td className="hidden px-5 py-3 text-sm text-muted md:table-cell">{system || "—"}</td>
      <td className="hidden px-5 py-3 text-sm text-muted lg:table-cell">{resources || "—"}</td>
      <td className="px-5 py-3 text-sm text-muted">
        {server.last_seen_at ? (
          <time dateTime={server.last_seen_at}>{formatRelative(server.last_seen_at, language)}</time>
        ) : (
          t("common.never")
        )}
      </td>
    </tr>
  );
}

export function ServersPage() {
  const t = useT();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("servers.title"), org.name);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ServerStatus | "">("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const servers = useServers(org.slug, { search, status, page });
  const canManage = can(org, "servers.manage");
  const filtered = search !== "" || status !== "";

  return (
    <>
      <PageHeader
        title={t("servers.title")}
        description={t("servers.subtitle", { org: org.name })}
        actions={
          canManage ? (
            <Button icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
              {t("servers.add")}
            </Button>
          ) : null
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <label className="relative block min-w-0 flex-1 sm:max-w-sm">
            <span className="sr-only">{t("common.search")}</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={t("servers.search")}
              className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
            />
          </label>
          <Select
            aria-label={t("servers.status")}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as ServerStatus | "");
              setPage(1);
            }}
            className="h-9 max-w-48"
          >
            <option value="">{t("servers.allStatuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`servers.status.${value}`)}
              </option>
            ))}
          </Select>
        </div>

        {servers.isPending ? (
          <Spinner />
        ) : servers.error ? (
          <ErrorState error={servers.error} onRetry={() => servers.refetch()} />
        ) : servers.data.results.length === 0 ? (
          filtered ? (
            <EmptyState title={t("servers.noMatch")} />
          ) : (
            <EmptyState title={t("servers.empty")} icon={<ServerIcon className="size-6" aria-hidden />}>
              <p>{t("servers.emptyHelp")}</p>
              {canManage ? (
                <Button className="mt-4" icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
                  {t("servers.add")}
                </Button>
              ) : (
                <p className="mt-2">{t("servers.readOnly")}</p>
              )}
            </EmptyState>
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("servers.name")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("servers.status")}</th>
                  <th scope="col" className="hidden px-5 py-2.5 font-medium md:table-cell">{t("servers.system")}</th>
                  <th scope="col" className="hidden px-5 py-2.5 font-medium lg:table-cell">{t("servers.resources")}</th>
                  <th scope="col" className="px-5 py-2.5 font-medium">{t("servers.lastSeen")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {servers.data.results.map((server) => (
                  <ServerRow key={server.id} server={server} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {servers.data ? <Pagination page={page} count={servers.data.count} onPage={setPage} /> : null}
      </Card>

      {canManage ? <AddServerDialog org={org} open={adding} onClose={() => setAdding(false)} /> : null}
    </>
  );
}
