import { useEffect, useMemo, useState } from "react";
import type {
  ComparisonResponse,
  EventInfo,
  SessionInfo,
  DriverInfo,
} from "../api";
import { useApi } from "../hooks/useApi";
import SeasonSelect from "../components/SeasonSelect";
import DataState from "../components/DataState";
import LapReplay from "../components/LapReplay";
import TelemetryChart from "../components/TelemetryChart";

export function ComparisonView({ data }: { data: ComparisonResponse }) {
  const first = data.driver1.abbreviation ?? data.driver1.driver ?? "A",
    second = data.driver2.abbreviation ?? data.driver2.driver ?? "B";
  const chart = useMemo(
    () =>
      data.comparison.distance.map((distance, i) => ({
        distance: Math.round(distance),
        speedA: data.comparison.speed1[i],
        speedB: data.comparison.speed2[i],
        speedDelta: data.comparison.speedDelta[i],
        timeDelta: data.comparison.timeDelta[i],
        throttleA: data.comparison.throttle1[i],
        throttleB: data.comparison.throttle2[i],
        brakeA: data.comparison.brake1[i],
        brakeB: data.comparison.brake2[i],
        gearA: data.comparison.gear1[i],
        gearB: data.comparison.gear2[i],
        drsA: data.comparison.drs1[i],
        drsB: data.comparison.drs2[i],
      })),
    [data],
  );
  return (
    <>
      {data.dataSource && <p className="notice">Source: {data.dataSource}</p>}
      {data.warnings?.map((warning) => (
        <p className="notice" key={warning}>{warning}</p>
      ))}
      <div className="stats-grid">
        <div>
          <small>
            {first} · {data.driver1.compound}
          </small>
          <strong>{data.driver1.lapTime}</strong>
        </div>
        <div>
          <small>
            {second} · {data.driver2.compound}
          </small>
          <strong>{data.driver2.lapTime}</strong>
        </div>
        <div>
          <small>
            LAP GAP {first} − {second}
          </small>
          <strong>
            {(
              data.driver1.lapTimeSeconds - data.driver2.lapTimeSeconds
            ).toFixed(3)}{" "}
            s
          </strong>
        </div>
      </div>
      <LapReplay first={data.driver1} second={data.driver2} />
      <p className="notice">
        A = {first}, B = {second}. Charts align by distance in metres. Brake is
        an on/off signal. DRS is the raw provider code; 2026 aero channels need
        separate interpretation.
      </p>
      <div className="telemetry-section">
        <TelemetryChart
          title="Speed (km/h)"
          data={chart}
          dataKey1="speedA"
          dataKey2="speedB"
        />
        <TelemetryChart
          title={`Cumulative time A − B (s) · positive = A behind`}
          data={chart}
          dataKey1="timeDelta"
          isArea
        />
        <TelemetryChart
          title="Throttle (%)"
          data={chart}
          dataKey1="throttleA"
          dataKey2="throttleB"
        />
        <TelemetryChart
          title="Brake applied (0 / 1)"
          data={chart}
          dataKey1="brakeA"
          dataKey2="brakeB"
        />
        <TelemetryChart
          title="Gear"
          data={chart}
          dataKey1="gearA"
          dataKey2="gearB"
        />
        {data.comparison.drs1.some((v) => v !== null) || data.comparison.drs2.some((v) => v !== null) ? (
          <TelemetryChart
            title="DRS provider code"
            data={chart}
            dataKey1="drsA"
            dataKey2="drsB"
          />
        ) : <p className="notice">DRS data is unavailable for these laps.</p>}
      </div>
    </>
  );
}
export default function GhostCarPage() {
  const [year, setYear] = useState(new Date().getFullYear()),
    [round, setRound] = useState(""),
    [session, setSession] = useState("Q");
  const [first, setFirst] = useState(""),
    [second, setSecond] = useState(""),
    [path, setPath] = useState<string | null>(null);
  const schedule = useApi<{ events: EventInfo[] }>(`/schedule/${year}`);
  const sessions = useApi<{ sessions: SessionInfo[] }>(
    round ? `/sessions/${year}/${round}` : null,
  );
  const drivers = useApi<{ drivers: DriverInfo[] }>(
    round && session && sessions.data?.sessions.some((s) => s.key === session)
      ? `/drivers/${year}/${round}/${session}`
      : null,
  );
  const comparison = useApi<ComparisonResponse>(path);
  useEffect(() => {
    const races = schedule.data?.events.filter((e) => !e.isTesting) ?? [];
    setRound(
      String(
        (
          races
            .filter((e) => new Date(e.date).getTime() <= Date.now())
            .at(-1) ?? races[0]
        )?.roundNumber ?? "",
      ),
    );
  }, [schedule.data]);
  useEffect(() => {
    const list = sessions.data?.sessions ?? [];
    if (list.length && !list.some((s) => s.key === session))
      setSession(list[0].key);
  }, [sessions.data, session]);
  useEffect(() => {
    setFirst(drivers.data?.drivers[0]?.abbreviation ?? "");
    setSecond(drivers.data?.drivers[1]?.abbreviation ?? "");
  }, [drivers.data]);
  useEffect(() => setPath(null), [year, round, session, first, second]);
  return (
    <>
      <div className="page__header">
        <h1 className="page__title">Ghost Car</h1>
        <p className="page__subtitle">
          Recorded fastest-lap replay and distance-aligned telemetry. Selecting
          a race still compares fastest laps, not the full race.
        </p>
      </div>
      <div className="control-panel control-panel__row">
        <SeasonSelect
          value={year}
          onChange={(y) => {
            setRound("");
            setYear(y);
          }}
        />
        <select
          aria-label="Grand Prix"
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
        <select
          aria-label="Session"
          className="form-select"
          value={session}
          onChange={(e) => setSession(e.target.value)}
        >
          {sessions.data?.sessions.map((s) => (
            <option key={s.key} value={s.key}>
              {s.name}
            </option>
          ))}
        </select>
        {[
          { value: first, set: setFirst, label: "Driver A" },
          { value: second, set: setSecond, label: "Driver B" },
        ].map((control) => (
          <select
            key={control.label}
            aria-label={control.label}
            className="form-select"
            value={control.value}
            onChange={(e) => control.set(e.target.value)}
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
          disabled={!first || !second || first === second || comparison.loading}
          onClick={() =>
            setPath(
              `/ghost-car/compare/${year}/${round}/${session}/${first}/${second}`,
            )
          }
        >
          Compare
        </button>
      </div>
      {[schedule, sessions, drivers, comparison].map((state, i) => (
        <DataState key={i} {...state} />
      ))}
      {comparison.data && <ComparisonView data={comparison.data} />}
    </>
  );
}
