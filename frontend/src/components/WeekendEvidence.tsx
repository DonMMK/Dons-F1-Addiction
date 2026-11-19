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
  WeekendEvidence as Evidence,
} from "../weekendTypes";
import { useApi } from "../hooks/useApi";
import DataState from "./DataState";
import StrategyTyres from "./StrategyTyres";
import FiaDocuments from "./FiaDocuments";
import PerformanceGrid from "./PerformanceGrid";
import { Link } from "react-router-dom";

const value = (v: number | null | undefined, digits = 3) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

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
        Source: {data.source} · {data.first} L{data.lapA ?? "?"}{" "}
        {data.lapTimeA.toFixed(3)}s / {data.second} L{data.lapB ?? "?"}{" "}
        {data.lapTimeB.toFixed(3)}s
      </p>
      <div className="chart-legend">
        <span>
          <i style={{ background: "#59d6cd" }} />
          {data.first} gains time
        </span>
        <span>
          <i style={{ background: "#ffbd70" }} />
          {data.second} gains time
        </span>
        <span>
          <i style={{ background: "#718097" }} />
          Within ±0.020 s per bin
        </span>
      </div>
      <p className="notice">
        Classified lap-time A−B: {value(data.lapTimeA - data.lapTimeB)} s.
        Telemetry spans {data.observedDurationA.toFixed(3)} /{" "}
        {data.observedDurationB.toFixed(3)} s; sampled-span A−B:{" "}
        {value(data.observedDurationA - data.observedDurationB)} s. Boundary
        coverage differs: use the classified lap times for the overall order,
        and the map to inspect approximate gains within the sampled spans.
      </p>
      <svg
        viewBox="0 0 950 430"
        role="img"
        aria-label="Estimated mini-sector time dominance with detected speed zones"
        style={{ width: "100%", maxHeight: 430 }}
      >
        <polyline
          points={data.trace.map((p) => xy(p.x, p.y).join(",")).join(" ")}
          fill="none"
          stroke="#718097"
          strokeWidth="9"
        />
        {data.trace.slice(1).map((p, i) => {
          const previous = data.trace[i];
          const bin = data.miniSectors?.find(
            (s) =>
              (p.fraction + previous.fraction) / 2 >= s.start &&
              (p.fraction + previous.fraction) / 2 <= s.end,
          );
          const [x1, y1] = xy(previous.x, previous.y),
            [x2, y2] = xy(p.x, p.y);
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={
                bin?.winner === data.first
                  ? "#59d6cd"
                  : bin?.winner === data.second
                    ? "#ffbd70"
                    : "#718097"
              }
              strokeWidth="9"
              strokeLinecap="round"
            >
              <title>
                {bin
                  ? `Estimated mini-sector ${bin.index}: ${value(bin.deltaSeconds)} s (${data.first} − ${data.second})`
                  : "Unknown bin"}
              </title>
            </line>
          );
        })}
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
        Colours compare elapsed time in estimated mini-sectors, not official
        timing sectors. Detected speed zones are not official turn numbers.
        Higher corner minimum speed alone does not establish a faster lap or a
        better car.
      </p>
      {!!data.comparison?.length && (
        <div className="grid-2">
          <div>
            <h3>Speed around the lap</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data.comparison}>
                <CartesianGrid stroke="#303a48" />
                <XAxis
                  dataKey="fraction"
                  type="number"
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                />
                <YAxis domain={["auto", "auto"]} unit=" km/h" width={70} />
                <Tooltip
                  contentStyle={{ background: "#17212e" }}
                  labelFormatter={(v) =>
                    `${(Number(v) * 100).toFixed(1)}% lap distance`
                  }
                />
                <Line
                  dataKey="speedA"
                  name={data.first}
                  stroke="#59d6cd"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  dataKey="speedB"
                  name={data.second}
                  stroke="#ffbd70"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>Elapsed-time difference · A−B</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data.comparison}>
                <CartesianGrid stroke="#303a48" />
                <XAxis
                  dataKey="fraction"
                  type="number"
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                />
                <YAxis unit=" s" />
                <ReferenceLine y={0} stroke="#718097" />
                <Tooltip
                  contentStyle={{ background: "#17212e" }}
                  labelFormatter={(v) =>
                    `${(Number(v) * 100).toFixed(1)}% lap distance`
                  }
                />
                <Line
                  dataKey="deltaSeconds"
                  name={`${data.first} − ${data.second} (s)`}
                  stroke="#b2a1ff"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
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
  initialTab,
}: {
  data: Evidence;
  year: number;
  round: string;
  condition: string;
  initialTab?: string;
}) {
  const tabs = [
    "Overview",
    "Car performance",
    "Pace",
    "Strategy & tyres",
    "Laps & track",
    "Upgrades",
  ];
  const [tab, setTab] = useState(
    initialTab === "performance" ? "Car performance" : "Overview",
  );
  const [practice, setPractice] = useState("FP2"),
    [practicePath, setPracticePath] = useState<string | null>(null);
  const [first, setFirst] = useState(""),
    [second, setSecond] = useState(""),
    [trackSession, setTrackSession] = useState("Q"),
    [trackPath, setTrackPath] = useState<string | null>(null);
  const [lapA, setLapA] = useState(""),
    [lapB, setLapB] = useState("");
  type Options = {
    laps: {
      lap: number;
      seconds: number;
      compound: string | null;
      age: number | null;
    }[];
    note: string;
  };
  const optionsA = useApi<Options>(
    tab === "Laps & track" && first
      ? `/weekend/${year}/${round}/laps/${trackSession}/${first}`
      : null,
  );
  const optionsB = useApi<Options>(
    tab === "Laps & track" && second
      ? `/weekend/${year}/${round}/laps/${trackSession}/${second}`
      : null,
  );
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
  useEffect(() => {
    setLapA("");
    setLapB("");
  }, [trackSession, first, second]);
  useEffect(
    () => setTrackPath(null),
    [trackSession, first, second, lapA, lapB],
  );
  return (
    <>
      <div className="evidence-summary">
        <div>
          <span>Matched race samples</span>
          <strong>{data.pace?.coverage.used ?? "—"}</strong>
          <small>After weather and traffic checks</small>
        </div>
        <div>
          <span>Track temperature</span>
          <strong>
            {data.conditions.summary.TrackTemp?.median == null
              ? "Unknown"
              : `${data.conditions.summary.TrackTemp.median.toFixed(1)}°C`}
          </strong>
          <small>Session median · inspect the timeline</small>
        </div>
        <div>
          <span>Teams declaring updates</span>
          <strong>
            {data.upgrades.teams.some((t) =>
              ["declared_updates", "declared_none"].includes(t.status),
            )
              ? data.upgrades.teams.filter(
                  (t) => t.status === "declared_updates",
                ).length
              : "Unknown"}
          </strong>
          <small>
            {
              data.upgrades.teams.filter((t) =>
                ["declared_updates", "declared_none"].includes(t.status),
              ).length
            }
            /{data.upgrades.teams.length} teams indexed · missing records
            unknown
          </small>
        </div>
      </div>
      <div
        className="analysis-tabs"
        role="tablist"
        aria-label="Weekend analysis views"
      >
        {tabs.map((name, i) => (
          <button
            key={name}
            id={`analysis-tab-${i}`}
            role="tab"
            aria-selected={tab === name}
            aria-controls="analysis-panel"
            tabIndex={tab === name ? 0 : -1}
            onClick={() => setTab(name)}
            onKeyDown={(e) => {
              let next = i;
              if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
              else if (e.key === "ArrowLeft")
                next = (i + tabs.length - 1) % tabs.length;
              else if (e.key === "Home") next = 0;
              else if (e.key === "End") next = tabs.length - 1;
              else return;
              e.preventDefault();
              setTab(tabs[next]);
              document.getElementById(`analysis-tab-${next}`)?.focus();
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="analysis-panel"
        aria-labelledby={`analysis-tab-${tabs.indexOf(tab)}`}
      >
        {tab === "Overview" && (
          <>
            <section className="visual-panel">
              <h2>Race result and pace evidence</h2>
              <p className="notice">{data.verdict}</p>
              <p>
                Use the condition-specific pace estimates, both cars' coverage
                and uncertainty before assessing a “fastest car” claim. A lower
                finish can coexist with faster observed pace; the execution
                records below provide context without assigning a luck or
                driver-craft score.
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
              <h3>
                Recorded session weather · {data.conditions.samples} samples
              </h3>
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
                        labelFormatter={(v) =>
                          new Date(Number(v)).toLocaleString()
                        }
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
                      data.conditions.timeline.filter(
                        (w) => w.rainReported === true,
                      ).length
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
          </>
        )}
        {tab === "Car performance" && (
          <PerformanceGrid year={year} round={round} condition={condition} />
        )}
        {tab === "Pace" && (
          <>
            {data.pace ? (
              <PaceEvidence pace={data.pace} />
            ) : (
              <p className="notice">No race pace estimate is available yet.</p>
            )}
            <section className="visual-panel">
              <h2>Practice long-run evidence</h2>
              <p>
                Loaded on demand. Unknown fuel and traffic prevent treating
                practice pace as an isolated car ranking.
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
          </>
        )}
        {tab === "Laps & track" && (
          <section className="visual-panel">
            <p className="eyebrow">WHERE LAP TIME WAS GAINED</p>
            <h2>Lap comparison and track dominance</h2>
            <p>
              Compare two recorded laps to inspect slow, medium and fast speed
              minima. These observations can suggest where a package gains
              speed; they do not identify aero design, setup or driver
              contribution.
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
            <div className="analysis-controls">
              {[
                { name: "Lap A", value: lapA, set: setLapA, options: optionsA },
                { name: "Lap B", value: lapB, set: setLapB, options: optionsB },
              ].map((c) => (
                <div key={c.name}>
                  <label>
                    {c.name}
                    <select
                      aria-label={c.name}
                      className="form-select"
                      value={c.value}
                      onChange={(e) => c.set(e.target.value)}
                    >
                      <option value="">Fastest screened lap</option>
                      {c.options.data?.laps.map((l) => (
                        <option key={l.lap} value={l.lap}>
                          L{l.lap} · {l.seconds.toFixed(3)}s ·{" "}
                          {l.compound ?? "unknown tyre"} · age {l.age ?? "?"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DataState {...c.options} />
                </div>
              ))}
            </div>
            <button
              className="btn btn--secondary"
              disabled={
                !first || !second || first === second || trackData.loading
              }
              onClick={() =>
                setTrackPath(
                  `/weekend/${year}/${round}/track/${trackSession}/${first}/${second}?${new URLSearchParams({ ...(lapA ? { lap_a: lapA } : {}), ...(lapB ? { lap_b: lapB } : {}) })}`,
                )
              }
            >
              Compare selected laps
            </button>
            <DataState {...trackData} />
            {trackData.data && <SpeedZones data={trackData.data} />}
            <p className="text-gray">
              <Link to="/ghost-car">
                Open the animated Ghost Car replay and full speed, throttle,
                brake and gear traces →
              </Link>
            </p>
          </section>
        )}
        {tab === "Upgrades" && (
          <FiaDocuments year={year} round={round} initial={data.upgrades} />
        )}
        {tab === "Strategy & tyres" && (
          <>
            <StrategyTyres year={year} round={round} />
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
        )}
      </div>
    </>
  );
}
