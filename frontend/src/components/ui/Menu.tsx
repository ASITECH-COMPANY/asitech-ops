import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { cn } from "./cn";

/** Small accessible disclosure menu: closes on outside click, Escape and selection. */
export function Menu({
  label,
  trigger,
  children,
  align = "end",
  triggerClassName,
}: {
  label: string;
  trigger: ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "start" | "end";
  triggerClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-fg hover:bg-surface-2",
          triggerClassName,
        )}
      >
        {trigger}
      </button>
      {open ? (
        <div
          id={menuId}
          className={cn(
            "absolute z-40 mt-1 min-w-56 overflow-hidden rounded-xl border border-line bg-surface p-1 shadow-lg",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          {children(() => setOpen(false))}
        </div>
      ) : null}
    </div>
  );
}

export function MenuItem({
  onSelect,
  icon,
  children,
  active = false,
}: {
  onSelect: () => void;
  icon?: ReactNode;
  children: ReactNode;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active || undefined}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-surface-2",
        active ? "font-medium text-primary" : "text-fg",
      )}
    >
      {icon ? <span className="text-muted">{icon}</span> : null}
      <span className="min-w-0 flex-1 truncate">{children}</span>
    </button>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <div className="px-2.5 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-muted">{children}</div>;
}

export function MenuDivider() {
  return <div className="my-1 h-px bg-line" />;
}
