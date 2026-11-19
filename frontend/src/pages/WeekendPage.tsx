import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { EventInfo, WeekendResponse } from "../api";
import { useApi } from "../hooks/useApi";
import SeasonSelect from "../components/SeasonSelect";
import DataState from "../components/DataState";
import WeekendEvidence from "../components/WeekendEvidence";
import { useSearchParams } from "react-router-dom";

const delta = (value: number | null) =>
  value == null
    ? "Insufficient data"
    : `${value > 0 ? "+" : ""}${value.toFixed(3)} s`;
export default function WeekendPage() {
  const [query] = useSearchParams();
  const queryYear = Number(query.get("year"));
  const linkedYear =
    Number.isInteger(queryYear) &&
    queryYear >= 2018 &&
    queryYear <= new Date().getFullYear()
      ? queryYear
      : new Date().getFullYear();
  const linkedRound = /^\d+$/.test(query.get("round") ?? "")
    ? query.get("round")!
    : "";
  const linkedCondition = ["slick", "wet", "cool", "warm", "all"].includes(
    query.get("condition") ?? "",
  )
    ? query.get("condition")!
    : "slick";
  const [year, setYear] = useState(linkedYear);
  const [round, setRound] = useState(linkedRound);
  const [selected, setSelected] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [condition, setCondition] = useState(linkedCondition);
  useEffect(() => {
    setYear(linkedYear);
    setRound(linkedRound);
    setCondition(linkedCondition);
    setSelected(0);
  }, [linkedYear, linkedRound, linkedCondition]);
  const schedule = useApi<{ events: EventInfo[] }>(`/schedule/${year}`);
  const report = useApi<WeekendResponse>(
    round ? `/weekend/${year}/${round}?condition=${condition}` : null,
    refresh,
  );
  useEffect(() => {
    if (!schedule.data) return;
    const races = schedule.data?.events.filter((e) => !e.isTesting) ?? [];
    const past = races.filter((e) => new Date(e.date).getTime() <= Date.now());
    setRound((current) =>
      races.some((e) => String(e.roundNumber) === current)
        ? current
        : String((past.at(-1) ?? races[0])?.roundNumber ?? ""),
    );
  }, [schedule.data]);
  const team = report.data?.teams[selected];
  return (
    <>
      <div className="page__header">
        <p className="eyebrow">MEASURE FIRST. EXPLAIN CAREFULLY.</p>
        <h1 className="page__title">Weekend by Weekend: Overview</h1>
        <p className="page__subtitle">
          Track context, conditions, observed package pace, declared upgrades
          and execution records, alongside teammate comparisons. Car and driver
          effects are not assumed to be separable.
        </p>
      </div>
      <div className="control-panel control-panel__row">
        <SeasonSelect
          value={year}
          onChange={(y) => {
            setRound("");
            setSelected(0);
            setYear(y);
          }}
        />
        <div className="form-group">
          <label htmlFor="weekend">Grand Prix</label>
          <select
            id="weekend"
            className="form-select"
            value={round}
            onChange={(e) => {
              setRound(e.target.value);
              setSelected(0);
            }}
          >
            {schedule.data?.events
              .filter((e) => !e.isTesting)
              .map((e) => (
                <option key={e.roundNumber} value={e.roundNumber}>
                  {e.eventName}
                </option>
              ))}
          </select>
        </div>
        <button
          className="btn btn--secondary"
          onClick={() => setRefresh((v) => v + 1)}
        >
          Refresh weekend
        </button>
        <select
          aria-label="Pace conditions"
          className="form-select"
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
        >
          <option value="slick">Slick-tyre laps</option>
          <option value="wet">Wet / intermediate tyres</option>
          <option value="cool">Track below 30°C</option>
          <option value="warm">Track at least 40°C</option>
          <option value="all">All matched conditions</option>
        </select>
      </div>
      <DataState {...schedule} />
      <DataState {...report} />
      {report.data && (
        <>
          <h2>{report.data.eventName}</h2>
          {report.data.evidence && (
            <WeekendEvidence
              key={`${year}-${round}-${condition}-${query.get("view") ?? "overview"}`}
              data={report.data.evidence}
              year={year}
              round={round}
              condition={condition}
              initialTab={query.get("view") ?? undefined}
            />
          )}
          <details className="supporting-evidence">
            <summary>
              Teammate head-to-head and supporting evidence
              {report.data.warnings.length > 0 && (
                <span className="tag">
                  {report.data.warnings.length} data notices
                </span>
              )}
            </summary>
            <h2>Teammate head-to-head</h2>
            {report.data.dataSources && (
              <p className="notice">
                Sources:{" "}
                {Object.entries(report.data.dataSources)
                  .map(([session, source]) => `${session}: ${source}`)
                  .join(" · ")}
              </p>
            )}
            <p className="notice">{report.data.method}</p>
            {report.data.warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <div className="table-scroll">
              <table className="f1-table">
                <thead>
                  <tr>
                    <th>Team / A — B</th>
                    <th>Shared qualifying</th>
                    <th>Q gap A−B</th>
                    <th>Matched race gap A−B</th>
                    <th>Matched laps</th>
                    <th>95% interval (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {report.data.teams.map((t, i) => (
                    <tr
                      key={`${t.team}-${t.first}-${t.second}`}
                      className={i === selected ? "selected-row" : ""}
                    >
                      <td>
                        <button
                          className="text-button"
                          onClick={() => setSelected(i)}
                        >
                          {t.team}
                          <br />
                          {t.first} — {t.second}
                        </button>
                      </td>
                      <td>{t.qualifying.segment ?? "—"}</td>
                      <td>{delta(t.qualifying.deltaSeconds)}</td>
                      <td>
                        {delta(t.raceDeltaSeconds)}
                        {t.paceReversal && (
                          <span className="tag">Quali/race reversal</span>
                        )}
                      </td>
                      <td>{t.matchedLaps}</td>
                      <td>
                        {t.interval95?.map((v) => v.toFixed(3)).join(" to ") ??
                          "Too few pairs"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {team && (
              <section className="visual-panel">
                <h2>
                  {team.first} vs {team.second} · matched race laps
                </h2>
                <p className="text-gray">{team.qualifying.reason}</p>
                {team.samples.length ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={team.samples}>
                      <CartesianGrid stroke="#363649" />
                      <XAxis
                        dataKey="lap"
                        label={{
                          value: "Race lap",
                          position: "insideBottom",
                          offset: -2,
                        }}
                      />
                      <YAxis domain={["auto", "auto"]} />
                      <Tooltip
                        contentStyle={{
                          background: "#242433",
                          border: "1px solid #444",
                        }}
                      />
                      <ReferenceLine y={0} stroke="#ddd" />
                      <Line
                        dataKey="delta"
                        name={`${team.first} minus ${team.second} (s)`}
                        stroke="#ff6565"
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="notice">
                    No laps meet the matching criteria. No race-pace verdict is
                    reported.
                  </p>
                )}
                <div className="grid-2">
                  {[team.first, team.second].map((d) => (
                    <div key={d}>
                      <h3>{d} · tyre-age trends</h3>
                      {team.tyreTrends[d].map((t) => (
                        <p className="notice" key={t.compound}>
                          <strong>
                            {t.compound} · {t.laps} valid laps
                          </strong>
                          <br />
                          {t.slopeSecondsPerTyreLap == null
                            ? "Trend unavailable"
                            : `${t.slopeSecondsPerTyreLap.toFixed(3)} s per tyre-age lap`}
                          <br />
                          <small>{t.reason}</small>
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
                <details>
                  <summary>Inspect matched evidence</summary>
                  <div className="table-scroll">
                    <table className="f1-table">
                      <thead>
                        <tr>
                          <th>Lap</th>
                          <th>Compound</th>
                          <th>{team.first} tyre age</th>
                          <th>{team.second} tyre age</th>
                          <th>{team.first} time</th>
                          <th>{team.second} time</th>
                          <th>Δ s</th>
                        </tr>
                      </thead>
                      <tbody>
                        {team.samples.map((r) => (
                          <tr key={r.lap}>
                            <td>{r.lap}</td>
                            <td>{r.compound}</td>
                            <td>{r.ageA}</td>
                            <td>{r.ageB}</td>
                            <td>{r.first.toFixed(3)}</td>
                            <td>{r.second.toFixed(3)}</td>
                            <td>{r.delta.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </section>
            )}
            <section className="visual-panel">
              <h2>Qualifying position and observed race pace</h2>
              <p className="text-gray">
                Each clean race lap is compared with at least two other drivers
                on the same lap and compound, with tyre age within one lap.
                Negative is faster than that peer median. Peer sets change
                across laps; this is descriptive pace, not an isolated car or
                driver ranking. At least five matched laps are needed.
              </p>
              <div className="table-scroll">
                <table className="f1-table">
                  <thead>
                    <tr>
                      <th>Driver / team</th>
                      <th>Qualifying</th>
                      <th>Race classification</th>
                      <th>Peer-relative race pace</th>
                      <th>Matched laps</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(report.data.fieldPace ?? []).map((p) => (
                      <tr key={p.driver}>
                        <td>
                          {p.driver} · {p.team}
                        </td>
                        <td>{p.qualifyingPosition ?? "—"}</td>
                        <td>{p.finishPosition ?? "—"}</td>
                        <td>
                          {p.relativePacePercent == null
                            ? "Insufficient data"
                            : `${p.relativePacePercent > 0 ? "+" : ""}${p.relativePacePercent.toFixed(3)}%`}
                        </td>
                        <td>{p.matchedLaps}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            {report.data.weather && (
              <p className="notice">
                Session weather averages · track{" "}
                {report.data.weather.TrackTemp ?? "—"}°C · air{" "}
                {report.data.weather.AirTemp ?? "—"}°C · rain reported{" "}
                {report.data.weather.rainfall ? "yes" : "no"}. Session averages
                do not describe every matched lap.
              </p>
            )}
            <section className="methodology">
              <h2>What this evidence can tell you</h2>
              <p>
                A qualifying deficit and race advantage can coexist. Check the
                shared qualifying segment, the number of matched race laps and
                the interval before drawing a conclusion. An interval spanning
                zero is inconclusive in this sample.
              </p>
              <ul>
                {report.data.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
              <p>
                <strong>Unavailable measurements:</strong>{" "}
                {report.data.unavailable.join(" · ")}
              </p>
            </section>
          </details>
        </>
      )}
    </>
  );
}
