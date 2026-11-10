#!/usr/bin/env node
// Post-build checks for the static site. Fails the build on any problem.
// Usage: node scripts/check-dist.mjs   (after `npm run build`)
import { readFileSync, readdirSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join, relative } from "node:path";

const DIST = new URL("../dist/", import.meta.url).pathname;
const MAX_INITIAL_KB = 300;
const errors = [];
const fail = (message) => errors.push(message);

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const files = walk(DIST);
const read = (path) => readFileSync(join(DIST, path), "utf8");

const pages = { fr: "index.html", en: "en/index.html" };
for (const [lang, page] of Object.entries(pages)) {
  const html = read(page);
  if (!html.includes(`<html lang="${lang}"`)) fail(`${page}: <html lang="${lang}"> missing`);
  for (const hreflang of ["fr", "en", "x-default"]) {
    if (!html.includes(`hreflang="${hreflang}"`)) fail(`${page}: hreflang="${hreflang}" missing`);
  }
  for (const needle of ['rel="canonical"', 'property="og:image"', 'name="twitter:card"', "application/ld+json", '<meta name="description"']) {
    if (!html.includes(needle)) fail(`${page}: ${needle} missing`);
  }
  if (/lorem ipsum/i.test(html)) fail(`${page}: placeholder text (lorem ipsum) found`);
  if (html.includes("<!--prerender:")) fail(`${page}: pre-render placeholder not replaced`);
  // Nothing may block the first render: the only script must be the deferred module.
  for (const match of html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/g)) {
    if (!/type="module"/.test(match[0])) fail(`${page}: render-blocking script ${match[1]}`);
  }
  if (/\sstyle="/.test(html)) fail(`${page}: inline style attribute (blocked by the CSP)`);
  if (/<script(?![^>]*\bsrc=)(?![^>]*application\/ld\+json)[^>]*>/.test(html)) fail(`${page}: inline script (blocked by the CSP)`);

  // Every external link must open safely.
  for (const match of html.matchAll(/<a\s[^>]*href="(https?:[^"]+)"[^>]*>/g)) {
    const tag = match[0];
    if (!/rel="[^"]*noopener[^"]*noreferrer[^"]*"/.test(tag)) fail(`${page}: external link without rel="noopener noreferrer": ${match[1]}`);
  }
  // Every in-page anchor must have a target.
  const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
  for (const match of html.matchAll(/href="#([^"]*)"/g)) {
    if (match[1] && !ids.has(match[1])) fail(`${page}: anchor #${match[1]} has no target`);
  }
  // Every image needs an alt attribute.
  for (const match of html.matchAll(/<img\s[^>]*>/g)) {
    if (!/\salt="/.test(match[0])) fail(`${page}: <img> without alt`);
  }

  // Initial weight: the HTML plus the CSS/JS it references, gzipped as served.
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+\.(?:js|css))"/g)].map((m) => m[1].slice(1));
  const bytes = [page, ...assets].reduce((sum, path) => sum + gzipSync(readFileSync(join(DIST, path))).length, 0);
  const kb = bytes / 1024;
  console.log(`${page}: initial transfer ≈ ${kb.toFixed(1)} KB gzipped (${assets.length} assets)`);
  if (kb > MAX_INITIAL_KB) fail(`${page}: initial weight ${kb.toFixed(1)} KB exceeds ${MAX_INITIAL_KB} KB`);
}

for (const required of ["404.html", "robots.txt", "sitemap.xml", "og-image.png", "favicon.svg"]) {
  if (!files.some((file) => relative(DIST, file) === required)) fail(`dist/${required} missing`);
}

if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("All landing checks passed.");
