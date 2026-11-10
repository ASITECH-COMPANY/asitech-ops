/**
 * Build-time renderer: produces the full, static HTML of each language version.
 * Runs in Node (via the Vite plugin in vite.config.ts), never in the browser.
 */
import { dictionaries, makeContext, PATHS, type Ctx, type Lang } from "./context.ts";
import { esc } from "./lib/html.ts";
import { Architecture } from "./sections/Architecture.ts";
import { FAQ } from "./sections/FAQ.ts";
import { Features } from "./sections/Features.ts";
import { Footer } from "./sections/Footer.ts";
import { Header, logo } from "./sections/Header.ts";
import { Hero } from "./sections/Hero.ts";
import { HowItWorks } from "./sections/HowItWorks.ts";
import { Install } from "./sections/Install.ts";
import { OpenSource } from "./sections/OpenSource.ts";
import { Roadmap } from "./sections/Roadmap.ts";
import { Security } from "./sections/Security.ts";
import { StatusBanner } from "./sections/StatusBanner.ts";

const OG_LOCALE: Record<Lang, string> = { fr: "fr_FR", en: "en_US" };

function absolute(ctx: Ctx, path: string): string {
  return `${ctx.site.siteUrl}${path}`;
}

function jsonLd(ctx: Ctx): string {
  const data = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "ASITECH OPS",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Linux",
    description: ctx.t.meta.description,
    url: absolute(ctx, ctx.path),
    inLanguage: ctx.lang,
    license: "https://www.apache.org/licenses/LICENSE-2.0",
    isAccessibleForFree: true,
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    sameAs: [ctx.site.repoUrl],
    author: { "@type": "Organization", name: "ASITECH SOLUTION", url: ctx.site.companyUrl },
    publisher: { "@type": "Organization", name: "ASITECH SOLUTION", url: ctx.site.companyUrl },
  };
  // "<" is escaped so the JSON can never close the script element.
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

export function renderHead(lang: Lang): string {
  const ctx = makeContext(lang);
  const { meta } = ctx.t;
  const url = absolute(ctx, ctx.path);
  const image = absolute(ctx, "/og-image.png");
  return `
    <title>${esc(meta.title)}</title>
    <meta name="description" content="${esc(meta.description)}" />
    <link rel="canonical" href="${url}" />
    <link rel="alternate" hreflang="fr" href="${absolute(ctx, PATHS.fr)}" />
    <link rel="alternate" hreflang="en" href="${absolute(ctx, PATHS.en)}" />
    <link rel="alternate" hreflang="x-default" href="${absolute(ctx, PATHS.fr)}" />
    <meta name="theme-color" content="#f7f8fa" media="(prefers-color-scheme: light)" />
    <meta name="theme-color" content="#0b0f17" media="(prefers-color-scheme: dark)" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="ASITECH OPS" />
    <meta property="og:title" content="${esc(meta.title)}" />
    <meta property="og:description" content="${esc(meta.description)}" />
    <meta property="og:url" content="${url}" />
    <meta property="og:locale" content="${OG_LOCALE[lang]}" />
    <meta property="og:locale:alternate" content="${OG_LOCALE[ctx.altLang]}" />
    <meta property="og:image" content="${image}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="${esc(meta.ogAlt)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${esc(meta.title)}" />
    <meta name="twitter:description" content="${esc(meta.description)}" />
    <meta name="twitter:image" content="${image}" />
    <script type="application/ld+json">${jsonLd(ctx)}</script>`;
}

export function renderBody(lang: Lang): string {
  const ctx = makeContext(lang);
  return [
    Header(ctx),
    `<main id="main" tabindex="-1">`,
    Hero(ctx),
    StatusBanner(ctx),
    Features(ctx),
    HowItWorks(ctx),
    Architecture(ctx),
    Security(ctx),
    Install(ctx),
    OpenSource(ctx),
    Roadmap(ctx),
    FAQ(ctx),
    `</main>`,
    Footer(ctx),
  ].join("\n");
}

/** Bilingual 404 page (served by Nginx for unknown paths). */
export function renderNotFoundHead(): string {
  return `<title>404 — ASITECH OPS</title>\n    <meta name="robots" content="noindex" />`;
}

export function renderNotFoundBody(): string {
  const block = (lang: Lang) => {
    const t = dictionaries[lang].notFound;
    return `<div lang="${lang}"><h${lang === "fr" ? 1 : 2} class="text-2xl font-semibold text-fg">${esc(t.title)}</h${lang === "fr" ? 1 : 2}>
      <p class="mt-2 text-muted">${esc(t.text)}</p>
      <a class="mt-4 inline-block font-semibold text-primary hover:underline" href="${PATHS[lang]}">${esc(t.home)}</a></div>`;
  };
  return `<main class="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-10 px-4 py-16 sm:px-6">
    <a href="/" class="inline-flex items-center gap-2.5" aria-label="ASITECH OPS">${logo()}<span class="text-[15px] font-semibold text-fg">ASITECH <span class="text-primary">OPS</span></span></a>
    ${block("fr")}
    ${block("en")}
  </main>`;
}
