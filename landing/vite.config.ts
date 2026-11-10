import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";
import { defineConfig, type Plugin, type ViteDevServer } from "vite";

import * as staticRender from "./src/render.ts";

type Renderer = typeof staticRender;

/**
 * Pre-renders every page at build time (and on each request in dev), so the
 * shipped HTML is complete: fast, indexable, and usable without JavaScript.
 */
function prerender(): Plugin {
  let server: ViteDevServer | undefined;
  return {
    name: "asitech-prerender",
    configureServer(devServer) {
      server = devServer;
    },
    transformIndexHtml: {
      order: "pre",
      async handler(html, ctx) {
        const render: Renderer = server ? ((await server.ssrLoadModule("/src/render.ts")) as Renderer) : staticRender;
        const page = ctx.path.replace(/^\//, "");
        let head: string;
        let body: string;
        if (page === "404.html") {
          head = render.renderNotFoundHead();
          body = render.renderNotFoundBody();
        } else {
          const lang = page.startsWith("en/") ? "en" : "fr";
          head = render.renderHead(lang);
          body = render.renderBody(lang);
        }
        return html.replace("<!--prerender:head-->", head).replace("<!--prerender:body-->", body);
      },
    },
  };
}

export default defineConfig({
  plugins: [tailwindcss(), prerender()],
  build: {
    modulePreload: { polyfill: false },
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        en: resolve(import.meta.dirname, "en/index.html"),
        notFound: resolve(import.meta.dirname, "404.html"),
      },
    },
  },
});
