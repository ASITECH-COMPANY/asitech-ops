import { LogIn } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { LogoMark } from "../components/Logo";
import { Button } from "../components/ui/Button";
import { Alert, TextField } from "../components/ui/Field";
import { useLogin } from "../hooks/queries";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";
import { ApiError } from "../lib/api";
import { safeNext } from "../lib/redirect";
import { usePreferences } from "../stores/preferences";

export function AuthLayout({ children }: { children: ReactNode }) {
  const t = useT();
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <LogoMark className="size-11" />
          <p className="mt-4 text-sm text-muted">{t("app.tagline")}</p>
        </div>
        {children}
        <p className="mt-8 text-center text-xs text-muted">{t("login.footer")}</p>
      </div>
    </div>
  );
}

export function LoginPage() {
  const t = useT();
  useDocumentTitle(t("login.submit"));
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setLanguage = usePreferences((s) => s.setLanguage);
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate(
      { email, password },
      {
        onSuccess: (user) => {
          setLanguage(user.language);
          navigate(safeNext(params.get("next")), { replace: true });
        },
      },
    );
  };

  const error = login.error;
  let message: string | null = null;
  if (error instanceof ApiError) {
    message =
      error.status === 429 ? t("login.throttled") : error.status === 0 ? t("common.networkError") : error.displayMessage;
  } else if (error) {
    message = t("common.networkError");
  }

  return (
    <AuthLayout>
      <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-fg">{t("login.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("login.subtitle")}</p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
          {message ? <Alert>{message}</Alert> : null}
          <TextField
            label={t("login.email")}
            type="email"
            name="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
          />
          <TextField
            label={t("login.password")}
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button type="submit" className="w-full" loading={login.isPending} icon={<LogIn className="size-4" />}>
            {login.isPending ? t("login.submitting") : t("login.submit")}
          </Button>
        </form>
      </div>
    </AuthLayout>
  );
}
