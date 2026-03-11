import { useState, useEffect, useMemo } from 'react'
import {
  fetchEras,
  fetchEraDetail,
  fetchSeasonProgression,
  fetchGapToLeader,
  type EraConfig,
} from '../api'
import Spinner from '../components/Spinner'
import TelemetryChart from '../components/TelemetryChart'

export default function BestCarPage() {
  const [erasMap, setErasMap] = useState<Record<string, string>>({})
  const [eraKey, setEraKey] = useState('')
  const [era, setEra] = useState<EraConfig | null>(null)
  const [progressionData, setProgressionData] = useState<{ round: number; race: string; gap: number }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Gap to leader for a selected race
  const [gapRace, setGapRace] = useState('')
  const [gapData, setGapData] = useState<{ driver: string; team: string; gap: number }[]>([])
  const [gapLoading, setGapLoading] = useState(false)

  // Fetch eras
  useEffect(() => {
    fetchEras().then((r) => {
      setErasMap(r.eras)
      const keys = Object.keys(r.eras)
      if (keys.length) setEraKey(keys[keys.length - 1])
    }).catch(() => {})
  }, [])

  // Fetch era detail + progression
  useEffect(() => {
    if (!eraKey) return
    setLoading(true)
    setError('')
    Promise.all([fetchEraDetail(eraKey), fetchSeasonProgression(eraKey)])
      .then(([eraRes, progRes]) => {
        setEra(eraRes)
        setProgressionData(progRes.progression)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Load error'))
      .finally(() => setLoading(false))
  }, [eraKey])

  // Convert progression for TelemetryChart
  const chartData = useMemo(
    () => progressionData.map((p) => ({ distance: p.round, gap: p.gap })),
    [progressionData],
  )

  const handleGapLoad = async () => {
    if (!gapRace || !era) return
    setGapLoading(true)
    try {
      const res = await fetchGapToLeader(era.year, gapRace)
      setGapData(res.gaps)
    } catch {
      /* ignore */
    } finally {
      setGapLoading(false)
    }
  }

  return (
    <>
      <div className="page__header">
        <h1 className="page__title">Best Car Analysis</h1>
        <p className="page__subtitle">
          Compare dominant cars across eras — qualifying gaps, season progression, and performance
          metrics.
        </p>
      </div>

      {/* ── Era Selector ──────────────────────────────────────── */}
      <div className="control-panel">
        <div className="control-panel__row">
          <div className="form-group">
            <label>Era</label>
            <select className="form-select" value={eraKey} onChange={(e) => setEraKey(e.target.value)}>
              {Object.entries(erasMap).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading && <Spinner text="Loading era data…" />}
      {error && <p style={{ color: 'var(--f1-red)' }}>⚠ {error}</p>}

      {era && !loading && (
        <>
          {/* ── Era Overview Cards ────────────────────────────── */}
          <div className="grid-3 mb-3">
            <CarCard label="Primary" car={era.primaryCar} />
            {era.competitors.map((c) => (
              <CarCard key={c.team} label="Competitor" car={c} />
            ))}
          </div>

          {/* ── Season Progression Chart ──────────────────────── */}
          {chartData.length > 0 && (
            <div className="mb-3">
              <TelemetryChart
                title={`${era.primaryCar.team} – Qualifying Gap to Leader (s)`}
                data={chartData}
                dataKey1="gap"
                color1={era.primaryCar.color}
                isArea
              />
            </div>
          )}

          {/* ── Race Gap Lookup ────────────────────────────────── */}
          <div className="control-panel">
            <div className="control-panel__row">
              <div className="form-group">
                <label>Race (for gap breakdown)</label>
                <select className="form-select" value={gapRace} onChange={(e) => setGapRace(e.target.value)}>
                  <option value="">Select a race…</option>
                  {progressionData.map((p) => (
                    <option key={p.round} value={p.race}>{p.race}</option>
                  ))}
                </select>
              </div>
              <button className="btn btn--secondary" onClick={handleGapLoad} disabled={!gapRace || gapLoading}>
                {gapLoading ? 'Loading…' : 'Load Gaps'}
              </button>
            </div>
          </div>

          {gapData.length > 0 && (
            <div className="results-panel mt-2">
              <div className="results-panel__header">
                <span className="results-panel__title">Gap to Leader — {gapRace}</span>
              </div>
              <div className="results-panel__body">
                <table className="f1-table">
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>Pos</th>
                      <th>Driver</th>
                      <th>Team</th>
                      <th>Gap (s)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gapData.map((g, i) => (
                      <tr key={g.driver}>
                        <td className={i < 3 ? `pos-${i + 1}` : ''}>{i + 1}</td>
                        <td className="font-bold">{g.driver}</td>
                        <td className="text-gray">{g.team}</td>
                        <td>{i === 0 ? '—' : `+${g.gap.toFixed(3)}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}

function CarCard({ label, car }: { label: string; car: EraConfig['primaryCar'] }) {
  return (
    <div className="card">
      <div className="card__accent" style={{ background: car.color }} />
      <div className="card__body">
        <p className="text-gray" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {label}
        </p>
        <h3 className="card__title">{car.car}</h3>
        <p className="card__text">
          {car.team} &middot; {car.drivers.join(' / ')}
        </p>
      </div>
    </div>
  )
}
