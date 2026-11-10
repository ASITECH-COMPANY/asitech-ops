import type { Ctx } from "../context";
import { esc } from "../lib/html";
import { icon, type IconName } from "../lib/icons";
import { section, sectionHeading } from "./common";

const ORDER: [keyof Ctx["t"]["features"]["items"], IconName][] = [
  ["multiServer", "server"],
  ["git", "gitBranch"],
  ["docker", "container"],
  ["logs", "scrollText"],
  ["monitoring", "activity"],
  ["domains", "globe"],
  ["rollback", "rotateCcw"],
  ["teams", "users"],
];

export function Features(ctx: Ctx): string {
  const f = ctx.t.features;
  const cards = ORDER.map(([key, iconName]) => {
    const item = f.items[key];
    return `
      <li class="rounded-xl border border-line bg-surface p-5 transition-colors hover:border-primary/40">
        <span class="inline-flex size-10 items-center justify-center rounded-lg bg-primary-soft text-primary">${icon(iconName, "size-5")}</span>
        <h3 class="mt-4 text-base font-semibold text-fg">${esc(item.title)}</h3>
        <p class="mt-1.5 text-sm leading-relaxed text-muted">${esc(item.text)}</p>
      </li>`;
  }).join("");
  return section(
    "features",
    `${sectionHeading("features", f.title, f.subtitle)}
     <ul class="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">${cards}</ul>`,
  );
}
