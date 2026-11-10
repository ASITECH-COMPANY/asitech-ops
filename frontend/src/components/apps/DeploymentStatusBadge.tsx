import { CircleCheck, CircleX, Clock, LoaderCircle } from "lucide-react";

import { useT } from "../../i18n";
import type { DeploymentStatus } from "../../lib/types";
import { Badge } from "../ui/Badge";

const STYLES = {
  queued: { tone: "neutral", Icon: Clock, spin: false },
  running: { tone: "primary", Icon: LoaderCircle, spin: true },
  succeeded: { tone: "success", Icon: CircleCheck, spin: false },
  failed: { tone: "danger", Icon: CircleX, spin: false },
} as const;

export function DeploymentStatusBadge({ status }: { status: DeploymentStatus }) {
  const t = useT();
  const { tone, Icon, spin } = STYLES[status];
  return (
    <Badge tone={tone}>
      <Icon className={spin ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden />
      {t(`deployments.status.${status}`)}
    </Badge>
  );
}
