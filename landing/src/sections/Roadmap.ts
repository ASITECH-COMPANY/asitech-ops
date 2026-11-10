import type { Ctx } from "../context";
import { esc } from "../lib/html";
import { icon } from "../lib/icons";
import { section, sectionHeading } from "./common";

type Status = "planned" | "in-progress" | "done";

const STYLE: Record<Status, { badge: string; dot: string }> = {
  done: { badge: "border-success/30 bg-success-soft text-success", dot: "bg-success text-white" },
  "in-progress": { badge: "border-accent/40 bg-accent-soft text-accent-strong", dot: "bg-accent text-white" },
  planned: { badge: "border-line bg-surface-2 text-muted", dot: "bg-surface-2 text-muted border border-line" },
};

export function Roadmap(ctx: Ctx): string {
  const r = ctx.t.roadmap;
  const phases = ctx.roadmap.phases
    .map((phase) => {
      const status = phase.status as Status;
      const style = STYLE[status];
      const glyph = status === "done" ? icon("check", "size-3.5") : status === "in-progress" ? icon("loader", "size-3.5") : icon("circleDashed", "size-3.5");
      const items = phase.items[ctx.lang].map((item) => `<li>${esc(item)}</li>`).join("");
      return `
      <li class="relative pl-10">
        <span class="absolute left-0 top-0.5 inline-flex size-7 items-center justify-center rounded-full ${style.dot}" aria-hidden="true">${glyph}</span>
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-base font-semibold text-fg">${esc(phase.title[ctx.lang])}</h3>
          <span class="rounded-full border px-2 py-0.5 text-xs font-medium ${style.badge}">${esc(r.status[status])}</span>
        </div>
        <ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-muted marker:text-line">${items}</ul>
      </li>`;
    })
    .join("");
  return section(
    "roadmap",
    `${sectionHeading("roadmap", r.title, r.subtitle)}
     <ol class="relative mt-12 space-y-8 before:absolute before:bottom-2 before:left-3.5 before:top-2 before:w-px before:bg-line">${phases}</ol>`,
  );
}
