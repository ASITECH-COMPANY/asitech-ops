/**
 * The only JavaScript shipped with the page: theme toggle, mobile menu and copy button.
 * Everything else is pre-rendered HTML and works without JavaScript.
 */
import "./styles.css";

const THEME_KEY = "asitech-landing-theme";

function storedTheme(): string | null {
  try {
    return window.localStorage.getItem(THEME_KEY);
  } catch {
    return null;
  }
}

function storeTheme(value: string): void {
  try {
    window.localStorage.setItem(THEME_KEY, value);
  } catch {
    /* storage unavailable: the choice lasts for this page view only */
  }
}

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * The OS preference is applied by CSS alone. A manual choice is stored and
 * expressed as an explicit .dark or .light class on <html>.
 */
function applyTheme(choice: string | null): void {
  const root = document.documentElement;
  root.classList.toggle("dark", choice === "dark");
  root.classList.toggle("light", choice === "light");
}

function setupTheme(): void {
  const root = document.documentElement;
  applyTheme(storedTheme());
  document.querySelector<HTMLButtonElement>("[data-theme-toggle]")?.addEventListener("click", () => {
    const isDark = root.classList.contains("dark") || (!root.classList.contains("light") && prefersDark());
    const next = isDark ? "light" : "dark";
    applyTheme(next);
    storeTheme(next);
  });
}

function setupMenu(): void {
  const toggle = document.querySelector<HTMLButtonElement>("[data-menu-toggle]");
  const menu = document.querySelector<HTMLElement>("[data-mobile-menu]");
  if (!toggle || !menu) return;
  const openIcon = toggle.querySelector("[data-menu-icon-open]");
  const closeIcon = toggle.querySelector("[data-menu-icon-close]");

  const setOpen = (open: boolean) => {
    menu.classList.toggle("hidden", !open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", (open ? toggle.dataset.labelClose : toggle.dataset.labelOpen) ?? "");
    openIcon?.classList.toggle("hidden", open);
    closeIcon?.classList.toggle("hidden", !open);
  };

  toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
  menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setOpen(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setOpen(false);
      toggle.focus();
    }
  });
}

function setupCopy(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-copy-target]").forEach((button) => {
    const source = document.getElementById(button.dataset.copyTarget ?? "");
    const label = button.querySelector("[data-copy-text]");
    if (!source || !label) return;
    if (!navigator.clipboard) {
      button.hidden = true;
      return;
    }
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(source.dataset.copySource ?? source.textContent ?? "");
        label.textContent = button.dataset.copiedLabel ?? "";
        window.setTimeout(() => (label.textContent = button.dataset.copyLabel ?? ""), 2000);
      } catch {
        /* clipboard permission denied: the code stays selectable */
      }
    });
  });
}

setupTheme();
setupMenu();
setupCopy();
