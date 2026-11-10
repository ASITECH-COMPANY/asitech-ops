import { Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useOutletContext } from "react-router";

import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/Dialog";
import { Alert, TextField } from "../components/ui/Field";
import { useDeleteOrganization, useUpdateOrganization } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";
import { ApiError } from "../lib/api";
import { can } from "../lib/permissions";
import { usePreferences } from "../stores/preferences";
import type { OrgContext } from "./OrgLayout";

export function OrgSettingsPage() {
  const t = useT();
  const navigate = useNavigate();
  const { org } = useOutletContext<OrgContext>();
  useDocumentTitle(t("settings.title"), org.name);
  const setLastOrg = usePreferences((s) => s.setLastOrg);
  const update = useUpdateOrganization(org.slug);
  const remove = useDeleteOrganization(org.slug);
  const [name, setName] = useState(org.name);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const canEdit = can(org, "organization.update");
  const error = update.error instanceof ApiError ? update.error : null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ name });
  };

  return (
    <>
      <PageHeader title={t("settings.title")} />
      <div className="space-y-6">
        <Card>
          <CardHeader title={t("settings.general")} />
          <form className="space-y-4 p-5" onSubmit={onSubmit} noValidate>
            {!canEdit ? <Alert tone="info">{t("settings.readOnly")}</Alert> : null}
            {update.isSuccess ? <Alert tone="success">{t("common.saved")}</Alert> : null}
            <TextField
              label={t("org.name")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!canEdit}
              maxLength={120}
              error={error?.fieldError("name") ?? (error ? error.displayMessage : undefined)}
              className="max-w-md"
            />
            <TextField label={t("org.slug")} value={org.slug} disabled readOnly className="max-w-md" />
            {canEdit ? (
              <Button type="submit" loading={update.isPending} disabled={name.trim() === org.name || name.trim().length < 2}>
                {update.isPending ? t("common.saving") : t("common.save")}
              </Button>
            ) : null}
          </form>
        </Card>

        {can(org, "organization.delete") ? (
          <Card className="border-danger/40">
            <CardHeader title={<span className="text-danger">{t("settings.danger")}</span>} />
            <div className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div>
                <p className="text-sm font-medium text-fg">{t("settings.delete")}</p>
                <p className="mt-0.5 text-sm text-muted">{t("settings.deleteHelp")}</p>
              </div>
              <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirmOpen(true)}>
                {t("settings.delete")}
              </Button>
            </div>
          </Card>
        ) : null}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => {
          setConfirmOpen(false);
          remove.reset();
        }}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setLastOrg(null);
              navigate("/", { replace: true });
            },
          })
        }
        title={t("settings.deleteTitle", { org: org.name })}
        description={t("settings.deleteBody", { slug: org.slug })}
        confirmLabel={t("settings.delete")}
        confirmText={org.slug}
        loading={remove.isPending}
        error={remove.error instanceof ApiError ? remove.error.displayMessage : null}
      />
    </>
  );
}
