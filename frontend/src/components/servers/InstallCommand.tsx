import { Info } from "lucide-react";

import { useLanguage, useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import type { Enrollment } from "../../lib/types";
import { CopyField } from "../ui/CopyField";

export function InstallCommand({ enrollment }: { enrollment: Enrollment }) {
  const t = useT();
  const language = useLanguage();
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        {t("servers.installHelp", { date: formatDateTime(enrollment.expires_at, language) })}
      </p>
      <CopyField label={t("servers.command")} value={enrollment.command} />
      <p className="flex gap-2 text-xs text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        {t("servers.installNote")}
      </p>
    </div>
  );
}
