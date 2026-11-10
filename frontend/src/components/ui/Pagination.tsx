import { useT } from "../../i18n";
import { Button } from "./Button";

export function Pagination({
  page,
  count,
  pageSize = 25,
  onPage,
}: {
  page: number;
  count: number;
  pageSize?: number;
  onPage: (page: number) => void;
}) {
  const t = useT();
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;
  return (
    <nav className="flex items-center justify-between gap-3 border-t border-line px-5 py-3" aria-label="Pagination">
      <span className="text-sm text-muted">{t("common.pageOf", { page, pages })}</span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          {t("common.previous")}
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {t("common.next")}
        </Button>
      </div>
    </nav>
  );
}
