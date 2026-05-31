import { useEffect, useRef } from "react";

export function usePolling(fn, intervalMs = 2000, enabled = true) {
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; }, [fn]);
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      try { await fnRef.current(); } catch (_) { /* ignore */ }
      if (!stopped) setTimeout(tick, intervalMs);
    };
    tick();
    return () => { stopped = true; };
  }, [intervalMs, enabled]);
}
