import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { keys } from "./queries";

export type LiveStatus = "connecting" | "live" | "offline";

const CLOSE_FORBIDDEN = 4403;
const CLOSE_UNAUTHORIZED = 4401;
const PING_INTERVAL_MS = 25_000;

interface ServerEvent {
  type: "hello" | "event" | "pong";
  action?: string;
  resource?: "organization" | "members" | "invitations";
}

/**
 * Subscribes to the organization event stream and refreshes affected queries.
 * Events only say what changed; data is always refetched through the REST API.
 */
export function useOrgEvents(slug: string): LiveStatus {
  const qc = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry = 0;
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const connect = () => {
      setStatus("connecting");
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws/v1/organizations/${slug}/events/`);

      socket.onopen = () => {
        retry = 0;
        setStatus("live");
        pingTimer = setInterval(() => socket?.send(JSON.stringify({ type: "ping" })), PING_INTERVAL_MS);
      };

      socket.onmessage = (message) => {
        let event: ServerEvent;
        try {
          event = JSON.parse(String(message.data)) as ServerEvent;
        } catch {
          return;
        }
        if (event.type !== "event") return;
        qc.invalidateQueries({ queryKey: keys.dashboard(slug) });
        qc.invalidateQueries({ queryKey: keys.audit(slug) });
        if (event.resource === "members") {
          qc.invalidateQueries({ queryKey: keys.members(slug) });
          qc.invalidateQueries({ queryKey: keys.organization(slug) });
          qc.invalidateQueries({ queryKey: keys.organizations });
          qc.invalidateQueries({ queryKey: keys.invitations(slug) });
        } else if (event.resource === "invitations") {
          qc.invalidateQueries({ queryKey: keys.invitations(slug) });
        } else {
          qc.invalidateQueries({ queryKey: keys.organization(slug) });
          qc.invalidateQueries({ queryKey: keys.organizations });
        }
      };

      socket.onclose = (event) => {
        clearInterval(pingTimer);
        setStatus("offline");
        if (stopped) return;
        if (event.code === CLOSE_FORBIDDEN || event.code === CLOSE_UNAUTHORIZED) {
          // Access was revoked or the session ended: let the REST layer decide where to go.
          qc.invalidateQueries({ queryKey: keys.organization(slug) });
          qc.invalidateQueries({ queryKey: keys.organizations });
          qc.invalidateQueries({ queryKey: keys.me });
          return;
        }
        const delay = Math.min(30_000, 1_000 * 2 ** retry) + Math.random() * 500;
        retry += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      clearInterval(pingTimer);
      socket?.close();
    };
  }, [qc, slug]);

  return status;
}
