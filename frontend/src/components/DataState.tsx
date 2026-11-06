import Spinner from "./Spinner";
import { useEffect, useState } from "react";
import type { ApiError } from "../api";

export default function DataState({
  loading,
  error,
  apiError,
  retry,
}: {
  loading: boolean;
  error: string;
  apiError?: ApiError | null;
  retry?: () => void;
}) {
  const [now, setNow] = useState(Date.now);
  const isPending = apiError?.status === 425;
  const retryAt = isPending ? apiError.retryAt : null;
  useEffect(() => {
    let timer: number | undefined;
    function updateAvailability() {
      const current = Date.now();
      setNow(current);
      if (retryAt !== null && retryAt > current) {
        timer = window.setTimeout(updateAvailability,
          Math.min(retryAt - current + 50, 2_147_483_647));
      }
    }
    updateAvailability();
    return () => window.clearTimeout(timer);
  }, [retryAt]);
  const title = apiError?.code === "session_not_started"
    ? "This session hasn't started yet"
    : apiError?.code === "classification_not_published"
      ? "Session results aren't published yet"
      : "Session data isn't available yet";

  return (
    <>
      {loading && <Spinner text="Loading published data…" />}
      {!loading && error && isPending && (
        <div role="status" aria-live="polite" className="notice">
          <strong>{title}</strong>
          <p>{error}</p>
          <p>Choose an earlier completed session, or check again once this session has finished and its data is published.</p>
          {retryAt !== null && retryAt > now && (
            <p>You can try again after {new Date(retryAt).toLocaleString([], {
              month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit",
            })} (your local time). Data may still be pending then.</p>
          )}
          {retry && (
            <button className="btn btn--secondary" type="button"
              disabled={retryAt !== null && retryAt > now} onClick={retry}>
              Check again
            </button>
          )}
        </div>
      )}
      {!loading && error && !isPending && (
        <p role="alert" className="notice notice--error">
          {error}
        </p>
      )}
    </>
  );
}
