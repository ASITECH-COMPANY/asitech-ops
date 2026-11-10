import { Building2, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Alert, TextField } from "../components/ui/Field";
import { useCreateOrganization, useMe } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";
import { ApiError } from "../lib/api";

export function OnboardingPage() {
  const t = useT();
  useDocumentTitle(t("onboarding.title"));
  const navigate = useNavigate();
  const { data: me } = useMe();
  const create = useCreateOrganization();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { name, ...(slug ? { slug } : {}) },
      { onSuccess: (org) => navigate(`/orgs/${org.slug}`, { replace: true }) },
    );
  };
  const error = create.error instanceof ApiError ? create.error : null;

  return (
    <AppShell>
      <div className="mx-auto max-w-lg py-6">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">{t("onboarding.title")}</h1>
        {me?.can_create_organizations ? (
          <Card className="mt-6 p-6">
            <div className="flex items-start gap-3">
              <span className="rounded-lg bg-primary-soft p-2 text-primary">
                <Building2 className="size-5" aria-hidden />
              </span>
              <div>
                <h2 className="font-semibold text-fg">{t("onboarding.create")}</h2>
                <p className="mt-1 text-sm text-muted">{t("onboarding.createHelp")}</p>
              </div>
            </div>
            <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
              {error && !error.fieldError("name") && !error.fieldError("slug") ? <Alert>{error.displayMessage}</Alert> : null}
              <TextField
                label={t("org.name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={120}
                error={error?.fieldError("name")}
                autoFocus
              />
              <TextField
                label={t("org.slug")}
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase())}
                maxLength={60}
                pattern="[a-z0-9-]*"
                hint={t("org.slugHelp")}
                error={error?.fieldError("slug")}
                spellCheck={false}
              />
              <Button type="submit" loading={create.isPending} disabled={name.trim().length < 2}>
                {create.isPending ? t("org.creating") : t("org.create")}
              </Button>
            </form>
          </Card>
        ) : (
          <Card className="mt-6 flex items-start gap-3 p-6">
            <span className="rounded-lg bg-accent-soft p-2 text-accent">
              <Mail className="size-5" aria-hidden />
            </span>
            <div>
              <h2 className="font-semibold text-fg">{t("onboarding.noAccess")}</h2>
              <p className="mt-1 text-sm text-muted">{t("onboarding.noAccessHelp")}</p>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
