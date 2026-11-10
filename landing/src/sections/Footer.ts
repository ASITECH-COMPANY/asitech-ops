import type { Ctx } from "../context";
import { esc, fill } from "../lib/html";
import { icon } from "../lib/icons";
import { logo } from "./Header";

export function Footer(ctx: Ctx): string {
  const f = ctx.t.footer;
  const link = (href: string, label: string, external = true) =>
    `<a href="${esc(href)}" class="hover:text-fg"${external ? ' target="_blank" rel="noopener noreferrer"' : ""}>${esc(label)}</a>`;
  return `
<footer class="border-t border-line">
  <div class="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-12 sm:px-6 md:flex-row md:items-start md:justify-between">
    <div>
      <div class="flex items-center gap-2.5">${logo("size-7")}<span class="text-sm font-semibold text-fg">ASITECH <span class="text-primary">OPS</span></span></div>
      <p class="mt-3 text-sm text-muted">${esc(f.tagline)} <span class="whitespace-nowrap">· ${esc(f.madeIn)} 🇧🇯</span></p>
    </div>
    <nav aria-label="Footer" class="flex flex-wrap gap-x-6 gap-y-3 text-sm text-muted">
      ${link(ctx.site.companyUrl, f.company)}
      ${link(ctx.site.repoUrl, ctx.t.nav.github)}
      ${link(ctx.repo("LICENSE"), f.license)}
      <a href="mailto:${esc(ctx.site.contactEmail)}" class="inline-flex items-center gap-1.5 hover:text-fg">${icon("mail", "size-4")}${esc(f.contact)}</a>
      <a href="${ctx.altPath}" hreflang="${ctx.altLang}" lang="${ctx.altLang}" class="hover:text-fg">${esc(ctx.t.nav.switchTo)}</a>
    </nav>
  </div>
  <div class="border-t border-line">
    <p class="mx-auto max-w-6xl px-4 py-6 text-xs text-muted sm:px-6">${fill(f.rights, { year: String(ctx.site.copyrightYear) })}</p>
  </div>
</footer>`;
}
