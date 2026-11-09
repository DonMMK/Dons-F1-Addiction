# Don's F1 Addiction

A React / TypeScript frontend and FastAPI backend for championship context,
empirical weekend comparisons, recorded lap replay and auditable race predictions.

## Pages

| Route | What it does |
| --- | --- |
| `/` | Driver / constructor standings, previous-round movement, animated schematic championship order, F1 calendar and next session in the viewer's timezone |
| `/weekend` | Five analysis views: track/weather overview, matched pace, strategy/tyre plots, selected-lap track dominance, FIA upgrades; supporting teammate comparisons |
| `/prediction` | Version descriptions, saved winner distributions, post-race Brier / log-loss scores and trained-iteration validation metrics |
| `/ghost-car` | Two recorded fastest laps with play / pause / scrub controls and speed, throttle, brake, gear, DRS and cumulative time traces |
| `/looking-back` | Cited W11 / RB19 / MCL39 engineering context, conceptual car diagrams, signed qualifying advantage and recorded lap comparisons |
| `/not-just-f1` | Mixed-series calendar: F1, WEC / Hypercar, IMSA, all ten 2026 NLS races, GT Europe and Supercars; browser-local calendar imports |
| `/best-car` | Redirect to `/looking-back` for existing bookmarks |

See [expanded weekend evidence](docs/WEEKEND_EVIDENCE.md) for sources, matching,
uncertainty and FIA history refresh commands.

See [the free analysis workbench notes](docs/FREE_INSIGHTS_WORKBENCH.md) for the
competitor comparison, data sources, new views, fuel assumptions and remaining gaps.

See [the refactor notes](docs/F1_REFACTOR.md) for the original findings, methodology,
limits, source provenance, model workflow and verification details.

## Install and run

Python 3.10+ and Node.js 18+ are required. Activate your existing Python virtual
environment first. Run these commands from the repository root:

```bash
python -m pip install -r backend/requirements.txt
npm --prefix frontend install
npm --prefix frontend run build
python -m uvicorn backend.app:app --reload --port 8000
```

In another terminal:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.
The Vite development proxy forwards `/api` to the backend. A production host must
serve the React assets and forward `/api` to FastAPI; `vite preview` alone does not
provide this backend proxy.

No F1TV account is needed for historical analysis from 2023 onwards. The backend
uses existing FastF1 caches and free OpenF1 historical timing, with Jolpica for
published classifications. See [Backend data loading](docs/F1_DATA_LOADING.md)
for setup, diagnostics, coverage and optional archive access.

The uploaded code export excluded lockfiles, so this patch deliberately leaves
your existing `frontend/package-lock.json` untouched. `npm install` updates it;
commit the resulting lockfile in your repository after reviewing it.

## Runtime data

`var/` holds SQLite prediction history and JSON model iterations. The backend
reuses populated legacy FastF1 caches when available, otherwise `var/fastf1`.
Set `F1_CACHE_DIR` to select the cache explicitly. Set `F1_DATA_DIR` to a persistent absolute path when deploying. Keep
this directory out of version control (add `/var/` to your repository's existing
`.gitignore`). Existing CLI tools and their caches are retained; the web backend
shares the selected cache. OpenF1 responses and its shared rate budget are stored
in `var/openf1/openf1.sqlite3`. First uncached loads need network access and can
take time; subsequent requests reuse the cache. Set `F1_TIMING_PROVIDER=openf1`
to force the free provider, or `fastf1` for optional native archive access.
The default `auto` prefers existing timing caches, then OpenF1.

Season analyses run in a bounded background queue and report their progress. Run
one Uvicorn worker with this in-process job queue; multiple independent workers
need a shared job store / queue before deployment. Forecast snapshots are durable
SQLite records, independently of those transient analysis jobs.

## Verify

```bash
python -m unittest discover -s backend/tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

Frontend interaction tests use DOM fixtures, not live data or a rendered browser.
The offline backend suite exercises model adapters, forecast persistence / scoring,
chronological training, lap matching and timezone conversion.

## Create an empirical model iteration

Legacy v1–v12 remain available with explicit limitations. They are not relabelled
as empirically validated models. v13 uses learned numeric features without driver
names, team names or personal tier assignments.

```bash
python -m backend.train_predictor --from-year 2023 --through-year 2025
```

After a later race, create a new immutable iteration, for example:

```bash
python -m backend.train_predictor --from-year 2023 --through-year 2026 --through-round 10
```

Use the last round with completed, published results. Reload the Predictor page
to see the new iteration. Training downloads historical sessions and needs at
least 15 complete events. No trained v13 weights or claimed accuracy are bundled.
Models trained after a selected weekend cannot forecast that weekend through the
API. Older eligible iterations remain selectable.

## Other motorsport calendars

F1 sessions refresh from FastF1. Other series ship with a source-labelled 2026
calendar snapshot checked on 7 November 2026. These are mostly event dates, not
complete timed session schedules. Two published Monza WEC session starts are
included. Exact timed entries are converted using the viewer's timezone and its
DST rules. Date-only weekends remain venue dates.

On “Not Just F1”, import a downloaded publisher `.ics` file to replace the selected
series / year in your browser. Your imported data stays in that browser. For a
shared repository snapshot:

```bash
python -m backend.services.ical path/to/publisher-calendar.ics \
  --series imsa --year 2027 --source-url https://www.imsa.com/schedule
```

Inspect and commit `data/motorsport-2027.json`. Imports require UTC or an explicit
timezone, reject unexpanded recurring entries, omit cancelled entries and replace
the chosen series / year so removed sessions do not survive a refresh. There is
no automatic HTML scraping or invented session time for unsupported providers.

## Original standalone tools

The `formula1-prediction`, `formula1-ghost-car` and `formula1-best-car` tools remain.
Install their own requirements to use their desktop / CLI export functionality.
The website replays fastest laps; the standalone full-race replay is not exposed
as a web feature in this patch.
