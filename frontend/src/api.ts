const BASE = "/api";

export async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

/* ── Common ─────────────────────────────────────────────────────── */

export const fetchSeasons = () => request<{ seasons: number[] }>("/seasons");

export const fetchSchedule = (year: number) =>
  request<{ year: number; events: EventInfo[] }>(`/schedule/${year}`);

export const fetchSessions = (year: number, round: number) =>
  request<{ sessions: SessionInfo[] }>(`/sessions/${year}/${round}`);

export const fetchDrivers = (year: number, round: number, session: string) =>
  request<{ drivers: DriverInfo[] }>(`/drivers/${year}/${round}/${session}`);

/* ── Prediction ─────────────────────────────────────────────────── */

export const fetchModels = () =>
  request<{ models: string[] }>("/prediction/models");

export interface PredictionResult {
  position: number;
  driver: string;
  winProbability: number;
}

export interface PredictionResponse {
  year: number;
  gp: string;
  session: string;
  sessionLabel: string;
  model: string;
  monteCarloRuns: number;
  predictions: PredictionResult[];
  runId: string;
  mode: string;
  createdAt: string;
  warnings: string[];
  winningMargins: Record<string, number> | null;
}

export const runPrediction = (body: {
  year: number;
  gp: string;
  session: string;
  model: string;
}) =>
  request<PredictionResponse>("/prediction/run", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const fetchGrandPrix = (year: number) =>
  request<{ year: number; events: EventInfo[] }>(
    `/prediction/grand-prix/${year}`,
  );

/* ── Ghost Car ──────────────────────────────────────────────────── */

export interface TelemetryData {
  x: number[];
  y: number[];
  speed: number[];
  throttle: number[];
  brake: number[];
  gear: number[];
  distance: number[];
  time: number[];
  drs: number[];
}

export interface LapData {
  driver?: string;
  abbreviation?: string;
  team: string;
  lapTime: string;
  lapTimeSeconds: number;
  compound: string;
  telemetry: TelemetryData;
}

export interface ComparisonResponse {
  eventName: string;
  driver1: LapData;
  driver2: LapData;
  comparison: {
    distance: number[];
    speed1: number[];
    speed2: number[];
    speedDelta: number[];
    timeDelta: number[];
    throttle1: number[];
    throttle2: number[];
    brake1: number[];
    brake2: number[];
    gear1: number[];
    gear2: number[];
    drs1: number[];
    drs2: number[];
  };
}

export const fetchTrackLayout = (
  year: number,
  round: number,
  session: string,
) =>
  request<{
    track: { x: number[]; y: number[] };
    circuitInfo: unknown;
    eventName: string;
  }>(`/ghost-car/track/${year}/${round}/${session}`);

export const fetchFastestLap = (
  year: number,
  round: number,
  session: string,
  driver: string,
) =>
  request<LapData>(
    `/ghost-car/fastest-lap/${year}/${round}/${session}/${driver}`,
  );

export const fetchComparison = (
  year: number,
  round: number,
  session: string,
  d1: string,
  d2: string,
) =>
  request<ComparisonResponse>(
    `/ghost-car/compare/${year}/${round}/${session}/${d1}/${d2}`,
  );

export const fetchWeather = (year: number, round: number, session: string) =>
  request<{
    weather: {
      airTemp: number;
      trackTemp: number;
      humidity: number;
      windSpeed: number;
      rainfall: boolean;
    } | null;
  }>(`/ghost-car/weather/${year}/${round}/${session}`);

/* ── Best Car ───────────────────────────────────────────────────── */

export interface EraConfig {
  name: string;
  year: number;
  primaryCar: { team: string; car: string; drivers: string[]; color: string };
  competitors: {
    team: string;
    car: string;
    drivers: string[];
    color: string;
  }[];
}

export const fetchEras = () =>
  request<{ eras: Record<string, string> }>("/best-car/eras");

export const fetchEraDetail = (key: string) =>
  request<EraConfig>(`/best-car/era/${key}`);

export const fetchGapToLeader = (year: number, race: string) =>
  request<{
    race: string;
    year: number;
    gaps: {
      driver: string;
      team: string;
      lapTime: number;
      gap: number;
      gapPercent: number;
    }[];
  }>(`/best-car/gap-to-leader/${year}/${encodeURIComponent(race)}`);

export const fetchSeasonProgression = (eraKey: string) =>
  request<{
    eraKey: string;
    team: string;
    progression: { round: number; race: string; gap: number }[];
  }>(`/best-car/season-progression/${eraKey}`);

export const fetchRacePace = (year: number, race: string) =>
  request<{
    year: number;
    race: string;
    pace: {
      driver: string;
      team: string;
      avgLapTime: number;
      medianLapTime: number;
      fastestLap: number;
      laps: number;
    }[];
  }>(`/best-car/race-pace/${year}/${encodeURIComponent(race)}`);

/* ── Types ──────────────────────────────────────────────────────── */

export interface EventInfo {
  roundNumber: number;
  eventName: string;
  country: string;
  location?: string;
  date: string;
  isTesting?: boolean;
  testNumber?: number;
}

export interface SessionInfo {
  key: string;
  name: string;
}

export interface DriverInfo {
  abbreviation: string;
  fullName: string;
  team: string;
  number: string;
}

export interface Standing {
  id: string;
  label: string;
  name: string;
  team: string;
  position: number;
  points: number;
  wins: number;
  previousPosition: number | null;
  previousPoints: number | null;
  positionChange: number | null;
  pointsChange: number | null;
}
export interface StandingsResponse {
  year: number;
  round: number | null;
  previousRound: number | null;
  drivers: Standing[];
  constructors: Standing[];
  asOf: string;
  source: string;
  comparison?: string;
}
export interface CalendarEvent {
  id: string;
  series: string;
  title: string;
  event: string;
  session?: string;
  round?: number;
  start: string;
  end: string | null;
  dateOnly: boolean;
  location: string;
  source: string;
  sourceUrl: string;
  verifiedAt: string;
  status: string;
}
export interface CalendarResponse {
  year: number;
  events: CalendarEvent[];
  nextSession?: CalendarEvent | null;
  warnings?: string[];
  note?: string;
}
export interface TyreTrend {
  compound: string;
  laps: number;
  slopeSecondsPerTyreLap: number | null;
  reason: string;
}
export interface TeamComparison {
  team: string;
  first: string;
  second: string;
  qualifying: {
    segment: string | null;
    deltaSeconds: number | null;
    reason: string;
  };
  raceDeltaSeconds: number | null;
  matchedLaps: number;
  interval95: number[] | null;
  paceReversal: boolean;
  samples: {
    lap: number;
    first: number;
    second: number;
    delta: number;
    compound: string;
    ageA: number;
    ageB: number;
  }[];
  tyreTrends: Record<string, TyreTrend[]>;
}
export interface FieldPace {
  driver: string;
  team: string;
  qualifyingPosition: number | null;
  finishPosition: number | null;
  matchedLaps: number;
  relativePacePercent: number | null;
}
export interface WeekendResponse {
  fieldPace?: FieldPace[];
  year: number;
  round: number;
  eventName: string;
  teams: TeamComparison[];
  weather: Record<string, number | boolean | null> | null;
  warnings: string[];
  limitations: string[];
  method: string;
  unavailable: string[];
}
export interface Score {
  events: number;
  brier: number;
  logLoss: number;
  top1Accuracy: number;
}
export interface ModelInfo {
  id: string;
  name: string;
  improvements: string[];
  limitations: string[];
  sessions: string[];
  metrics: Score | null;
  trainedThrough: string | null;
  trainingEvents?: number;
  baselines?: Record<string, Score>;
  improvesGridLogLoss?: boolean;
  previousComparable?: Score | null;
}
export interface ModelCatalog {
  models: string[];
  catalog: ModelInfo[];
  defaultModel: string;
  trainingCommand: string;
}
export interface Evaluation {
  status: string;
  detail?: string;
  mode?: string;
  winner?: string;
  predictedWinner?: string;
  winnerProbability?: number;
  correct?: boolean;
  brier?: number;
  logLoss?: number;
  note?: string;
  asOf?: string;
  results?: {
    position: number;
    driver: string;
    predictedProbability: number;
  }[];
}
export interface RunSummary {
  runId: string;
  year: number;
  gp: string;
  model: string;
  mode: string;
  createdAt: string;
}
export interface EngineeringTopic {
  id: string;
  title: string;
  documented: string;
  measure: string;
  cannotInfer: string;
  sourceLabel: string;
  sourceUrl: string;
}
