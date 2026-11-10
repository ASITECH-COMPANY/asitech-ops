import { esc } from "../lib/html";

export function sectionHeading(id: string, title: string, subtitle?: string, eyebrow?: string): string {
  return `
    <div class="max-w-2xl">
      ${eyebrow ? `<p class="text-sm font-semibold text-primary">${esc(eyebrow)}</p>` : ""}
      <h2 id="${id}-title" class="mt-2 text-balance text-3xl font-semibold tracking-tight text-fg sm:text-4xl">${esc(title)}</h2>
      ${subtitle ? `<p class="mt-4 text-pretty text-base leading-relaxed text-muted">${esc(subtitle)}</p>` : ""}
    </div>`;
}

export function section(id: string, inner: string, className = ""): string {
  return `<section id="${id}" aria-labelledby="${id}-title" class="scroll-mt-20 ${className}"><div class="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">${inner}</div></section>`;
}
