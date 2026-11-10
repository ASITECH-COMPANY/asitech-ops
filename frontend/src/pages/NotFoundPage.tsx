import { Compass } from "lucide-react";
import { Link } from "react-router";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT } from "../i18n";

export function NotFoundContent() {
  const t = useT();
  useDocumentTitle(t("notFound.title"));
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <Compass className="size-8 text-muted" aria-hidden />
      <h1 className="mt-4 text-xl font-semibold text-fg">{t("notFound.title")}</h1>
      <p className="mt-2 max-w-md text-sm text-muted">{t("notFound.body")}</p>
      <Link to="/" className="mt-6 text-sm font-medium text-primary hover:underline">
        {t("notFound.home")}
      </Link>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="flex min-h-full items-center justify-center">
      <NotFoundContent />
    </div>
  );
}
