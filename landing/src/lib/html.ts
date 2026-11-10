const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape text for HTML content and attribute values. All dictionary text goes through this. */
export function esc(value: string | number): string {
  return String(value).replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

/** Replace {name} placeholders with already-escaped HTML fragments. */
export function fill(template: string, params: Record<string, string>): string {
  return esc(template).replace(/\{(\w+)\}/g, (match, name: string) => params[name] ?? match);
}

/** External link: always opened safely, with an accessible hint. */
export function extLink(href: string, label: string, className = "", newTabHint = ""): string {
  const hint = newTabHint ? `<span class="sr-only"> ${esc(newTabHint)}</span>` : "";
  return `<a href="${esc(href)}" class="${className}" target="_blank" rel="noopener noreferrer">${label}${hint}</a>`;
}
