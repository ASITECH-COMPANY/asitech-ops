import { useEffect, useRef, useState } from "react";

import { runOperation } from "../../hooks/queries";
import { useT } from "../../i18n";
import { ApiError } from "../../lib/api";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Field";
import { Spinner } from "../ui/States";

/** Last 200 lines of a container, optionally refreshed every 3 s. */
export function LogsDialog({
  slug,
  serverId,
  container,
  onClose,
}: {
  slug: string;
  serverId: string;
  container: string;
  onClose: () => void;
}) {
  const t = useT();
  const [lines, setLines] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [follow, setFollow] = useState(false);
  const boxRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const result = await runOperation(slug, serverId, "container.logs", container, { tail: 200 });
        if (cancelled) return;
        setLines(((result.result?.lines as string[]) ?? []).slice());
        setError(null);
      } catch (exc) {
        if (!cancelled) setError(exc instanceof ApiError ? exc.displayMessage : String(exc));
      }
      if (!cancelled && follow) timer = setTimeout(load, 3000);
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [slug, serverId, container, follow]);

  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={`${t("infra.logs")} ${container}`}>
      <div className="absolute inset-0 bg-black/60" aria-hidden onClick={onClose} />
      <div className="relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-xl">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 px-4 py-3 text-sm text-slate-200">
          <span className="font-mono">{container}</span>
          {lines ? <span className="text-xs text-slate-400">{t("infra.lines", { count: lines.length })}</span> : null}
          <label className="ml-auto flex items-center gap-2 text-xs text-slate-300">
            <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
            {t("infra.follow")}
          </label>
          <Button size="sm" variant="secondary" onClick={onClose} data-autofocus>
            {t("common.close")}
          </Button>
        </div>
        {error ? <div className="p-4"><Alert>{error}</Alert></div> : null}
        {lines === null && !error ? (
          <div className="text-slate-300"><Spinner /></div>
        ) : (
          <pre ref={boxRef} tabIndex={0} className="min-h-64 flex-1 overflow-auto whitespace-pre-wrap break-all p-4 font-mono text-xs leading-5 text-slate-200">
            {lines && lines.length ? lines.join("\n") : t("infra.noLogs")}
          </pre>
        )}
      </div>
    </div>
  );
}

export function InspectDialog({ slug, serverId, container, onClose }: { slug: string; serverId: string; container: string; onClose: () => void }) {
  const t = useT();
  const [data, setData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    runOperation(slug, serverId, "container.inspect", container)
      .then((result) => !cancelled && setData(JSON.stringify(result.result?.inspect ?? {}, null, 2)))
      .catch((exc) => !cancelled && setError(exc instanceof ApiError ? exc.displayMessage : String(exc)));
    return () => {
      cancelled = true;
    };
  }, [slug, serverId, container]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={`${t("infra.inspect")} ${container}`}>
      <div className="absolute inset-0 bg-black/60" aria-hidden onClick={onClose} />
      <div className="relative flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3 text-sm">
          <span className="font-mono text-fg">{container}</span>
          <Button size="sm" variant="secondary" onClick={onClose} data-autofocus>
            {t("common.close")}
          </Button>
        </div>
        {error ? <div className="p-4"><Alert>{error}</Alert></div> : null}
        {data === null && !error ? <Spinner /> : null}
        {data ? <pre className="flex-1 overflow-auto p-4 font-mono text-xs leading-5 text-fg">{data}</pre> : null}
      </div>
    </div>
  );
}
