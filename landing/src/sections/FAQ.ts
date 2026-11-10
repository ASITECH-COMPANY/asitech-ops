import type { Ctx } from "../context.ts";
import { esc, fill } from "../lib/html.ts";
import { section, sectionHeading } from "./common.ts";

export function FAQ(ctx: Ctx): string {
  const f = ctx.t.faq;
  const email = esc(ctx.site.securityEmail);
  const items = f.items
    .map(
      (item) => `
      <details class="group rounded-xl border border-line bg-surface px-5 py-4 open:bg-surface">
        <summary class="flex cursor-pointer list-none items-center justify-between gap-4 text-left text-sm font-semibold text-fg">
          ${esc(item.q)}
          <span class="text-muted transition-transform group-open:rotate-45" aria-hidden="true">+</span>
        </summary>
        <p class="mt-3 text-sm leading-relaxed text-muted">${fill(item.a, { securityEmail: `<a class="font-medium text-fg underline underline-offset-4" href="mailto:${email}">${email}</a>` })}</p>
      </details>`,
    )
    .join("");
  return section(
    "faq",
    `${sectionHeading("faq", f.title)}
     <div class="mt-10 grid gap-3 lg:grid-cols-2 lg:items-start">${items}</div>`,
    "border-t border-line bg-surface-2/60",
  );
}
