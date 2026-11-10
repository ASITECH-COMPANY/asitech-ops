import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { useT } from "../../i18n";
import { Button } from "./Button";

export function CopyField({ value, label }: { value: string; label: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div>
      <span className="mb-1.5 block text-sm font-medium text-fg">{label}</span>
      <div className="flex gap-2">
        <input
          readOnly
          value={value}
          aria-label={label}
          onFocus={(event) => event.currentTarget.select()}
          className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 font-mono text-xs text-fg"
        />
        <Button variant="secondary" onClick={copy} icon={copied ? <Check className="size-4" /> : <Copy className="size-4" />}>
          {copied ? t("common.copied") : t("common.copy")}
        </Button>
      </div>
    </div>
  );
}
