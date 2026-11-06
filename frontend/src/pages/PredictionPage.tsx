import { useEffect, useRef, useState } from "react";
import {
  request,
  type ModelCatalog,
  type EventInfo,
  type SessionInfo,
  type PredictionResponse,
  type RunSummary,
  type Evaluation,
} from "../api";
import { useApi } from "../hooks/useApi";
import SeasonSelect from "../components/SeasonSelect";
import DataState from "../components/DataState";

export default function PredictionPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [round, setRound] = useState("");
  const [session, setSession] = useState("Q");
  const [model, setModel] = useState("");
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [runId, setRunId] = useState("");
  const [evaluationRefresh, setEvaluationRefresh] = useState(0);
  const catalog = useApi<ModelCatalog>("/prediction/models");
  const schedule = useApi<{ events: EventInfo[] }>(
    `/prediction/grand-prix/${year}`,
  );
  const sessions = useApi<{ sessions: SessionInfo[] }>(
    round ? `/sessions/${year}/${round}` : null,
  );
  const history = useApi<{ runs: RunSummary[] }>(
    "/prediction/history",
    historyRefresh,
  );
  const evaluation = useApi<Evaluation>(
    runId ? `/prediction/evaluate/${encodeURIComponent(runId)}` : null,
    evaluationRefresh,
  );
  const pending = useRef<AbortController | null>(null);
  const selectedModel = catalog.data?.catalog.find((m) => m.id === model);
  const gp = schedule.data?.events.find(
    (e) => String(e.roundNumber) === round,
  )?.eventName;
  useEffect(() => {
    if (catalog.data) setModel(catalog.data.defaultModel);
  }, [catalog.data]);
  useEffect(() => {
    const ev = schedule.data?.events ?? [];
    const past = ev.filter((e) => new Date(e.date).getTime() <= Date.now());
    setRound(String((past.at(-1) ?? ev[0])?.roundNumber ?? ""));
  }, [schedule.data]);
  useEffect(() => {
    pending.current?.abort();
    setLoading(false);
    setResult(null);
    setError("");
  }, [year, round, session, model]);
  useEffect(() => () => pending.current?.abort(), []);
  const available = (sessions.data?.sessions ?? []).filter((s) =>
    selectedModel?.sessions.includes(s.key),
  );
  useEffect(() => {
    if (available.length && !available.some((s) => s.key === session))
      setSession(available[0].key);
  }, [available.map((s) => s.key).join(","), session]);
  async function run() {
    if (!gp || !model) return;
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await request<PredictionResponse>("/prediction/run", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({ year, gp, session, model }),
      });
      if (!controller.signal.aborted) {
        setResult(res);
        setRunId(res.runId);
        setHistoryRefresh((v) => v + 1);
      }
    } catch (e: unknown) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return (
    <>
      <div className="page__header">
        <p className="eyebrow">FORECAST. SAVE. CHECK.</p>
        <h1 className="page__title">Race Predictor</h1>
        <p className="page__subtitle">
          Versioned winner probabilities, saved forecasts and transparent
          post-race scores.
        </p>
      </div>
      <div className="control-panel control-panel__row">
        <SeasonSelect
          value={year}
          onChange={(y) => {
            setRound("");
            setYear(y);
          }}
        />
        <div className="form-group">
          <label htmlFor="prediction-gp">Grand Prix</label>
          <select
            id="prediction-gp"
            className="form-select"
            value={round}
            onChange={(e) => setRound(e.target.value)}
          >
            {schedule.data?.events.map((e) => (
              <option key={e.roundNumber} value={e.roundNumber}>
                {e.eventName}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="model">Model</label>
          <select
            id="model"
            className="form-select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {catalog.data?.catalog.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id} · {m.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="prediction-session">Input session</label>
          <select
            id="prediction-session"
            className="form-select"
            value={session}
            onChange={(e) => setSession(e.target.value)}
          >
            {available.map((s) => (
              <option key={s.key} value={s.key}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn btn--primary"
          disabled={
            loading ||
            !gp ||
            !model ||
            !available.some((s) => s.key === session)
          }
          onClick={run}
        >
          {loading ? "Running…" : "Run & save prediction"}
        </button>
      </div>
      <DataState {...catalog} />
      <DataState {...schedule} />
      <DataState {...sessions} />
      <DataState loading={loading} error={error} />
      {selectedModel && (
        <section className="model-card">
          <h2>What changed in {selectedModel.id}</h2>
          <ul>
            {selectedModel.improvements.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          {selectedModel.metrics ? (
            <>
              <p>
                Chronological hold-out: {selectedModel.metrics.events} races ·
                winner accuracy{" "}
                {(selectedModel.metrics.top1Accuracy * 100).toFixed(1)}% · Brier{" "}
                {selectedModel.metrics.brier} · log loss{" "}
                {selectedModel.metrics.logLoss}
              </p>
              <p>
                Trained through{" "}
                {new Date(selectedModel.trainedThrough!).toLocaleDateString()} ·{" "}
                {selectedModel.trainingEvents} races. A trained iteration can
                only forecast weekends after its training cutoff.
              </p>
              <div className="table-scroll">
                <table className="f1-table">
                  <thead>
                    <tr>
                      <th>Same test races</th>
                      <th>Brier ↓</th>
                      <th>Log loss ↓</th>
                      <th>Winner accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(selectedModel.baselines ?? {}).map(
                      ([name, m]) => (
                        <tr key={name}>
                          <td>
                            {name === "uniform"
                              ? "Equal probabilities"
                              : "50% to qualifying leader"}
                          </td>
                          <td>{m.brier}</td>
                          <td>{m.logLoss}</td>
                          <td>{(100 * m.top1Accuracy).toFixed(1)}%</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
              {selectedModel.previousComparable && (
                <p className="notice">
                  Previous eligible iteration on these same held-out races:
                  Brier {selectedModel.previousComparable.brier}, log loss{" "}
                  {selectedModel.previousComparable.logLoss}, winner accuracy{" "}
                  {(
                    100 * selectedModel.previousComparable.top1Accuracy
                  ).toFixed(1)}
                  %. Compare these scores with the candidate above; lower Brier
                  and log loss are better.
                </p>
              )}
              <p>
                {selectedModel.improvesGridLogLoss
                  ? "Lower held-out log loss than the qualifying-leader baseline."
                  : "No held-out log-loss improvement over the qualifying-leader baseline demonstrated."}
              </p>
            </>
          ) : (
            <p className="text-gray">
              Version changes are documented; benchmarked accuracy improvements
              are not established for this legacy model.
            </p>
          )}
          <ul className="text-gray">
            {selectedModel.limitations.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}
      {result && (
        <section className="results-panel">
          <div className="results-panel__header">
            <strong>
              {result.gp} {result.year} · {result.model}
            </strong>
            <span className="tag">{result.mode}</span>
          </div>
          <div className="results-panel__body">
            <p>
              Saved {new Date(result.createdAt).toLocaleString()} ·{" "}
              {result.monteCarloRuns
                ? `${result.monteCarloRuns.toLocaleString()} output counts / weights`
                : "Learned probabilities"}
            </p>
            {result.warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <div className="table-scroll">
              <table className="f1-table">
                <thead>
                  <tr>
                    <th>Winner rank</th>
                    <th>Driver</th>
                    <th>Win probability</th>
                  </tr>
                </thead>
                <tbody>
                  {result.predictions.map((p) => (
                    <tr key={p.driver}>
                      <td>{p.position}</td>
                      <td>{p.driver}</td>
                      <td>
                        <div className="probability-cell">
                          <span
                            className="probability-fill"
                            style={{ width: `${p.winProbability}%` }}
                          />
                          <strong>{p.winProbability.toFixed(2)}%</strong>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {result.winningMargins && (
              <p className="notice">
                Simulated winning margins:{" "}
                {Object.entries(result.winningMargins)
                  .map(([k, v]) => `${k}: ${v}%`)
                  .join(" · ")}
              </p>
            )}
          </div>
        </section>
      )}
      <section className="visual-panel">
        <h2>After the chequered flag</h2>
        <p className="text-gray">
          Score a stored winner distribution. Forecasts created after race start
          are labelled retrospective.
        </p>
        <div className="control-panel__row">
          <select
            aria-label="Saved prediction"
            className="form-select"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          >
            <option value="">Select a saved prediction…</option>
            {history.data?.runs.map((r) => (
              <option key={r.runId} value={r.runId}>
                {r.year} {r.gp} · {r.model} · {r.mode} ·{" "}
                {new Date(r.createdAt).toLocaleString()}
              </option>
            ))}
          </select>
          <button
            className="btn btn--secondary"
            disabled={!runId}
            onClick={() => setEvaluationRefresh((v) => v + 1)}
          >
            Check results
          </button>
        </div>
        <DataState {...history} />
        <DataState {...evaluation} />
        {evaluation.data?.status === "pending" && (
          <p className="notice">{evaluation.data.detail}</p>
        )}
        {evaluation.data?.status === "scored" && (
          <>
            <div className="stats-grid">
              <div>
                <small>ACTUAL WINNER</small>
                <strong>{evaluation.data.winner}</strong>
              </div>
              <div>
                <small>MODEL FAVOURITE</small>
                <strong>{evaluation.data.predictedWinner}</strong>
              </div>
              <div>
                <small>BRIER ↓</small>
                <strong>{evaluation.data.brier}</strong>
              </div>
              <div>
                <small>LOG LOSS ↓</small>
                <strong>{evaluation.data.logLoss}</strong>
              </div>
            </div>
            <p className="notice">
              {evaluation.data.mode} · actual winner had{" "}
              {evaluation.data.winnerProbability}% probability.{" "}
              {evaluation.data.note}
            </p>
            <details>
              <summary>
                Actual classification and saved win probabilities
              </summary>
              <table className="f1-table">
                <thead>
                  <tr>
                    <th>Finish</th>
                    <th>Driver</th>
                    <th>Saved win probability</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.data.results?.map((r) => (
                    <tr key={r.driver}>
                      <td>{r.position}</td>
                      <td>{r.driver}</td>
                      <td>{r.predictedProbability}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </section>
      <details className="methodology">
        <summary>Model history</summary>
        {catalog.data?.catalog.map((m) => (
          <p key={m.id}>
            <strong>{m.id}</strong> · {m.improvements.join(" · ")}
          </p>
        ))}
      </details>
    </>
  );
}
