import { useState, type FormEvent } from "react";

import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { Alert, SelectField, TextField } from "../components/ui/Field";
import { useChangePassword, useMe, useOrganization, useUpdateProfile } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";
import { ApiError } from "../lib/api";
import type { Language, User } from "../lib/types";
import { usePreferences } from "../stores/preferences";

function ProfileForm({ me }: { me: User }) {
  const t = useT();
  const setLanguage = usePreferences((s) => s.setLanguage);
  const update = useUpdateProfile();
  const [fullName, setFullName] = useState(me.full_name);
  const [language, setLang] = useState<Language>(me.language);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ full_name: fullName, language }, { onSuccess: (user) => setLanguage(user.language) });
  };

  return (
    <form className="space-y-4 p-5" onSubmit={onSubmit} noValidate>
      {update.isSuccess ? <Alert tone="success">{t("common.saved")}</Alert> : null}
      {update.error instanceof ApiError ? <Alert>{update.error.displayMessage}</Alert> : null}
      <TextField label={t("account.email")} value={me.email} readOnly disabled className="max-w-md" />
      <TextField
        label={t("account.fullName")}
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        maxLength={150}
        autoComplete="name"
        className="max-w-md"
      />
      <SelectField
        label={t("account.language")}
        value={language}
        onChange={(e) => setLang(e.target.value as Language)}
        className="max-w-md"
      >
        <option value="en">English</option>
        <option value="fr">Français</option>
      </SelectField>
      <Button type="submit" loading={update.isPending}>
        {update.isPending ? t("common.saving") : t("common.save")}
      </Button>
    </form>
  );
}

function PasswordForm() {
  const t = useT();
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const error = change.error instanceof ApiError ? change.error : null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
        },
      },
    );
  };

  return (
    <form className="space-y-4 p-5" onSubmit={onSubmit} noValidate>
      {change.isSuccess ? <Alert tone="success">{t("account.passwordChanged")}</Alert> : null}
      {error && !error.fieldError("current_password") && !error.fieldError("new_password") ? (
        <Alert>{error.status === 429 ? t("login.throttled") : error.displayMessage}</Alert>
      ) : null}
      <input type="text" autoComplete="username" className="hidden" readOnly aria-hidden tabIndex={-1} />
      <TextField
        label={t("account.currentPassword")}
        type="password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        autoComplete="current-password"
        error={error?.fieldError("current_password")}
        className="max-w-md"
      />
      <TextField
        label={t("account.newPassword")}
        type="password"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        autoComplete="new-password"
        hint={t("invite.passwordHint")}
        error={error?.fieldError("new_password")}
        className="max-w-md"
      />
      <Button type="submit" loading={change.isPending} disabled={!current || !next}>
        {t("account.changePassword")}
      </Button>
    </form>
  );
}

export function AccountPage() {
  const t = useT();
  useDocumentTitle(t("account.title"));
  const { data: me } = useMe();
  const lastOrg = usePreferences((s) => s.lastOrg);
  const { data: org } = useOrganization(lastOrg ?? "", lastOrg !== null);

  return (
    <AppShell org={lastOrg ? org : undefined}>
      <PageHeader title={t("account.title")} />
      {me ? (
        <div className="space-y-6">
          <Card>
            <CardHeader title={t("account.profile")} />
            <ProfileForm me={me} />
          </Card>
          <Card>
            <CardHeader title={t("account.password")} />
            <PasswordForm />
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
