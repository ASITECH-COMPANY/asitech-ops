import { Activity, AppWindow, ExternalLink, Rocket, Server, type LucideIcon } from "lucide-react";
import { useOutletContext } from "react-router";

import { Card } from "../components/ui/Card";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useT, type MessageKey } from "../i18n";
import type { OrgContext } from "./OrgLayout";

export type ModuleName = "servers" | "applications" | "deployments" | "monitoring";

const MODULES: Record<ModuleName, { label: MessageKey; body: MessageKey; phase: string; icon: LucideIcon }> = {
  servers: { label: "nav.servers", body: "soon.servers", phase: "Phase 2", icon: Server },
  applications: { label: "nav.applications", body: "soon.applications", phase: "Phase 3", icon: AppWindow },
  deployments: { label: "nav.deployments", body: "soon.deployments", phase: "Phase 3", icon: Rocket },
  monitoring: { label: "nav.monitoring", body: "soon.monitoring", phase: "Phase 4", icon: Activity },
};

export const ROADMAP_URL = "https://asitechsolution.cloud/#roadmap";

export function ComingSoonPage({ module }: { module: ModuleName }) {
  const t = useT();
  const { org } = useOutletContext<OrgContext>();
  const info = MODULES[module];
  const Icon = info.icon;
  useDocumentTitle(t(info.label), org.name);

  return (
    <Card className="mx-auto mt-6 max-w-xl p-8 text-center">
      <span className="mx-auto flex size-12 items-center justify-center rounded-xl bg-accent-soft text-accent">
        <Icon className="size-6" aria-hidden />
      </span>
      <h1 className="mt-4 text-lg font-semibold text-fg">{t("soon.title", { module: t(info.label) })}</h1>
      <p className="mt-2 text-sm text-muted">{t(info.body)}</p>
      <p className="mt-2 text-sm text-muted">{t("soon.body", { phase: info.phase })}</p>
      <a
        href={ROADMAP_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
      >
        {t("soon.roadmap")}
        <ExternalLink className="size-3.5" aria-hidden />
      </a>
    </Card>
  );
}
