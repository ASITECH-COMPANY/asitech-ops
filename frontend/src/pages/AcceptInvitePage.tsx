import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { Button } from "../components/ui/Button";
import { Alert, TextField } from "../components/ui/Field";
import { ErrorState, Spinner } from "../components/ui/States";
import { keys, useLogout, useMe } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useLanguage, useT } from "../i18n";
import { api, ApiError } from "../lib/api";
import { formatDateTime } from "../lib/format";
import type { InvitationPreview, Organization, User } from "../lib/types";
import { AuthLayout } from "./LoginPage";

export function AcceptInvitePage() {
  const t = useT();
  const language = useLanguage();
  useDocumentTitle(t("invite.title"));
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  // The token lives in the URL fragment, which is never sent to the server.
  const token = location.hash.replace(/^#/, "");
  const me = useMe();
  const logout = useLogout();
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => api<InvitationPreview>("/invitations/preview/", { method: "POST", body: { token } }),
    enabled: token.length > 0,
    retry: false,
  });

  const accept = useMutation({
    mutationFn: (body: { full_name?: string; password?: string }) =>
      api<Organization & { user: User }>("/invitations/accept/", { method: "POST", body: { token, ...body } }),
    onSuccess: (org) => {
      qc.setQueryData(keys.me, org.user);
      qc.invalidateQueries({ queryKey: keys.organizations });
      navigate(`/orgs/${org.slug}`, { replace: true });
    },
  });

  const content = () => {
    if (!token) return <Alert>{t("invite.invalid")}</Alert>;
    if (preview.isPending) return <Spinner />;
    if (preview.error) {
      return preview.error instanceof ApiError && preview.error.status === 404 ? (
        <Alert>{t("invite.invalid")}</Alert>
      ) : (
        <ErrorState error={preview.error} onRetry={() => preview.refetch()} />
      );
    }
    const invite = preview.data;
    if (invite.status !== "pending") return <Alert>{t(`invite.status.${invite.status}`)}</Alert>;

    const summaryParams = {
      inviter: invite.invited_by ?? "",
      email: invite.email,
      org: invite.organization.name,
      role: t(`role.${invite.role}`),
    };
    const acceptError = accept.error instanceof ApiError ? accept.error : null;

    let action: ReactNode;
    if (me.data) {
      action =
        me.data.email === invite.email ? (
          <Button className="w-full" loading={accept.isPending} onClick={() => accept.mutate({})}>
            {accept.isPending ? t("invite.accepting") : t("invite.accept")}
          </Button>
        ) : (
          <div className="space-y-3">
            <Alert>{t("invite.wrongAccount", { current: me.data.email, email: invite.email })}</Alert>
            <Button variant="secondary" className="w-full" onClick={() => logout.mutate()}>
              {t("topbar.logout")}
            </Button>
          </div>
        );
    } else if (me.isPending) {
      action = <Spinner />;
    } else if (invite.account_exists) {
      action = (
        <div className="space-y-3">
          <Alert tone="info">{t("invite.signInFirst", { email: invite.email })}</Alert>
          <Link
            to={`/login?next=${encodeURIComponent(`/invite#${token}`)}`}
            className="flex h-10 w-full items-center justify-center rounded-lg bg-primary text-sm font-medium text-primary-fg hover:bg-primary-hover"
          >
            {t("invite.signIn")}
          </Link>
        </div>
      );
    } else {
      const onSubmit = (event: FormEvent) => {
        event.preventDefault();
        accept.mutate({ full_name: fullName, password });
      };
      action = (
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <p className="text-sm font-medium text-fg">{t("invite.createAccount")}</p>
          <TextField label={t("login.email")} value={invite.email} readOnly autoComplete="username" />
          <TextField
            label={t("invite.fullName")}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            required
            error={acceptError?.fieldError("full_name")}
          />
          <TextField
            label={t("invite.password")}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
            hint={t("invite.passwordHint")}
            error={acceptError?.fieldError("password")}
          />
          <Button type="submit" className="w-full" loading={accept.isPending}>
            {accept.isPending ? t("invite.accepting") : t("invite.accept")}
          </Button>
        </form>
      );
    }

    return (
      <div className="space-y-5">
        <div className="flex gap-3 rounded-lg bg-primary-soft p-4 text-sm text-fg">
          <MailCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
          <div>
            <p>{t(invite.invited_by ? "invite.summary" : "invite.summaryAnonymous", summaryParams)}</p>
            <p className="mt-1 text-xs text-muted">
              {t("invite.expires", { date: formatDateTime(invite.expires_at, language) })}
            </p>
          </div>
        </div>
        {acceptError && !acceptError.fieldError("password") && !acceptError.fieldError("full_name") ? (
          <Alert>{acceptError.displayMessage}</Alert>
        ) : null}
        {action}
      </div>
    );
  };

  return (
    <AuthLayout>
      <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
        <h1 className="mb-5 text-lg font-semibold text-fg">{t("invite.title")}</h1>
        {content()}
      </div>
    </AuthLayout>
  );
}
