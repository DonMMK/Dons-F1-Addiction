import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  PaceReport,
  PaceRow,
  TrackEvidence,
  UpgradeTeam,
  WeekendEvidence as Evidence,
} from "../weekendTypes";
import { useApi } from "../hooks/useApi";
import DataState from "./DataState";

const value = (v: number | null | undefined, digits = 3) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;
const label = (status: string) =>
  ({
    declared_updates: "Declared component changes",
    declared_none: "No updates submitted",
    not_indexed: "Not indexed — unknown",
    unparsed: "Document needs review",
  })[status] ?? status;

function PaceTable({ rows, title }: { rows: PaceRow[]; title: string }) {
  return (
    <>
      <h3>{title}</h3>
      {!rows.length ? (
        <p className="notice">
          Insufficient matched evidence for this ranking. Unknown coverage is
          not treated as a slow car.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="f1-table">
            <thead>
              <tr>
                <th>Group / estimated rank</th>
                <th>Package</th>
                <th>Relative pace (s/lap)</th>
                <th>Exploratory 95% interval</th>
                <th>95% rank range</th>
                <th>Matched windows / rivals</th>
                <th>Sector 1 / 2 / 3 (s)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td>
                    G{r.component} · {r.rank}
                  </td>
                  <td>
                    {r.name}
                    <br />
                    <small>{r.drivers.join(" / ")}</small>
                  </td>
                  <td>{value(r.scoreSeconds)}</td>
                  <td>
                    {r.interval95?.map((v) => value(v)).join(" to ") ??
                      "Too few bootstrap samples"}
                  </td>
                  <td>{r.rankRange95?.join("–") ?? "—"}</td>
                  <td>
                    {r.windows} / {r.rivals}
                  </td>
                  <td>{r.sectors.map((v) => value(v)).join(" / ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function PaceEvidence({ pace }: { pace: PaceReport }) {
  return (
    <section className="visual-panel">
      <h2>{pace.session} · observed package pace</h2>
      {pace.warnings?.map((w) => (
        <p className="notice" key={w}>
          {w}
        </p>
      ))}
      <p className="notice">
        Ranks describe car + driver + remaining strategy effects in the selected
        conditions. A pure car ranking or driver-skill score is not
        identifiable.
      </p>
      <p className="text-gray">
        {pace.coverage.recorded} recorded laps → {pace.coverage.qualityScreened}{" "}
        quality screened → {pace.coverage.weatherMatched} with weather →{" "}
        {pace.coverage.used} eligible samples. Race samples require measured
        traffic coverage; practice traffic and fuel remain unknown.
      </p>
      <PaceTable
        rows={pace.teamPace.rows}
        title="Team pace · equal weight for both cars"
      />
      {pace.teamPace.components > 1 && (
        <p className="notice">
          Comparison groups are disconnected. Rank 1 in one group is not
          comparable with rank 1 in another.
        </p>
      )}
      {pace.teamPace.components === 1 && !!pace.teamPace.rows.length && (
        <ResponsiveContainer
          width="100%"
          height={Math.max(220, pace.teamPace.rows.length * 35)}
        >
          <BarChart
            data={pace.teamPace.rows}
            layout="vertical"
            margin={{ left: 30, right: 20 }}
          >
            <CartesianGrid stroke="#363649" />
            <XAxis type="number" />
            <YAxis type="category" dataKey="name" width={125} />
            <ReferenceLine x={0} stroke="#ddd" />
            <Tooltip contentStyle={{ background: "#242433" }} />
            <Bar
              dataKey="scoreSeconds"
              name="Relative package pace (s/lap)"
              fill="#59c8bd"
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
      {!!pace.unrankedTeams.length && (
        <p className="notice">
          Unranked teams: {pace.unrankedTeams.join(" · ")}. Both cars need
          usable links in the same comparison group.
        </p>
      )}
      {!!pace.teamPace.rows.length && (
        <>
          <h3>Observed sector strengths and deficits</h3>
          <p>
            These are point estimates against the same group reference, not
            isolated corner or aerodynamic effects.
          </p>
          {pace.teamPace.rows.map((r) => {
            const valid = r.sectors
              .map((seconds, i) => ({ seconds, sector: i + 1 }))
              .filter(
                (s): s is { seconds: number; sector: number } =>
                  s.seconds !== null,
              );
            const best = [...valid].sort((a, b) => a.seconds - b.seconds)[0],
              worst = [...valid].sort((a, b) => b.seconds - a.seconds)[0];
            return (
              <p key={r.name}>
                <strong>{r.name}</strong> ·{" "}
                {best && best.seconds < 0
                  ? `Relative advantage strongest in S${best.sector} (${value(best.seconds)} s)`
                  : "No measured relative sector advantage"}{" "}
                ·{" "}
                {worst && worst.seconds > 0
                  ? `largest relative deficit in S${worst.sector} (${value(worst.seconds)} s)`
                  : "no measured relative sector deficit"}
                .
              </p>
            );
          })}
        </>
      )}
      <details>
        <summary>Driver package estimates and direct comparisons</summary>
        <PaceTable
          rows={pace.driverPace.rows}
          title="Driver-car observations · same matched reference"
        />
        <div className="table-scroll">
          <table className="f1-table">
            <thead>
              <tr>
                <th>A / B</th>
                <th>Observed median A−B</th>
                <th>Matched windows</th>
              </tr>
            </thead>
            <tbody>
              {pace.driverPace.pairwise.map((p) => (
                <tr key={`${p.first}-${p.second}`}>
                  <td>
                    {p.first} / {p.second}
                  </td>
                  <td>{value(p.deltaSeconds)} s</td>
                  <td>{p.windows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>Matching, uncertainty and limits</summary>
        <p>{pace.method}</p>
        <ul>
          {pace.limitations.map((v) => (
            <li key={v}>{v}</li>
          ))}
        </ul>
        <p>
          Negative scores are faster than the comparison-group reference. Sector
          scores use the same matched observations. The bar order is an
          estimate; overlapping intervals or rank ranges do not establish a
          unique winner.
        </p>
        <p>
          Largest graph-fit mismatch:{" "}
          {value(
            Math.max(0, ...pace.driverPace.rows.map((r) => r.fitRmsSeconds)),
          )}{" "}
          s. This measures inconsistency between the pairwise observations and
          the fitted model, not car performance.
        </p>
      </details>
    </section>
  );
}

function UpgradeRows({ teams }: { teams: UpgradeTeam[] }) {
  return (
    <div className="table-scroll">
      <table className="f1-table">
        <thead>
          <tr>
            <th>Team</th>
            <th>Evidence status</th>
            <th>Declared components</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((t) => (
            <tr key={t.team}>
              <td>{t.team}</td>
              <td>{label(t.status)}</td>
              <td>
                {t.components.length
                  ? t.components.map((c) => (
                      <div key={`${c.component}-${c.page}`}>
                        <a href={c.sourceUrl} target="_blank" rel="noreferrer">
                          {c.component} · PDF p{c.page}
                        </a>
                      </div>
                    ))
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SpeedZones({ data }: { data: TrackEvidence }) {
  const xs = data.trace.map((p) => p.x),
    ys = data.trace.map((p) => p.y);
  const minX = Math.min(...xs),
    minY = Math.min(...ys),
    width = Math.max(...xs) - minX || 1,
    height = Math.max(...ys) - minY || 1;
  const scale = Math.min(820 / width, 330 / height);
  const xy = (x: number, y: number) => [
    50 + (x - minX) * scale,
    380 - (y - minY) * scale,
  ];
  return (
    <>
      <p>
        Source: {data.source} · {data.first} {data.lapTimeA.toFixed(3)}s /{" "}
        {data.second} {data.lapTimeB.toFixed(3)}s
      </p>
      <svg
        viewBox="0 0 950 430"
        role="img"
        aria-label="Recorded track trace with detected speed zones"
        style={{ width: "100%", maxHeight: 430 }}
      >
        <polyline
          points={data.trace.map((p) => xy(p.x, p.y).join(",")).join(" ")}
          fill="none"
          stroke="#718097"
          strokeWidth="9"
        />
        {data.zones.map((z) => {
          const [x, y] = xy(z.x, z.y);
          return (
            <g key={z.zone}>
              <circle
                cx={x}
                cy={y}
                r="9"
                fill={
                  z.band === "slow"
                    ? "#ff7b7b"
                    : z.band === "medium"
                      ? "#ffd071"
                      : "#59c8bd"
                }
              >
                <title>{`Zone ${z.zone}: ${z.band}, ${z.speedA} km/h`}</title>
              </circle>
              <text x={x + 10} y={y - 8} fill="#fff" fontSize="14">
                Z{z.zone}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="notice">
        Detected speed zones, not official turn numbers. Higher corner minimum
        speed alone does not establish a faster lap or a better car.
      </p>
      {!data.zones.length ? (
        <p className="notice">
          No robust speed minima were detected in these samples.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="f1-table">
            <thead>
              <tr>
                <th>Zone / sector</th>
                <th>Speed band</th>
                <th>{data.first} minimum (km/h)</th>
                <th>{data.second} nearby minimum (km/h)</th>
                <th>A−B</th>
              </tr>
            </thead>
            <tbody>
              {data.zones.map((z) => (
                <tr key={z.zone}>
                  <td>
                    Z{z.zone} / S{z.sector ?? "?"}
                  </td>
                  <td>{z.band}</td>
                  <td>{z.speedA.toFixed(1)}</td>
                  <td>{z.speedB.toFixed(1)}</td>
                  <td>{value(z.deltaKmH, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details>
        <summary>Speed-zone method and limits</summary>
        <p>{data.method}</p>
        <p>{data.limitations}</p>
      </details>
    </>
  );
}

export default function WeekendEvidence({
  data,
  year,
  round,
  condition,
}: {
  data: Evidence;
  year: number;
  round: string;
  condition: string;
}) {
  const [practice, setPractice] = useState("FP2"),
    [practicePath, setPracticePath] = useState<string | null>(null);
  const [first, setFirst] = useState(""),
    [second, setSecond] = useState(""),
    [trackSession, setTrackSession] = useState("Q"),
    [trackPath, setTrackPath] = useState<string | null>(null);
  const drivers = data.drivers;
  const practiceData = useApi<{
    pace: PaceReport;
    source: string;
    warnings: string[];
  }>(practicePath);
  const trackData = useApi<TrackEvidence>(trackPath);
  useEffect(() => {
    setFirst(drivers[0] ?? "");
    setSecond(drivers[1] ?? "");
  }, [drivers.join(",")]);
  useEffect(() => {
    setPracticePath(null);
    setTrackPath(null);
  }, [year, round, condition]);
  useEffect(() => setPracticePath(null), [practice]);
  useEffect(() => setTrackPath(null), [trackSession, first, second]);
  return (
    <>
      <section className="visual-panel">
        <h2>Race result and pace evidence</h2>
        <p className="notice">{data.verdict}</p>
        <p>
          Use the condition-specific pace estimates, both cars' coverage and
          uncertainty before assessing a “fastest car” claim. A lower finish can
          coexist with faster observed pace; the execution records below provide
          context without assigning a luck or driver-craft score.
        </p>
      </section>
      <section className="visual-panel">
        <h2>Track demands and conditions</h2>
        <h3>{data.track.name}</h3>
        {data.track.demands.map((d) => (
          <p key={d.area}>
            <strong>{d.area}</strong> · {d.interpretation}
          </p>
        ))}
        {data.track.tyreAllocation && (
          <p>
            Published tyre allocation:{" "}
            {Object.entries(data.track.tyreAllocation)
              .map(([c, spec]) => `${c} ${spec}`)
              .join(" · ")}
          </p>
        )}
        <p>{data.track.note}</p>
        {data.track.sources.map((s) => (
          <p key={s.url}>
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.label}
            </a>
          </p>
        ))}
        {data.upgrades.documents
          ?.filter((d) => /pirelli|circuit map/i.test(d.title))
          .map((d) => (
            <p key={d.url}>
              <a href={d.url} target="_blank" rel="noreferrer">
                {d.title}
              </a>
            </p>
          ))}
        <h3>Recorded session weather · {data.conditions.samples} samples</h3>
        {!!data.conditions.timeline.length ? (
          <>
            <p>
              Track temperature min / median / max:{" "}
              {Object.values(data.conditions.summary.TrackTemp)
                .map((v) => (v == null ? "—" : `${v.toFixed(1)}°C`))
                .join(" / ")}
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart
                data={data.conditions.timeline.map((w) => ({
                  ...w,
                  time: Date.parse(w.date),
                }))}
              >
                <CartesianGrid stroke="#363649" />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(v) =>
                    new Date(v).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                />
                <YAxis />
                <Tooltip
                  labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                  contentStyle={{ background: "#242433" }}
                />
                <Line
                  dataKey="trackTemp"
                  name="Track °C"
                  stroke="#ffc464"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  dataKey="airTemp"
                  name="Air °C"
                  stroke="#59c8bd"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
            <p>
              Rain reported in{" "}
              {
                data.conditions.timeline.filter((w) => w.rainReported === true)
                  .length
              }{" "}
              samples. Weather times use your local time zone.
            </p>
          </>
        ) : (
          <p className="notice">
            Weather coverage unavailable. No temperature-conditioned pace
            verdict is generated.
          </p>
        )}
        <p className="text-gray">{data.conditions.note}</p>
      </section>
      {data.pace && <PaceEvidence pace={data.pace} />}
      <section className="visual-panel">
        <h2>Practice long-run evidence</h2>
        <p>
          Loaded on demand. Unknown fuel and traffic prevent treating practice
          pace as an isolated car ranking.
        </p>
        <select
          aria-label="Practice session"
          className="form-select"
          value={practice}
          onChange={(e) => setPractice(e.target.value)}
        >
          {["FP1", "FP2", "FP3"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>{" "}
        <button
          className="btn btn--secondary"
          disabled={practiceData.loading}
          onClick={() =>
            setPracticePath(
              `/weekend/${year}/${round}/pace/${practice}?condition=${condition}`,
            )
          }
        >
          Load practice evidence
        </button>
        <DataState {...practiceData} />
        {practiceData.data && (
          <>
            <p>Source: {practiceData.data.source}</p>
            {practiceData.data.warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <PaceEvidence pace={practiceData.data.pace} />
          </>
        )}
      </section>
      <section className="visual-panel">
        <h2>Corner-speed signatures</h2>
        <p>
          Compare two recorded laps to inspect slow, medium and fast speed
          minima. These observations can suggest where a package gains speed;
          they do not identify aero design, setup or driver contribution.
        </p>
        <select
          aria-label="Track comparison session"
          className="form-select"
          value={trackSession}
          onChange={(e) => setTrackSession(e.target.value)}
        >
          {["Q", "R", "FP1", "FP2", "FP3"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>{" "}
        {[
          { name: "Corner driver A", value: first, set: setFirst },
          { name: "Corner driver B", value: second, set: setSecond },
        ].map((c) => (
          <select
            key={c.name}
            aria-label={c.name}
            className="form-select"
            value={c.value}
            onChange={(e) => c.set(e.target.value)}
          >
            {drivers.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        ))}{" "}
        <button
          className="btn btn--secondary"
          disabled={!first || !second || first === second || trackData.loading}
          onClick={() =>
            setTrackPath(
              `/weekend/${year}/${round}/track/${trackSession}/${first}/${second}`,
            )
          }
        >
          Load corner-speed map
        </button>
        <DataState {...trackData} />
        {trackData.data && <SpeedZones data={trackData.data} />}
      </section>
      <section className="visual-panel">
        <h2>Declared upgrades · this weekend</h2>
        <p>{data.upgrades.note}</p>
        <p>
          <a href={data.upgrades.sourceUrl} target="_blank" rel="noreferrer">
            Official FIA source
          </a>
          {data.upgrades.checkedAt &&
            ` · Indexed ${new Date(data.upgrades.checkedAt).toLocaleDateString()}`}
        </p>
        <UpgradeRows teams={data.upgrades.teams} />
        <details>
          <summary>Season upgrade timeline · indexed rounds only</summary>
          {data.upgrades.timeline.map((r) => (
            <div key={r.round}>
              <h3>
                Round {r.round} · {r.eventName}
              </h3>
              <p>
                <a href={r.sourceUrl} target="_blank" rel="noreferrer">
                  FIA declaration
                </a>
              </p>
              <UpgradeRows teams={r.teams} />
            </div>
          ))}
          {!data.upgrades.timeline.length && (
            <p>
              No declarations have been indexed for this season yet. Missing
              records do not mean no upgrades.
            </p>
          )}
        </details>
      </section>
      <section className="visual-panel">
        <h2>Execution, incidents and classification</h2>
        <p>{data.execution.note}</p>
        <div className="table-scroll">
          <table className="f1-table">
            <thead>
              <tr>
                <th>Driver / team</th>
                <th>Qualifying</th>
                <th>Actual grid</th>
                <th>Finish / status</th>
                <th>Recorded stops: lap · stationary / lane time</th>
              </tr>
            </thead>
            <tbody>
              {data.execution.drivers.map((d) => (
                <tr key={d.driver}>
                  <td>
                    {d.driver} · {d.team}
                  </td>
                  <td>{d.qualifying ?? "—"}</td>
                  <td>{d.grid ?? "—"}</td>
                  <td>
                    {d.finish ?? "—"} · {d.status}
                  </td>
                  <td>
                    {d.stops.map((s, i) => (
                      <div key={i}>
                        L{s.lap ?? "?"} · {s.stationarySeconds ?? "—"} /{" "}
                        {s.laneSeconds ?? "—"} s
                        {s.deltaToSessionMedian != null &&
                          ` (stationary Δ ${value(s.deltaToSessionMedian)} s vs session median)`}
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <details>
          <summary>Race-control event timeline</summary>
          {data.execution.events.map((e, i) => (
            <p key={i}>
              <strong>
                {e.date
                  ? new Date(e.date).toLocaleTimeString()
                  : "Time unavailable"}{" "}
                · L{e.lap ?? "?"}
              </strong>{" "}
              · {e.message}
            </p>
          ))}
        </details>
      </section>
    </>
  );
}
