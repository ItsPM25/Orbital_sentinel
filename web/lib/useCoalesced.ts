"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Returns a trigger that runs `fn` at most once per `ms`; triggers that arrive in
 * between collapse into a single trailing run. Live SSE events can arrive several
 * per second while a replay runs, and refetching on each one flooded the API and
 * re-rendered the page (and its charts) on every event.
 */
export function useCoalesced(fn: () => void, ms = 1000) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastRun = useRef(0);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return useCallback(() => {
    if (timer.current) return; // a run is already scheduled; this trigger joins it
    const wait = Math.max(0, lastRun.current + ms - Date.now());
    timer.current = setTimeout(() => {
      timer.current = null;
      lastRun.current = Date.now();
      fnRef.current();
    }, wait);
  }, [ms]);
}
