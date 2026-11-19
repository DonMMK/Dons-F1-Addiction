import type { CalendarEvent } from "../api";
export const browserZone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
export function formatEvent(event: CalendarEvent, zone: string) {
  if (event.dateOnly) {
    const fmt = (d: Date) =>
      d.toLocaleDateString(undefined, {
        timeZone: "UTC",
        month: "short",
        day: "numeric",
      });
    const start = new Date(`${event.start.slice(0, 10)}T12:00:00Z`);
    const end = event.end
      ? new Date(`${event.end.slice(0, 10)}T12:00:00Z`)
      : start;
    if (event.end) end.setUTCDate(end.getUTCDate() - 1);
    return `${fmt(start)}${end > start ? ` – ${fmt(end)}` : ""} · venue dates; session time TBC`;
  }
  return new Date(event.start).toLocaleString(undefined, {
    timeZone: zone,
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
export default function CalendarList({
  events,
  zone,
}: {
  events: CalendarEvent[];
  zone: string;
}) {
  return (
    <div className="calendar-list">
      {events.map((event) => (
        <article className="calendar-row" key={event.id}>
          <span className={`series-pill series-${event.series}`}>
            {event.series.toUpperCase()}
          </span>
          <div>
            <strong>{event.title}</strong>
            <p>{formatEvent(event, zone)}</p>
            <small className="text-gray">
              {event.source} · checked {event.verifiedAt.slice(0, 10)}
            </small>
          </div>
          <a href={event.sourceUrl} target="_blank" rel="noreferrer">
            Source ↗
          </a>
        </article>
      ))}
      {!events.length && (
        <p className="notice">No published sessions in this selection.</p>
      )}
    </div>
  );
}
