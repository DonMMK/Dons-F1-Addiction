import { useState, useEffect, useMemo } from 'react'
import {
  fetchSchedule,
  fetchSessions,
  fetchDrivers,
  fetchComparison,
  type EventInfo,
  type SessionInfo,
  type DriverInfo,
  type ComparisonResponse,
} from '../api'
import Spinner from '../components/Spinner'
import TrackMap from '../components/TrackMap'
import TelemetryChart from '../components/TelemetryChart'
import type { LapData } from '../api'

function driverName(d: LapData): string {
  return d.abbreviation ?? d.driver ?? '???'
}

export default function GhostCarPage() {
  const [year, setYear] = useState(2025)
  const [events, setEvents] = useState<EventInfo[]>([])
  const [round, setRound] = useState<number | null>(null)
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [sessionKey, setSessionKey] = useState('')
  const [drivers, setDrivers] = useState<DriverInfo[]>([])
  const [driver1, setDriver1] = useState('')
  const [driver2, setDriver2] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState<ComparisonResponse | null>(null)

  // Fetch schedule
  useEffect(() => {
    fetchSchedule(year).then((r) => {
      const races = r.events.filter((e) => !e.isTesting)
      setEvents(races)
      if (races.length) setRound(races[0].roundNumber)
    }).catch(() => {})
  }, [year])

  // Fetch sessions when round changes
  useEffect(() => {
    if (round == null) return
    fetchSessions(year, round).then((r) => {
      setSessions(r.sessions)
      if (r.sessions.length) setSessionKey(r.sessions[0].key)
    }).catch(() => {})
  }, [year, round])

  // Fetch drivers when session changes
  useEffect(() => {
    if (round == null || !sessionKey) return
    fetchDrivers(year, round, sessionKey).then((r) => {
      setDrivers(r.drivers)
      if (r.drivers.length >= 2) {
        setDriver1(r.drivers[0].abbreviation)
        setDriver2(r.drivers[1].abbreviation)
      }
    }).catch(() => {})
  }, [year, round, sessionKey])

  const handleCompare = async () => {
    if (round == null || !sessionKey || !driver1 || !driver2) return
    setLoading(true)
    setError('')
    setData(null)
    try {
      const res = await fetchComparison(year, round, sessionKey, driver1, driver2)
      setData(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Comparison failed')
    } finally {
      setLoading(false)
    }
  }

  // Sample distance points for charts (take every 5th point for perf)
  const chartData = useMemo(() => {
    if (!data) return null
    const c = data.comparison
    const step = 5
    const rows = []
    for (let i = 0; i < c.distance.length; i += step) {
      rows.push({
        distance: Math.round(c.distance[i]),
        [driverName(data.driver1)]: Math.round(c.speed1[i]),
        [driverName(data.driver2)]: Math.round(c.speed2[i]),
        delta: c.speedDelta[i],
      })
    }
    return rows
  }, [data])

  const gapStr = data
    ? (data.driver1.lapTimeSeconds - data.driver2.lapTimeSeconds).toFixed(3)
    : null

  return (
    <>
      <div className="page__header">
        <h1 className="page__title">Ghost Car Comparison</h1>
        <p className="page__subtitle">
          Compare two drivers' fastest laps — telemetry overlay on the track map with speed, throttle, and brake traces.
        </p>
      </div>

      {/* ── Controls ──────────────────────────────────────────── */}
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
            <select className="form-select" value={round ?? ''} onChange={(e) => setRound(+e.target.value)}>
              {events.map((ev) => (
                <option key={ev.roundNumber} value={ev.roundNumber}>{ev.eventName}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Session</label>
            <select className="form-select" value={sessionKey} onChange={(e) => setSessionKey(e.target.value)}>
              {sessions.map((s) => (
                <option key={s.key} value={s.key}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Driver 1</label>
            <select className="form-select" value={driver1} onChange={(e) => setDriver1(e.target.value)}>
              {drivers.map((d) => (
                <option key={d.abbreviation} value={d.abbreviation}>
                  {d.abbreviation} — {d.team}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Driver 2</label>
            <select className="form-select" value={driver2} onChange={(e) => setDriver2(e.target.value)}>
              {drivers.map((d) => (
                <option key={d.abbreviation} value={d.abbreviation}>
                  {d.abbreviation} — {d.team}
                </option>
              ))}
            </select>
          </div>

          <button className="btn btn--primary" onClick={handleCompare} disabled={loading || driver1 === driver2}>
            {loading ? 'Loading…' : 'Compare'}
          </button>
        </div>
      </div>

      {loading && <Spinner text="Loading telemetry data…" />}
      {error && <p style={{ color: 'var(--f1-red)', marginBottom: '1rem' }}>⚠ {error}</p>}

      {data && (
        <>
          {/* ── Lap Summary ──────────────────────────────────── */}
          <div className="grid-2 mb-3">
            <DriverCard driver={data.driver1} />
            <DriverCard driver={data.driver2} />
          </div>

          {gapStr && (
            <p className="text-center mb-3" style={{ fontSize: '1.2rem' }}>
              Gap: <span className="font-black text-red">{Number(gapStr) > 0 ? '+' : ''}{gapStr}s</span>
            </p>
          )}

          {/* ── Track Map ────────────────────────────────────── */}
          <TrackMap
            x1={data.driver1.telemetry.x}
            y1={data.driver1.telemetry.y}
            x2={data.driver2.telemetry.x}
            y2={data.driver2.telemetry.y}
            label1={driverName(data.driver1)}
            label2={driverName(data.driver2)}
          />

          {/* ── Telemetry Charts ──────────────────────────────── */}
          {chartData && (
            <div className="telemetry-section">
              <TelemetryChart
                title="Speed (km/h)"
                data={chartData}
                dataKey1={driverName(data.driver1)}
                dataKey2={driverName(data.driver2)}
                color1="var(--f1-red)"
                color2="var(--team-mercedes)"
              />
              <TelemetryChart
                title="Speed Delta"
                data={chartData}
                dataKey1="delta"
                color1="var(--f1-red)"
                isArea
              />
            </div>
          )}
        </>
      )}
    </>
  )
}

function DriverCard({ driver }: { driver: ComparisonResponse['driver1'] }) {
  return (
    <div className="card">
      <div className="card__accent" />
      <div className="card__body">
        <h3 className="card__title">{driverName(driver)}</h3>
        <p className="card__text">
          {driver.team} &middot; {driver.compound} &middot;{' '}
          <span className="font-bold" style={{ color: 'var(--f1-white)' }}>{driver.lapTime}</span>
        </p>
      </div>
    </div>
  )
}
