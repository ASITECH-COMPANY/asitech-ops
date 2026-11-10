import { useEffect, useRef, useState } from "react";

import { deploymentLogs } from "../../hooks/queries";
import { useT } from "../../i18n";
import type { DeploymentLogLine, DeploymentStatus } from "../../lib/types";
import { cn } from "../ui/cn";

/** Polls the logs incrementally while the deployment is active; keeps the view at the bottom when following. */
export function LogViewer({ slug, deploymentId, status }: { slug: string; deploymentId: string; status: DeploymentStatus }) {
  const t = useT();
  const [lines, setLines] = useState<DeploymentLogLine[]>([]);
  const [follow, setFollow] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);
  // Survives effect re-runs so lines are never fetched twice.
  const afterRef = useRef(0);
  const active = status === "queued" || status === "running";

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const page = await deploymentLogs(slug, deploymentId, afterRef.current);
        if (cancelled) return;
        if (page.lines.length) {
          afterRef.current = page.lines[page.lines.length - 1].seq;
          setLines((current) => [...current, ...page.lines]);
        }
        const more = page.lines.length === 1000 || page.status === "queued" || page.status === "running";
        if (more) timer = setTimeout(poll, page.lines.length === 1000 ? 0 : 1500);
      } catch {
        if (!cancelled) timer = setTimeout(poll, 3000);
      }
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // A finished deployment needs one last fetch to get the final lines.
  }, [slug, deploymentId, active]);

  useEffect(() => {
    if (follow && boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines, follow]);

  return (
    <div>
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-xs text-slate-400">
        <span>{t("deployments.logs")}</span>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} className="accent-current" />
          {t("deployments.follow")}
        </label>
      </div>
      <div
        ref={boxRef}
        className="h-[28rem] overflow-auto px-4 py-3 font-mono text-xs leading-5 text-slate-200"
        role="log"
        aria-live="polite"
        tabIndex={0}
      >
        {lines.length === 0 ? (
          <p className="text-slate-500">{t("deployments.noLogs")}</p>
        ) : (
          lines.map((line) => (
            <div
              key={line.seq}
              className={cn(
                "whitespace-pre-wrap break-all",
                line.stream === "system" && "text-sky-300",
                line.stream === "stderr" && "text-amber-300",
              )}
            >
              {line.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
