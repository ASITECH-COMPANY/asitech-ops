import { describe, expect, it } from "vitest";

import { dictionaries, translate } from "../src/i18n";
import { en } from "../src/i18n/en";

describe("i18n", () => {
  it("French defines exactly the same keys as English", () => {
    expect(Object.keys(dictionaries.fr).sort()).toEqual(Object.keys(en).sort());
  });

  it("keeps the same placeholders in every language", () => {
    const placeholders = (value: string) => (value.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(placeholders(dictionaries.fr[key]), key).toEqual(placeholders(en[key]));
    }
  });

  it("interpolates parameters and leaves unknown placeholders intact", () => {
    expect(translate("en", "common.pageOf", { page: 2, pages: 5 })).toBe("Page 2 of 5");
    expect(translate("fr", "common.pageOf", { page: 2 })).toBe("Page 2 sur {pages}");
  });

  it("has no empty translations", () => {
    for (const [key, value] of Object.entries(dictionaries.fr)) expect(value.trim(), key).not.toBe("");
  });
});
