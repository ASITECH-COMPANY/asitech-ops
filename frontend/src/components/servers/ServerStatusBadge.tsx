import { Ban, CircleCheck, CircleDashed, CloudOff } from "lucide-react";

import { useT } from "../../i18n";
import type { ServerStatus } from "../../lib/types";
import { Badge } from "../ui/Badge";

// Status is never conveyed by color alone: each state has its own icon and label.
const STYLES = {
  online: { tone: "success", Icon: CircleCheck },
  offline: { tone: "warning", Icon: CloudOff },
  pending: { tone: "neutral", Icon: CircleDashed },
  revoked: { tone: "danger", Icon: Ban },
} as const;

export function ServerStatusBadge({ status }: { status: ServerStatus }) {
  const t = useT();
  const { tone, Icon } = STYLES[status];
  return (
    <Badge tone={tone}>
      <Icon className="size-3.5" aria-hidden />
      {t(`servers.status.${status}`)}
    </Badge>
  );
}
