import type { Ctx } from "../context.ts";
import { esc } from "../lib/html.ts";
import { icon, type IconName } from "../lib/icons.ts";
import { section, sectionHeading } from "./common.ts";

export function OpenSource(ctx: Ctx): string {
  const o = ctx.t.openSource;
  const links: [string, string, IconName, boolean][] = [
    [ctx.site.repoUrl, o.links.repo, "code", true],
    [ctx.repo("CONTRIBUTING.md"), o.links.contributing, "bookOpen", true],
    [`${ctx.site.repoUrl}/issues`, o.links.issues, "bug", true],
    ["#roadmap", o.links.roadmap, "rocket", false],
  ];
  const items = links
    .map(
      ([href, label, iconName, external]) => `
      <li>
        <a href="${esc(href)}"${external ? ' target="_blank" rel="noopener noreferrer"' : ""} class="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3.5 text-sm font-medium text-fg transition-colors hover:border-primary/40 hover:bg-surface-2">
          <span class="text-primary">${icon(iconName, "size-5")}</span><span class="flex-1">${esc(label)}</span><span class="text-muted">${icon("arrowRight", "size-4")}</span>${external ? `<span class="sr-only"> ${esc(ctx.t.a11y.newTab)}</span>` : ""}
        </a>
      </li>`,
    )
    .join("");
  return section(
    "open-source",
    `<div class="grid gap-10 lg:grid-cols-2 lg:items-center">
       <div>
         <a href="${esc(ctx.repo("LICENSE"))}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-semibold text-fg hover:bg-surface-2">${icon("scale", "size-3.5")}${esc(o.license)}<span class="sr-only"> ${esc(ctx.t.a11y.newTab)}</span></a>
         ${sectionHeading("open-source", o.title, o.subtitle)}
         <p class="mt-4 text-sm text-muted">${esc(o.invite)}</p>
       </div>
       <ul class="grid gap-3 sm:grid-cols-2">${items}</ul>
     </div>`,
    "border-y border-line bg-surface-2/60",
  );
}
