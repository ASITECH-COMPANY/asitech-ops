import { useState } from "react";

import { useOperation } from "../../hooks/queries";
import { ApiError } from "../../lib/api";
import type { OperationName } from "../../lib/types";

export interface PendingAction {
  op: OperationName;
  target: string;
  label: string;
}

/** One confirmation flow for every mutating Docker action of a server. */
export function useServerOps(slug: string, serverId: string) {
  const operation = useOperation(slug, serverId);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  return {
    pending,
    notice,
    error: operation.error instanceof ApiError ? operation.error.displayMessage : operation.error ? String(operation.error) : null,
    loading: operation.isPending,
    ask: (action: PendingAction) => {
      operation.reset();
      setNotice(null);
      setPending(action);
    },
    cancel: () => {
      setPending(null);
      operation.reset();
    },
    confirm: (doneText: string) => {
      if (!pending) return;
      operation.mutate(
        { op: pending.op, target: pending.target },
        {
          onSuccess: () => {
            setPending(null);
            setNotice(doneText);
          },
        },
      );
    },
  };
}
