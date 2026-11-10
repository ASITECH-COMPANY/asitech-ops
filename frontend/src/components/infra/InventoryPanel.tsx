import { FileSearch, Play, RotateCw, ScrollText, Search, Square, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { useInventory, useOperation } from "../../hooks/queries";
import { useLanguage, useT, type MessageKey } from "../../i18n";
import { formatRelative } from "../../lib/format";
import { can } from "../../lib/permissions";
import type { ContainerItem, Organization, Server } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/Dialog";
import { Alert } from "../ui/Field";
import { EmptyState, ErrorState, Spinner } from "../ui/States";
import { InspectDialog, LogsDialog } from "./LogsDialog";
import { useServerOps } from "./useServerOps";

export type InventoryTab = "containers" | "images" | "volumes" | "networks";

export function containerState(t: ReturnType<typeof useT>, state: string): string {
  const key = `infra.stateValue.${state}` as MessageKey;
  const label = t(key);
  return label === key ? state : label;
}

const STATE_TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "primary"> = {
  running: "success",
  restarting: "warning",
  paused: "warning",
  exited: "neutral",
  dead: "danger",
  created: "primary",
};

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-left text-sm">
        <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={i} scope="col" className={i === head.length - 1 ? "px-4 py-2.5 text-right font-medium" : "px-4 py-2.5 font-medium"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

export function InventoryPanel({ org, server, tab }: { org: Organization; server: Server; tab: InventoryTab }) {
  const t = useT();
  const language = useLanguage();
  const inventory = useInventory(org.slug, server.id);
  const refresh = useOperation(org.slug, server.id);
  const ops = useServerOps(org.slug, server.id);
  const [filter, setFilter] = useState("");
  const [logs, setLogs] = useState<string | null>(null);
  const [inspect, setInspect] = useState<string | null>(null);
  const manage = can(org, "servers.manage");
  const canLogs = can(org, "applications.deploy");
  const online = server.status === "online";
  const isManaged = (name: string) => server.manage_all_containers || name.startsWith("asitech");
  const allowed = (managed: boolean) => manage && online && (server.manage_all_containers || managed);

  if (inventory.isPending) return <Spinner />;
  if (inventory.error) return <ErrorState error={inventory.error} onRetry={() => inventory.refetch()} />;
  const data = inventory.data.data;
  const query = filter.trim().toLowerCase();
  const match = (...values: string[]) => !query || values.some((v) => v.toLowerCase().includes(query));

  const header = (
    <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
      <label className="relative block min-w-0 flex-1 sm:max-w-sm">
        <span className="sr-only">{t("common.search")}</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={t("infra.search")}
          className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
        />
      </label>
      <span className="text-xs text-muted">
        {inventory.data.collected_at ? t("infra.collected", { time: formatRelative(inventory.data.collected_at, language) }) : null}
      </span>
      <Button
        size="sm"
        variant="secondary"
        icon={<RotateCw className="size-4" />}
        loading={refresh.isPending}
        disabled={!online}
        onClick={() => refresh.mutate({ op: "inventory.refresh" })}
      >
        {t("infra.refresh")}
      </Button>
      {tab === "images" && manage ? (
        <Button size="sm" variant="secondary" icon={<Trash2 className="size-4" />} disabled={!online}
          onClick={() => ops.ask({ op: "images.prune", target: "", label: t("infra.prune") })}>
          {t("infra.prune")}
        </Button>
      ) : null}
    </div>
  );

  let body: ReactNode;
  if (!data) {
    body = <EmptyState title={t("infra.noInventory")} />;
  } else if (data.docker === "unavailable") {
    body = <div className="p-4"><Alert>{t("infra.dockerUnavailable", { error: data.error || "?" })}</Alert></div>;
  } else if (tab === "containers") {
    const rows = data.containers.filter((c) => match(c.name, c.image, c.compose_project));
    const actions = (c: ContainerItem) => {
      const managed = Boolean(c.app_id);
      const ok = allowed(managed);
      const reason = ok ? undefined : t("infra.readOnlyRow");
      const ask = (op: "container.start" | "container.stop" | "container.restart" | "container.remove", key: MessageKey) =>
        ops.ask({ op, target: c.name, label: t(key) });
      return (
        <div className="flex justify-end gap-0.5" role="group" aria-label={t("infra.actions", { name: c.name })}>
          {canLogs ? (
            <IconButton label={t("infra.logs")} disabled={!online} onClick={() => setLogs(c.name)}>
              <ScrollText className="size-4" aria-hidden />
            </IconButton>
          ) : null}
          {manage ? (
            <IconButton label={t("infra.inspect")} disabled={!online} onClick={() => setInspect(c.name)}>
              <FileSearch className="size-4" aria-hidden />
            </IconButton>
          ) : null}
          {manage ? (
            c.state === "running" ? (
              <>
                <IconButton label={reason ?? t("infra.restart")} disabled={!ok} onClick={() => ask("container.restart", "infra.restart")}>
                  <RotateCw className="size-4" aria-hidden />
                </IconButton>
                <IconButton label={reason ?? t("infra.stop")} disabled={!ok} onClick={() => ask("container.stop", "infra.stop")}>
                  <Square className="size-4" aria-hidden />
                </IconButton>
              </>
            ) : (
              <>
                <IconButton label={reason ?? t("infra.start")} disabled={!ok} onClick={() => ask("container.start", "infra.start")}>
                  <Play className="size-4" aria-hidden />
                </IconButton>
                <IconButton label={reason ?? t("infra.remove")} disabled={!ok} onClick={() => ask("container.remove", "infra.remove")}>
                  <Trash2 className="size-4" aria-hidden />
                </IconButton>
              </>
            )
          ) : null}
        </div>
      );
    };
    body = rows.length === 0 ? <EmptyState title={t("infra.empty")} /> : (
      <Table head={[t("infra.name"), t("infra.state"), t("infra.image"), t("infra.usage"), t("infra.ports"), ""]}>
        {rows.map((c) => (
          <tr key={c.id} className="align-middle">
            <td className="px-4 py-2.5">
              <p className="font-medium text-fg">{c.name}</p>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {c.app_id ? <Badge tone="primary">{t("infra.managed")}</Badge> : null}
                {c.compose_project ? <Badge>{t("infra.stack", { name: c.compose_project })}</Badge> : null}
              </div>
            </td>
            <td className="px-4 py-2.5">
              <Badge tone={STATE_TONE[c.state] ?? "neutral"}>{containerState(t, c.state)}</Badge>
              <p className="mt-0.5 text-xs text-muted">{c.status}</p>
            </td>
            <td className="max-w-56 truncate px-4 py-2.5 font-mono text-xs text-muted" title={c.image}>{c.image}</td>
            <td className="px-4 py-2.5 text-xs tabular-nums text-muted">
              {c.cpu_percent !== null ? `${c.cpu_percent} % · ${c.memory_usage.split(" / ")[0] || "—"}` : "—"}
            </td>
            <td className="max-w-48 truncate px-4 py-2.5 font-mono text-xs text-muted" title={c.ports}>{c.ports || "—"}</td>
            <td className="px-4 py-2.5">{actions(c)}</td>
          </tr>
        ))}
      </Table>
    );
  } else if (tab === "images") {
    const rows = data.images.filter((i) => match(i.repository, i.tag, i.id));
    body = rows.length === 0 ? <EmptyState title={t("infra.empty")} /> : (
      <Table head={[t("infra.image"), t("infra.size"), t("infra.created"), t("infra.state"), ""]}>
        {rows.map((i) => {
          const ref = i.tag && i.tag !== "<none>" ? `${i.repository}:${i.tag}` : i.id;
          const ok = allowed(isManaged(i.repository)) && !i.in_use;
          return (
            <tr key={`${i.id}-${i.tag}`}>
              <td className="px-4 py-2.5 font-mono text-xs text-fg">{ref}</td>
              <td className="px-4 py-2.5 text-muted">{i.size}</td>
              <td className="px-4 py-2.5 text-muted">{i.created}</td>
              <td className="px-4 py-2.5"><Badge tone={i.in_use ? "success" : "neutral"}>{i.in_use ? t("infra.inUse") : t("infra.unused")}</Badge></td>
              <td className="px-4 py-2.5 text-right">
                {manage ? (
                  <IconButton label={ok ? t("infra.remove") : t("infra.readOnlyRow")} disabled={!ok}
                    onClick={() => ops.ask({ op: "image.remove", target: ref, label: t("infra.remove") })}>
                    <Trash2 className="size-4" aria-hidden />
                  </IconButton>
                ) : null}
              </td>
            </tr>
          );
        })}
      </Table>
    );
  } else if (tab === "volumes") {
    const rows = data.volumes.filter((v) => match(v.name, v.compose_project));
    body = rows.length === 0 ? <EmptyState title={t("infra.empty")} /> : (
      <Table head={[t("infra.name"), t("infra.driver"), t("infra.state"), ""]}>
        {rows.map((v) => {
          const ok = allowed(isManaged(v.name)) && !v.in_use;
          return (
            <tr key={v.name}>
              <td className="px-4 py-2.5">
                <p className="max-w-md truncate font-mono text-xs text-fg" title={v.name}>{v.name}</p>
                {v.compose_project ? <Badge className="mt-1">{t("infra.stack", { name: v.compose_project })}</Badge> : null}
              </td>
              <td className="px-4 py-2.5 text-muted">{v.driver}</td>
              <td className="px-4 py-2.5"><Badge tone={v.in_use ? "success" : "neutral"}>{v.in_use ? t("infra.inUse") : t("infra.unused")}</Badge></td>
              <td className="px-4 py-2.5 text-right">
                {manage ? (
                  <IconButton label={ok ? t("infra.remove") : t("infra.readOnlyRow")} disabled={!ok}
                    onClick={() => ops.ask({ op: "volume.remove", target: v.name, label: t("infra.remove") })}>
                    <Trash2 className="size-4" aria-hidden />
                  </IconButton>
                ) : null}
              </td>
            </tr>
          );
        })}
      </Table>
    );
  } else {
    const rows = data.networks.filter((n) => match(n.name, n.driver));
    body = rows.length === 0 ? <EmptyState title={t("infra.empty")} /> : (
      <Table head={[t("infra.name"), t("infra.driver"), t("infra.scope"), ""]}>
        {rows.map((n) => {
          const ok = allowed(isManaged(n.name)) && !n.builtin;
          return (
            <tr key={n.id}>
              <td className="px-4 py-2.5">
                <span className="font-mono text-xs text-fg">{n.name}</span>
                {n.builtin ? <Badge className="ml-2">{t("infra.builtin")}</Badge> : null}
              </td>
              <td className="px-4 py-2.5 text-muted">{n.driver}</td>
              <td className="px-4 py-2.5 text-muted">{n.scope}</td>
              <td className="px-4 py-2.5 text-right">
                {manage ? (
                  <IconButton label={ok ? t("infra.remove") : t("infra.readOnlyRow")} disabled={!ok}
                    onClick={() => ops.ask({ op: "network.remove", target: n.name, label: t("infra.remove") })}>
                    <Trash2 className="size-4" aria-hidden />
                  </IconButton>
                ) : null}
              </td>
            </tr>
          );
        })}
      </Table>
    );
  }

  const confirmBody: Record<string, MessageKey> = {
    "container.stop": "infra.confirmStop",
    "container.restart": "infra.confirmRestart",
    "container.remove": "infra.confirmRemove",
    "container.start": "infra.confirmStart",
    "image.remove": "infra.confirmImage",
    "volume.remove": "infra.confirmVolume",
    "network.remove": "infra.confirmNetwork",
    "images.prune": "infra.pruneBody",
  };
  const pending = ops.pending;

  return (
    <Card>
      {header}
      {ops.notice ? <div className="px-4 pt-3"><Alert tone="success">{ops.notice}</Alert></div> : null}
      {refresh.error ? <div className="px-4 pt-3"><Alert>{String((refresh.error as Error).message)}</Alert></div> : null}
      {body}
      {pending ? (
        <ConfirmDialog
          open
          onClose={ops.cancel}
          onConfirm={() => ops.confirm(t("infra.done"))}
          title={pending.op === "images.prune" ? t("infra.pruneTitle") : t("infra.confirmTitle", { action: pending.label, name: pending.target })}
          description={t(confirmBody[pending.op], { name: pending.target })}
          confirmLabel={pending.label}
          confirmText={pending.op === "volume.remove" ? pending.target : undefined}
          loading={ops.loading}
          error={ops.error}
        />
      ) : null}
      {logs ? <LogsDialog slug={org.slug} serverId={server.id} container={logs} onClose={() => setLogs(null)} /> : null}
      {inspect ? <InspectDialog slug={org.slug} serverId={server.id} container={inspect} onClose={() => setInspect(null)} /> : null}
    </Card>
  );
}
