import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

import type { Language } from "../lib/types";

export type ThemePreference = "light" | "dark" | "system";

// Storage can be unavailable (private mode, blocked site data): never let it crash the app.
const safeStorage: StateStorage = {
  getItem: (name) => {
    try {
      return window.localStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name, value) => {
    try {
      window.localStorage.setItem(name, value);
    } catch {
      /* ignore */
    }
  },
  removeItem: (name) => {
    try {
      window.localStorage.removeItem(name);
    } catch {
      /* ignore */
    }
  },
};

export function detectLanguage(): Language {
  const languages = typeof navigator === "undefined" ? [] : (navigator.languages ?? [navigator.language]);
  return languages.some((lang) => lang?.toLowerCase().startsWith("fr")) ? "fr" : "en";
}

interface PreferencesState {
  theme: ThemePreference;
  language: Language;
  /** Last organization opened, so "/" can return to it. */
  lastOrg: string | null;
  setTheme: (theme: ThemePreference) => void;
  setLanguage: (language: Language) => void;
  setLastOrg: (slug: string | null) => void;
}

export const usePreferences = create<PreferencesState>()(
  persist(
    (set) => ({
      theme: "system",
      language: detectLanguage(),
      lastOrg: null,
      setTheme: (theme) => set({ theme }),
      setLanguage: (language) => set({ language }),
      setLastOrg: (lastOrg) => set({ lastOrg }),
    }),
    {
      name: "asitech-ops:preferences",
      storage: createJSONStorage(() => safeStorage),
      partialize: ({ theme, language, lastOrg }) => ({ theme, language, lastOrg }),
    },
  ),
);

export function resolveTheme(theme: ThemePreference): "light" | "dark" {
  if (theme !== "system") return theme;
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}
