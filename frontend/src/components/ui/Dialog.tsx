import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { useT } from "../../i18n";
import { Button } from "./Button";
import { Alert, TextField } from "./Field";

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  const t = useT();
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  // Keep the latest callback without re-running the focus effect on every render.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const focusables = () => Array.from(panel?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    (focusables().find((el) => el.dataset.autofocus !== undefined) ?? focusables()[0] ?? panel)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      } else if (event.key === "Tab") {
        const items = focusables();
        if (items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <div className="absolute inset-0 bg-black/50" aria-hidden onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className="relative w-full max-w-md rounded-xl border border-line bg-surface shadow-xl"
      >
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-fg">
              {title}
            </h2>
            {description ? (
              <div id={descriptionId} className="mt-1 text-sm text-muted">
                {description}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg"
            aria-label={t("common.close")}
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        {children ? <div className="px-5 pt-4">{children}</div> : null}
        <div className="flex flex-wrap justify-end gap-2 px-5 pb-5 pt-5">{footer}</div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * Confirmation for destructive actions. With `confirmText`, the user must type
 * that value (e.g. the organization identifier) before confirming.
 */
interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  confirmText?: string;
  loading?: boolean;
  error?: string | null;
}

export function ConfirmDialog(props: ConfirmDialogProps) {
  // Mount the body only while open so the typed confirmation resets every time.
  return props.open ? <ConfirmDialogBody {...props} /> : null;
}

function ConfirmDialogBody({
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel,
  confirmText,
  loading = false,
  error,
}: ConfirmDialogProps) {
  const t = useT();
  const [typed, setTyped] = useState("");
  const blocked = confirmText !== undefined && typed !== confirmText;

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={blocked} loading={loading} data-autofocus>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {confirmText !== undefined || error ? (
        <div className="space-y-3">
          {confirmText !== undefined ? (
            <TextField
              label={t("common.confirm")}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder={confirmText}
            />
          ) : null}
          {error ? <Alert>{error}</Alert> : null}
        </div>
      ) : null}
    </Modal>
  );
}
