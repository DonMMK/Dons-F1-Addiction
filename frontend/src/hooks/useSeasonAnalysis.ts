import { useEffect, useState } from "react";
import { request } from "../api";
interface Job<T> {
  id: string;
  status: string;
  completed: number;
  total: number;
  data: T | null;
  error: string | null;
}
export function useSeasonAnalysis<T>(era: string) {
  const [data, setData] = useState<T | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [progress, setProgress] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setData(null);
    setError("");
    setLoading(true);
    setProgress("Queued");
    const update = (job: Job<T>) => {
      if (controller.signal.aborted) return;
      setProgress(`${job.completed} / ${job.total || "?"} rounds`);
      if (job.status === "complete") {
        setData(job.data);
        setLoading(false);
      } else if (job.status === "failed") {
        setError(job.error ?? "Analysis failed");
        setLoading(false);
      } else
        timer = setTimeout(() => {
          request<Job<T>>(`/best-car/season-jobs/status/${job.id}`, {
            signal: controller.signal,
          })
            .then(update)
            .catch(fail);
        }, 1500);
    };
    const fail = (e: unknown) => {
      if (!controller.signal.aborted) {
        setError(e instanceof Error ? e.message : "Analysis failed");
        setLoading(false);
      }
    };
    request<Job<T>>(`/best-car/season-jobs/${era}`, {
      method: "POST",
      signal: controller.signal,
    })
      .then(update)
      .catch(fail);
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [era]);
  return { data, loading, error, progress };
}
