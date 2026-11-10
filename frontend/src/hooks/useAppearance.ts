import { useEffect } from "react";

import { resolveTheme, usePreferences } from "../stores/preferences";

/** Applies the theme class and the document language; follows OS theme changes in "system" mode. */
export function useAppearance() {
  const theme = usePreferences((s) => s.theme);
  const language = usePreferences((s) => s.language);

  useEffect(() => {
    const apply = () => document.documentElement.classList.toggle("dark", resolveTheme(theme) === "dark");
    apply();
    if (theme !== "system" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
}
