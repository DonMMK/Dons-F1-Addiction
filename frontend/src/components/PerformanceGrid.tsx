import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import type {
  PerformanceBoard,
  PerformanceResponse,
  PerformanceRow,
} from "../performanceTypes";
import CarGlyph, { teamColor } from "./CarGlyph";
import DataState from "./DataState";

const signed = (v: number | null, digits = 3) => {
  if (v == null) return "—";
  const rounded = Number(v.toFixed(digits));
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(digits)}`;
};
const colour = (row: PerformanceRow) =>
  row.colour && /^#?[a-f\d]{6}$/i.test(row.colour)
    ? `#${row.colour.replace(/^#/, "")}`
    : teamColor(row.team);
const weekendLink = (year: number, round: number, condition: string) =>
  `/weekend?${new URLSearchParams({ year: String(year), round: String(round), condition, view: "performance" })}`;

/** A shared axis for one connected comparison group, including uncertainty. */
function axis(values: number[]) {
  const finite = values.filter(Number.isFinite);
  const min = Math.min(0, ...finite),
    max = Math.max(0.25, ...finite);
  const rough = (max - min) / 5,
    magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].find((v) => v * magnitude >= rough)! * magnitude;
  const low = Math.floor(min / step) * step,
    high = Math.ceil(max / step) * step;
  return {
    low,
    high,
    ticks: Array.from(
      { length: Math.round((high - low) / step) + 1 },
      (_, i) => low + i * step,
    ),
  };
}

export function PaceLaneGrid({
  board,
  compact = false,
}: {
  board: PerformanceBoard;
  compact?: boolean;
}) {
  const [strict, setStrict] = useState(false);
  return (
    <>
      {board.strictBoard && (
        <div
          className="button-group performance-view"
          aria-label="Pace evidence view"
        >
          <button
            className={`btn ${!strict ? "btn--primary" : "btn--secondary"}`}
            aria-pressed={!strict}
            onClick={() => setStrict(false)}
          >
            Adjusted race pace
          </button>
          <button
            className={`btn ${strict ? "btn--primary" : "btn--secondary"}`}
            aria-pressed={strict}
            onClick={() => setStrict(true)}
          >
            Strict matched evidence
          </button>
        </div>
      )}
      <PaceLanePlot
        key={strict ? "strict" : "adjusted"}
        board={strict && board.strictBoard ? board.strictBoard : board}
        compact={compact}
      />
    </>
  );
}

