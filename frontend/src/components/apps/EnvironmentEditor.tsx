import { Lock, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { useEnvironment, useSetEnvironment } from "../../hooks/queries";
import { useT } from "../../i18n";
import { ApiError } from "../../lib/api";
import type { EnvVar } from "../../lib/types";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Field";
import { ErrorState, Spinner } from "../ui/States";

interface Row {
  key: string;
  value: string;
  is_secret: boolean;
  stored: boolean; // exists on the server; an empty secret keeps its stored value
}

const input =
  "h-9 w-full rounded-lg border border-line bg-surface px-3 font-mono text-xs text-fg placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-60";

function toRows(vars: EnvVar[]): Row[] {
  return vars.map((v) => ({ key: v.key, value: v.value ?? "", is_secret: v.is_secret, stored: true }));
}

function Editor({ slug, appId, initial, canEdit }: { slug: string; appId: string; initial: EnvVar[]; canEdit: boolean }) {
  const t = useT();
  const save = useSetEnvironment(slug, appId);
  const [rows, setRows] = useState<Row[]>(() => toRows(initial));
  const update = (index: number, patch: Partial<Row>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const submit = () => {
    const variables = rows
      .filter((row) => row.key.trim())
      .map((row) => ({
        key: row.key.trim(),
        is_secret: row.is_secret,
        ...(row.is_secret && row.stored && row.value === "" ? {} : { value: row.value }),
      }));
    save.mutate(variables, { onSuccess: (data) => setRows(toRows(data)) });
  };
  const error = save.error instanceof ApiError ? save.error : null;

  return (
    <div className="space-y-4 p-5">
      <p className="text-sm text-muted">{t("env.help")}</p>
      {save.isSuccess ? <Alert tone="success">{t("env.saved")}</Alert> : null}
      {error ? <Alert>{error.displayMessage}{error.details ? ` ${JSON.stringify(error.details)}` : ""}</Alert> : null}
      {rows.length === 0 ? <p className="text-sm text-muted">{t("env.empty")}</p> : null}
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={index} className="grid grid-cols-[1fr_1.5fr_auto_auto] items-center gap-2">
            <input
              aria-label={t("env.key")}
              className={input}
              value={row.key}
              placeholder="KEY"
              disabled={!canEdit || row.stored}
              onChange={(e) => update(index, { key: e.target.value.toUpperCase() })}
            />
            <input
              aria-label={`${t("env.value")} ${row.key}`}
              className={input}
              type={row.is_secret ? "password" : "text"}
              autoComplete="off"
              value={row.value}
              placeholder={row.is_secret && row.stored ? t("env.hidden") : ""}
              disabled={!canEdit}
              onChange={(e) => update(index, { value: e.target.value })}
            />
            <label className="flex items-center gap-1.5 text-xs text-muted" title={t("env.secret")}>
              <input
                type="checkbox"
                checked={row.is_secret}
                disabled={!canEdit}
                onChange={(e) => update(index, { is_secret: e.target.checked })}
              />
              <Lock className="size-3.5" aria-hidden />
              <span className="sr-only">{t("env.secret")}</span>
            </label>
            {canEdit ? (
              <button
                type="button"
                className="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-danger"
                aria-label={t("env.remove", { key: row.key || "…" })}
                onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
              >
                <Trash2 className="size-4" aria-hidden />
              </button>
            ) : (
              <span />
            )}
          </div>
        ))}
      </div>
      {canEdit ? (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<Plus className="size-4" />}
            onClick={() => setRows((current) => [...current, { key: "", value: "", is_secret: true, stored: false }])}
          >
            {t("env.add")}
          </Button>
          <Button size="sm" onClick={submit} loading={save.isPending}>
            {t("env.save")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function EnvironmentEditor({ slug, appId, canEdit }: { slug: string; appId: string; canEdit: boolean }) {
  const env = useEnvironment(slug, appId);
  if (env.isPending) return <Spinner />;
  if (env.error) return <ErrorState error={env.error} onRetry={() => env.refetch()} />;
  return <Editor slug={slug} appId={appId} initial={env.data} canEdit={canEdit} />;
}
