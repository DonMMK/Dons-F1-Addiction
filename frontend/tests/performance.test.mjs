/** Real React interactions with deterministic cached API fixtures. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
import React, { act } from "react";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output = path.join(root, "node_modules/.cache/performance-ui-test.cjs");
await fs.mkdir(path.dirname(output), { recursive: true });
await build({
  entryPoints: [path.join(root, "src/App.tsx")],
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
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(
  dom.window,
);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(
  dom.window,
);
const nativeInterval = globalThis.setInterval;
let poll;
globalThis.setInterval = (fn, delay, ...args) => {
  if (delay === 60000) poll = fn;
  return nativeInterval(fn, delay, ...args);
};
const { createRoot } = await import("react-dom/client");
const { BrowserRouter } = await import("react-router-dom");
const imported = await import(output);
const App = imported.default.default ?? imported.default;
const year = new Date().getFullYear();
const rows = [
  {
    team: "Alpha",
    colour: "27f4d2",
    rank: 1,
    gapSeconds: 0,
    gapPercent: 0,
    gapInterval95: [0, 0],
    previousRank: 2,
    rankChange: 1,
    previousGapPercentToReference: 0,
    previousEquivalentGapSeconds: 0,
    deltaGapPercentagePoints: 0,
  },
  {
    team: "Beta",
    colour: "ff8700",
    rank: 2,
    gapSeconds: 0.6,
    gapPercent: 0.6,
    gapInterval95: [0.4, 0.8],
    previousRank: 1,
    rankChange: -1,
    previousGapPercentToReference: -0.5,
    previousEquivalentGapSeconds: -0.5,
    deltaGapPercentagePoints: 1.1,
  },
  {
    team: "Gamma",
    colour: "3671c6",
    rank: 3,
    gapSeconds: 1,
    gapPercent: 1,
    gapInterval95: [0.8, 1.2],
    previousRank: 3,
    rankChange: 0,
    previousGapPercentToReference: 1.25,
    previousEquivalentGapSeconds: 1.25,
    deltaGapPercentagePoints: -0.25,
  },
].map((r) => ({
  ...r,
  rankRange95: [r.rank, r.rank + 1],
  windows: 18,
  rivals: 2,
  drivers: [r.team + "1", r.team + "2"],
  comparisonNote: "Same ranked team set",
}));
function board(round = 2) {
  const strict = {
    year,
    round,
    eventName: `Event ${round}`,
    checkedAt: "2026-11-10T01:00:00Z",
    source: "Recorded API fixture",
    condition: "slick",
    previousRound: round > 1 ? round - 1 : null,
    previousEvent: round > 1 ? `Event ${round - 1}` : null,
    normalisationLapSeconds: 100,
    groups: [{ component: 1, referenceTeam: "Alpha", rows }],
    unrankedTeams: ["Unknown team"],
    coverage: {
      recorded: 100,
      qualityScreened: 80,
      weatherMatched: 70,
      trafficScreened: 60,
      used: 60,
    },
    warnings: [],
    method: "Matched same-condition observations",
    comparisonMethod: "Same reference, normalised to eligible lap time",
    limitations: ["Car and driver effects remain combined"],
  };
  if (stage === "unsupported")
    return {
      ...strict,
      view: "adjusted",
      groups: [],
      unrankedTeams: ["Alpha", "Beta", "Gamma", "Unknown team"],
      strictBoard: strict,
    };
  if (stage !== "adjusted") return strict;
  return {
    ...strict,
    view: "adjusted",
    totalTeams: 4,
    strictBoard: strict,
    groups: [
      {
        ...strict.groups[0],
        rows: rows.map((r) => ({
          ...r,
          evidenceTier: r.team === "Gamma" ? "single_car" : "adjusted_two_car",
          strictMatched: r.team === "Alpha",
          driverLaps: { [r.team + "1"]: 40 },
          drivers: r.team === "Gamma" ? ["Gamma1"] : r.drivers,
        })),
      },
    ],
    diagnostics: [
      {
        team: "Beta",
        strictReason: "Drivers are in separate matched groups",
        drivers: [
          {
            driver: "Beta1",
            usableLaps: 40,
            clearAirLaps: 1,
            strictComponent: null,
            trafficObservedFraction: 0.98,
          },
        ],
      },
    ],
    validation: {
      heldOutWindows: 45,
      pairDifferenceMaeSeconds: 0.63,
      zeroDifferenceMaeSeconds: 1.12,
      note: "Observed differences, not true car pace.",
    },
  };
}
let stage = "normal";
const calls = [];
const evidence = {
  drivers: ["AAA", "BBB"],
  pace: { coverage: { used: 60 } },
  conditions: {
    summary: { TrackTemp: { median: 35 } },
    samples: 0,
    timeline: [],
    note: "Recorded weather",
  },
  upgrades: {
    teams: [],
    documents: [],
    timeline: [],
    note: "Declared only",
    status: "not_indexed",
    checkedAt: null,
    sourceUrl: "https://www.fia.com/documents",
  },
  track: {
    name: "Test circuit",
    demands: [],
    sources: [],
    note: "No design priors",
  },
  execution: { drivers: [], events: [], note: "Records" },
  verdict: "Observed package estimates",
};
globalThis.fetch = async (url) => {
  const value = String(url);
  calls.push(value);
  const parsed = new URL(value, "http://localhost");
  let data;
  if (parsed.pathname.startsWith("/api/performance/")) {
    const selected = Number(parsed.searchParams.get("round"));
    const rd = selected || (stage === "published" ? 3 : 2);
    const cold =
      stage === "cold" || parsed.searchParams.get("condition") === "wet";
    data = {
      year,
      condition: parsed.searchParams.get("condition"),
      requestedRound: stage === "pending" && !selected ? 3 : rd,
      displayedRound: cold ? null : rd,
      board: cold ? null : board(rd),
      history: [
        { round: 1, eventName: "Event 1", board: board(1) },
        { round: 2, eventName: "Event 2", board: board(2) },
      ],
      update: {
        enabled: true,
        state: cold ? "pending" : "ready",
        checkedAt: "2026-11-10T01:00:00Z",
        nextCheckAt: "2026-11-10T07:00:00Z",
        message: "Cached race evidence",
        showingEarlierRound: stage === "pending" && !selected,
      },
    };
  } else if (value === "/api/seasons") data = { seasons: [year] };
  else if (parsed.pathname.startsWith("/api/standings/"))
    data = {
      year,
      round: 2,
      previousRound: 1,
      drivers: [],
      constructors: [],
      source: "Fixture",
      asOf: new Date().toISOString(),
    };
  else if (parsed.pathname.startsWith("/api/calendar/f1/"))
    data = { events: [] };
  else if (parsed.pathname.startsWith("/api/schedule/"))
    data = {
      events: [
        {
          roundNumber: 1,
          eventName: "Event 1",
          date: "2024-01-01",
          isTesting: false,
        },
        {
          roundNumber: 2,
          eventName: "Event 2",
          date: "2024-01-08",
          isTesting: false,
        },
      ],
    };
  else if (parsed.pathname.startsWith("/api/weekend/"))
    data = {
      year,
      round: Number(parsed.pathname.split("/").at(-1)),
      eventName: "Test weekend",
      evidence,
      teams: [],
      warnings: [],
      dataSources: {},
      method: "Matched laps",
      fieldPace: [],
      limitations: [],
      unavailable: [],
      weather: null,
    };
  else throw Error(`Unexpected request ${value}`);
  return { ok: true, json: async () => data };
};
let app;
const text = () => document.body.textContent;
async function flush() {
  await act(async () => new Promise((r) => setTimeout(r, 20)));
}
async function navigate(url) {
  if (app) await act(async () => app.unmount());
  window.history.replaceState({}, "", url);
  app = createRoot(document.getElementById("root"));
  await act(async () =>
    app.render(
      React.createElement(BrowserRouter, null, React.createElement(App)),
    ),
  );
  for (let i = 0; i < 6; i++) await flush();
}
async function click(name) {
  const target = [...document.querySelectorAll("button,a")].find(
    (e) => e.textContent === name,
  );
  assert.ok(target, `Missing control ${name}`);
  await act(async () => target.click());
  await flush();
}

try {
  await navigate("/");
  assert.match(text(), /This week’s car performance/);
  assert.match(text(), /Recorded API fixture/);
  assert.equal(document.querySelectorAll(".performance-grid-row").length, 3);
  assert.match(
    document.querySelector(".performance-unranked").textContent,
    /Unknown team/,
  );
  assert.ok(
    ![...document.querySelectorAll(".performance-grid-row")].some((r) =>
      r.textContent.includes("Unknown team"),
    ),
  );
  assert.match(
    document.querySelector(".performance-grid").textContent,
    /1.100/,
  );
  const inspect = document.querySelector(
    '.performance-grid-row[aria-label^="Beta:"]',
  );
  await act(async () =>
    inspect.dispatchEvent(
      new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    ),
  );
  assert.match(
    document.querySelector(".performance-focus").textContent,
    /Beta1 \/ Beta2/,
  );
  await click("% of lap");
  assert.match(
    document.querySelector(".performance-grid").textContent,
    /% lap/,
  );
  await click("Replay pace movement");
  assert.match(text(), /Previous GP positions, normalised to this lap/);
  await click("Show current pace");
  stage = "adjusted";
  await navigate("/");
  assert.match(text(), /Adjusted race-pace estimates/);
  assert.match(document.querySelector(".performance-grid").textContent, /~1/);
  assert.match(
    document.querySelector(".performance-grid").textContent,
    /Single-car proxy/,
  );
  assert.match(
    document.querySelector(".performance-grid").textContent,
    /Unknown team/,
  );
  assert.match(text(), /Held-out check: 45 race laps/);
  assert.match(text(), /Drivers are in separate matched groups/);
  await click("Strict matched evidence");
  assert.match(text(), /Missing teams may be faster/);
  assert.match(
    document
      .querySelector('.performance-grid-row[aria-label^="Beta:"]')
      .getAttribute("aria-label"),
    /rank 2 of 3 compared teams; full-field rank unavailable/,
  );
  await click("Adjusted race pace");
  const proxy = document.querySelector(
    '.performance-grid-row[aria-label^="Gamma:"]',
  );
  await act(async () =>
    proxy.dispatchEvent(new window.MouseEvent("click", { bubbles: true })),
  );
  assert.match(
    document.querySelector(".performance-focus").textContent,
    /Gamma1: 40 laps/,
  );
  assert.match(
    document.querySelector(".performance-focus").textContent,
    /missing car is not observed/,
  );
  stage = "unsupported";
  await navigate("/");
  assert.equal(document.querySelectorAll(".performance-grid-row").length, 0);
  assert.equal(
    document.querySelectorAll(
      '.performance-grid g[aria-label$="no current-race estimate"]',
    ).length,
    4,
  );
  assert.match(
    document.querySelector(".performance-grid").textContent,
    /NO SUPPORTED PACE ESTIMATES/,
  );
  // Save the exact rendered SVG only when explicitly requested by the local QA command.
  if (process.env.PERFORMANCE_QA_SVG) {
    await click("Seconds / lap");
    const svg = document
      .querySelector(".performance-grid")
      .outerHTML.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
    await fs.writeFile(process.env.PERFORMANCE_QA_SVG, svg);
  }
  const before = calls.length;
  stage = "published";
  await act(async () => poll());
  await flush();
  assert.match(text(), /Round 3 · Event 3/);
  assert.ok(
    calls.slice(before).every((p) => p.startsWith("/api/performance/")),
    "Automatic pace updates only fetch the local cached endpoint",
  );
  stage = "pending";
  await navigate("/");
  assert.match(text(), /Preparing round 3; showing cached round 2/);
  stage = "normal";
  await navigate(`/weekend?year=${year}&round=1&view=performance`);
  assert.equal(
    document.querySelector('[role="tab"][aria-selected="true"]').textContent,
    "Car performance",
  );
  assert.equal(
    document.querySelector("#weekend").value,
    "1",
    "A linked historical round must survive schedule loading",
  );
  assert.ok(
    calls.some((p) => p.includes("/performance/") && p.includes("round=1")),
  );
  assert.match(text(), /Recent weekends · car-performance grid/);
  assert.ok(
    document.querySelector(`a[href*="round=2"][href*="view=performance"]`),
  );
  const select = document.querySelector('select[aria-label="Pace conditions"]');
  await act(async () => {
    select.value = "wet";
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
  await flush();
  assert.ok(
    calls.some(
      (p) => p.includes("/performance/") && p.includes("condition=wet"),
    ),
  );
  assert.equal(
    document.querySelector(".performance-grid"),
    null,
    "Missing wet evidence must not display a stale slick-pace grid",
  );
  assert.match(text(), /No cached completed-race pace board yet/);
  assert.equal(document.querySelectorAll('[role="alert"]').length, 0);
  console.log(
    "PASS: adjusted/strict views, proxy labels, coverage diagnostics, missing teams, partial-field ranks, homepage, keyboard inspection, replay, percentage scale, automatic refresh, deep links, history and condition handling",
  );
} finally {
  globalThis.setInterval = nativeInterval;
  if (app) await act(async () => app.unmount());
  dom.window.close();
  await fs.rm(output, { force: true });
}
