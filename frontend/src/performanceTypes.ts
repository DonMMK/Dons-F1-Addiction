export interface PerformanceRow {
  evidenceTier?: "strict_matched" | "adjusted_two_car" | "single_car";
  strictMatched?: boolean;
  driverLaps?: Record<string, number>;
  expectedDrivers?: string[];
  team: string;
  colour: string | null;
  rank: number;
  rankRange95: number[] | null;
  gapSeconds: number;
  gapPercent: number | null;
  gapInterval95: number[] | null;
  previousRank: number | null;
  rankChange: number | null;
  previousGapPercentToReference: number | null;
  previousEquivalentGapSeconds: number | null;
  deltaGapPercentagePoints: number | null;
  comparisonNote: string;
  windows: number;
  drivers: string[];
  rivals: number;
}
export interface PerformanceBoard {
  view?: "adjusted" | "strict";
  strictBoard?: PerformanceBoard;
  totalTeams?: number;
  diagnostics?: {
    team: string;
    strictReason: string;
    drivers: {
      driver: string;
      usableLaps: number;
      clearAirLaps: number;
      strictComponent: number | null;
      trafficObservedFraction: number | null;
    }[];
  }[];
  validation?: {
    heldOutWindows: number;
    pairDifferenceMaeSeconds: number | null;
    zeroDifferenceMaeSeconds: number | null;
    note: string;
  } | null;
  year: number;
  round: number;
  eventName: string;
  checkedAt: string;
  source: string;
  condition: string;
  previousRound: number | null;
  previousEvent: string | null;
  normalisationLapSeconds: number | null;
  groups: {
    component: number;
    referenceTeam: string;
    rows: PerformanceRow[];
  }[];
  unrankedTeams: string[];
  coverage: {
    recorded: number;
    qualityScreened: number;
    weatherMatched: number;
    trafficScreened: number;
    used: number;
  };
  warnings: string[];
  method: string;
  limitations: string[];
  comparisonMethod: string;
}
export interface PerformanceResponse {
  year: number;
  condition: string;
  requestedRound: number | null;
  displayedRound: number | null;
  board: PerformanceBoard | null;
  history: {
    round: number;
    eventName: string;
    board: PerformanceBoard | null;
  }[];
  update: {
    enabled: boolean;
    state: string;
    checkedAt: string | null;
    nextCheckAt: string | null;
    message: string;
    showingEarlierRound: boolean;
  };
}
