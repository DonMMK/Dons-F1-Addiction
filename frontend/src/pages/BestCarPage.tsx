import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type {
  EraConfig,
  EngineeringTopic,
  EventInfo,
  DriverInfo,
  ComparisonResponse,
} from "../api";
import { useApi } from "../hooks/useApi";
import { useSeasonAnalysis } from "../hooks/useSeasonAnalysis";
import DataState from "../components/DataState";
import EngineeringCar from "../components/EngineeringCar";
import { ComparisonView } from "./GhostCarPage";

interface Progression {
  progression: {
    round: number;
    race: string;
    gap: number;
    gapPercent: number;
  }[];
  unavailable: string[];
  method: string;
}
export default function BestCarPage() {
  const [eraKey, setEraKey] = useState("2025"),
    [topic, setTopic] = useState(0),
    [round, setRound] = useState("");
  const [first, setFirst] = useState(""),
    [second, setSecond] = useState(""),
    [comparisonPath, setComparisonPath] = useState<string | null>(null);
  const eras = useApi<{ eras: Record<string, string> }>("/best-car/eras");
  const era = useApi<EraConfig>(`/best-car/era/${eraKey}`);
  const topics = useApi<{
    eras: Record<string, EngineeringTopic[]>;
    note: string;
  }>("/engineering/topics");
  const progression = useSeasonAnalysis<Progression>(eraKey);
  const schedule = useApi<{ events: EventInfo[] }>(
    era.data ? `/schedule/${era.data.year}` : null,
  );
  const drivers = useApi<{ drivers: DriverInfo[] }>(
    era.data && round ? `/drivers/${era.data.year}/${round}/Q` : null,
  );
  const comparison = useApi<ComparisonResponse>(comparisonPath);
  const active = topics.data?.eras[eraKey]?.[topic];
  useEffect(() => {
    setRound(
      String(
        schedule.data?.events.find((e) => !e.isTesting)?.roundNumber ?? "",
      ),
    );
  }, [schedule.data]);
  useEffect(() => {
    const list = drivers.data?.drivers ?? [];
    setFirst(
      list.find((d) => d.team === era.data?.primaryCar.team)?.abbreviation ??
        list[0]?.abbreviation ??
        "",
    );
    setSecond(
      list.find((d) => d.team !== era.data?.primaryCar.team)?.abbreviation ??
        list[1]?.abbreviation ??
        "",
    );
  }, [drivers.data, era.data]);
  useEffect(() => setComparisonPath(null), [eraKey, round, first, second]);
  return (
    <>
      <div className="page__header">
        <p className="eyebrow">LOOKING BACK</p>
        <h1 className="page__title">The engineering behind the lap</h1>
        <p className="page__subtitle">
          Explore documented design decisions alongside observed performance.
          Timing evidence shows outcomes; it cannot isolate the effect of a
          single component.
        </p>
      </div>
      <div className="control-panel">
        <label htmlFor="era">Car / era</label>
        <select
          id="era"
          className="form-select"
          value={eraKey}
          onChange={(e) => {
            setEraKey(e.target.value);
            setTopic(0);
            setRound("");
          }}
        >
          {Object.entries(eras.data?.eras ?? {}).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>
      <DataState {...era} />
      <DataState {...topics} />
      {era.data && (
        <div className="grid-3">
          {[era.data.primaryCar, ...era.data.competitors].map((car) => (
            <article
              className="model-card"
              key={car.car}
              style={{ borderTop: `3px solid ${car.color}` }}
            >
              <h2>{car.car}</h2>
              <p>
                {car.team} · {car.drivers.join(" / ")}
              </p>
            </article>
          ))}
        </div>
      )}
      {active && (
        <section className="engineering-layout">
          <EngineeringCar focus={active.id} />
          <div>
            <div className="button-group">
              {topics.data?.eras[eraKey].map((t, i) => (
                <button
                  key={t.id}
                  className={`btn ${topic === i ? "btn--primary" : "btn--secondary"}`}
                  onClick={() => setTopic(i)}
                >
                  {t.id}
                </button>
              ))}
            </div>
            <h2>{active.title}</h2>
            <p>{active.documented}</p>
            <h3>What to inspect in the data</h3>
            <p>{active.measure}</p>
            <p className="notice">{active.cannotInfer}</p>
            <a
              className="source-link"
              href={active.sourceUrl}
              target="_blank"
              rel="noreferrer"
            >
              {active.sourceLabel} ↗
            </a>
          </div>
        </section>
      )}
      <section className="visual-panel">
        <h2>Season advantage against the closest rival</h2>
        <p className="text-gray">
          Best primary-team Q1 lap minus best other-team Q1 lap. Negative means
          the primary team was faster. Percentage gaps account for lap length,
          while circuit and weather effects remain.
        </p>
        <DataState {...progression} />
        {progression.loading && (
          <p className="text-gray">
            {progression.progress} · first load downloads the season in the
            background.
          </p>
        )}
        {progression.data && (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={progression.data.progression}>
                <CartesianGrid stroke="#39394b" />
                <XAxis
                  dataKey="round"
                  label={{
                    value: "Round",
                    position: "insideBottom",
                    offset: -2,
                  }}
                />
                <YAxis unit="%" />
                <Tooltip
                  contentStyle={{ background: "#242433" }}
                  labelFormatter={(v) => `Round ${v}`}
                />
                <ReferenceLine y={0} stroke="#ddd" />
                <Line
                  name="Gap to rival (%)"
                  dataKey="gapPercent"
                  stroke={era.data?.primaryCar.color ?? "#f66"}
                  dot
                />
              </LineChart>
            </ResponsiveContainer>
            {progression.data.unavailable.length > 0 && (
              <p className="notice">
                Missing rounds: {progression.data.unavailable.join(", ")}. No
                values were substituted.
              </p>
            )}
          </>
        )}
      </section>
      <section className="visual-panel">
        <h2>Inspect the recorded laps</h2>
        <p className="text-gray">
          Compare any two drivers in the same qualifying session. Their fastest
          laps may come from different Q segments; use Weekend by Weekend for a
          shared-segment teammate comparison.
        </p>
        <div className="control-panel__row">
          <select
            aria-label="Historical race"
            className="form-select"
            value={round}
            onChange={(e) => setRound(e.target.value)}
          >
            {schedule.data?.events
              .filter((e) => !e.isTesting)
              .map((e) => (
                <option key={e.roundNumber} value={e.roundNumber}>
                  {e.eventName}
                </option>
              ))}
          </select>
          {[
            { value: first, set: setFirst, label: "Historical driver A" },
            { value: second, set: setSecond, label: "Historical driver B" },
          ].map((c) => (
            <select
              key={c.label}
              aria-label={c.label}
              className="form-select"
              value={c.value}
              onChange={(e) => c.set(e.target.value)}
            >
              {drivers.data?.drivers.map((d) => (
                <option key={d.abbreviation} value={d.abbreviation}>
                  {d.abbreviation} · {d.team}
                </option>
              ))}
            </select>
          ))}
          <button
            className="btn btn--primary"
            disabled={
              !era.data || !round || !first || !second || first === second
            }
            onClick={() =>
              setComparisonPath(
                `/ghost-car/compare/${era.data!.year}/${round}/Q/${first}/${second}`,
              )
            }
          >
            Load telemetry
          </button>
        </div>
        <DataState {...schedule} />
        <DataState {...drivers} />
        <DataState {...comparison} />
        {comparison.data && <ComparisonView data={comparison.data} />}
      </section>
    </>
  );
}
