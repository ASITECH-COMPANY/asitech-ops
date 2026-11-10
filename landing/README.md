# asitechsolution.cloud — ASITECH OPS public website

Static, bilingual (French at `/`, English at `/en/`) landing page for ASITECH OPS.
Apache-2.0, like the rest of the repository.

* **No framework runtime.** Pages are pre-rendered at build time by a small Vite
  plugin (`vite.config.ts` → `src/render.ts` → `src/sections/*.ts`). The only
  JavaScript shipped is the deferred `src/main.ts` (theme toggle, mobile menu,
  copy button). Dark mode follows the OS in pure CSS; nothing blocks rendering.
* **Content is data:** text in `src/i18n/fr.json` / `en.json`, project status
  and links in `src/data/site.json`, roadmap in `src/data/roadmap.json`.
* **No tracking, no cookies, no third-party requests.** System font stack, inline
  SVG icons (Lucide, rendered at build time). If analytics are ever added, use a
  cookie-less, privacy-friendly tool and document it here.
* **Security:** strict same-origin CSP (no inline scripts or styles), served by
  `nginxinc/nginx-unprivileged` in a read-only container with all capabilities
  dropped, bound to `127.0.0.1`.

## Commands

```bash
npm ci
npm run dev          # http://localhost:5173 and http://localhost:5173/en/
npm run build        # type check + static build into dist/
npm run check        # HTML validation, hreflang/SEO tags, links, CSP, weight budget (< 300 KB)
npm run preview      # serve dist/ on http://localhost:4173
npm run og-image     # regenerate og-image.png and PNG/ICO icons (needs Chrome)
```

Container:

```bash
docker build -t asitech-landing:dev .
docker run --rm -p 127.0.0.1:8088:8080 --read-only --tmpfs /tmp --tmpfs /var/cache/nginx:uid=101,gid=101 asitech-landing:dev
curl http://127.0.0.1:8088/healthz
```

Deployment on the ASITECH server: [docs/landing/deployment.md](../docs/landing/deployment.md).

## Editing rules

* Keep `fr.json` and `en.json` in sync (same keys).
* No invented metrics, testimonials, logos or star counts.
* Before going public, confirm `repoUrl`, `contactEmail` and `securityEmail` in
  `src/data/site.json`. Set `installEndpointLive` to `true` only when
  `get.asitechsolution.cloud` actually serves signed release artifacts.
