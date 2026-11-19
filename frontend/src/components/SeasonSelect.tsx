import { useApi } from "../hooks/useApi";
export default function SeasonSelect({
  value,
  onChange,
}: {
  value: number;
  onChange: (year: number) => void;
}) {
  const { data, error } = useApi<{ seasons: number[] }>("/seasons");
  const years = [...new Set([...(data?.seasons ?? []), value])].sort(
    (a, b) => a - b,
  );
  return (
    <div className="form-group">
      <label htmlFor="season">Season</label>
      <select
        id="season"
        className="form-select"
        value={value}
        onChange={(e) => onChange(+e.target.value)}
      >
        {[...years].reverse().map((y) => (
          <option key={y}>{y}</option>
        ))}
      </select>
      {error && <small role="alert">{error}</small>}
    </div>
  );
}
