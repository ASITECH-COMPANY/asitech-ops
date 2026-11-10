import type { Ctx } from "../context.ts";
import { esc } from "../lib/html.ts";
import { icon } from "../lib/icons.ts";

export function logo(className = "size-8"): string {
  return `<svg viewBox="0 0 32 32" class="${className}" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="7" fill="#1D4ED8"/><path d="M9 22.5 15.2 8.8a.9.9 0 0 1 1.6 0L23 22.5" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M11.8 17.6h8.4" stroke="#F97316" stroke-width="2.6" stroke-linecap="round"/></svg>`;
}

export function Header(ctx: Ctx): string {
  const { t } = ctx;
  const links: [string, string, boolean][] = [
    ["#features", t.nav.features, false],
    ["#how-it-works", t.nav.how, false],
    ["#security", t.nav.security, false],
    ["#install", t.nav.install, false],
    [`${ctx.site.repoUrl}/tree/${ctx.site.defaultBranch}/docs`, t.nav.docs, true],
  ];
  const navLink = ([href, label, external]: [string, string, boolean], mobile = false) =>
    `<a href="${esc(href)}" class="${
      mobile
        ? "block rounded-lg px-3 py-2.5 text-base text-fg hover:bg-surface-2"
        : "rounded-md px-3 py-2 text-sm text-muted transition-colors hover:text-fg"
    }"${external ? ' target="_blank" rel="noopener noreferrer"' : ""} data-nav-link>${esc(label)}</a>`;

  return `
<a href="#main" class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-fg focus:shadow-lg">${esc(t.a11y.skip)}</a>
<header class="sticky top-0 z-50 border-b border-line/80 bg-bg/85 backdrop-blur-md" data-header>
  <div class="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
    <a href="${ctx.path}" class="flex shrink-0 items-center gap-2.5 rounded-lg" aria-label="${esc(t.a11y.home)}">
      ${logo()}
      <span class="text-[15px] font-semibold tracking-tight text-fg">ASITECH <span class="text-primary">OPS</span></span>
    </a>
    <nav class="ml-4 hidden items-center lg:flex" aria-label="Main">
      ${links.map((link) => navLink(link)).join("")}
    </nav>
    <div class="ml-auto flex items-center gap-1.5">
      <a href="${ctx.altPath}" hreflang="${ctx.altLang}" lang="${ctx.altLang}" class="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-muted hover:bg-surface-2 hover:text-fg" data-lang-switch>
        ${icon("languages", "size-4")}<span class="sr-only">${esc(t.a11y.language)}: </span><span aria-hidden="true">${esc(t.nav.switchToShort)}</span><span class="sr-only">${esc(t.nav.switchTo)}</span>
      </a>
      <button type="button" class="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg" aria-label="${esc(t.a11y.theme)}" data-theme-toggle>
        <span class="dark:hidden">${icon("moon", "size-4")}</span><span class="hidden dark:inline">${icon("sun", "size-4")}</span>
      </button>
      <a href="${esc(ctx.site.repoUrl)}" target="_blank" rel="noopener noreferrer" class="ml-1 hidden h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-fg hover:bg-surface-2 sm:inline-flex">
        ${icon("code", "size-4")}${esc(t.nav.github)}
      </a>
      <button type="button" class="inline-flex size-9 items-center justify-center rounded-lg text-fg hover:bg-surface-2 lg:hidden" aria-expanded="false" aria-controls="mobile-menu" aria-label="${esc(t.a11y.menu)}" data-label-open="${esc(t.a11y.menu)}" data-label-close="${esc(t.a11y.closeMenu)}" data-menu-toggle>
        <span data-menu-icon-open>${icon("menu", "size-5")}</span><span class="hidden" data-menu-icon-close>${icon("x", "size-5")}</span>
      </button>
    </div>
  </div>
  <div id="mobile-menu" class="hidden border-t border-line bg-bg px-4 pb-4 pt-2 lg:hidden" data-mobile-menu>
    <nav aria-label="Mobile">
      ${links.map((link) => navLink(link, true)).join("")}
      <a href="${esc(ctx.site.repoUrl)}" target="_blank" rel="noopener noreferrer" class="mt-2 flex items-center gap-2 rounded-lg px-3 py-2.5 text-base text-fg hover:bg-surface-2">${icon("code", "size-5")}${esc(t.nav.github)}</a>
    </nav>
  </div>
</header>`;
}
