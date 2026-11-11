import { useEffect, useMemo, useRef, useState } from "react";
import type { LapData, TelemetryData } from "../api";
import CarGlyph, { teamColor } from "./CarGlyph";

function sample(tel: TelemetryData, elapsed: number) {
  const times = tel.time,
    offset = times[0] ?? 0;
  let i = 0;
  while (i < times.length - 2 && times[i + 1] - offset < elapsed) i++;
  const j = Math.min(i + 1, times.length - 1),
    a = times[i] - offset,
    b = times[j] - offset;
  const fraction = Math.max(0, Math.min(1, (elapsed - a) / (b - a || 1)));
  return {
    x: tel.x[i] + (tel.x[j] - tel.x[i]) * fraction,
    y: tel.y[i] + (tel.y[j] - tel.y[i]) * fraction,
    speed: tel.speed[i],
    gear: tel.gear[i],
  };
}
export default function LapReplay({
  first,
  second,
}: {
  first: LapData;
  second: LapData;
}) {
  const [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  const clock = useRef<number | null>(null);
  const duration = Math.max(
    first.telemetry.time.at(-1)! - first.telemetry.time[0],
    second.telemetry.time.at(-1)! - second.telemetry.time[0],
  );
  useEffect(() => {
    setTime(0);
    setPlaying(false);
  }, [first, second]);
  useEffect(() => {
    if (!playing) return;
    let handle = 0;
    clock.current = null;
    const animate = (now: number) => {
      if (clock.current != null) {
        const dt = ((now - clock.current) / 1000) * speed;
        setTime((t) => Math.min(duration, t + dt));
      }
      clock.current = now;
      handle = requestAnimationFrame(animate);
    };
    handle = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(handle);
  }, [playing, speed, duration]);
  useEffect(() => {
    if (time >= duration) setPlaying(false);
  }, [time, duration]);
  const bounds = useMemo(() => {
    const xs = [...first.telemetry.x, ...second.telemetry.x],
      ys = [...first.telemetry.y, ...second.telemetry.y];
    const minX = Math.min(...xs),
      maxX = Math.max(...xs),
      minY = Math.min(...ys),
      maxY = Math.max(...ys);
    const scale = Math.min(820 / (maxX - minX || 1), 430 / (maxY - minY || 1));
    return { minX, minY, scale };
  }, [first, second]);
  const norm = (x: number, y: number) => ({
    x: 80 + (x - bounds.minX) * bounds.scale,
    y: 490 - (y - bounds.minY) * bounds.scale,
  });
  const path = first.telemetry.x
    .map((x, i) => {
      const p = norm(x, first.telemetry.y[i]);
      return `${p.x},${p.y}`;
    })
    .join(" ");
  return (
    <section className="visual-panel">
      <div className="section-heading">
        <h2>Bird’s-eye lap replay</h2>
        <span className="tag">Recorded position samples</span>
      </div>
      <p className="text-gray">
        Both fastest laps start together at t=0. Position is interpolated
        between samples; this is not a reconstruction of an on-track battle.
      </p>
      <svg
        viewBox="0 0 1000 550"
        className="lap-replay"
        role="img"
        aria-label="Two fastest laps replayed on the recorded circuit"
      >
        <polyline
          points={path}
          fill="none"
          stroke="#48485d"
          strokeWidth="18"
          strokeLinejoin="round"
        />
        {[first, second].map((d, index) => {
          const point = sample(
            d.telemetry,
            Math.min(time, d.telemetry.time.at(-1)! - d.telemetry.time[0]),
          );
          const p = norm(point.x, point.y),
            next = sample(
              d.telemetry,
              Math.min(
                time + 0.2,
                d.telemetry.time.at(-1)! - d.telemetry.time[0],
              ),
            ),
            nextP = norm(next.x, next.y);
          const angle =
            (Math.atan2(nextP.y - p.y, nextP.x - p.x) * 180) / Math.PI + 90;
          return (
            <g key={index} transform={`translate(${p.x} ${p.y})`}>
              <g transform={`rotate(${angle}) scale(.8)`}>
                <CarGlyph color={teamColor(d.team)} />
              </g>
              <text
                x="20"
                y={index ? 22 : -15}
                fill={teamColor(d.team)}
                fontSize="17"
                fontWeight="bold"
              >
                {d.abbreviation ?? d.driver}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="replay-controls">
        <button
          className="btn btn--primary"
          onClick={() => {
            if (time >= duration) setTime(0);
            setPlaying((v) => !v);
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button
          className="btn btn--secondary"
          onClick={() => {
            setTime(0);
            setPlaying(false);
          }}
        >
          Reset
        </button>
        <input
          aria-label="Lap playback position"
          type="range"
          min="0"
          max={duration}
          step="0.05"
          value={time}
          onChange={(e) => setTime(+e.target.value)}
        />
        <span>
          {time.toFixed(1)} / {duration.toFixed(1)} s
        </span>
        <select
          aria-label="Playback speed"
          className="form-select"
          value={speed}
          onChange={(e) => setSpeed(+e.target.value)}
        >
          {[0.25, 0.5, 1, 2, 4].map((v) => (
            <option key={v} value={v}>
              {v}×
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}
