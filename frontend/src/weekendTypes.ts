export interface PaceRow {
  name: string;
  component: number;
  rank: number;
  scoreSeconds: number;
  interval95: number[] | null;
  rankRange95: number[] | null;
  windows: number;
  rivals: number;
  drivers: string[];
  sectors: (number | null)[];
  fitRmsSeconds: number;
}
export interface PaceReport {
  warnings?: string[];
  condition: string;
  session: string;
  status: string;
  coverage: {
    recorded: number;
    qualityScreened: number;
    weatherMatched: number;
    trafficScreened: number;
    used: number;
  };
  teamPace: { rows: PaceRow[]; components: number };
  driverPace: {
    rows: PaceRow[];
    components: number;
    pairwise: {
      first: string;
      second: string;
      deltaSeconds: number;
      windows: number;
      component: number;
    }[];
  };
  unrankedTeams: string[];
  method: string;
  limitations: string[];
}
export interface UpgradeTeam {
  team: string;
  status: string;
  pages: number[];
  components: {
    component: string;
    page: number;
    sourceUrl: string;
    effectSeconds: null;
    fitment: string;
  }[];
}
export interface WeekendEvidence {
  drivers: string[];
  verdict: string;
  pace: PaceReport | null;
  conditions: {
    samples: number;
    summary: Record<
      string,
      { min: number | null; median: number | null; max: number | null }
    >;
    timeline: {
      date: string;
      trackTemp: number | null;
      airTemp: number | null;
      windSpeed: number | null;
      rainReported: boolean | null;
    }[];
    note: string;
  };
  track: {
    name: string;
    status: string;
    demands: { area: string; interpretation: string }[];
    note: string;
    sources: { label: string; url: string }[];
    tyreAllocation?: Record<string, string>;
  };
  upgrades: {
    documents?: { title: string; url: string }[];
    status: string;
    checkedAt: string | null;
    sourceUrl: string;
    teams: UpgradeTeam[];
    note: string;
    timeline: {
      round: number;
      eventName: string;
      checkedAt: string;
      sourceUrl: string;
      teams: UpgradeTeam[];
    }[];
  };
  execution: {
    note: string;
    pitMedianSeconds?: number | null;
    drivers: {
      driver: string;
      team: string;
      qualifying: number | null;
      grid: number | null;
      finish: number | null;
      status: string;
      stops: {
        lap: number | null;
        stationarySeconds: number | null;
        laneSeconds: number | null;
        deltaToSessionMedian: number | null;
      }[];
    }[];
    events: { date: string | null; message: string; lap: number | null }[];
  };
}
export interface TrackEvidence {
  source: string;
  first: string;
  second: string;
  lapTimeA: number;
  lapTimeB: number;
  lapA: number | null;
  lapB: number | null;
  observedDurationA: number;
  observedDurationB: number;
  trace: { x: number; y: number; fraction: number }[];
  miniSectors: {
    index: number;
    start: number;
    end: number;
    deltaSeconds: number;
    winner: string | null;
  }[];
  comparison: {
    fraction: number;
    speedA: number;
    speedB: number;
    deltaSeconds: number;
  }[];
  zones: {
    zone: number;
    fraction: number;
    x: number;
    y: number;
    band: string;
    sector: number | null;
    speedA: number;
    speedB: number;
    deltaKmH: number;
  }[];
  method: string;
  limitations: string;
}
