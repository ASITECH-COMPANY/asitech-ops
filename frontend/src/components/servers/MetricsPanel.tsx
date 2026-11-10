import { useMemo, useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useServerMetrics } from "../../hooks/queries";
import { useLanguage, useT } from "../../i18n";
import { formatBytes, formatPercent, formatRate, percent } from "../../lib/format";
import type { Language, MetricsRange } from "../../lib/types";
import { Card, CardHeader } from "../ui/Card";
import { cn } from "../ui/cn";
import { EmptyState, ErrorState, Spinner } from "../ui/States";

const RANGES: MetricsRange[] = ["1h", "6h", "24h", "7d"];

interface Row {
  ts: number;
  cpu: number | null;
  memory: number | null;
  disk: number | null;
  rx: number | null;
  tx: number | null;
  memoryUsed: number | null;
  diskUsed: number | null;
}

function timeFormatter(range: MetricsRange, language: Language) {
  const locale = language === "fr" ? "fr-FR" : "en-GB";
  const options: Intl.DateTimeFormatOptions =
    range === "7d" ? { weekday: "short", hour: "2-digit" } : { hour: "2-digit", minute: "2-digit" };
  const format = new Intl.DateTimeFormat(locale, options);
  return (value: number) => format.format(new Date(value));
}

// Shared, recessive chart chrome: hairline solid grid, muted axis text, no axis lines.
const axisProps = {
  tick: { fill: "var(--muted)", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;

interface TooltipItem {
  dataKey?: unknown;
  name?: unknown;
  value?: unknown;
  color?: string;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: readonly TooltipItem[];
  label?: unknown;
  formatTime: (v: number) => string;
  formatValue: (v: number) => string;
}

function ChartTooltip({ active, payload, label, formatTime, formatValue }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-muted">{formatTime(Number(label))}</p>
      {payload.map((item) => (
        <p key={String(item.dataKey)} className="flex items-center gap-2 text-fg">
          <span className="h-0.5 w-3 rounded-full" style={{ background: item.color }} aria-hidden />
          <span className="text-muted">{String(item.name)}</span>
          <span className="ml-auto font-medium tabular-nums">
            {item.value === null || item.value === undefined ? "—" : formatValue(Number(item.value))}
          </span>
        </p>
      ))}
    </div>
  );
}

function ChartCard({ title, value, children }: { title: string; value: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium text-muted">{title}</h3>
        <span className="text-lg font-semibold tabular-nums text-fg">{value}</span>
      </div>
      <div className="h-40">{children}</div>
    </div>
  );
}

function PercentChart({
  rows,
  dataKey,
  name,
  formatTime,
}: {
  rows: Row[];
  dataKey: "cpu" | "memory" | "disk";
  name: string;
  formatTime: (v: number) => string;
}) {
  const language = useLanguage();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey="ts" type="number" domain={["dataMin", "dataMax"]} scale="time" tickFormatter={formatTime} minTickGap={40} {...axisProps} />
        <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(v: number) => `${v} %`} width={48} {...axisProps} />
        <Tooltip
          cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
          content={({ active, payload, label }) => (
            <ChartTooltip
              active={active}
              payload={payload}
              label={label}
              formatTime={formatTime}
              formatValue={(v) => formatPercent(v, language)}
            />
          )}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={name}
          stroke="var(--chart-1)"
          strokeWidth={2}
          fill="var(--chart-1)"
          fillOpacity={0.1}
          dot={false}
          activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function NetworkChart({ rows, formatTime }: { rows: Row[]; formatTime: (v: number) => string }) {
  const t = useT();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey="ts" type="number" domain={["dataMin", "dataMax"]} scale="time" tickFormatter={formatTime} minTickGap={40} {...axisProps} />
        <YAxis tickFormatter={(v: number) => formatBytes(v, 0)} tickCount={3} width={60} {...axisProps} />
        <Tooltip
          cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
          content={({ active, payload, label }) => (
            <ChartTooltip active={active} payload={payload} label={label} formatTime={formatTime} formatValue={formatRate} />
          )}
        />
        {(["rx", "tx"] as const).map((key, index) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={t(`servers.chart.${key}`)}
            stroke={`var(--chart-${index + 1})`}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function SeriesLegend() {
  const t = useT();
  return (
    <ul className="mb-2 flex gap-4 text-xs text-muted" aria-label={t("servers.chart.network")}>
      {(["rx", "tx"] as const).map((key, index) => (
        <li key={key} className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{ background: `var(--chart-${index + 1})` }} aria-hidden />
          {t(`servers.chart.${key}`)}
        </li>
      ))}
    </ul>
  );
}

export function MetricsPanel({ slug, serverId }: { slug: string; serverId: string }) {
  const t = useT();
  const language = useLanguage();
  const [range, setRange] = useState<MetricsRange>("1h");
  const metrics = useServerMetrics(slug, serverId, range);
  const formatTime = useMemo(() => timeFormatter(range, language), [range, language]);

  const rows: Row[] = useMemo(
    () =>
      (metrics.data?.points ?? []).map((p) => ({
        ts: new Date(p.ts).getTime(),
        cpu: p.cpu_percent,
        memory: percent(p.memory_used, p.memory_total),
        disk: percent(p.disk_used, p.disk_total),
        rx: p.net_rx_rate,
        tx: p.net_tx_rate,
        memoryUsed: p.memory_used,
        diskUsed: p.disk_used,
      })),
    [metrics.data],
  );
  const last = rows.at(-1);
  const lastNet = [...rows].reverse().find((r) => r.rx !== null);

  return (
    <Card>
      <CardHeader
        title={t("servers.metrics")}
        actions={
          <div role="group" aria-label={t("servers.metrics")} className="flex rounded-lg border border-line p-0.5">
            {RANGES.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={range === value}
                onClick={() => setRange(value)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium",
                  range === value ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
                )}
              >
                {value}
              </button>
            ))}
          </div>
        }
      />
      {metrics.isPending ? (
        <Spinner />
      ) : metrics.error ? (
        <ErrorState error={metrics.error} onRetry={() => metrics.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title={t("servers.noMetrics")} />
      ) : (
        <div className="p-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title={t("servers.chart.cpu")} value={formatPercent(last?.cpu, language)}>
              <PercentChart rows={rows} dataKey="cpu" name={t("servers.chart.cpu")} formatTime={formatTime} />
            </ChartCard>
            <ChartCard
              title={t("servers.chart.memory")}
              value={formatPercent(last?.memory, language)}
            >
              <PercentChart rows={rows} dataKey="memory" name={t("servers.chart.memory")} formatTime={formatTime} />
            </ChartCard>
            <ChartCard title={t("servers.chart.disk")} value={formatPercent(last?.disk, language)}>
              <PercentChart rows={rows} dataKey="disk" name={t("servers.chart.disk")} formatTime={formatTime} />
            </ChartCard>
            <div className="rounded-lg border border-line p-4">
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <h3 className="text-sm font-medium text-muted">{t("servers.chart.network")}</h3>
                <span className="text-sm font-semibold tabular-nums text-fg">
                  ↓ {formatRate(lastNet?.rx)} · ↑ {formatRate(lastNet?.tx)}
                </span>
              </div>
              <SeriesLegend />
              <div className="h-[8.5rem]">
                <NetworkChart rows={rows} formatTime={formatTime} />
              </div>
            </div>
          </div>

          <details className="mt-4 text-sm">
            <summary className="cursor-pointer text-muted hover:text-fg">{t("servers.tableView")}</summary>
            <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-line">
              <table className="w-full min-w-[36rem] text-left text-xs">
                <thead className="sticky top-0 bg-surface-2 text-muted">
                  <tr>
                    {(["time", "cpu", "memory", "disk", "rx", "tx"] as const).map((key) => (
                      <th key={key} scope="col" className="px-3 py-2 font-medium">
                        {t(`servers.chart.${key}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line tabular-nums">
                  {[...rows].reverse().map((row) => (
                    <tr key={row.ts}>
                      <td className="px-3 py-1.5 text-muted">{formatTime(row.ts)}</td>
                      <td className="px-3 py-1.5">{formatPercent(row.cpu, language)}</td>
                      <td className="px-3 py-1.5">{formatBytes(row.memoryUsed)}</td>
                      <td className="px-3 py-1.5">{formatBytes(row.diskUsed)}</td>
                      <td className="px-3 py-1.5">{formatRate(row.rx)}</td>
                      <td className="px-3 py-1.5">{formatRate(row.tx)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </Card>
  );
}
