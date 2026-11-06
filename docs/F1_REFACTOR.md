# F1 evidence dashboard: implementation and review notes

This patch is based on the supplied `f1-addiction-llm.txt` source snapshot. It adds
no invented fuel measurements, driver preference tiers to the empirical model,
or claimed component-specific lap-time gains.

## Original review findings and resolutions

| Finding | Resolution / remaining limitation |
| --- | --- |
| Alphabetical discovery defaulted to v9 instead of v12 | Numeric discovery; exact model IDs; latest trained iteration is explicitly selected when available |
| v4–v9 constructor mismatch | Shared adapter supplies physics, grid and GP arguments correctly |
| v12 returned a tuple while API expected a dictionary | Winner and margin outputs unpacked separately |
| NumPy timedelta `.values[0].total_seconds()` silently discarded qualifying times | Scalar extraction uses `.iloc[0]` in v10–v12; regression tested |
| Empty v1–v3 physics profiles bypassed practice analysis | Available completed practice at or before the selected input is analysed; missing evidence is labelled as a grid fallback |
| v1 fallback weights were divided by configured simulation count | Normalize actual output weights / counts, preserve zero-probability drivers, reject invalid distributions |
| v5 had a broken `TrackConfig.get_laps.get` call | Uses the existing lap-count dictionary |
| v10 / v11 truncated a 22-car field to 20 | Include the supplied field; v12 retains its 22-car implementation |
| Missing `rich` backend dependency | Added with calendar parsing and test HTTP dependencies |
| Ghost website did not show available channels or replay | Added actual-position replay, throttle, binary brake, gear, raw DRS and cumulative time delta |
| Speed difference could be confused with time gained | Cumulative time delta is now separately calculated and labelled |
| Best Car showed zero whenever primary team was fastest | Signed primary-vs-nearest-other-team Q1 gap; seconds and percent retained |
| Qualifying gaps mixed Q1 / Q2 / Q3 | Era progression uses common Q1; teammate comparisons use deepest shared timed segment |
| Season load blocked the whole result and hid missing races | Bounded background job, progress polling, explicit missing-race list |
| Per-router global cache reconfiguration | Web routes use one shared loader and cache |
| Frontend swallowed fetch failures and accepted stale selections | Shared abortable request hook, cleared dependent results and visible errors |
| No durable forecast records or honest post-race scoring | Immutable SQLite snapshots and a winner-distribution evaluation endpoint |
| No model validation / version evidence in frontend | Catalog describes legacy changes; trained iterations report held-out metrics and baselines |
| Hardcoded frontend year limits and default 2025 | Season service supplies years through current year; current year is initial selection |
| Testing support was partially wired | Testing remains excluded from the web session comparison; original CLI testing support remains |

## Empirical teammate analysis

“Same car” is a useful partial control, not an experimental randomization.
Teammates can have different parts, setup, damage, engine modes and instructions.

1. Qualifying: fastest valid lap in the deepest Q segment where both have a time.
   Q1 vs Q3 is never presented as a like-for-like teammate comparison.
2. Race: pair by the same race lap and compound, and require tyre age within one
   lap. This reduces differences in fuel-burn timing and weather timing.
3. Exclude inaccurate, deleted, synthesized, pit-in / out and non-green laps.
   Traffic is not guessed from a slow lap and is not claimed to be removed.
4. Report median A-minus-B time, counts and every retained pair. Negative is A
   faster. Qualifying-vs-race reversal is an observation, not a driver ranking.
5. At eight or more pairs, show an exploratory 95% moving-block bootstrap
   interval using blocks of three within contiguous matched stint segments.
   It is conditional on the retained sample, not a causal confidence statement.
6. Tyre-age trends fit lap time against race lap and tyre age within each driver /
   compound. Require 15 valid laps, two stints and an identifiable, sufficiently
   conditioned design matrix. Otherwise return unavailable. Negative slopes are
   retained rather than clipped into “wear”. These are descriptive pace slopes;
   fuel, weather, traffic and stint effects remain.

