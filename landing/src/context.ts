import en from "./i18n/en.json" with { type: "json" };
import fr from "./i18n/fr.json" with { type: "json" };
import roadmap from "./data/roadmap.json" with { type: "json" };
import site from "./data/site.json" with { type: "json" };

export type Lang = "fr" | "en";
export type Dict = typeof fr;
export type Site = typeof site;
export type Roadmap = typeof roadmap;

export const dictionaries: Record<Lang, Dict> = { fr, en: en as Dict };

export interface Ctx {
  lang: Lang;
  t: Dict;
  site: Site;
  roadmap: Roadmap;
  /** Path of this page and of its translation. */
  path: string;
  altLang: Lang;
  altPath: string;
  /** Helpers for repository links. */
  repo: (path?: string) => string;
}

export const PATHS: Record<Lang, string> = { fr: "/", en: "/en/" };

export function makeContext(lang: Lang): Ctx {
  const altLang: Lang = lang === "fr" ? "en" : "fr";
  return {
    lang,
    t: dictionaries[lang],
    site,
    roadmap,
    path: PATHS[lang],
    altLang,
    altPath: PATHS[altLang],
    repo: (path = "") => (path ? `${site.repoUrl}/blob/${site.defaultBranch}/${path}` : site.repoUrl),
  };
}
