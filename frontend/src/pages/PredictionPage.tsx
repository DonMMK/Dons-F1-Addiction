import { useState, useEffect } from 'react'
import {
  fetchModels,
  fetchGrandPrix,
  runPrediction,
  type PredictionResponse,
  type EventInfo,
} from '../api'
import Spinner from '../components/Spinner'

const SESSION_OPTIONS = [
  { key: 'FP1', label: 'Free Practice 1' },
  { key: 'FP2', label: 'Free Practice 2' },
  { key: 'FP3', label: 'Free Practice 3' },
  { key: 'Q', label: 'Qualifying' },
]

export default function PredictionPage() {
  const [models, setModels] = useState<string[]>([])
  const [events, setEvents] = useState<EventInfo[]>([])

  const [year, setYear] = useState(2025)
  const [gp, setGp] = useState('')
  const [session, setSession] = useState('Q')
  const [model, setModel] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<PredictionResponse | null>(null)

  // Fetch models on mount
  useEffect(() => {
    fetchModels()
      .then((r) => {
        setModels(r.models)
        if (r.models.length) setModel(r.models[r.models.length - 1]) // default to latest
      })
      .catch(() => {})
  }, [])

  // Fetch events when year changes
  useEffect(() => {
    fetchGrandPrix(year)
      .then((r) => {
        setEvents(r.events)
        if (r.events.length) setGp(r.events[0].eventName)
      })
      .catch(() => setEvents([]))
  }, [year])

  const handleRun = async () => {
    if (!gp || !model) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await runPrediction({ year, gp, session, model })
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Prediction failed')
    } finally {
      setLoading(false)
    }
  }

  const maxProb = result ? Math.max(...result.predictions.map((p) => p.winProbability)) : 1

  return (
    <>
      <div className="page__header">
        <h1 className="page__title">Race Prediction</h1>
        <p className="page__subtitle">
          Monte Carlo simulation — select a model version, season, Grand Prix, and session to predict
          race outcomes.
        </p>
      </div>

      {/* ── Controls ─────────────────────────────────────────────── */}
      <div className="control-panel">
        <div className="control-panel__row">
          <div className="form-group">
            <label>Season</label>
            <select className="form-select" value={year} onChange={(e) => setYear(+e.target.value)}>
              {Array.from({ length: 9 }, (_, i) => 2018 + i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Grand Prix</label>
            <select className="form-select" value={gp} onChange={(e) => setGp(e.target.value)}>
              {events.map((ev) => (
                <option key={ev.roundNumber} value={ev.eventName}>{ev.eventName}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Session</label>
            <select className="form-select" value={session} onChange={(e) => setSession(e.target.value)}>
              {SESSION_OPTIONS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Model Version</label>
            <select className="form-select" value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <button className="btn btn--primary" onClick={handleRun} disabled={loading || !gp}>
            {loading ? 'Running…' : 'Run Prediction'}
          </button>
        </div>
      </div>

      {/* ── Loading / Error ─────────────────────────────────────── */}
      {loading && <Spinner text="Running Monte Carlo simulation…" />}
      {error && <p style={{ color: 'var(--f1-red)', marginBottom: '1rem' }}>⚠ {error}</p>}

      {/* ── Results ─────────────────────────────────────────────── */}
      {result && (
        <div className="results-panel">
          <div className="results-panel__header">
            <span className="results-panel__title">
              {result.gp} GP {result.year} — {result.sessionLabel}
            </span>
            <span className="text-gray" style={{ fontSize: '0.8rem' }}>
              {result.monteCarloRuns.toLocaleString()} simulations &middot; Model: {result.model}
            </span>
          </div>
          <div className="results-panel__body">
            <table className="f1-table">
              <thead>
                <tr>
                  <th style={{ width: 48 }}>Pos</th>
                  <th>Driver</th>
                  <th>Win Probability</th>
                  <th style={{ width: 80 }}>%</th>
                </tr>
              </thead>
              <tbody>
                {result.predictions.slice(0, 20).map((p) => (
                  <tr key={p.driver}>
                    <td className={p.position <= 3 ? `pos-${p.position}` : ''}>
                      {p.position}
                    </td>
                    <td className="font-bold">{p.driver}</td>
                    <td>
                      <div className="prob-bar">
                        <div
                          className="prob-bar__fill"
                          style={{ width: `${(p.winProbability / maxProb) * 100}%`, maxWidth: '100%' }}
                        />
                      </div>
                    </td>
                    <td className="prob-bar__label">{p.winProbability}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
