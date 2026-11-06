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
let failure = null;
globalThis.fetch = async (url, options = {}) => {
  calls.push(String(url));
  if (failure && String(url).includes(failure.match)) {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (failure.code) headers.set("X-F1-Data-Error", failure.code);
    if (failure.retryAfter) headers.set("Retry-After", failure.retryAfter);
    return new Response(JSON.stringify({ detail: failure.detail }), {
      status: failure.status, headers,
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
  else if (String(url).includes("/weekend/"))
    data = {
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
  failure = { match: "/drivers/", status: 425, code: "session_not_started",
    retryAfter: "1", detail: "This session has not started yet." };
  await navigate("/ghost-car");
  assert.match(text(), /This session hasn't started yet/);
  assert.match(text(), /Choose an earlier completed session/);
  assert.match(text(), /your local time/);
  assert.equal(document.querySelectorAll('[role="alert"]').length, 0);
  assert.ok(document.querySelector('[role="status"]'));
  const retry = [...document.querySelectorAll("button")].find((b) => b.textContent === "Check again");
  assert.ok(retry.disabled);
  const driverCalls = () => calls.filter((p) => p.includes("/drivers/")).length;
  const before = driverCalls();
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1100)); });
  assert.equal(driverCalls(), before, "A pending session must not auto-poll");
  assert.equal(retry.disabled, false);
  failure = null;
  await click("Check again");
  assert.equal(driverCalls(), before + 1);
  assert.doesNotMatch(text(), /This session hasn't started yet/);

  failure = { match: "/drivers/", status: 425, code: "classification_not_published",
    retryAfter: new Date(Date.now() + 60_000).toUTCString(), detail: "The session classification has not been published yet." };
  await navigate("/ghost-car");
  assert.match(text(), /Session results aren't published yet/);
  assert.ok([...document.querySelectorAll("button")].find((b) => b.textContent === "Check again").disabled);
  failure = null;
  await navigate("/");
  assert.doesNotMatch(text(), /Session results aren't published yet/);

  failure = { match: "/drivers/", status: 502, detail: "Timing provider unavailable" };
  await navigate("/ghost-car");
  assert.match(document.querySelector('[role="alert"]').textContent, /Timing provider unavailable/);
  assert.doesNotMatch(text(), /Session data isn't available yet/);

  failure = { match: "/prediction/run", status: 425,
    detail: "Practice results are still being published." };
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
