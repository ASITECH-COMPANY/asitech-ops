import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { useT } from "../../i18n";
import { ApiError } from "../../lib/api";
import { Button } from "./Button";

export function Spinner({ label }: { label?: string }) {
  const t = useT();
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label ?? t("common.loading")}
    </div>
  );
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-full items-center justify-center">
      <Spinner />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  const message =
    error instanceof ApiError
      ? error.status === 0
        ? t("common.networkError")
        : error.displayMessage
      : t("common.networkError");
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <AlertTriangle className="size-6 text-danger" aria-hidden />
      <div>
        <p className="font-medium text-fg">{t("common.errorTitle")}</p>
        <p className="mt-1 text-sm text-muted">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <span className="text-muted">{icon ?? <Inbox className="size-6" aria-hidden />}</span>
      <p className="text-sm font-medium text-fg">{title}</p>
      {children ? <div className="text-sm text-muted">{children}</div> : null}
    </div>
  );
}
