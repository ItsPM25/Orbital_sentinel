"use client";

// Subscribes to GET /api/stream (SSE) with auto-reconnect. ARCHITECTURE.md section 7:
// events are "detection", "alert.created", "alert.updated", "ranking".
import { useEffect, useRef } from "react";

export interface StreamEvent {
  event: string;
  satelliteId: string;
  timestamp: string;
  [key: string]: unknown;
}

const RECONNECT_DELAY_MS = 2000;

export function useStream(onEvent: (event: StreamEvent) => void, enabled = true) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    function connect() {
      if (stopped) return;
      source = new EventSource("/api/stream");
      const events = ["detection", "alert.created", "alert.updated", "ranking"];
      for (const name of events) {
        source.addEventListener(name, (evt: MessageEvent) => {
          try {
            handlerRef.current(JSON.parse(evt.data));
          } catch {
            // malformed event: ignore rather than crash the page
          }
        });
      }
      source.onerror = () => {
        source?.close();
        if (!stopped) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();
    return () => {
      stopped = true;
      source?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [enabled]);
}
