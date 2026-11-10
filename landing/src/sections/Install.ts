import type { Ctx } from "../context.ts";
import { esc } from "../lib/html.ts";
import { icon } from "../lib/icons.ts";
import { section, sectionHeading } from "./common.ts";

export function installCommands(base: string): string[] {
  return [
    `curl -fsSL ${base}/install.sh -o install.sh`,
    `curl -fsSL ${base}/install.sh.sha256 -o install.sh.sha256`,
    "sha256sum -c install.sh.sha256",
    "sudo bash install.sh",
  ];
}

export function Install(ctx: Ctx): string {
  const i = ctx.t.install;
  const commands = installCommands(ctx.site.installBaseUrl);
  const code = commands
    .map((line) => `<span class="block"><span class="select-none text-slate-400" aria-hidden="true">$ </span>${esc(line)}</span>`)
    .join("");
  const notLive = ctx.site.installEndpointLive
    ? ""
    : `<div class="mt-4 flex gap-3 rounded-xl border border-accent/40 bg-accent-soft p-4 text-sm text-fg" role="note">
         <span class="mt-0.5 shrink-0 text-accent-strong">${icon("alert", "size-4")}</span>
         <div>
           <p>${esc(i.notLive)}</p>
           <a href="${esc(ctx.repo("docs/development/setup.md"))}" target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex items-center gap-1 font-semibold text-fg underline decoration-accent decoration-2 underline-offset-4">${esc(i.devGuide)}${icon("arrowRight", "size-4")}<span class="sr-only"> ${esc(ctx.t.a11y.newTab)}</span></a>
         </div>
       </div>`;
  return section(
    "install",
    `${sectionHeading("install", i.title, i.subtitle)}
     <div class="mt-10 max-w-3xl">
       <div class="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-lg">
         <div class="flex items-center justify-between border-b border-slate-800 px-4 py-2.5">
           <span class="flex items-center gap-2 text-xs font-medium text-slate-300">${icon("terminal", "size-4")}${esc(i.codeLabel)}</span>
           <button type="button" class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-800" data-copy-target="install-code" data-copy-label="${esc(i.copy)}" data-copied-label="${esc(i.copied)}">
             ${icon("copy", "size-3.5")}<span data-copy-text>${esc(i.copy)}</span>
           </button>
         </div>
         <pre class="overflow-x-auto px-4 py-4 text-[13px] leading-6 text-slate-100" tabindex="0" aria-label="${esc(i.codeLabel)}"><code id="install-code" data-copy-source="${esc(commands.join("\n"))}">${code}</code></pre>
       </div>
       ${notLive}
       <p class="mt-4 text-sm text-muted">${esc(i.requirements)}</p>
     </div>`,
  );
}
