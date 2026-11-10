import type { Ctx } from "../context";
import { esc, fill } from "../lib/html";
import { icon, type IconName } from "../lib/icons";
import { section, sectionHeading } from "./common";

const ICONS: IconName[] = ["lock", "keyRound", "terminal", "scrollText", "boxes", "alert"];

export function Security(ctx: Ctx): string {
  const s = ctx.t.security;
  const items = s.items
    .map(
      (item, i) => `
      <li class="flex gap-4 rounded-xl border border-line bg-surface p-5">
        <span class="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-success-soft text-success">${icon(ICONS[i], "size-4")}</span>
        <div>
          <h3 class="text-sm font-semibold text-fg">${esc(item.title)}</h3>
          <p class="mt-1 text-sm leading-relaxed text-muted">${esc(item.text)}</p>
        </div>
      </li>`,
    )
    .join("");
  const email = esc(ctx.site.securityEmail);
  return section(
    "security",
    `${sectionHeading("security", s.title, s.subtitle)}
     <ul class="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">${items}</ul>
     <div class="mt-8 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:gap-6">
       <a href="${esc(ctx.repo("SECURITY.md"))}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 font-semibold text-primary hover:underline">${icon("shieldCheck", "size-4")}${esc(s.policy)}<span class="sr-only"> ${esc(ctx.t.a11y.newTab)}</span></a>
       <p class="text-muted">${fill(s.report, { email: `<a class="font-medium text-fg underline underline-offset-4" href="mailto:${email}">${email}</a>` })}</p>
     </div>`,
    "border-y border-line bg-surface-2/60",
  );
}
