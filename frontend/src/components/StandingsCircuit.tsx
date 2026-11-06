import { useState } from "react";
import type { Standing } from "../api";
import CarGlyph, { teamColor } from "./CarGlyph";

export default function StandingsCircuit({
  rows,
  previousRound,
  round,
}: {
  rows: Standing[];
  previousRound: number | null;
  round: number | null;
}) {
  const [current, setCurrent] = useState(true);
  const [selected, setSelected] = useState("");
  const focus = rows.find((r) => r.id === selected);
  return (
    <section className="visual-panel">
      <div className="section-heading">
        <div>
          <h2>Championship on track</h2>
          <p className="text-gray">
            Schematic rank positions · spacing does not represent seconds or
            points
          </p>
        </div>
        <button
          className="btn btn--secondary"
          disabled={!previousRound}
          onClick={() => setCurrent((v) => !v)}
        >
          {current
            ? `Replay change from round ${previousRound ?? "—"}`
            : `Show round ${round}`}
        </button>
      </div>
      <svg
        className="standings-circuit"
        viewBox="0 0 1000 550"
        role="img"
        aria-label={`Championship positions after round ${current ? round : previousRound}`}
      >
        <ellipse
          cx="500"
          cy="260"
          rx="405"
          ry="185"
          fill="none"
          stroke="#39394d"
          strokeWidth="68"
        />
        <ellipse
          cx="500"
          cy="260"
          rx="405"
          ry="185"
          fill="none"
          stroke="#77778a"
          strokeDasharray="10 16"
        />
        <text
          x="500"
          y="240"
          textAnchor="middle"
          fill="#fff"
          fontSize="30"
          fontWeight="900"
        >
          ROUND {current ? round : previousRound}
        </text>
        <text x="500" y="275" textAnchor="middle" fill="#aaaabe" fontSize="16">
          {current ? "Current order" : "Previous published order"}
        </text>
        {rows.map((row) => {
          const pos = current ? row.position : row.previousPosition;
          if (pos == null) return null;
          const angle =
            -Math.PI / 2 + ((pos - 1) * 2 * Math.PI) / Math.max(rows.length, 1);
          const x = 500 + 405 * Math.cos(angle),
            y = 260 + 185 * Math.sin(angle);
          return (
            <g
              key={row.id}
              className="rank-car"
              style={{ transform: `translate(${x}px, ${y}px)` }}
              role="button"
              tabIndex={0}
              aria-label={`${row.name}, position ${pos}`}
              onClick={() => setSelected(row.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") setSelected(row.id);
              }}
            >
              <title>
                {row.name} · P{pos} ·{" "}
                {current ? row.points : row.previousPoints} points
              </title>
              <CarGlyph
                color={teamColor(row.team)}
                label={
                  row.label.length > 10 ? row.label.slice(0, 10) : row.label
                }
              />
              <text x="22" y="4" fontSize="13" fill="#fff">
                {pos}
              </text>
            </g>
          );
        })}
      </svg>
      {focus && (
        <p className="notice">
          {focus.name} · {focus.points} points ·{" "}
          {focus.positionChange == null
            ? "No previous snapshot"
            : `${focus.positionChange > 0 ? "+" : ""}${focus.positionChange} places`}{" "}
          · {focus.pointsChange ?? "—"} points since last round
        </p>
      )}
    </section>
  );
}
