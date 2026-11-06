import { useEffect, useState } from "react";
import { request } from "../api";

/** Abort obsolete requests, clear stale results, and expose every failure. */
export function useApi<T>(path: string | null, refresh = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setLoading(Boolean(path));
    if (!path) return () => controller.abort();
    request<T>(path, { signal: controller.signal })
      .then(setData)
      .catch((e: unknown) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Unable to load data");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, refresh]);
  return { data, error, loading };
}
