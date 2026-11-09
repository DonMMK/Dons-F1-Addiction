/** Real React navigation and interaction tests with deterministic HTTP fixtures. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
import React, { act } from "react";

const rootDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(rootDir, "node_modules", ".cache", "f1-ui-test.cjs");
await fs.mkdir(path.dirname(output), { recursive: true });
await build({
  entryPoints: [path.join(rootDir, "src/App.tsx")],
  outfile: output,
  bundle: true,
  platform: "node",
  format: "cjs",
  jsx: "automatic",
  external: ["react", "react-dom", "react-router-dom"],
  logLevel: "silent",
});
const mathsOutput = path.join(
  rootDir,
  "node_modules",
  ".cache",
  "f1-tyre-maths.cjs",
);
await build({
  entryPoints: [path.join(rootDir, "src/tyreMath.ts")],
  outfile: mathsOutput,
  bundle: true,
  platform: "node",
  format: "cjs",
  logLevel: "silent",
});
const { normaliseFuel, stintDrift } = await import(mathsOutput);
const rawPoint = Object.freeze({
  lap: 11,
  age: 5,
  stint: 1,
  compound: "HARD",
  seconds: 80,
});
assert.equal(normaliseFuel(rawPoint, 0), 80);
assert.equal(normaliseFuel(rawPoint, 0.06), 80.6);
assert.equal(
  rawPoint.seconds,
  80,
  "An assumption must not mutate raw observations",
);
const trend = Array.from({ length: 10 }, (_, i) => ({
  ...rawPoint,
  age: i + 1,
  lap: i + 1,
  seconds: 80 + i * 0.1,
}));
assert.ok(Math.abs(stintDrift(trend, 0) - 0.1) < 1e-9);
assert.ok(Math.abs(stintDrift(trend, 0.06) - 0.16) < 1e-9);
assert.equal(stintDrift(trend.slice(0, 7), 0), null);
await fs.rm(mathsOutput, { force: true });
const dom = new JSDOM('<div id="root"></div>', {
  url: "http://localhost/",
  pretendToBeVisual: true,
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  localStorage: dom.window.localStorage,
  IS_REACT_ACT_ENVIRONMENT: true,
});
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(
  dom.window,
);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(
  dom.window,
);
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
const { createRoot } = await import("react-dom/client");
const { BrowserRouter } = await import("react-router-dom");
const { default: App } = await import(output);
const Component = App.default ?? App;
const current = new Date().getFullYear();
const standing = {
  id: "aaa",
  label: "AAA",
  name: "Alpha Driver",
  team: "McLaren",
  position: 1,
  points: 100,
  wins: 2,
  previousPosition: 3,
  previousPoints: 75,
  positionChange: 2,
  pointsChange: 25,
};
const event = {
  id: "f1-test",
  series: "f1",
  title: "Test Grand Prix — Race",
  event: "Test Grand Prix",
  start: new Date(Date.now() + 86400000).toISOString(),
  end: null,
  dateOnly: false,
  location: "Test",
  source: "Fixture",
  sourceUrl: "https://example.com",
  verifiedAt: "2026-11-07",
  status: "published",
};
const events = [
  {
    roundNumber: 1,
    eventName: "Test Grand Prix",
    country: "Test",
    date: "2024-01-01",
    isTesting: false,
  },
];
const lap = {
  abbreviation: "AAA",
  team: "McLaren",
  lapTime: "1:20.000",
  lapTimeSeconds: 80,
  compound: "MEDIUM",
  telemetry: {
    x: [0, 100, 200],
    y: [0, 100, 0],
    time: [0, 40, 80],
    speed: [100, 150, 100],
    throttle: [100, 50, 100],
    brake: [0, 1, 0],
    gear: [3, 4, 3],
    distance: [0, 150, 300],
    drs: [0, 10, 0],
  },
};
const comp = {
  eventName: "Test GP",
  dataSource: "OpenF1 historical timing",
  warnings: ["Distance estimated from speed; DRS unavailable"],
  driver1: lap,
  driver2: { ...lap, abbreviation: "BBB" },
  comparison: {
    distance: [0, 150, 300],
    speed1: [100, 150, 100],
    speed2: [99, 149, 99],
    speedDelta: [1, 1, 1],
    timeDelta: [0, -0.1, -0.2],
    throttle1: [100, 50, 100],
    throttle2: [100, 45, 100],
    brake1: [0, 1, 0],
    brake2: [0, 1, 0],
    gear1: [3, 4, 3],
    gear2: [3, 4, 3],
    drs1: [null, null, null],
    drs2: [null, null, null],
  },
};
const calls = [];
const paceRow = {
  name: "McLaren",
  component: 1,
  rank: 1,
  scoreSeconds: -0.2,
  interval95: [-0.3, -0.1],
  rankRange95: [1, 2],
  windows: 18,
  rivals: 2,
  drivers: ["AAA", "BBB"],
  sectors: [-0.1, -0.1, 0],
  fitRmsSeconds: 0.01,
};
const paceFixture = {
  condition: "slick",
  session: "Race",
  status: "observed",
  coverage: {
    recorded: 100,
    qualityScreened: 80,
    weatherMatched: 70,
    trafficScreened: 50,
    used: 50,
  },
  teamPace: { rows: [paceRow], components: 1 },
  driverPace: {
    rows: [{ ...paceRow, name: "AAA", drivers: ["AAA"] }],
    components: 1,
    pairwise: [],
  },
  unrankedTeams: ["Ferrari"],
  method: "Matched evidence fixture",
  limitations: ["Fuel loads unknown"],
};
const upgradeFixture = {
  team: "McLaren",
  status: "declared_updates",
  pages: [2],
  components: [
    {
      component: "Front Wing",
      page: 2,
      sourceUrl: "https://www.fia.com/system/files/fixture.pdf",
      effectSeconds: null,
      fitment: "Not verified",
    },
  ],
};
const evidenceFixture = {
  drivers: ["AAA", "BBB"],
  verdict: "A race win does not identify the fastest underlying car.",
  pace: paceFixture,
  conditions: {
    samples: 2,
    summary: { TrackTemp: { min: 25, median: 30, max: 35 } },
    timeline: [
      {
        date: "2026-01-01T10:00:00Z",
        trackTemp: 25,
        airTemp: 20,
        windSpeed: 2,
        rainReported: false,
      },
      {
        date: "2026-01-01T10:10:00Z",
        trackTemp: 35,
        airTemp: 22,
        windSpeed: 2,
        rainReported: true,
      },
    ],
    note: "Rainfall does not measure grip",
  },
  track: {
    name: "Reviewed circuit",
    status: "reviewed_context",
    demands: [
      { area: "Fast corners", interpretation: "Compare observed sector pace" },
    ],
    sources: [],
    note: "No team design bonus",
  },
  upgrades: {
    status: "indexed",
    checkedAt: "2026-01-01T09:00:00Z",
    sourceUrl: "https://www.fia.com/system/files/fixture.pdf",
    teams: [
      upgradeFixture,
      { team: "Ferrari", status: "not_indexed", pages: [], components: [] },
    ],
    timeline: [
      {
        round: 1,
        eventName: "Test GP",
        checkedAt: "2026-01-01T09:00:00Z",
        sourceUrl: "https://www.fia.com/system/files/fixture.pdf",
        teams: [upgradeFixture],
      },
    ],
    note: "Declaration does not establish a lap-time gain",
  },
  execution: {
    drivers: [
      {
        driver: "AAA",
        team: "McLaren",
        qualifying: 1,
        grid: 5,
        finish: 2,
        status: "Finished",
        stops: [
          {
            lap: 20,
            stationarySeconds: 3,
            laneSeconds: 24,
            deltaToSessionMedian: 0.5,
          },
        ],
      },
    ],
    events: [],
    note: "No luck score",
  },
};
let failure = null;
globalThis.fetch = async (url, options = {}) => {
  calls.push(String(url));
  if (failure && String(url).includes(failure.match)) {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (failure.code) headers.set("X-F1-Data-Error", failure.code);
    if (failure.retryAfter) headers.set("Retry-After", failure.retryAfter);
    return new Response(JSON.stringify({ detail: failure.detail }), {
      status: failure.status,
      headers,
    });
  }
  let data;
  if (url === "/api/seasons") data = { seasons: [2025, current] };
  else if (String(url).startsWith("/api/standings/"))
    data = {
      year: current,
      round: 2,
      previousRound: 1,
      drivers: [
        standing,
        {
          ...standing,
          id: "bbb",
          label: "BBB",
          name: "Beta Driver",
          position: 2,
          previousPosition: 1,
        },
      ],
      constructors: [{ ...standing, name: "McLaren" }],
      asOf: new Date().toISOString(),
      source: "Fixture",
    };
  else if (String(url).includes("/calendar/f1/")) data = { events: [event] };
  else if (String(url).includes("/calendar/motorsport/"))
    data = { events: [event] };
  else if (url === "/api/prediction/models")
    data = {
      catalog: [
        {
          id: "v12",
          name: "Legacy",
          improvements: ["22-car grid"],
          limitations: ["Heuristic"],
          sessions: ["Q"],
          metrics: null,
          trainedThrough: null,
        },
      ],
      models: ["v12"],
      defaultModel: "v12",
    };
  else if (url === "/api/prediction/history") data = { runs: [] };
  else if (url === "/api/prediction/run")
    data = {
      year: current,
      gp: "Test Grand Prix",
      model: "v12",
      mode: "pre-race",
      runId: "saved-one",
      monteCarloRuns: 5000,
      createdAt: new Date().toISOString(),
      warnings: [],
      predictions: [
        { driver: "AAA", position: 1, winProbability: 70 },
        { driver: "BBB", position: 2, winProbability: 30 },
      ],
      winningMargins: null,
    };
  else if (String(url).includes("/prediction/evaluate/"))
    data = {
      status: "scored",
      mode: "pre-race",
      winner: "BBB",
      predictedWinner: "AAA",
      winnerProbability: 30,
      brier: 0.98,
      logLoss: 1.204,
      note: "Saved probabilities",
      results: [],
    };
  else if (
    String(url).includes("/grand-prix/") ||
    String(url).includes("/schedule/")
  )
    data = { events };
  else if (String(url).includes("/sessions/"))
    data = { sessions: [{ key: "Q", name: "Qualifying" }] };
  else if (String(url).includes("/drivers/"))
    data = {
      drivers: [
        { abbreviation: "AAA", team: "McLaren" },
        { abbreviation: "BBB", team: "Other" },
      ],
    };
  else if (String(url).includes("/ghost-car/compare/")) data = comp;
  else if (
    String(url).includes("/weekend/") &&
    String(url).endsWith("/strategy")
  )
    data = {
      source: "OpenF1 fixture",
      maxLap: 20,
      coverage: { observed: 40, screened: 32, tyrePoints: 32 },
      warnings: [],
      method: "Observed spans; missing records stay blank",
      limitations: "Fuel not measured",
      drivers: ["AAA", "BBB"].map((driver, i) => ({
        driver,
        team: "McLaren",
        finish: i + 1,
        spans: [{ startLap: 1, endLap: 20, stint: 1, compound: "MEDIUM" }],
        points: Array.from({ length: 16 }, (_, n) => ({
          lap: n + 2,
          age: n + 2,
          stint: 1,
          compound: "MEDIUM",
          seconds: 80 + n * 0.01 + i * 0.2,
        })),
      })),
    };
  else if (String(url).includes("/weekend/") && String(url).includes("/laps/"))
    data = {
      laps: [
        { lap: 4, seconds: 80, compound: "MEDIUM", age: 4 },
        { lap: 8, seconds: 79.5, compound: "HARD", age: 2 },
      ],
      note: "Screened laps",
    };
  else if (String(url).includes("/weekend/") && String(url).includes("/pace/"))
    data = {
      pace: { ...paceFixture, session: "Practice 2" },
      source: "OpenF1 fixture",
      warnings: [],
    };
  else if (String(url).includes("/weekend/") && String(url).includes("/track/"))
    data = {
      source: "OpenF1 fixture",
      first: "AAA",
      second: "BBB",
      lapTimeA: 80,
      lapTimeB: 81,
      lapA: String(url).includes("lap_a=4") ? 4 : 8,
      lapB: 8,
      observedDurationA: 80,
      observedDurationB: 81,
      miniSectors: [
        { index: 1, start: 0, end: 1, deltaSeconds: -1, winner: "AAA" },
      ],
      comparison: [
        { fraction: 0, speedA: 100, speedB: 99, deltaSeconds: 0 },
        { fraction: 1, speedA: 150, speedB: 149, deltaSeconds: -1 },
      ],
      trace: [
        { x: 0, y: 0, fraction: 0 },
        { x: 100, y: 100, fraction: 0.5 },
        { x: 200, y: 0, fraction: 1 },
      ],
      zones: [
        {
          zone: 1,
          fraction: 0.5,
          x: 100,
          y: 100,
          band: "slow",
          sector: 2,
          speedA: 100,
          speedB: 95,
          deltaKmH: 5,
        },
      ],
      method: "Detected speed minima, not official turns",
      limitations: "Approximate position samples",
    };
  else if (String(url).includes("/weekend/"))
    data = {
      evidence: evidenceFixture,
      year: current,
      round: 1,
      eventName: "Test GP",
      dataSources: { Q: "Jolpica", R: "OpenF1 historical timing" },
      teams: [
        {
          team: "McLaren",
          first: "AAA",
          second: "BBB",
          qualifying: {
            segment: "Q1",
            deltaSeconds: 0.2,
            reason: "Shared segment",
          },
          raceDeltaSeconds: -0.4,
          matchedLaps: 0,
          interval95: null,
          paceReversal: true,
          samples: [],
          tyreTrends: { AAA: [], BBB: [] },
        },
      ],
      warnings: [],
      weather: null,
      limitations: ["Fuel not observed"],
      method: "Matched empirical laps",
      unavailable: ["Fuel mass"],
    };
  else if (url === "/api/best-car/eras")
    data = { eras: { 2025: "McLaren MCL39" } };
  else if (String(url).includes("/best-car/era/"))
    data = {
      year: 2025,
      name: "McLaren",
      primaryCar: {
        team: "McLaren",
        car: "MCL39",
        drivers: ["AAA", "BBB"],
        color: "#ff8700",
      },
      competitors: [],
    };
  else if (String(url).includes("/best-car/season-jobs/"))
    data = {
      id: "job",
      status: "complete",
      completed: 1,
      total: 1,
      data: { progression: [], unavailable: [], method: "Q1" },
    };
  else if (url === "/api/engineering/topics")
    data = {
      eras: {
        2025: [
          {
            id: "brakes",
            title: "Brake cooling",
            documented: "Documented context",
            measure: "Compare pace",
            cannotInfer: "No brake temperature channel",
            sourceLabel: "Publisher",
            sourceUrl: "https://example.com",
          },
        ],
      },
      note: "Context",
    };
  else throw new Error(`Unexpected request ${url} ${options.method ?? "GET"}`);
  return { ok: true, json: async () => data };
};
let appRoot;
async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 20));
  });
}
async function navigate(url) {
  if (appRoot) await act(async () => appRoot.unmount());
  window.history.replaceState({}, "", url);
  appRoot = createRoot(document.getElementById("root"));
  await act(async () =>
    appRoot.render(
      React.createElement(BrowserRouter, null, React.createElement(Component)),
    ),
  );
  for (let i = 0; i < 5; i++) await flush();
}
async function click(text) {
  const target = [...document.querySelectorAll("button,a")].find((e) =>
    e.textContent.includes(text),
  );
  assert.ok(target, `Missing control ${text}`);
  await act(async () =>
    target.dispatchEvent(new window.MouseEvent("click", { bubbles: true })),
  );
  await flush();
}
const text = () => document.body.textContent;
try {
  await navigate("/");
  assert.match(text(), /championship picture/);
  assert.match(text(), /Alpha Driver/);
  assert.match(text(), /NEXT F1 SESSION/);
  await click("Replay change");
  assert.match(text(), /Previous published order/);
  await click("Constructors");
  assert.match(text(), /McLaren/);
  await navigate("/weekend");
  assert.match(text(), /Weekend by Weekend/);
  assert.match(text(), /Quali\/race reversal/);
  assert.match(text(), /Fuel mass/);
  assert.match(text(), /Sources: Q: Jolpica/);
  assert.match(text(), /Track demands and conditions/);
  assert.doesNotMatch(text(), /Team pace · equal weight for both cars/);
  assert.ok(
    !calls.some((p) => p.includes("/strategy")),
    "Strategy is loaded only when opened",
  );
  await click("Pace");
  assert.match(text(), /Team pace · equal weight for both cars/);
  await click("Load practice evidence");
  assert.match(text(), /Practice 2 · observed package pace/);
  await click("Upgrades");
  assert.match(text(), /Not indexed — unknown/);
  assert.match(text(), /Front Wing/);
  await click("Strategy & tyres");
  assert.match(text(), /Actual grid/);
  assert.match(text(), /Raw lap times · no fuel correction applied/);
  assert.ok(
    document.querySelector(
      'svg[aria-label="Observed tyre stints by driver and race lap"]',
    ),
  );
  const assumption = document.querySelector(
    '.assumption-control input[type="checkbox"]',
  );
  await act(async () => assumption.click());
  assert.match(text(), /Assumption active/);
  assert.match(text(), /Faint points retain raw times/);
  await act(async () => assumption.click());
  assert.match(text(), /Raw lap times · no fuel correction applied/);
  await click("Laps & track");
  await act(async () => {
    const select = document.querySelector('select[aria-label="Lap A"]');
    select.value = "4";
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
  await flush();
  await click("Compare selected laps");
  assert.ok(calls.some((p) => p.includes("lap_a=4")));
  assert.ok(
    document.querySelector(
      'svg[aria-label="Estimated mini-sector time dominance with detected speed zones"]',
    ),
  );
  assert.match(text(), /AAA L4/);
  assert.match(text(), /not official timing sectors/);
  assert.match(text(), /full speed, throttle, brake and gear traces/);
  // Changing a lap clears the previous comparison rather than mislabelling it.
  await act(async () => {
    const select = document.querySelector('select[aria-label="Lap A"]');
    select.value = "8";
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
  await flush();
  assert.equal(
    document.querySelector(
      'svg[aria-label="Estimated mini-sector time dominance with detected speed zones"]',
    ),
    null,
  );
  // The tab strip supports keyboard movement and updates the labelled panel.
  await act(async () =>
    document
      .querySelector('[role="tab"][aria-selected="true"]')
      .dispatchEvent(
        new window.KeyboardEvent("keydown", { key: "Home", bubbles: true }),
      ),
  );
  assert.equal(
    document.querySelector('[role="tab"][aria-selected="true"]').textContent,
    "Overview",
  );
  await act(async () => {
    const select = document.querySelector(
      'select[aria-label="Pace conditions"]',
    );
    select.value = "wet";
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
  await flush();
  assert.ok(calls.some((p) => p.includes("condition=wet")));
  await navigate("/prediction");
  assert.match(text(), /What changed in v12/);
  await click("Run & save");
  assert.match(text(), /70.00%/);
  assert.match(text(), /ACTUAL WINNER/);
  await navigate("/ghost-car");
  await click("Compare");
  assert.match(text(), /Bird’s-eye lap replay/);
  assert.match(text(), /Source: OpenF1 historical timing/);
  assert.match(text(), /Distance estimated from speed/);
  await click("Play");
  assert.match(text(), /Pause/);
  await click("Pause");
  await navigate("/looking-back");
  assert.match(text(), /engineering behind the lap/);
  assert.match(text(), /Brake cooling/);
  assert.match(text(), /No brake temperature channel/);
  await navigate("/not-just-f1");
  assert.match(text(), /Your year in racing/);
  assert.match(text(), /venue dates/);
  assert.ok(calls.some((p) => p.includes("/prediction/evaluate/saved-one")));

  // Expected publication delays are a calm status, with a manual retry only.
  failure = {
    match: "/drivers/",
    status: 425,
    code: "session_not_started",
    retryAfter: "1",
    detail: "This session has not started yet.",
  };
  await navigate("/ghost-car");
  assert.match(text(), /This session hasn't started yet/);
  assert.match(text(), /Choose an earlier completed session/);
  assert.match(text(), /your local time/);
  assert.equal(document.querySelectorAll('[role="alert"]').length, 0);
  assert.ok(document.querySelector('[role="status"]'));
  const retry = [...document.querySelectorAll("button")].find(
    (b) => b.textContent === "Check again",
  );
  assert.ok(retry.disabled);
  const driverCalls = () => calls.filter((p) => p.includes("/drivers/")).length;
  const before = driverCalls();
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1100));
  });
  assert.equal(driverCalls(), before, "A pending session must not auto-poll");
  assert.equal(retry.disabled, false);
  failure = null;
  await click("Check again");
  assert.equal(driverCalls(), before + 1);
  assert.doesNotMatch(text(), /This session hasn't started yet/);

  failure = {
    match: "/drivers/",
    status: 425,
    code: "classification_not_published",
    retryAfter: new Date(Date.now() + 60_000).toUTCString(),
    detail: "The session classification has not been published yet.",
  };
  await navigate("/ghost-car");
  assert.match(text(), /Session results aren't published yet/);
  assert.ok(
    [...document.querySelectorAll("button")].find(
      (b) => b.textContent === "Check again",
    ).disabled,
  );
  failure = null;
  await navigate("/");
  assert.doesNotMatch(text(), /Session results aren't published yet/);

  failure = {
    match: "/drivers/",
    status: 502,
    detail: "Timing provider unavailable",
  };
  await navigate("/ghost-car");
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /Timing provider unavailable/,
  );
  assert.doesNotMatch(text(), /Session data isn't available yet/);

  failure = {
    match: "/prediction/run",
    status: 425,
    detail: "Practice results are still being published.",
  };
  await navigate("/prediction");
  await click("Run & save");
  assert.match(text(), /Session data isn't available yet/);
  assert.match(text(), /Practice results are still being published/);
  assert.equal(document.querySelectorAll('[role="alert"]').length, 0);
  failure = null;
  console.log(
    "PASS: six routes; source notices, 425 publication status, retry timing/manual recovery, genuine errors, predictions and replay",
  );
} finally {
  if (appRoot) await act(async () => appRoot.unmount());
  dom.window.close();
  await fs.rm(output, { force: true });
}
