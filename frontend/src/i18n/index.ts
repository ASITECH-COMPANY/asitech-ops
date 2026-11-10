import { useCallback } from "react";

import type { Language } from "../lib/types";
import { usePreferences } from "../stores/preferences";
import { en, type MessageKey } from "./en";
import { fr } from "./fr";

export type { MessageKey };

export const dictionaries: Record<Language, Record<MessageKey, string>> = { en, fr };

export type TranslateParams = Record<string, string | number>;

export function translate(language: Language, key: MessageKey, params?: TranslateParams): string {
  const template = dictionaries[language][key] ?? en[key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

export function useT() {
  const language = usePreferences((state) => state.language);
  return useCallback(
    (key: MessageKey, params?: TranslateParams) => translate(language, key, params),
    [language],
  );
}

export function useLanguage(): Language {
  return usePreferences((state) => state.language);
}

/** Translate an audit action, falling back to the raw identifier for unknown ones. */
export function actionKey(action: string): MessageKey | null {
  const key = `action.${action}` as MessageKey;
  return key in en ? key : null;
}
