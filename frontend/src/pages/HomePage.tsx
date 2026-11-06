import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { StandingsResponse, CalendarResponse } from "../api";
import { useApi } from "../hooks/useApi";
import SeasonSelect from "../components/SeasonSelect";
import DataState from "../components/DataState";
import StandingsCircuit from "../components/StandingsCircuit";
import CalendarList, {
  browserZone,
  formatEvent,
} from "../components/CalendarList";

export default function HomePage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [kind, setKind] = useState<"drivers" | "constructors">("drivers");
  const [all, setAll] = useState(false);
  const [tick, setTick] = useState(Date.now());
  const [refresh, setRefresh] = useState(0);
  const standings = useApi<StandingsResponse>(`/standings/${year}`, refresh);
  const calendar = useApi<CalendarResponse>(`/calendar/f1/${year}`, refresh);
  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 1000);
    const reload = setInterval(() => setRefresh((v) => v + 1), 300000);
    return () => {
      clearInterval(timer);
      clearInterval(reload);
    };
  }, []);
  const next = calendar.data?.events.find(
    (e) => new Date(e.start).getTime() > tick,
  );
  const remaining = next
    ? Math.max(0, Math.floor((new Date(next.start).getTime() - tick) / 1000))
    : 0;
  const rows = standings.data?.[kind] ?? [];
  const zone = browserZone();
  return (
    <>
      <div className="page__header">
        <p className="eyebrow">THE SEASON, IN CONTEXT</p>
        <h1 className="page__title">The championship picture</h1>
        <p className="page__subtitle">
          Published standings, movement since the previous Grand Prix, and your
          next lights out.
        </p>
      </div>
      <div className="control-panel control-panel__row">
        <SeasonSelect value={year} onChange={setYear} />
        <button
          className="btn btn--secondary"
          onClick={() => setRefresh((v) => v + 1)}
        >
          Refresh data
        </button>
      </div>
      <section className="next-session">
        <p className="eyebrow">NEXT F1 SESSION · {zone}</p>
        {next ? (
          <>
            <h2>{next.title}</h2>
            <p>{formatEvent(next, zone)}</p>
            <strong className="countdown">
              {Math.floor(remaining / 86400)}d{" "}
              {Math.floor(remaining / 3600) % 24}h{" "}
              {Math.floor(remaining / 60) % 60}m {remaining % 60}s
            </strong>
          </>
        ) : (
          <p>
            {calendar.loading
              ? "Checking the schedule…"
              : `No later published session in ${year}. Select next season when its schedule is released.`}
          </p>
        )}
      </section>
      <DataState {...standings} />
      {standings.data && (
        <>
          <div className="section-heading">
            <div>
              <h2>Standings after round {standings.data.round ?? "—"}</h2>
              <p className="text-gray">
                {standings.data.comparison} Retrieved{" "}
                {new Date(standings.data.asOf).toLocaleString()}
              </p>
            </div>
            <div className="button-group">
              {(["drivers", "constructors"] as const).map((k) => (
                <button
                  className={`btn ${kind === k ? "btn--primary" : "btn--secondary"}`}
                  key={k}
                  aria-pressed={kind === k}
                  onClick={() => setKind(k)}
                >
                  {k === "drivers" ? "Drivers" : "Constructors"}
                </button>
              ))}
            </div>
          </div>
          {rows.length > 0 && (
            <StandingsCircuit
              key={kind}
              rows={rows}
              round={standings.data.round}
              previousRound={standings.data.previousRound}
            />
          )}
          <div className="table-scroll">
            <table className="f1-table">
              <thead>
                <tr>
                  <th>Pos</th>
                  <th>{kind === "drivers" ? "Driver" : "Constructor"}</th>
                  <th>Team</th>
                  <th>Points</th>
                  <th>Δ points</th>
                  <th>Δ places</th>
                  <th>Wins</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.position}</td>
                    <td className="font-bold">{r.name}</td>
                    <td>{r.team}</td>
                    <td>{r.points}</td>
                    <td>
                      {r.pointsChange == null
                        ? "—"
                        : `${r.pointsChange > 0 ? "+" : ""}${r.pointsChange}`}
                    </td>
                    <td
                      className={(r.positionChange ?? 0) > 0 ? "positive" : ""}
                    >
                      {r.positionChange == null
                        ? "—"
                        : `${r.positionChange > 0 ? "↑ " : r.positionChange < 0 ? "↓ " : ""}${Math.abs(r.positionChange)}`}
                    </td>
                    <td>{r.wins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && (
            <p className="notice">
              No standings published for this season yet.
            </p>
          )}
        </>
      )}
      <div className="section-heading">
        <h2>F1 calendar · your local time</h2>
        <button
          className="btn btn--secondary"
          onClick={() => setAll((v) => !v)}
        >
          {all ? "Show upcoming" : "Show full year"}
        </button>
      </div>
      <DataState {...calendar} />
      <CalendarList
        events={(calendar.data?.events ?? [])
          .filter((e) => all || new Date(e.start).getTime() > tick)
          .slice(0, all ? 200 : 10)}
        zone={zone}
      />
      <Link className="racing-link" to="/not-just-f1">
        <p className="eyebrow">NOT JUST F1</p>
        <h2>One calendar. A whole world of racing. ↗</h2>
        <p>WEC / Hypercar · IMSA · NLS · GT Europe · Supercars</p>
      </Link>
    </>
  );
}
