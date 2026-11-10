import type { Ctx } from "../context";
import { esc } from "../lib/html";
import { icon } from "../lib/icons";

/** A schematic of the planned dashboard. Deliberately free of numbers: it is an illustration, not data. */
function illustration(ctx: Ctx): string {
  const l = ctx.t.hero.illustration;
  const row = (y: number, label: string, pill: string, tone: "success" | "accent") => `
    <g transform="translate(196 ${y})">
      <rect width="368" height="44" rx="8" class="fill-surface stroke-line" stroke-width="1"/>
      <rect x="14" y="13" width="18" height="18" rx="4" class="fill-primary-soft"/>
      <rect x="44" y="14" width="${label.length * 7 + 20}" height="7" rx="3.5" class="fill-fg/70"/>
      <rect x="44" y="27" width="96" height="5" rx="2.5" class="fill-muted/40"/>
      <rect x="${368 - 14 - (pill.length * 6.4 + 24)}" y="12" width="${pill.length * 6.4 + 24}" height="20" rx="10" class="${tone === "success" ? "fill-success-soft" : "fill-accent-soft"}"/>
      <circle cx="${368 - 14 - (pill.length * 6.4 + 24) + 11}" cy="22" r="3.5" class="${tone === "success" ? "fill-success" : "fill-accent"}"/>
      <text x="${368 - 14 - (pill.length * 6.4 + 24) + 19}" y="26" font-size="11" font-weight="600" class="${tone === "success" ? "fill-success" : "fill-accent-strong"}">${esc(pill)}</text>
    </g>`;
  const navItem = (y: number, label: string, active = false) => `
    <g transform="translate(16 ${y})">
      ${active ? '<rect x="-6" y="-14" width="148" height="28" rx="7" class="fill-primary-soft"/>' : ""}
      <rect x="2" y="-5" width="10" height="10" rx="2.5" class="${active ? "fill-primary" : "fill-muted/50"}"/>
      <text x="22" y="4" font-size="12" font-weight="${active ? 600 : 400}" class="${active ? "fill-primary" : "fill-muted"}">${esc(label)}</text>
    </g>`;
  return `
<svg viewBox="0 0 580 380" class="h-auto w-full" role="img" aria-label="${esc(ctx.t.hero.illustrationCaption)}">
  <rect width="580" height="380" rx="14" class="fill-bg"/>
  <rect x="0.5" y="0.5" width="579" height="379" rx="13.5" fill="none" class="stroke-line"/>
  <rect x="0" y="0" width="172" height="380" rx="14" class="fill-surface"/>
  <rect x="171" y="0" width="1" height="380" class="fill-line"/>
  <g transform="translate(16 22)">
    <rect width="22" height="22" rx="5" fill="#1D4ED8"/>
    <rect x="30" y="7" width="70" height="8" rx="4" class="fill-fg/70"/>
  </g>
  ${navItem(78, l.overview, true)}
  ${navItem(112, l.servers)}
  ${navItem(146, l.apps)}
  ${navItem(180, l.deployments)}
  <g transform="translate(196 22)">
    <rect width="150" height="10" rx="5" class="fill-fg/80"/>
    <rect y="18" width="220" height="6" rx="3" class="fill-muted/40"/>
  </g>
  ${[0, 1, 2]
    .map(
      (i) => `
  <g transform="translate(${196 + i * 126} 62)">
    <rect width="116" height="70" rx="10" class="fill-surface stroke-line" stroke-width="1"/>
    <rect x="12" y="14" width="56" height="6" rx="3" class="fill-muted/50"/>
    <rect x="12" y="32" width="${[44, 30, 52][i]}" height="12" rx="4" class="fill-fg/75"/>
    <circle cx="98" cy="17" r="5" class="${i === 2 ? "fill-accent" : "fill-success"}"/>
    <rect x="12" y="52" width="80" height="5" rx="2.5" class="fill-muted/30"/>
  </g>`,
    )
    .join("")}
  <g transform="translate(196 146)">
    <rect width="368" height="96" rx="10" class="fill-surface stroke-line" stroke-width="1"/>
    <text x="14" y="22" font-size="11" font-weight="600" class="fill-muted">${esc(l.activity)}</text>
    <path d="M14 78 C 50 70, 70 46, 106 52 S 160 74, 196 58 S 252 30, 290 40 S 336 54, 354 36" fill="none" class="stroke-primary" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M14 78 C 50 70, 70 46, 106 52 S 160 74, 196 58 S 252 30, 290 40 S 336 54, 354 36 L 354 86 L 14 86 Z" class="fill-primary/10"/>
  </g>
  ${row(256, "api", l.healthy, "success")}
  ${row(308, "web", l.deploying, "accent")}
</svg>`;
}

export function Hero(ctx: Ctx): string {
  const { t } = ctx;
  return `
<section class="relative overflow-hidden" aria-labelledby="hero-title">
  <div class="hero-grid pointer-events-none absolute inset-0" aria-hidden="true"></div>
  <div class="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 sm:pt-20 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pb-24">
    <div>
      <p class="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted">
        <span class="size-1.5 rounded-full bg-accent" aria-hidden="true"></span>${esc(t.hero.eyebrow)}
      </p>
      <h1 id="hero-title" class="mt-5 text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-fg sm:text-5xl">${esc(t.hero.title)}</h1>
      <p class="mt-5 max-w-xl text-pretty text-base leading-relaxed text-muted sm:text-lg">${esc(t.hero.subtitle)}</p>
      <div class="mt-8 flex flex-col gap-3 sm:flex-row">
        <a href="${esc(ctx.site.repoUrl)}" target="_blank" rel="noopener noreferrer" class="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-fg shadow-sm transition-colors hover:bg-primary-hover">
          ${icon("github", "size-4")}${esc(t.hero.ctaPrimary)}<span class="sr-only"> ${esc(t.a11y.newTab)}</span>
        </a>
        <a href="#install" class="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-line bg-surface px-5 text-sm font-semibold text-fg transition-colors hover:bg-surface-2">
          ${icon("terminal", "size-4")}${esc(t.hero.ctaSecondary)}
        </a>
      </div>
    </div>
    <figure class="relative">
      <div class="rounded-2xl border border-line bg-surface p-2 shadow-[0_20px_60px_-30px_rgba(29,78,216,0.45)]">
        ${illustration(ctx)}
      </div>
      <figcaption class="mt-3 flex items-start gap-2 text-xs text-muted">
        <span class="mt-px shrink-0 rounded border border-line bg-surface px-1.5 py-0.5 font-semibold uppercase tracking-wide">${esc(t.hero.illustrationLabel)}</span>
        <span>${esc(t.hero.illustrationCaption)}</span>
      </figcaption>
    </figure>
  </div>
</section>`;
}
