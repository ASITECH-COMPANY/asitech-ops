import { useState, type FormEvent, type ReactNode } from "react";

import { useSaveApplication, useServers } from "../../hooks/queries";
import { useT } from "../../i18n";
import { ApiError } from "../../lib/api";
import type { Application, ApplicationInput } from "../../lib/types";
import { Button } from "../ui/Button";
import { Alert, SelectField, TextField } from "../ui/Field";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-1 text-sm font-semibold text-fg">{title}</legend>
      {children}
    </fieldset>
  );
}

const numberOrNull = (value: string) => (value.trim() === "" ? null : Number(value));

/** Create (no `app`) or edit an application. */
export function ApplicationForm({
  slug,
  app,
  onSaved,
  formId,
  showSubmit = true,
}: {
  slug: string;
  app?: Application;
  onSaved: (app: Application) => void;
  formId: string;
  showSubmit?: boolean;
}) {
  const t = useT();
  const save = useSaveApplication(slug, app?.id);
  const servers = useServers(slug, { search: "", status: "", page: 1 });
  const [form, setForm] = useState({
    name: app?.name ?? "",
    server: app?.server.id ?? "",
    repo_url: app?.repo_url ?? "",
    branch: app?.branch ?? "main",
    repo_token: "",
    remove_token: false,
    build_type: app?.build_type ?? "dockerfile",
    dockerfile_path: app?.dockerfile_path ?? "Dockerfile",
    build_context: app?.build_context ?? ".",
    compose_file: app?.compose_file ?? "docker-compose.yml",
    start_command: (app?.start_command ?? []).join("\n"),
    container_port: app?.container_port?.toString() ?? "",
    host_port: app?.host_port?.toString() ?? "",
    bind_address: app?.bind_address ?? "127.0.0.1",
    healthcheck_path: app?.healthcheck_path ?? "/",
    healthcheck_timeout_seconds: (app?.healthcheck_timeout_seconds ?? 60).toString(),
  });
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));
  const error = save.error instanceof ApiError ? save.error : null;
  const fieldError = (name: string) => error?.fieldError(name);
  const availableServers = (servers.data?.results ?? []).filter((s) => s.status !== "revoked");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const body: ApplicationInput = {
      name: form.name,
      repo_url: form.repo_url.trim(),
      branch: form.branch.trim(),
      build_type: form.build_type as Application["build_type"],
      dockerfile_path: form.dockerfile_path,
      build_context: form.build_context,
      compose_file: form.compose_file,
      start_command: form.start_command.split("\n").map((a) => a.trim()).filter(Boolean),
      container_port: numberOrNull(form.container_port),
      host_port: numberOrNull(form.host_port),
      bind_address: form.bind_address as Application["bind_address"],
      healthcheck_path: form.healthcheck_path.trim(),
      healthcheck_timeout_seconds: Number(form.healthcheck_timeout_seconds) || 60,
    };
    if (!app) body.server = form.server;
    if (form.repo_token) body.repo_token = form.repo_token;
    else if (form.remove_token) body.repo_token = "";
    save.mutate(body, { onSuccess: onSaved });
  };

  return (
    <form id={formId} className="space-y-8" onSubmit={onSubmit} noValidate>
      {error && !error.details ? <Alert>{error.displayMessage}</Alert> : null}
      {error?.details && Object.keys(error.details).some((k) => !(k in form)) ? <Alert>{error.displayMessage}</Alert> : null}

      <Section title={t("apps.form.source")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label={t("apps.name")} value={form.name} onChange={set("name")} error={fieldError("name")} maxLength={100} />
          <SelectField
            label={t("apps.server")}
            value={form.server}
            onChange={set("server")}
            disabled={Boolean(app)}
            error={fieldError("server")}
          >
            <option value="" disabled>
              —
            </option>
            {(app ? [app.server] : availableServers).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({t(`servers.status.${s.status}`)})
              </option>
            ))}
          </SelectField>
        </div>
        <TextField
          label={t("apps.form.repoUrl")}
          value={form.repo_url}
          onChange={set("repo_url")}
          hint={t("apps.form.repoUrlHint")}
          error={fieldError("repo_url")}
          placeholder="https://github.com/…"
          spellCheck={false}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label={t("apps.form.branch")} value={form.branch} onChange={set("branch")} error={fieldError("branch")} spellCheck={false} />
          <TextField
            label={t("apps.form.token")}
            type="password"
            autoComplete="off"
            value={form.repo_token}
            onChange={set("repo_token")}
            hint={app?.has_repo_token ? t("apps.form.tokenSet") : t("apps.form.tokenHint")}
            error={fieldError("repo_token")}
          />
        </div>
        {app?.has_repo_token ? (
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={form.remove_token}
              onChange={(e) => setForm((c) => ({ ...c, remove_token: e.target.checked }))}
            />
            {t("apps.form.removeToken")}
          </label>
        ) : null}
      </Section>

      <Section title={t("apps.form.build")}>
        <SelectField label={t("apps.form.buildType")} value={form.build_type} onChange={set("build_type")} className="sm:max-w-xs">
          <option value="dockerfile">Dockerfile</option>
          <option value="compose">Docker Compose</option>
        </SelectField>
        {form.build_type === "dockerfile" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label={t("apps.form.dockerfile")} value={form.dockerfile_path} onChange={set("dockerfile_path")} error={fieldError("dockerfile_path")} spellCheck={false} />
            <TextField label={t("apps.form.context")} value={form.build_context} onChange={set("build_context")} error={fieldError("build_context")} spellCheck={false} />
          </div>
        ) : (
          <TextField label={t("apps.form.composeFile")} value={form.compose_file} onChange={set("compose_file")} error={fieldError("compose_file")} spellCheck={false} />
        )}
      </Section>

      <Section title={t("apps.form.run")}>
        {form.build_type === "dockerfile" ? (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField label={t("apps.form.containerPort")} inputMode="numeric" value={form.container_port} onChange={set("container_port")} error={fieldError("container_port")} />
              <TextField label={t("apps.form.hostPort")} inputMode="numeric" value={form.host_port} onChange={set("host_port")} error={fieldError("host_port")} />
              <SelectField label={t("apps.form.bind")} value={form.bind_address} onChange={set("bind_address")}>
                <option value="127.0.0.1">{t("apps.form.bindLocal")}</option>
                <option value="0.0.0.0">{t("apps.form.bindAll")}</option>
              </SelectField>
            </div>
            <p className="-mt-2 text-xs text-muted">{t("apps.form.hostPortHint")}</p>
            <div>
              <label htmlFor={`${formId}-cmd`} className="mb-1.5 block text-sm font-medium text-fg">
                {t("apps.form.command")}
              </label>
              <textarea
                id={`${formId}-cmd`}
                value={form.start_command}
                onChange={set("start_command")}
                rows={3}
                spellCheck={false}
                className="block w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-xs text-fg focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
              />
              <p className="mt-1.5 text-xs text-muted">{fieldError("start_command") ?? t("apps.form.commandHint")}</p>
            </div>
          </>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label={t("apps.form.healthPath")} value={form.healthcheck_path} onChange={set("healthcheck_path")} hint={t("apps.form.healthPathHint")} error={fieldError("healthcheck_path")} spellCheck={false} />
          <TextField label={t("apps.form.healthTimeout")} inputMode="numeric" value={form.healthcheck_timeout_seconds} onChange={set("healthcheck_timeout_seconds")} error={fieldError("healthcheck_timeout_seconds")} />
        </div>
      </Section>

      {showSubmit ? (
        <Button type="submit" loading={save.isPending}>
          {app ? t("apps.form.save") : t("apps.form.create")}
        </Button>
      ) : null}
    </form>
  );
}
