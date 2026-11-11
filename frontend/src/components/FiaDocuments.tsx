import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";
import DataState from "./DataState";
import type { UpgradeTeam, WeekendEvidence } from "../weekendTypes";

type Report = WeekendEvidence["upgrades"];
const label = (status: string) =>
  ({
    declared_updates: "Declared component changes",
    declared_none: "No updates submitted",
    not_indexed: "Not indexed — unknown",
    unparsed: "Document needs review",
  })[status] ?? status;

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

export default function FiaDocuments({
  year,
  round,
  initial,
}: {
  year: number;
  round: string;
  initial: Report;
}) {
  const [refresh, setRefresh] = useState(0);
  const [lastGood, setLastGood] = useState(initial);
  const response = useApi<Report>(`/documents/${year}/${round}`, refresh);
  useEffect(() => {
    if (response.data) setLastGood(response.data);
  }, [response.data]);
  const data = response.data ?? lastGood;
  useEffect(() => {
    if (data.refresh?.enabled === false) return;
    // This polls our cached status, never bypasses the server's FIA check interval.
    const timer = setInterval(() => {
      if (document.visibilityState !== "hidden") setRefresh((v) => v + 1);
    }, 30000);
    return () => clearInterval(timer);
  }, [data.refresh?.enabled]);
  const state = data.refresh?.state ?? "queued";
  const status =
    (
      {
        queued: "Discovery queued",
        checking: "Checking FIA publications",
        indexed: "Published submissions indexed",
        not_published: "Not published or not yet discoverable",
        needs_review: "Published PDF needs parser review",
        error: "FIA check failed · cached evidence retained",
        disabled: "Automatic checks disabled",
        idle: "Waiting for the race weekend",
      } as Record<string, string>
    )[state] ?? state;
  return (
    <section className="visual-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">OFFICIAL SOURCES · AUTOMATIC DISCOVERY</p>
          <h2>Declared upgrades · this weekend</h2>
        </div>
        <span className="evidence-badge">{status}</span>
      </div>
      <div role="status" aria-live="polite" className="notice">
        <strong>{status}</strong>
        <p>
          {data.refresh?.message ??
            "The backend checks published FIA catalogues in the background."}
        </p>
        {data.refresh?.checkedAt && (
          <p>
            Last publication check:{" "}
            {new Date(data.refresh.checkedAt).toLocaleString()}
          </p>
        )}
        {data.refresh?.nextCheckAt && (
          <p>
            Next eligible check:{" "}
            {new Date(data.refresh.nextCheckAt).toLocaleString()}
          </p>
        )}
        <p>
          Cached evidence:{" "}
          {data.checkedAt
            ? new Date(data.checkedAt).toLocaleString()
            : "none yet"}
          . This view checks the local status every 30 seconds while visible.
        </p>
      </div>
      <button
        className="btn btn--secondary"
        disabled={response.loading}
        onClick={() => setRefresh((v) => v + 1)}
      >
        Check cached document status
      </button>
      <DataState {...response} />
      <p>{data.note}</p>
      <p>
        <a href={data.sourceUrl} target="_blank" rel="noreferrer">
          Official FIA source
        </a>
      </p>
      <UpgradeRows teams={data.teams} />
      <details>
        <summary>
          Official weekend documents · {data.documents?.length ?? 0} published
          links
        </summary>
        <p className="text-gray">
          Documents are discovered from the selected season and event. Links are
          source evidence; only supported car-presentation tables are parsed
          into upgrade records.
        </p>
        {(data.documents ?? []).map((d) => (
          <p key={d.url}>
            <a href={d.url} target="_blank" rel="noreferrer">
              {d.title}
            </a>
            {d.published && (
              <small className="text-gray"> · {d.published}</small>
            )}
          </p>
        ))}
        {!data.documents?.length && (
          <p>
            No published links have been discovered yet. The app will check
            again automatically.
          </p>
        )}
      </details>
      <details>
        <summary>Season upgrade timeline · indexed rounds only</summary>
        {data.timeline.map((r) => (
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
        {!data.timeline.length && (
          <p>
            No declarations have been indexed for this season yet. Missing
            records do not mean no upgrades.
          </p>
        )}
      </details>
    </section>
  );
}
