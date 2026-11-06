import { useMemo, useState } from "react";
import ICAL from "ical.js";
import type { CalendarEvent, CalendarResponse } from "../api";
import { useApi } from "../hooks/useApi";
import DataState from "../components/DataState";
import CalendarList, { browserZone } from "../components/CalendarList";

const SERIES: Record<string, string> = {
  f1: "Formula 1",
  wec: "WEC · Hypercar / LMGT3",
  imsa: "IMSA WeatherTech",
  nls: "Nürburgring NLS",
  "gt-europe": "GT World Challenge Europe",
  supercars: "Supercars",
};
const STORAGE = "f1-addiction-calendar-imports-v1";
function saved(): CalendarEvent[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE) ?? "[]");
    return Array.isArray(value)
      ? value.filter(
          (e) =>
            typeof e.start === "string" &&
            typeof e.series === "string" &&
            typeof e.sourceUrl === "string" &&
            e.sourceUrl.startsWith("https://"),
        )
      : [];
  } catch {
    return [];
  }
}
export default function MotorsportPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState("");
  const [active, setActive] = useState(Object.keys(SERIES));
  const [zone, setZone] = useState(browserZone());
  const [imports, setImports] = useState<CalendarEvent[]>(saved);
  const [series, setSeries] = useState("wec");
  const [source, setSource] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const report = useApi<CalendarResponse>(`/calendar/motorsport/${year}`);
  const events = useMemo(() => {
    const overrides = new Set(
      imports.filter((e) => +e.start.slice(0, 4) === year).map((e) => e.series),
    );
    return [
      ...(report.data?.events ?? []).filter((e) => !overrides.has(e.series)),
      ...imports.filter((e) => +e.start.slice(0, 4) === year),
    ]
      .filter((e) => active.includes(e.series))
      .filter((e) => {
        if (!month) return true;
        if (e.dateOnly) {
          const end = new Date(`${(e.end ?? e.start).slice(0, 10)}T12:00:00Z`);
          if (e.end) end.setUTCDate(end.getUTCDate() - 1);
          const selectedMonth = `${year}-${month}`;
          return (
            e.start.slice(0, 7) <= selectedMonth &&
            end.toISOString().slice(0, 7) >= selectedMonth
          );
        }
        return (
          new Intl.DateTimeFormat("en-CA", {
            timeZone: zone,
            month: "2-digit",
          }).format(new Date(e.start)) === month
        );
      })
      .sort((a, b) => a.start.localeCompare(b.start));
  }, [report.data, imports, year, month, active, zone]);
  async function importFile(file: File | undefined) {
    if (!file) return;
    setError("");
    setStatus("");
    try {
      const url = new URL(source);
      if (url.protocol !== "https:")
        throw new Error(
          "Use an HTTPS publisher link to identify the calendar source.",
        );
      if (file.size > 2_000_000)
        throw new Error("Choose a calendar smaller than 2 MB.");
      const root = new ICAL.Component(ICAL.parse(await file.text()));
      root
        .getAllSubcomponents("vtimezone")
        .forEach((c) => ICAL.TimezoneService.register(new ICAL.Timezone(c)));
      const components = root.getAllSubcomponents("vevent");
      if (components.length > 2000)
        throw new Error("Import at most 2,000 sessions at once.");
      const parsed: CalendarEvent[] = components.flatMap((c) => {
        if (c.getFirstPropertyValue("status") === "CANCELLED") return [];
        if (c.hasProperty("rrule") || c.hasProperty("recurrence-id"))
          throw new Error(
            "Import a calendar with individual sessions; recurring entries need expansion first.",
          );
        const e = new ICAL.Event(c),
          start = e.startDate,
          end = e.endDate;
        if (!start) throw new Error("An event has no start date.");
        if (!start.isDate && start.zone.tzid === "floating")
          throw new Error(
            "A session has no timezone. Download a calendar with UTC or TZID times.",
          );
        if (
          !start.isDate &&
          start.zone.tzid !== "UTC" &&
          start.zone.tzid !== "Z" &&
          !root
            .getAllSubcomponents("vtimezone")
            .some((t) => t.getFirstPropertyValue("tzid") === start.zone.tzid)
        )
          throw new Error(
            "Calendar timezone definition is missing. Use a UTC export or one containing VTIMEZONE.",
          );
        const stamp = start.isDate
          ? start.toString()
          : start.toJSDate().toISOString();
        if (+stamp.slice(0, 4) !== year) return [];
        return [
          {
            id: `import-${series}-${e.uid || stamp}`,
            series,
            title: e.summary || "Session",
            event: e.summary || "Session",
            start: stamp,
            end: end
              ? end.isDate
                ? end.toString()
                : end.toJSDate().toISOString()
              : null,
            dateOnly: start.isDate,
            location: e.location || "",
            source: "Your imported calendar",
            sourceUrl: url.href,
            verifiedAt: new Date().toISOString(),
            status: "Imported publisher schedule",
          },
        ];
      });
      if (!parsed.length)
        throw new Error(`No sessions for ${year} in this file.`);
      const next = [
        ...imports.filter(
          (e) => e.series !== series || +e.start.slice(0, 4) !== year,
        ),
        ...parsed,
      ];
      localStorage.setItem(STORAGE, JSON.stringify(next));
      setImports(next);
      setStatus(
        `Imported ${parsed.length} entries for ${SERIES[series]}. This browser keeps your copy.`,
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Calendar import failed");
    }
  }
  return (
    <>
      <div className="page__header">
        <p className="eyebrow">NOT JUST F1</p>
        <h1 className="page__title">Your year in racing</h1>
        <p className="page__subtitle">
          Endurance, GT and touring cars in one place. Hypercar is included
          within WEC; IMSA prototypes appear within IMSA.
        </p>
      </div>
      <div className="control-panel control-panel__row">
        <div className="form-group">
          <label htmlFor="calendar-year">Year</label>
          <input
            id="calendar-year"
            className="form-select"
            type="number"
            min="2018"
            max="2100"
            value={year}
            onChange={(e) => setYear(+e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="month">Month</label>
          <select
            id="month"
            className="form-select"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          >
            <option value="">Whole year</option>
            {Array.from({ length: 12 }, (_, i) => (
              <option key={i} value={String(i + 1).padStart(2, "0")}>
                {new Date(2026, i, 1).toLocaleString(undefined, {
                  month: "long",
                })}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="timezone">Display timezone</label>
          <select
            id="timezone"
            className="form-select"
            value={zone}
            onChange={(e) => setZone(e.target.value)}
          >
            {[
              ...new Set([
                browserZone(),
                "UTC",
                "Australia/Brisbane",
                "Australia/Sydney",
                "Europe/London",
                "Europe/Berlin",
                "America/New_York",
                "America/Los_Angeles",
                "Asia/Tokyo",
              ]),
            ].map((z) => (
              <option key={z}>{z}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="series-filters">
        {Object.entries(SERIES).map(([key, label]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={active.includes(key)}
              onChange={() =>
                setActive((v) =>
                  v.includes(key) ? v.filter((k) => k !== key) : [...v, key],
                )
              }
            />
            {label}
          </label>
        ))}
      </div>
      <p className="notice">
        Timed sessions use {zone}, including daylight-saving rules. Date-only
        events retain venue dates and show “session time TBC”. Other-series
        dates are a checked-in 2026 snapshot; use the linked organiser schedule
        for changes.
      </p>
      <DataState {...report} />
      {report.data?.warnings?.map((w) => (
        <p className="notice" key={w}>
          {w}
        </p>
      ))}
      <CalendarList events={events} zone={zone} />
      <details className="methodology">
        <summary>Add or update a series from a publisher calendar</summary>
        <p>
          Download an .ics calendar from the organiser and import it here. It
          replaces this series’ displayed entries for the selected year in this
          browser.
        </p>
        <div className="control-panel__row">
          <select
            aria-label="Import series"
            className="form-select"
            value={series}
            onChange={(e) => setSeries(e.target.value)}
          >
            {Object.entries(SERIES)
              .filter(([k]) => k !== "f1")
              .map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
          </select>
          <input
            className="form-select"
            type="url"
            aria-label="Publisher source URL"
            placeholder="https://organiser.example/calendar"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          />
          <input
            aria-label="Calendar file"
            type="file"
            accept=".ics,text/calendar"
            onChange={(e) => {
              void importFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
        <p role="alert" className="text-red">
          {error}
        </p>
        <p role="status">{status}</p>
        {imports.length > 0 && (
          <button
            className="btn btn--secondary"
            onClick={() => {
              localStorage.removeItem(STORAGE);
              setImports([]);
              setStatus(
                "Imported calendars cleared; publisher snapshots restored.",
              );
            }}
          >
            Clear imported calendars
          </button>
        )}
      </details>
    </>
  );
}
