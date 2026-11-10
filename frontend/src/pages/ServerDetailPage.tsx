import { ArrowLeft, Ban, KeyRound, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router";

import { InstallCommand } from "../components/servers/InstallCommand";
import { MetricsPanel } from "../components/servers/MetricsPanel";
import { ServerStatusBadge } from "../components/servers/ServerStatusBadge";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { ConfirmDialog, Modal } from "../components/ui/Dialog";
import { Alert } from "../components/ui/Field";
import { ErrorState, Spinner } from "../components/ui/States";
import { useServer, useServerAction } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT, type MessageKey } from "../i18n";
import { ApiError } from "../lib/api";
import { formatBytes, formatDateTime, formatRelative } from "../lib/format";
import { can } from "../lib/permissions";
import type { Enrollment, Server } from "../lib/types";
import { NotFoundContent } from "./NotFoundPage";
import type { OrgContext } from "./OrgLayout";

function Facts({ server }: { server: Server }) {
  const t = useT();
  const language = useLanguage();
  const f = server.facts;
  const rows: [MessageKey, ReactNode][] = [
    ["servers.fact.hostname", f.hostname],
    ["servers.fact.os", [f.os_name, f.os_version].filter(Boolean).join(" ")],
    ["servers.fact.kernel", f.kernel],
    ["servers.fact.architecture", f.architecture],
    ["servers.fact.cpu", f.cpu_count ? t("servers.cpuCount", { count: f.cpu_count }) : null],
    ["servers.fact.memory", f.memory_total ? formatBytes(f.memory_total) : null],
    ["servers.fact.disk", f.disk_total ? formatBytes(f.disk_total) : null],
    ["servers.fact.docker", f.docker_version],
    ["servers.fact.agent", f.agent_version],
    ["servers.fact.ip", server.last_ip],
    ["servers.fact.enrolled", server.enrolled_at ? formatDateTime(server.enrolled_at, language) : null],
  ];
  return (
    <Card>
      <CardHeader title={t("servers.facts")} />
      <dl className="grid gap-x-6 gap-y-4 p-5 sm:grid-cols-2 lg:grid-cols-1">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted">{t(label)}</dt>
            <dd className="mt-0.5 break-words text-sm text-fg">{value || "—"}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function errorText(error: unknown): string | null {
  return error instanceof ApiError ? error.displayMessage : error ? String(error) : null;
}

export function ServerDetailPage() {
  const t = useT();
  const language = useLanguage();
  const navigate = useNavigate();
  const { org } = useOutletContext<OrgContext>();
  const { serverId = "" } = useParams();
  const { data: server, error, isPending, refetch } = useServer(org.slug, serverId);
  const actions = useServerAction(org.slug, serverId);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [confirm, setConfirm] = useState<"revoke" | "delete" | null>(null);
  useDocumentTitle(server?.name, org.name);
  const canManage = can(org, "servers.manage");

  if (isPending) return <Spinner />;
  if (error instanceof ApiError && error.status === 404) return <NotFoundContent />;
  if (error || !server) return <ErrorState error={error} onRetry={() => refetch()} />;

  const note =
    server.status === "pending"
      ? t("servers.pendingNote")
      : server.status === "revoked"
        ? t("servers.revokedNote")
        : server.status === "offline"
          ? t("servers.offlineNote")
          : null;

  return (
    <>
      <Link to=".." relative="path" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" aria-hidden />
        {t("servers.back")}
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-xl font-semibold tracking-tight text-fg sm:text-2xl">{server.name}</h1>
            <ServerStatusBadge status={server.status} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            {server.environment ? <Badge tone="primary">{server.environment}</Badge> : null}
            {server.project ? <Badge>{server.project}</Badge> : null}
            <span>
              {t("servers.lastSeen")} :{" "}
              {server.last_seen_at ? formatRelative(server.last_seen_at, language) : t("common.never")}
            </span>
          </div>
        </div>
        {canManage ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              icon={<KeyRound className="size-4" />}
              loading={actions.enrollment.isPending}
              onClick={() => actions.enrollment.mutate(undefined, { onSuccess: setEnrollment })}
              title={t("servers.newTokenHelp")}
            >
              {t("servers.newToken")}
            </Button>
            {server.status !== "revoked" ? (
              <Button variant="secondary" icon={<Ban className="size-4" />} onClick={() => setConfirm("revoke")}>
                {t("servers.revoke")}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {note ? (
        <div className="mb-6">
          <Alert tone={server.status === "revoked" ? "danger" : "info"}>{note}</Alert>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <MetricsPanel slug={org.slug} serverId={server.id} />
        <Facts server={server} />
      </div>

      {canManage ? (
        <Card className="mt-6 border-danger/40">
          <CardHeader title={<span className="text-danger">{t("servers.dangerZone")}</span>} />
          <div className="flex flex-wrap items-center justify-between gap-4 p-5">
            <p className="text-sm text-muted">{t("servers.revokeBody")}</p>
            <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirm("delete")}>
              {t("servers.delete")}
            </Button>
          </div>
        </Card>
      ) : null}

      <Modal
        open={enrollment !== null}
        onClose={() => setEnrollment(null)}
        title={t("servers.installTitle", { name: server.name })}
        footer={<Button onClick={() => setEnrollment(null)}>{t("common.close")}</Button>}
      >
        {enrollment ? <InstallCommand enrollment={enrollment} /> : null}
      </Modal>

      <ConfirmDialog
        open={confirm === "revoke"}
        onClose={() => {
          setConfirm(null);
          actions.revoke.reset();
        }}
        onConfirm={() => actions.revoke.mutate(undefined, { onSuccess: () => setConfirm(null) })}
        title={t("servers.revokeTitle", { name: server.name })}
        description={t("servers.revokeBody")}
        confirmLabel={t("servers.revoke")}
        loading={actions.revoke.isPending}
        error={errorText(actions.revoke.error)}
      />
      <ConfirmDialog
        open={confirm === "delete"}
        onClose={() => {
          setConfirm(null);
          actions.remove.reset();
        }}
        onConfirm={() =>
          actions.remove.mutate(undefined, { onSuccess: () => navigate(`/orgs/${org.slug}/servers`, { replace: true }) })
        }
        title={t("servers.deleteTitle", { name: server.name })}
        description={t("servers.deleteBody", { name: server.name })}
        confirmLabel={t("servers.delete")}
        confirmText={server.name}
        loading={actions.remove.isPending}
        error={errorText(actions.remove.error)}
      />
    </>
  );
}
