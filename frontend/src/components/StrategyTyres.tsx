import { useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { normaliseFuel, stintDrift, type TyrePoint } from "../tyreMath";
import DataState from "./DataState";

interface StrategyReport {
  source: string;
  maxLap: number;
  drivers: {
    driver: string;
    team: string;
    finish: number | null;
    spans: {
      startLap: number;
      endLap: number;
      stint: number | null;
      compound: string;
    }[];
    points: TyrePoint[];
  }[];
  coverage: { observed: number; screened: number; tyrePoints: number };
  warnings: string[];
  method: string;
  limitations: string;
}
const colours: Record<string, string> = {
  SOFT: "#ff676f",
  MEDIUM: "#f4cc64",
  HARD: "#e3e8ed",
  INTERMEDIATE: "#58c58b",
  WET: "#68a6ff",
  UNKNOWN: "#68768a",
};
const pairColours = ["#59d6cd", "#ffbd70"];

function StrategyViews({ data }: { data: StrategyReport }) {
  const [first, setFirst] = useState(data.drivers[0]?.driver ?? "");
  const [second, setSecond] = useState(data.drivers[1]?.driver ?? "");
  const [compound, setCompound] = useState("ALL");
  const [adjust, setAdjust] = useState(false);
  const [rate, setRate] = useState("0.06");
  const parsed = Number(rate);
  const validRate =
    rate.trim() !== "" &&
    Number.isFinite(parsed) &&
    parsed >= 0 &&
    parsed <= 0.2;
  const gain = adjust && validRate ? parsed : 0;
  const groups = [first, second]
    .filter((d, i, a) => d && a.indexOf(d) === i)
    .flatMap((driver, index) => {
      const points =
        data.drivers
          .find((d) => d.driver === driver)
          ?.points.filter(
            (p) => compound === "ALL" || p.compound === compound,
          ) ?? [];
      return [...new Set(points.map((p) => `${p.stint}|${p.compound}`))].map(
        (key) => {
          const selected = points.filter(
            (p) => `${p.stint}|${p.compound}` === key,
          );
          return {
            label: `${driver} · stint ${selected[0].stint} · ${selected[0].compound}`,
            colour: pairColours[index],
            points: selected,
            drift: stintDrift(selected, gain),
          };
        },
      );
    });
  return (
    <>
      <section className="visual-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">HOW THE RACE UNFOLDED</p>
            <h2>Tyre strategy timeline</h2>
          </div>
          <span className="evidence-badge">Observed lap records</span>
        </div>
        <p className="text-gray">
          Source: {data.source}. Blank spans are missing observations; grey
          means compound unknown. Bars show reported stint and compound,
          including pit and neutralised laps.
        </p>
        <div className="chart-legend">
          {Object.entries(colours).map(([name, colour]) => (
            <span key={name}>
              <i style={{ background: colour }} />
              {name}
            </span>
          ))}
        </div>
        <div className="table-scroll">
          <svg
            className="strategy-timeline"
            viewBox={`0 0 1000 ${48 + data.drivers.length * 34}`}
            role="img"
            aria-label="Observed tyre stints by driver and race lap"
          >
            {[
              1,
              ...Array.from(
                { length: Math.floor(data.maxLap / 10) },
                (_, i) => (i + 1) * 10,
              ),
            ].map((lap) => (
              <g key={lap}>
                <line
                  x1={100 + ((lap - 1) / data.maxLap) * 880}
                  x2={100 + ((lap - 1) / data.maxLap) * 880}
                  y1={28}
                  y2={36 + data.drivers.length * 34}
                  stroke="#303a48"
                />
                <text
                  x={100 + ((lap - 1) / data.maxLap) * 880}
                  y={18}
                  fill="#aab8c7"
                  fontSize="12"
                >
                  L{lap}
                </text>
              </g>
            ))}
            {data.drivers.map((driver, i) => (
              <g key={driver.driver}>
                <text x={8} y={51 + i * 34} fill="#e6edf5" fontSize="14">
                  {driver.finish ?? "—"} · {driver.driver}
                </text>
                {driver.spans.map((span, j) => (
                  <g key={j}>
                    <rect
                      x={100 + ((span.startLap - 1) / data.maxLap) * 880}
                      y={34 + i * 34}
                      width={
                        ((span.endLap - span.startLap + 1) / data.maxLap) * 880
                      }
                      height={24}
                      rx={3}
                      fill={colours[span.compound] ?? colours.UNKNOWN}
                      stroke="#101620"
                      strokeWidth="1.5"
                    >
                      <title>{`${driver.driver} · ${span.compound} · L${span.startLap}–${span.endLap} · reported stint ${span.stint ?? "unknown"}`}</title>
                    </rect>
                    {span.endLap - span.startLap >= 4 && (
                      <text
                        x={105 + ((span.startLap - 1) / data.maxLap) * 880}
                        y={51 + i * 34}
                        fill="#111923"
                        fontSize="12"
                      >
                        {span.compound.slice(0, 1)} · L{span.startLap}
                      </text>
                    )}
                  </g>
                ))}
              </g>
            ))}
          </svg>
        </div>
      </section>
      <section className="visual-panel">
        <p className="eyebrow">LOOK INSIDE EACH STINT</p>
        <h2>Tyre-age lap-time comparison</h2>
        <p>
          Compare quality-screened laps within each reported stint. Fuel,
          traffic and weather can move these points; a slope is observed time
          drift, not a physical wear measurement.
        </p>
        <div className="analysis-controls">
          {[
            [first, setFirst, "Tyre driver A"],
            [second, setSecond, "Tyre driver B"],
          ].map(([selected, setter, name]) => (
            <label key={String(name)}>
              {String(name)}
              <select
                className="form-select"
                aria-label={String(name)}
                value={String(selected)}
                onChange={(e) =>
                  (setter as (v: string) => void)(e.target.value)
                }
              >
                {data.drivers.map((d) => (
                  <option key={d.driver}>{d.driver}</option>
                ))}
              </select>
            </label>
          ))}
          <label>
            Compound
            <select
              className="form-select"
              value={compound}
              onChange={(e) => setCompound(e.target.value)}
            >
              <option value="ALL">All compounds</option>
              {Object.keys(colours)
                .filter((c) => c !== "UNKNOWN")
                .map((c) => (
                  <option key={c}>{c}</option>
                ))}
            </select>
          </label>
        </div>
        <div className="assumption-control">
          <label>
            <input
              type="checkbox"
              checked={adjust}
              onChange={(e) => setAdjust(e.target.checked)}
            />{" "}
            Apply assumed fuel-burn normalisation
          </label>
          {adjust && (
            <label>
              Assumed lap-time gain per race lap (s)
              <input
                className="form-input"
                aria-label="Assumed fuel gain"
                type="number"
                min="0"
                max="0.2"
                step="0.005"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
            </label>
          )}
          {adjust && !validRate && (
            <p role="alert">
              Enter a value from 0 to 0.20 s/lap. The chart is showing raw times
              until the assumption is valid.
            </p>
          )}
          <p className="text-gray">
            {adjust && validRate
              ? `Assumption active: add ${gain.toFixed(3)} × (race lap − 1) seconds to normalise to lap 1. Faint points retain raw times.`
              : "Raw lap times · no fuel correction applied."}{" "}
            Fuel mass is not measured. The supplied 0.060 value is an editable
            example, not a calibrated estimate.
          </p>
        </div>
        {!groups.some((g) => g.points.length) ? (
          <p className="notice">
            No screened laps with tyre age and stint are available for this
            selection.
          </p>
        ) : (
          <>
            <div className="chart-legend">
              {groups.map((g) => (
                <span key={g.label}>
                  <i style={{ background: g.colour }} />
                  {g.label}
                </span>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart
                margin={{ top: 15, right: 20, bottom: 24, left: 20 }}
              >
                <CartesianGrid stroke="#303a48" />
                <XAxis
                  dataKey="age"
                  type="number"
                  name="Reported tyre age"
                  label={{
                    value: "Reported tyre age (laps)",
                    position: "insideBottom",
                    offset: -15,
                  }}
                />
                <YAxis
                  dataKey="displaySeconds"
                  type="number"
                  domain={["auto", "auto"]}
                  name="Lap time"
                  unit=" s"
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    const p = payload?.[0]?.payload;
                    return active && p ? (
                      <div className="chart-tooltip">
                        L{p.lap} · age {p.age} · {p.compound}
                        <br />
                        Raw {p.seconds.toFixed(3)} s<br />
                        Displayed {p.displaySeconds.toFixed(3)} s
                      </div>
                    ) : null;
                  }}
                />
                {groups.map((g) => (
                  <Scatter
                    key={`${g.label}-raw`}
                    name={`${g.label} raw`}
                    data={g.points.map((p) => ({
                      ...p,
                      displaySeconds: p.seconds,
                    }))}
                    fill={g.colour}
                    opacity={adjust && validRate ? 0.25 : 0.9}
                    isAnimationActive={false}
                  />
                ))}
                {adjust &&
                  validRate &&
                  groups.map((g) => (
                    <Scatter
                      key={g.label}
                      name={`${g.label} assumed normalisation`}
                      data={g.points.map((p) => ({
                        ...p,
                        displaySeconds: normaliseFuel(p, gain),
                      }))}
                      fill={g.colour}
                      isAnimationActive={false}
                    />
                  ))}
              </ScatterChart>
            </ResponsiveContainer>
            <div className="table-scroll">
              <table className="f1-table">
                <thead>
                  <tr>
                    <th>Selected stint</th>
                    <th>Screened laps</th>
                    <th>Observed time drift (s / tyre-age lap)</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={g.label}>
                      <td>{g.label}</td>
                      <td>{g.points.length}</td>
                      <td>
                        {g.drift == null
                          ? "Needs ≥8 laps across ≥4 tyre-age laps"
                          : `${g.drift > 0 ? "+" : ""}${g.drift.toFixed(3)}${adjust && validRate ? " · assumed fuel normalisation" : " · raw"}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Inspect plotted lap data</summary>
              <div className="table-scroll">
                <table className="f1-table">
                  <thead>
                    <tr>
                      <th>Stint</th>
                      <th>Race lap</th>
                      <th>Tyre age</th>
                      <th>Raw seconds</th>
                      <th>Displayed seconds</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groups.flatMap((g) =>
                      g.points.map((p) => (
                        <tr key={`${g.label}-${p.lap}`}>
                          <td>{g.label}</td>
                          <td>{p.lap}</td>
                          <td>{p.age}</td>
                          <td>{p.seconds.toFixed(3)}</td>
                          <td>{normaliseFuel(p, gain).toFixed(3)}</td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        )}
        <details>
          <summary>Screening, assumptions and coverage</summary>
          <p>
            {data.coverage.observed} recorded laps · {data.coverage.screened}{" "}
            quality screened · {data.coverage.tyrePoints} with usable tyre
            metadata.
          </p>
          <p>{data.method}</p>
          <p>{data.limitations}</p>
          <p>
            Drift is the median of all within-stint pair slopes, with at least
            eight laps over four tyre-age laps. It has no uncertainty interval
            and is not used to rank teams or predict tyre life.
          </p>
        </details>
      </section>
    </>
  );
}

export default function StrategyTyres({
  year,
  round,
}: {
  year: number;
  round: string;
}) {
  const response = useApi<StrategyReport>(`/weekend/${year}/${round}/strategy`);
  return (
    <>
      <DataState {...response} />
      {response.data && (
        <>
          {response.data.warnings.map((w) => (
            <p className="notice" key={w}>
              {w}
            </p>
          ))}
          <StrategyViews key={`${year}-${round}`} data={response.data} />
        </>
      )}
    </>
  );
}
