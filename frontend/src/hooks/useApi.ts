import { useEffect, useState } from "react";
import { ApiError, request } from "../api";

/** Abort obsolete requests, clear stale results, and expose every failure. */
export function useApi<T>(path: string | null, refresh = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setApiError(null);
    setLoading(Boolean(path));
    if (!path) return () => controller.abort();
    request<T>(path, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Unable to load data");
          setApiError(e instanceof ApiError ? e : null);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, refresh, attempt]);
  return { data, error, apiError, loading, retry: () => setAttempt((v) => v + 1) };
}
