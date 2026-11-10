import { useEffect } from "react";

export function useDocumentTitle(...parts: (string | undefined)[]) {
  const title = [...parts.filter(Boolean), "ASITECH OPS"].join(" · ");
  useEffect(() => {
    document.title = title;
  }, [title]);
}