The field overview also compares each lap with at least two other drivers on the
same race lap / compound and tyre age within one lap. It reports the median
percentage difference only after five matching laps. Peer composition varies;
this is descriptive performance evidence alongside qualifying / finish position,
not a pure car-performance or driver-skill ranking.

Public data here includes compound, tyre age, lap/sector times, speed, throttle,
binary brake, gear, position and provider DRS codes. It does not contain measured
fuel kilograms, suspension setup, tyre carcass temperature, physical wear, brake
pressure or aerodynamic loads. Brake is an on/off channel, not pressure percent.
Tyre compounds labelled SOFT/MEDIUM/HARD are not identical specifications across
all circuits. Raw DRS codes are not automatically interpreted as 2026 active aero.

## Forecasting and learning

### Legacy adapters

The API loads actual completed input sessions. Earlier-session forecasts never
read later practice or the target race for their features. Qualifying-only v10 /
v11 reject practice inputs. The original CLI models retain their manually tuned
pace, fuel, tyre and driver assumptions. The UI exposes those limitations.

Their existing GP-name lookups are adapted to the names selected by the website.
The sparse original track tables remain assumptions; v1–v3 retain a labelled
58-lap default. A fixed seed makes runs repeatable; global legacy RNG use is
serialized and the prior state restored. This does not turn legacy models into
calibrated empirical probability models.

### v13 learned iterations

Each driver is represented by:

- Relative Q1 gap as a percentage of the fastest Q1 time.
- Qualifying result rank fraction (not a claim to know grid penalties).
- Prior completed practice long-run pace relative to that compound's field
  median, and an indicator for missing practice evidence.

The classifier never receives driver/team identity. Missing qualifying times use
a documented fallback of at least 5% or the slowest observed relative gap. Fuel
load and practice-run intent remain unobserved; relative practice pace is a proxy.

Train whole events chronologically. The first 60% fit candidate regularizations;
the next 20% choose regularization; the final 20% are untouched test events. Score
once on that test split, then refit the selected specification on all included
training events. Test scores describe the pre-refit holdout fit. They are not
future guarantees or scores of a final model already refitted on the test races.

Model output is normalized logistic winner likelihood over the actual field.
Evaluate event-level multiclass Brier (sum of squared errors), log loss and top-1
winner accuracy. Compare the same test races with equal probabilities and a fixed
50%-to-qualifying-leader baseline. No automatic “better” claim follows from a new
version number. A previous model is only compared on this holdout when it was
trained before the holdout began.

Artifacts are immutable JSON numeric coefficients with a data-manifest hash,
training cutoff, event list, split and metrics. Re-running the same manifest
reuses its artifact; changed features / labels create a new ID. The data and
algorithm version participate in the hash. No downloaded pickle is executed.

A training result is not promoted silently over an older iteration. It is added
to the catalog and selectable; the latest iteration is the default for later
weekends. The server rejects it for any event at or before its training cutoff.
For a rolling backtest, train only through round N and predict N+1, retaining
those saved runs. Training needs published historical data; weights are not
fabricated when downloads fail or fewer than 15 events are available.

### Prediction audit and scoring

Saved snapshots include exact probabilities, model ID and source hash, seed,
creation time, event, selected session and training cutoff. Learned runs also
retain their numeric feature entries. A run created after race start is labelled
retrospective even when its features came from qualifying. Legacy historical
runs are not presented as genuine pre-race forecasts. This does not certify the
historical freshness of mutable upstream data or manually authored legacy rules.

Post-race scoring uses the saved probabilities, not a rerun. It requires a
finished session and an available P1 classification. An excluded winner receives
zero probability (log loss clipped at 1e-15). Classification and penalties can
change; the evaluation includes a retrieval time. Winner rank is not a forecast
finishing order. Persistent snapshots survive restart; evaluations refresh from
the current classification.

## Calendar behavior and provenance

F1 timings use FastF1 UTC session timestamps; browser `Intl` formatting uses the
viewer's timezone including DST. The next session is the earliest published
future session start in the selected season; the homepage refreshes every five
minutes. It does not infer session ends or claim that the next session is live.