function PaceLanePlot({
  board,
  compact = false,
}: {
  board: PerformanceBoard;
  compact?: boolean;
}) {
  const [groupId, setGroupId] = useState<number | null>(null);
  const [percent, setPercent] = useState(false);
  const [previous, setPrevious] = useState(false);
  const [selected, setSelected] = useState("");
  const group =
    board.groups.find((g) => g.component === groupId) ??
    board.groups[0] ??
    (board.unrankedTeams.length
      ? { component: 0, referenceTeam: "none available", rows: [] }
      : undefined);
  const rows = group?.rows ?? [];
  const adjusted = board.view === "adjusted";
  const partial = board.unrankedTeams.length > 0 || board.groups.length > 1;
  const evidence = (r: PerformanceRow) =>
    r.evidenceTier === "single_car"
      ? "Single-car proxy"
      : adjusted
        ? "Adjusted · two cars"
        : "Strict matched";
  const missing = board.unrankedTeams;
  const unit = percent ? "% lap" : "s/lap";
  const convert = (seconds: number) =>
    percent && board.normalisationLapSeconds
      ? (seconds / board.normalisationLapSeconds) * 100
      : seconds;
  const position = (r: PerformanceRow) =>
    percent ? (r.gapPercent ?? 0) : r.gapSeconds;
  const oldPosition = (r: PerformanceRow) =>
    percent ? r.previousGapPercentToReference : r.previousEquivalentGapSeconds;
  const bounds = axis(
    rows.flatMap((r) => [
      position(r),
      ...(r.gapInterval95 ?? []).map(convert),
      ...(oldPosition(r) != null ? [oldPosition(r)!] : []),
    ]),
  );
  const x = (v: number) =>
    350 + ((v - bounds.low) / (bounds.high - bounds.low)) * 600;
  const rowHeight = compact ? 45 : 56;
  const height = 75 + (rows.length + missing.length) * rowHeight;
  const focus = rows.find((r) => r.team === selected);
  const hasPrevious = rows.some((r) => oldPosition(r) != null);
  return (
    <>
      <p className="notice performance-explainer">
        {adjusted
          ? "Estimated observed race pace: tyre age, compound, race lap and traffic are model controls. This includes laps rejected by strict matching. It is a car + driver + strategy estimate; intervals are exploratory model uncertainty."
          : `Strict matching only. ${partial ? "Ranks are within this comparison group, not positions in the full field. Missing teams may be faster." : "Both cars supply matched evidence."}`}
      </p>
      <div className="performance-controls">
        {board.groups.length > 1 && (
          <label>
            Comparison group
            <select
              className="form-select"
              aria-label="Performance comparison group"
              value={group?.component}
              onChange={(e) => {
                setGroupId(Number(e.target.value));
                setSelected("");
                setPrevious(false);
              }}
            >
              {board.groups.map((g) => (
                <option key={g.component} value={g.component}>
                  Group {g.component} · {g.rows.length} teams
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="button-group">
          <button
            className={`btn ${!percent ? "btn--primary" : "btn--secondary"}`}
            aria-pressed={!percent}
            onClick={() => setPercent(false)}
          >
            Seconds / lap
          </button>
          <button
            className={`btn ${percent ? "btn--primary" : "btn--secondary"}`}
            aria-pressed={percent}
            onClick={() => setPercent(true)}
            disabled={!board.normalisationLapSeconds}
          >
            % of lap
          </button>
        </div>
        <button
          className="btn btn--secondary"
          disabled={!hasPrevious}
          aria-pressed={previous}
          onClick={() => setPrevious((v) => !v)}
        >
          {previous ? "Show current pace" : "Replay pace movement"}
        </button>
      </div>
      {board.groups.length > 1 && (
        <p className="notice">
          The evidence forms separate comparison groups. Each has its own
          reference; ranks and gaps cannot be compared across groups.
        </p>
      )}
      {group && (
        <>
          <p className="performance-reference">
            <strong>
              {previous
                ? "Previous GP positions, normalised to this lap"
                : adjusted
                  ? "Adjusted race-pace estimates"
                  : "Strict matched estimates"}
            </strong>{" "}
            · {rows.length} of{" "}
            {board.totalTeams ?? rows.length + missing.length} teams estimated ·
            reference: {group.referenceTeam} ·{" "}
            {board.previousEvent
              ? `compared with ${board.previousEvent}`
              : "previous race evidence not available yet"}
          </p>
          <div className="chart-legend">
            <span>
              <i style={{ background: "#59d6a3" }} />
              Smaller relative gap
            </span>
            <span>
              <i style={{ background: "#ff788b" }} />
              Larger relative gap
            </span>
            <span>◇ Previous estimate, scaled to this lap</span>
            <span>
              Whisker: exploratory 95% {adjusted ? "model " : ""}gap interval
            </span>
          </div>
          <div className="table-scroll">
            <svg
              className="performance-grid"
              viewBox={`0 0 1200 ${height}`}
              role="group"
              aria-label={`Car performance grid · ${board.eventName} · group ${group.component}`}
              style={{ fontFamily: "system-ui, sans-serif" }}
            >
              <title>
                Observed car and driver package pace, not isolated car
                performance
              </title>
              <rect width="1200" height={height} fill="#111c29" rx="10" />
              {[
                {
                  x: 18,
                  label: adjusted ? "EST." : partial ? "GROUP" : "RANK",
                },
                { x: 65, label: "TEAM" },
                { x: 266, label: "MOVE" },
                {
                  x: 350,
                  label: rows.length
                    ? `GAP TO ${group.referenceTeam.toUpperCase()} · ${unit}`
                    : "NO SUPPORTED PACE ESTIMATES",
                },
                { x: 1005, label: "CHANGE · pp" },
                { x: 1120, label: adjusted ? "LAP WINDOWS" : "WINDOWS" },
              ].map((h) => (
                <text
                  key={h.label}
                  x={h.x}
                  y={22}
                  fill="#a8bacd"
                  fontSize="11"
                  fontWeight="700"
                >
                  {h.label}
                </text>
              ))}
              {bounds.ticks.map((t) => (
                <g key={t}>
                  <line
                    x1={x(t)}
                    x2={x(t)}
                    y1={49}
                    y2={height - 8}
                    stroke={Math.abs(t) < 1e-8 ? "#658a9c" : "#2c3b4b"}
                    strokeDasharray={Math.abs(t) < 1e-8 ? "3 3" : undefined}
                  />
                  <text
                    x={x(t)}
                    y={43}
                    textAnchor="middle"
                    fill="#a9bed2"
                    fontSize="11"
                  >
                    {Math.abs(t) < 1e-8 ? "0" : t.toFixed(2)}
                  </text>
                </g>
              ))}
              {rows.map((r, i) => {
                const y = 72 + i * rowHeight,
                  currentX = x(position(r)),
                  old = oldPosition(r),
                  oldX = old == null ? null : x(old);
                const displayed = previous && old != null ? old : position(r);
                const delta = r.deltaGapPercentagePoints;
                const changeColour =
                  delta == null || Math.abs(delta) < 0.0005
                    ? "#9cadbc"
                    : delta < 0
                      ? "#59d6a3"
                      : "#ff788b";
                return (
                  <g
                    className="performance-grid-row"
                    key={r.team}
                    role="button"
                    tabIndex={0}
                    aria-label={`${r.team}: ${adjusted ? "estimated " : ""}rank ${r.rank}${!adjusted && partial ? ` of ${rows.length} compared teams; full-field rank unavailable` : ""}, gap ${r.gapSeconds.toFixed(3)} seconds, ${r.windows} ${adjusted ? "race laps" : "matched windows"}, ${evidence(r)}`}
                    onClick={() => setSelected(r.team)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(r.team);
                      }
                    }}
                  >
                    <rect
                      x={6}
                      y={y - 19}
                      width={1188}
                      height={rowHeight - 2}
                      rx={4}
                      fill={
                        focus?.team === r.team
                          ? "#263a4c"
                          : i % 2
                            ? "#192635"
                            : "transparent"
                      }
                    />
                    {bounds.ticks.map((t) => (
                      <line
                        key={t}
                        x1={x(t)}
                        x2={x(t)}
                        y1={y - 19}
                        y2={y + rowHeight - 21}
                        stroke={Math.abs(t) < 1e-8 ? "#658a9c" : "#2c3b4b"}
                        strokeDasharray={Math.abs(t) < 1e-8 ? "3 3" : undefined}
                      />
                    ))}
                    <text
                      x={22}
                      y={y + 5}
                      fill="#edf4fc"
                      fontSize="13"
                      fontWeight="700"
                    >
                      {adjusted
                        ? `~${r.rank}`
                        : partial
                          ? `${r.rank}/${rows.length}`
                          : r.rank}
                    </text>
                    <rect
                      x={53}
                      y={y - 9}
                      width={3}
                      height={18}
                      fill={colour(r)}
                    />
                    <text
                      x={65}
                      y={y + 4}
                      fill="#e6edf7"
                      fontSize="13"
                      fontWeight="650"
                    >
                      <title>{r.team}</title>
                      {r.team.length > 24 ? `${r.team.slice(0, 23)}…` : r.team}
                    </text>
                    {adjusted && (
                      <text
                        x={65}
                        y={y + 19}
                        fill={
                          r.evidenceTier === "single_car"
                            ? "#f4bd71"
                            : "#a9bed2"
                        }
                        fontSize="10"
                      >
                        {evidence(r)}
                        {r.strictMatched ? " · matched too" : ""}
                      </text>
                    )}
                    {r.rankChange != null && r.rankChange !== 0 && (
                      <path
                        d={
                          r.rankChange > 0
                            ? `M 270 ${y + 4} l 5 -8 l 5 8 Z`
                            : `M 270 ${y - 4} l 5 8 l 5 -8 Z`
                        }
                        fill={r.rankChange > 0 ? "#59d6a3" : "#ff788b"}
                      />
                    )}
                    <text
                      x={284}
                      y={y + 5}
                      fill={
                        r.rankChange == null || r.rankChange === 0
                          ? "#9cadbc"
                          : r.rankChange > 0
                            ? "#59d6a3"
                            : "#ff788b"
                      }
                      fontSize="13"
                    >
                      <title>{r.comparisonNote}</title>
                      {r.rankChange == null
                        ? "—"
                        : r.rankChange === 0
                          ? "="
                          : String(Math.abs(r.rankChange))}
                    </text>
                    {oldX != null && (
                      <>
                        <rect
                          x={Math.min(oldX, currentX)}
                          y={y - 15}
                          width={Math.max(1, Math.abs(currentX - oldX))}
                          height={30}
                          fill={changeColour}
                          opacity={0.18}
                        />
                        {!previous && (
                          <path
                            d={`M ${oldX} ${y - 7} l 5 7 l -5 7 l -5 -7 Z`}
                            fill="none"
                            stroke="#a5b2c1"
                            strokeWidth="1.5"
                          />
                        )}
                      </>
                    )}
                    {!previous && r.gapInterval95 && (
                      <g stroke="#c6d4e3" strokeWidth="1.6">
                        <line
                          x1={x(convert(r.gapInterval95[0]))}
                          x2={x(convert(r.gapInterval95[1]))}
                          y1={y}
                          y2={y}
                        />
                        {r.gapInterval95.map((v, j) => (
                          <line
                            key={j}
                            x1={x(convert(v))}
                            x2={x(convert(v))}
                            y1={y - 6}
                            y2={y + 6}
                          />
                        ))}
                      </g>
                    )}
                    <g
                      className="performance-car"
                      transform={`translate(${x(displayed)}, ${y})`}
                      style={{
                        transform: `translate(${x(displayed)}px, ${y}px)`,
                      }}
                    >
                      <g transform="rotate(90) scale(1.05)">
                        <CarGlyph color={colour(r)} />
                      </g>
                    </g>
                    <text
                      x={Math.min(x(displayed) + 25, 970)}
                      y={y - 12}
                      fill="#e6edf7"
                      fontSize="11"
                      fontWeight="650"
                    >
                      {displayed.toFixed(3)}
                    </text>
                    <text
                      x={1005}
                      y={y + 5}
                      fill={changeColour}
                      fontSize="13"
                      fontWeight="700"
                    >
                      {signed(delta)}
                    </text>
                    <text x={1143} y={y + 5} fill="#bdd0e2" fontSize="13">
                      {r.windows}
                    </text>
                  </g>
                );
              })}
              {missing.map((team, i) => {
                const y = 72 + (rows.length + i) * rowHeight;
                return (
                  <g
                    key={`missing-${team}`}
                    aria-label={`${team}: no current-race estimate`}
                  >
                    <rect
                      x={6}
                      y={y - 19}
                      width={1188}
                      height={rowHeight - 2}
                      fill="#192635"
                    />
                    <text x={22} y={y + 5} fill="#a9bed2">
                      —
                    </text>
                    <text x={65} y={y + 5} fill="#e6edf7" fontSize="13">
                      {team}
                    </text>
                    <text x={350} y={y + 5} fill="#a9bed2" fontSize="12">
                      No identifiable current-race estimate · see coverage below
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <p className="text-gray performance-caption">
            Δ gap is percentage-point change against the same reference team,
            scaled by each race’s median eligible lap. It is descriptive and has
            no change-confidence interval. Rank arrows require the same ranked
            team set; “—” means unavailable. The reference’s zero is a plotting
            definition; its rank can still be uncertain.
          </p>
          {focus && (
            <div className="performance-focus" role="status">
              <strong>{focus.team}</strong> · {focus.drivers.join(" / ")} · rank{" "}
              {focus.rank}
              {focus.rankRange95 &&
                ` (exploratory 95% rank range ${focus.rankRange95.join("–")})`}{" "}
              · {focus.windows}{" "}
              {adjusted ? "race-lap windows" : "matched windows"} ·{" "}
              {focus.rivals} connected rivals. {focus.comparisonNote}.{" "}
              {focus.gapInterval95 &&
                `Gap interval ${focus.gapInterval95.map((v) => v.toFixed(3)).join(" to ")} s/lap.`}
              {adjusted && (
                <p>
                  {evidence(focus)} ·{" "}
                  {Object.entries(focus.driverLaps ?? {})
                    .map(([d, n]) => `${d}: ${n} laps`)
                    .join(" · ")}
                  .{" "}
                  {focus.evidenceTier === "single_car" &&
                    "The missing car is not observed; its uncertainty uses this race’s teammate differences."}
                </p>
              )}
            </div>
          )}
        </>
      )}
      {!rows.length && (
        <p className="notice">
          No teams have enough connected, matched evidence for a pace ranking
          under this condition.
        </p>
      )}
      {!!board.unrankedTeams.length && (
        <div className="performance-unranked">
          <strong>
            {adjusted
              ? "Visible without a numerical estimate"
              : "Outside this matched comparison"}
          </strong>
          <div>
            {board.unrankedTeams.map((t) => (
              <span key={t}>
                {t} <small>—</small>
              </span>
            ))}
          </div>
          <p>
            {adjusted
              ? "No supported estimate is available for these teams under this condition. They are not assigned a prior ranking."
              : "Both cars need usable evidence in the same comparison group. Use Adjusted race pace for broader coverage."}{" "}
            Unranked teams are not plotted at zero or treated as slow.
          </p>
        </div>
      )}
      <details>
        <summary>Exact values, coverage and method</summary>
        <p>
          {board.coverage.recorded} recorded laps → {board.coverage.used}{" "}
          eligible samples. Normalisation lap:{" "}
          {board.normalisationLapSeconds?.toFixed(3) ?? "unavailable"} seconds.
          {adjusted
            ? "Two-car estimates weight drivers equally; single-car proxies are labelled."
            : "Both driver estimates have equal weight."}
        </p>
        <div className="table-scroll">
          <table className="f1-table">
            <thead>
              <tr>
                <th>Group / team</th>
                <th>Evidence</th>
                <th>Rank / 95% range</th>
                <th>Gap to group reference</th>
                <th>95% gap interval</th>
                <th>Gap % of lap</th>
                <th>Previous gap % to same reference</th>
                <th>Δ gap (pp)</th>
                <th>Δ rank</th>
              </tr>
            </thead>
            <tbody>
              {board.groups.flatMap((g) =>
                g.rows.map((r) => (
                  <tr key={`${g.component}-${r.team}`}>
                    <td>
                      G{g.component} · {r.team}
                    </td>
                    <td>{evidence(r)}</td>
                    <td>
                      {r.rank} / {r.rankRange95?.join("–") ?? "—"}
                    </td>
                    <td>{r.gapSeconds.toFixed(3)} s</td>
                    <td>
                      {r.gapInterval95?.map((v) => v.toFixed(3)).join(" to ") ??
                        "Unavailable"}
                    </td>
                    <td>{signed(r.gapPercent)}%</td>
                    <td>{signed(r.previousGapPercentToReference)}%</td>
                    <td>{signed(r.deltaGapPercentagePoints)}</td>
                    <td>{signed(r.rankChange, 0)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        {board.validation && (
          <p>
            Held-out check: {board.validation.heldOutWindows} race laps;
            pair-difference MAE{" "}
            {board.validation.pairDifferenceMaeSeconds?.toFixed(3) ??
              "unavailable"}{" "}
            s, versus{" "}
            {board.validation.zeroDifferenceMaeSeconds?.toFixed(3) ??
              "unavailable"}{" "}
            s assuming no difference. {board.validation.note}
          </p>
        )}
        {!!board.diagnostics?.length && (
          <div className="table-scroll">
            <table className="f1-table performance-coverage">
              <thead>
                <tr>
                  <th>Team / driver</th>
                  <th>Condition laps</th>
                  <th>Strict clear-air laps</th>
                  <th>Observed traffic samples</th>
                  <th>Why strict matching excludes teams</th>
                </tr>
              </thead>
              <tbody>
                {board.diagnostics.flatMap((t) =>
                  t.drivers.map((d) => (
                    <tr key={`${t.team}-${d.driver}`}>
                      <th>
                        {t.team} / {d.driver}
                      </th>
                      <td>{d.usableLaps}</td>
                      <td>{d.clearAirLaps}</td>
                      <td>
                        {d.trafficObservedFraction == null
                          ? "Unknown"
                          : `${(d.trafficObservedFraction * 100).toFixed(0)}%`}
                      </td>
                      <td>{t.strictReason}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
        <p>{board.method}</p>
        <p>{board.comparisonMethod}</p>
        <p>
          The reference is the lowest point estimate in this group, selected
          from this sample; its zero gap is by definition. The rank interval
          still reflects uncertainty about the order.
        </p>
        <ul>
          {board.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </details>
    </>
  );
}

function HistoryGrid({ data }: { data: PerformanceResponse }) {
  const teams = [
    ...new Set(
      data.history.flatMap((h) =>
        h.board
          ? [
              ...h.board.groups.flatMap((g) => g.rows.map((r) => r.team)),
              ...h.board.unrankedTeams,
            ]
          : [],
      ),
    ),
  ].sort();
  if (!data.history.length) return null;
  return (
    <details className="performance-history" open>
      <summary>Recent weekends · car-performance grid</summary>
      <p className="text-gray">
        Each cell shows the estimated observed-package rank and gap % to that
        round’s group reference. Separate groups are labelled G1/G2. This is not
        a cumulative season score.
      </p>
      <div className="table-scroll">
        <table className="f1-table performance-matrix">
          <thead>
            <tr>
              <th>Team</th>
              {data.history.map((h) => (
                <th key={h.round}>
                  <Link to={weekendLink(data.year, h.round, data.condition)}>
                    R{h.round}
                    <br />
                    {h.eventName.replace(" Grand Prix", "")}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => (
              <tr key={team}>
                <th>{team}</th>
                {data.history.map((h) => {
                  const g = h.board?.groups.find((g) =>
                    g.rows.some((r) => r.team === team),
                  );
                  const r = g?.rows.find((r) => r.team === team);
                  return (
                    <td
                      key={h.round}
                      title={
                        r
                          ? `${g?.referenceTeam} reference · ${r.windows} laps/windows · ${r.evidenceTier === "single_car" ? "Single-car proxy" : h.board?.view === "adjusted" ? "Adjusted two-car estimate" : "Strict matched"}`
                          : h.board
                            ? "Insufficient matched coverage"
                            : "Evidence not yet indexed"
                      }
                      style={
                        r
                          ? {
                              background: `rgba(75,190,172,${Math.max(0.06, 0.3 - Math.min(r.gapPercent ?? 2, 2) * 0.12)})`,
                            }
                          : undefined
                      }
                    >
                      {r ? (
                        <>
                          <strong>
                            {h.board?.view === "adjusted" ? "~" : "#"}
                            {r.rank}
                          </strong>
                          {r.evidenceTier === "single_car" && (
                            <small>Single car</small>
                          )}
                          {(h.board?.groups.length ?? 0) > 1 &&
                            ` G${g?.component}`}
                          <small>+{r.gapPercent?.toFixed(3) ?? "—"}%</small>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default function PerformanceGrid({
  year,
  round,
  condition = "slick",
  compact = false,
}: {
  year: number;
  round?: string;
  condition?: string;
  compact?: boolean;
}) {
  const [tick, setTick] = useState(0);
  const [last, setLast] = useState<PerformanceResponse | null>(null);
  const query = new URLSearchParams({ condition, ...(round ? { round } : {}) });
  const response = useApi<PerformanceResponse>(
    `/performance/${year}?${query}`,
    tick,
  );
  useEffect(() => {
    setLast(null);
  }, [year, round, condition]);
  useEffect(() => {
    if (response.data) setLast(response.data);
  }, [response.data]);
  const data = response.data ?? last;
  const pending = !!data && ["queued", "checking"].includes(data.update.state);
  useEffect(() => {
    if (data?.update.enabled === false) return;
    const timer = setInterval(
      () => {
        if (document.visibilityState !== "hidden") setTick((v) => v + 1);
      },
      pending ? 10000 : 60000,
    );
    return () => clearInterval(timer);
  }, [pending, data?.update.enabled]);
  return (
    <section className="visual-panel performance-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PACE, WITH THE EVIDENCE ATTACHED</p>
          <h2>
            {compact
              ? "This week’s car performance"
              : "Car performance · weekend by weekend"}
          </h2>
          <p className="text-gray">
            Observed car + driver package pace · evidence and model estimates ·{" "}
            {condition} conditions
          </p>
        </div>
        {data?.board && (
          <Link
            className="btn btn--secondary"
            to={weekendLink(year, data.board.round, condition)}
          >
            Explore this weekend ↗
          </Link>
        )}
      </div>
      <DataState {...response} />
      {data && (
        <>
          <p className="performance-status" role="status">
            {data.update.showingEarlierRound && (
              <strong>
                Preparing round {data.requestedRound}; showing cached round{" "}
                {data.displayedRound}.{" "}
              </strong>
            )}
            {data.update.message}
            {data.update.checkedAt &&
              ` Last check ${new Date(data.update.checkedAt).toLocaleString()}.`}
            {data.update.nextCheckAt &&
              ` Next eligible check ${new Date(data.update.nextCheckAt).toLocaleString()}.`}
          </p>
          {data.board ? (
            <>
              <h3>
                Round {data.board.round} · {data.board.eventName}
              </h3>
              <p className="text-gray">
                Source: {data.board.source} · evidence checked{" "}
                {new Date(data.board.checkedAt).toLocaleString()}
              </p>
              <PaceLaneGrid
                key={`${year}-${data.board.round}-${condition}`}
                board={data.board}
                compact={compact}
              />
            </>
          ) : (
            <p className="notice">
              No cached completed-race pace board yet. The backend prepares it
              automatically after timing and results are published; standings do
              not stand in for measured pace.
            </p>
          )}
          {!compact && <HistoryGrid data={data} />}
          {!!data.board?.warnings.length && (
            <details>
              <summary>Source notices</summary>
              {data.board.warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </details>
          )}
        </>
      )}
    </section>
  );
}
