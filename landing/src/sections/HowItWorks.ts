import type { Ctx } from "../context";
import { esc } from "../lib/html";
import { icon, type IconName } from "../lib/icons";
import { section, sectionHeading } from "./common";

const ICONS: IconName[] = ["terminal", "network", "rocket"];

export function HowItWorks(ctx: Ctx): string {
  const h = ctx.t.how;
  const steps = h.steps
    .map(
      (step, index) => `
      <li class="relative rounded-xl border border-line bg-surface p-6">
        <div class="flex items-center gap-3">
          <span class="inline-flex size-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-fg" aria-hidden="true">${index + 1}</span>
          <span class="text-muted">${icon(ICONS[index], "size-5")}</span>
        </div>
        <h3 class="mt-5 text-lg font-semibold text-fg">${esc(step.title)}</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">${esc(step.text)}</p>
      </li>`,
    )
    .join("");
  return section(
    "how-it-works",
    `${sectionHeading("how-it-works", h.title, h.subtitle)}
     <ol class="mt-12 grid gap-4 md:grid-cols-3">${steps}</ol>`,
    "border-y border-line bg-surface-2/60",
  );
}