Standings come from Jolpica through FastF1. Driver and constructor snapshots are
aligned to one published round. Movement is against round N-1, not an arbitrary
seven-day window. Sprint points and published adjustments are included. First
round / newly appearing entries have no prior-position delta.

The top-down championship animation depicts ranks on a schematic oval. Spacing
is not elapsed time or points. The separate recorded lap replay interpolates
FastF1 X/Y samples on a common elapsed-time axis, starting both laps at t=0. It
is not a reconstruction of an on-track battle or precision racing-line tracking.

Other-series data is a checked-in snapshot, not a live scraper. The bundled 2026
snapshot includes all ten NLS races and WEC, IMSA WeatherTech, GT World Challenge
Europe and Supercars event dates. Hypercar is a WEC class rather than another
calendar to duplicate. Each entry retains a source URL and a check date.

- [NLS calendar](https://www.nuerburgring-langstrecken-serie.de/language/en/calendar-nurburgring-langstrecken-serie-2026/)
- [IMSA schedule announcement](https://www.imsa.com/news/2025/march/13/imsa-reveals-2026-weathertech-championship-michelin-pilot-challenge-schedules)
- [GT Europe calendar](https://gt-world-challenge-europe.com/calendar)
- [Supercars revised calendar](https://www.supercars.com/news/supercars-news-2026-change-of-date-penrite-oil-sandown-500-statement-calendar)
- [WEC original schedule](https://www.fiawec.com/en/news/le-calendrier-2026-du-fia-wec-devoile/8356)
- [WEC replacement final rounds](https://www.fiawec.com/en/news/fia-wec-and-fia-confirm-venues-for-final-two-rounds-of-2026/13698)
- [WEC Monza qualifying / race start times](https://www.fiawec.com/en/news/high-speeds-and-high-stakes-in-monza-season-finale/13912)

Date-only entries have exclusive end dates, as iCalendar specifies. They never
become false midnight local sessions. UTC / timezone-aware imported sessions are
converted; floating times are rejected. Browser imports need a VTIMEZONE definition
for non-UTC TZID entries and remain local. The CLI can use recognized IANA TZIDs.
Import replaces a series/year, including deletions; recurrent events need prior
expansion. No server endpoint fetches arbitrary user-submitted URLs.

## Looking Back and engineering evidence

Engineering topics retain publisher links in the API and UI. Source descriptions
are distinct from measured outcomes. W11 suspension / cooling, RB19 floor changes
and MCL39 brake cooling are starting points for investigating traces, not proof
of an isolated lap-time benefit. Concept animations are labelled schematics;
there is no fabricated CFD, temperature map or proprietary car geometry.

Era advantage uses primary **team identity**, including replacement drivers,
rather than assuming one fixed pair raced every round. Compare best Q1 lap to the
fastest other team's Q1 lap. Negative seconds/percent means advantage; missing
rounds are disclosed. Percent gaps improve scale comparisons but do not remove
circuit, weather, rule or tyre differences between years.

## Verification and operational limits

Run the commands in README after applying the patch. The backend suite uses
synthetic data to test the actual adapters and analysis contracts. DOM tests mount
all six routes, navigate tabs, replay championship movement, save / score a
forecast and operate lap controls. They do not verify browser layout or upstream
availability. Production TypeScript / Vite build is also checked.

During development, live F1 schedules and Jolpica standings responded. Raw
FastF1 session timing could not be loaded from this execution environment; the
provider attempted account authentication and timing data remained unavailable.
Consequently full live telemetry, empirical season training and a real historical
accuracy claim are not verified here. No credentials or model weights are bundled.
A browser binary download was also unavailable; UI checks use DOM interaction
fixtures, not a claimed visual browser run.

The season-analysis queue is intentionally single-worker and process-local,
limited to ten retained/queued jobs with one running download worker. Completed
jobs are reused for an hour. A backend restart expires those jobs; the UI offers
an explicit error on a lost job. Use a shared queue before adding server workers.
FastF1 upstream caching remains in addition to a bounded session-object cache.
Network requests are subject to provider availability and rate limits.
