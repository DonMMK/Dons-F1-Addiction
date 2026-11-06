import Spinner from "./Spinner";
export default function DataState({
  loading,
  error,
}: {
  loading: boolean;
  error: string;
}) {
  return (
    <>
      {loading && <Spinner text="Loading published data…" />}
      {error && (
        <p role="alert" className="notice notice--error">
          {error}
        </p>
      )}
    </>
  );
}
