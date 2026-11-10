import type { Ctx } from "../context.ts";
import { esc } from "../lib/html.ts";
import { icon } from "../lib/icons.ts";

type Status = "early-development" | "beta" | "stable";

export function StatusBanner(ctx: Ctx): string {
  const status = ctx.site.status as Status;
  const s = ctx.t.status;
  const headline = s[status];
  const detail = s[`${status}Detail` as const];
  const stable = status === "stable";
  return `
<section aria-label="${esc(s.label)}" class="mx-auto max-w-6xl px-4 sm:px-6">
  <div class="flex flex-col gap-3 rounded-xl border ${stable ? "border-success/30 bg-success-soft" : "border-accent/40 bg-accent-soft"} px-5 py-4 sm:flex-row sm:items-center">
    <span class="${stable ? "text-success" : "text-accent-strong"}">${icon(stable ? "circleCheck" : "alert", "size-5")}</span>
    <p class="flex-1 text-sm text-fg"><strong class="font-semibold">${esc(headline)}</strong> <span class="text-muted">${esc(detail)}</span></p>
    <a href="#roadmap" class="inline-flex items-center gap-1 text-sm font-semibold text-fg underline decoration-accent decoration-2 underline-offset-4 hover:decoration-fg">${esc(s.roadmapLink)}${icon("arrowRight", "size-4")}</a>
  </div>
</section>`;
}
