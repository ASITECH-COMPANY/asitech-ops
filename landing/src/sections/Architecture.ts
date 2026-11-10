import type { Ctx } from "../context.ts";
import { esc } from "../lib/html.ts";
import { icon } from "../lib/icons.ts";
import { section, sectionHeading } from "./common.ts";

function controlPlane(x: number, y: number, w: number, a: Ctx["t"]["architecture"]): string {
  const items = a.controlPlaneItems
    .map(
      (item, i) => `
      <rect x="${x + 18}" y="${y + 58 + i * 38}" width="${w - 36}" height="28" rx="6" class="fill-surface-2"/>
      <text x="${x + 32}" y="${y + 77 + i * 38}" font-size="13" class="fill-fg">${esc(item)}</text>`,
    )
    .join("");
  return `
    <rect x="${x}" y="${y}" width="${w}" height="182" rx="14" class="fill-surface stroke-primary" stroke-width="2"/>
    <rect x="${x + 18}" y="${y + 18}" width="12" height="12" rx="3" fill="#1D4ED8"/>
    <text x="${x + 38}" y="${y + 29}" font-size="15" font-weight="600" class="fill-fg">${esc(a.controlPlane)}</text>
    ${items}`;
}

function server(x: number, y: number, w: number, index: number, a: Ctx["t"]["architecture"]): string {
  return `
    <rect x="${x}" y="${y}" width="${w}" height="74" rx="12" class="fill-surface stroke-line" stroke-width="1.5"/>
    <text x="${x + 16}" y="${y + 24}" font-size="13" font-weight="600" class="fill-fg">${esc(a.server)} ${String.fromCharCode(65 + index)}</text>
    <rect x="${x + 16}" y="${y + 36}" width="${w / 2 - 22}" height="24" rx="6" class="fill-accent-soft"/>
    <text x="${x + 26}" y="${y + 52}" font-size="12" font-weight="600" class="fill-accent-strong">${esc(a.agent)}</text>
    <rect x="${x + w / 2 + 6}" y="${y + 36}" width="${w / 2 - 22}" height="24" rx="6" class="fill-primary-soft"/>
    <text x="${x + w / 2 + 16}" y="${y + 52}" font-size="12" font-weight="600" class="fill-primary">${esc(a.docker)}</text>`;
}

/** Horizontal layout for wide screens. Arrows point from agents to the Control Plane (outbound). */
function wideDiagram(a: Ctx["t"]["architecture"]): string {
  const servers = [0, 1, 2].map((i) => server(560, 18 + i * 100, 220, i, a)).join("");
  const arrows = [0, 1, 2]
    .map((i) => {
      const y = 55 + i * 100;
      return `<path d="M556 ${y} C 470 ${y}, 420 ${180}, 304 ${180}" fill="none" class="stroke-muted" stroke-width="1.8" stroke-dasharray="6 5" marker-end="url(#arrow-wide)"/>`;
    })
    .join("");
  return `
<svg viewBox="0 0 800 340" class="hidden h-auto w-full md:block" role="img" aria-labelledby="arch-wide-title arch-wide-desc">
  <title id="arch-wide-title">${esc(a.diagramTitle)}</title>
  <desc id="arch-wide-desc">${esc(a.diagramDesc)}</desc>
  <defs>
    <marker id="arrow-wide" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" class="fill-muted"/>
    </marker>
  </defs>
  ${controlPlane(20, 89, 280, a)}
  ${arrows}
  <rect x="368" y="160" width="128" height="26" rx="13" class="fill-bg stroke-line"/>
  ${lockGlyph(380, 166)}
  <text x="400" y="178" font-size="12" font-weight="600" class="fill-fg">${esc(a.link)}</text>
  ${servers}
</svg>`;
}

/** Stacked layout for phones, so labels stay readable. */
function narrowDiagram(a: Ctx["t"]["architecture"]): string {
  const servers = [0, 1].map((i) => server(16 + i * 168, 300, 152, i, a)).join("");
  return `
<svg viewBox="0 0 352 390" class="h-auto w-full md:hidden" role="img" aria-labelledby="arch-narrow-title arch-narrow-desc">
  <title id="arch-narrow-title">${esc(a.diagramTitle)}</title>
  <desc id="arch-narrow-desc">${esc(a.diagramDesc)}</desc>
  <defs>
    <marker id="arrow-narrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" class="fill-muted"/>
    </marker>
  </defs>
  ${controlPlane(16, 10, 320, a)}
  <path d="M92 296 L 120 198" fill="none" class="stroke-muted" stroke-width="1.8" stroke-dasharray="6 5" marker-end="url(#arrow-narrow)"/>
  <path d="M260 296 L 232 198" fill="none" class="stroke-muted" stroke-width="1.8" stroke-dasharray="6 5" marker-end="url(#arrow-narrow)"/>
  <rect x="112" y="232" width="128" height="26" rx="13" class="fill-bg stroke-line"/>
  ${lockGlyph(124, 238)}
  <text x="144" y="250" font-size="12" font-weight="600" class="fill-fg">${esc(a.link)}</text>
  ${servers}
</svg>`;
}

function lockGlyph(x: number, y: number): string {
  return `<g transform="translate(${x} ${y})" class="stroke-success" fill="none" stroke-width="1.6" stroke-linecap="round"><rect x="0.5" y="6" width="12" height="8" rx="2"/><path d="M3 6V4a3.5 3.5 0 0 1 7 0v2"/></g>`;
}

export function Architecture(ctx: Ctx): string {
  const a = ctx.t.architecture;
  const notes = a.notes
    .map(
      (note) =>
        `<li class="flex gap-3 text-sm leading-relaxed text-muted"><span class="mt-0.5 shrink-0 text-success">${icon("check", "size-4")}</span><span>${esc(note)}</span></li>`,
    )
    .join("");
  return section(
    "architecture",
    `${sectionHeading("architecture", a.title, a.subtitle)}
     <div class="mt-12 grid items-center gap-10 lg:grid-cols-[1.6fr_1fr]">
       <div class="rounded-2xl border border-line bg-surface-2/60 p-4 sm:p-6">${wideDiagram(a)}${narrowDiagram(a)}</div>
       <ul class="space-y-4">${notes}</ul>
     </div>`,
  );
}
