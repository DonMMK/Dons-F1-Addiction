# Car-performance grid

The original grid patch applies to `f1-addiction-llm(7).txt`. The incremental
`f1-performance-coverage-bridge.patch` applies after that grid patch. It uses the
same public timing, local cache and background worker. No new data account,
service or environment variable is required. `threadpoolctl`, already used by
scikit-learn, is now listed explicitly to bound numerical worker threads.

## Reading the supplied image

The reference uses one team per row, a horizontal seconds scale, top-down cars,
rank-movement arrows and green/red changes. Its title names a season span, but the
image does not establish how those values were estimated, aggregated or corrected.
This implementation borrows the visual structure and defines its own metrics
over the app's existing matched-lap analysis. It does not copy the image's values,
logos, car artwork or an unseen methodology.

## Where the views appear

- **Overview:** the latest cached completed-race car-performance board, updated
  automatically when a newer race becomes available. Championship standings keep
  their separate points/order visualisation.
- **Weekend by Weekend → Car performance:** the selected race's board, a recent
  six-weekend matrix, evidence inspection and links to exact historical weekends.
- **Pace:** the existing detailed matching, driver estimates and sector analysis
  remain available unchanged.

Each board shows a separate lane per estimated team, a team-coloured schematic car,
gap, lap/window count, rank movement, change in relative gap and
exploratory uncertainty. Click a row or activate it with Enter/Space for the
drivers, sample count and rank range. Replay toggles between the current position
and the previous estimate on the same normalised scale; reduced-motion settings
disable the transition. Percent/seconds controls change the axis units.

## What the numbers mean

The default **Adjusted race pace** view is a broader observed-package model,
described below. **Strict matched evidence** retains the original same-lap/
compound/tyre-age/weather/observed-traffic comparison graph unchanged. Strict
scores equally average both driver estimates in the same connected component.
No driver-name bonus, team tier, standings position, result, qualifying position
or upgrade count is added in either view. Strict subgroup ranks display `3/5`
and explicitly withhold a full-field rank; adjusted point orders display `~3`.

Within each comparison group, select the team with the lowest point estimate as
the reference. Current seconds/lap gap is:

```
gap_seconds = team_score - reference_team_score
gap_percent = 100 * gap_seconds / median_eligible_lap_seconds
```

For the immediately preceding scheduled eligible GP, compare the same team with
the **same current reference team**, even if that reference was not the leader
in the earlier race:

```
previous_gap_percent = 100 * (previous_team_score - previous_reference_score)
                      / previous_median_eligible_lap_seconds
change_pp = current_gap_percent - previous_gap_percent
```

Negative change means a smaller relative gap in this sample. A percentage point
is an absolute difference between percentages. A one-second gap around an 80-second
lap is not equivalent to a one-second gap around a 110-second lap; the change
column therefore uses **percentage points**, rather than subtracting raw seconds
from different circuits. The previous car marker on the seconds axis is an
equivalent position scaled to the current race's median eligible lap, not its
literal recorded seconds at the other circuit. It can be negative if that team
previously led the current reference team.

Rank arrows require exactly the same ranked team set, driver sets and evidence
tiers within a connected group in both races. A switch from a one-car proxy to
two cars cannot manufacture a progress arrow. Gap changes are also withheld when
the team or reference changes driver coverage or evidence tier. Changed membership,
missing data or disconnected previous comparisons
produce an unavailable value, not a zero change. The immediately preceding GP is
never silently replaced by an older indexed race. Condition/year/method versions
cannot be mixed. Separate comparison groups have separate zero references and
cannot be ordered against one another.

Whiskers subtract the reference score from the team score in each **shared
bootstrap draw**, preserving covariance. They are exploratory 95% gap intervals;
subtracting two marginal intervals would be incorrect. The reference's own zero
gap is a plotting definition, not certainty that it was uniquely fastest. Rank
ranges retain the uncertainty about ordering. Changes between weekends have no
confidence interval and are descriptive, not a statistical claim of improvement.

All roster teams remain visible. A team with no supported current-race estimate
gets a row without a pace marker, never an invented zero or slowest rank. The
strict view can still leave teams outside its comparison. The recent-weekend
matrix shows each round's estimated rank/gap percent, flags single-car proxies and
labels separate groups; it is not a cumulative season-performance score.

These observations combine car, driver and remaining strategy effects. Changes
in circuit, conditions, sampling, fuel, damage and management can change the
estimates. Green bars do not establish a physical upgrade gain or a driver-skill
effect. The new view cannot identify private fuel loads, setup or aerodynamic
capability that are absent from the public feeds.

## Why the field was incomplete, and the coverage bridge

In the supplied cached São Paulo data, the original screen records 1,438 laps,
keeps 1,072 quality-screened laps, and admits only 413 full-lap clear-air samples.
Norris has 54 quality-screened laps but only one strict clear-air lap. Ferrari's
drivers belong to different matched graph components. Bottas has no usable laps.
Requiring eight matched windows across three blocks for both cars therefore
leaves six teams outside the main comparison. This is a coverage restriction,
not evidence that Racing Bulls was the third-fastest car in the complete field.

The broader view uses quality-screened laps with known compound, tyre age and
matched weather under the selected condition. Pit, neutralised, deleted and
other rejected timing remains excluded by the existing quality screen. It fits:

```
lap_seconds = driver_offset + race_lap_effect + compound_effect
            + tyre_age_terms + close_traffic_fraction + unknown_traffic_fraction
            + track_temperature + rain_report + residual
```

Driver offsets are sum-constrained only to fix their common arbitrary zero.
Race-lap fixed effects absorb common time evolution; they are not actual fuel
measurements. Close traffic means the observed sample fraction at ≤1.5 seconds.
Missing or discontinuous interval streams become an explicit unknown control,
not verified clear air. These are observational associations: shared traffic
effects, management, setup, damage and actual fuel can still confound the order.

Both linear and quadratic tyre-age specifications must identify the driver
contrasts. QR removes redundant nuisance columns without discarding their span;
rank-deficient or near-singular driver comparisons are rejected. Each driver
needs eight distinct race-lap windows across three blocks, also after removing
isolated windows. The model cannot connect fully disconnected timing or a driver
whose tyre/traffic condition is perfectly confounded with identity.

Two-car estimates equally average their driver offsets, rather than choosing the
faster driver or letting the driver with more laps dominate the team average.
If only one driver qualifies, the team is labelled **Single-car proxy**. Its point
is that observed driver's estimate, not a fabricated second-car measurement.
Missing-car sensitivity samples symmetric half teammate differences from this
race; at least three observed paired teams are required. Teams with neither
driver represented remain visible without a numerical estimate. No prior team
order is carried forward, and no future weekend is promised measured data before
it exists. This covers every roster team visually while respecting real gaps.

Huber weights reduce outlier influence. Exploratory intervals combine 400 shared
three-lap wild residual draws across the two tyre-age specifications, holding
robust weights fixed. Reference subtraction uses the same draw, preserving
covariance. Proxy draws include the declared missing-car sensitivity. These are
conditional model intervals, **not calibrated 95% coverage of true car pace**;
systematic unobserved fuel or management bias is not quantified by them. Overlap
leaves rank order uncertain even when the point order is displayed.

Five held-out three-lap-block folds fit the quadratic lap model on training rows
only, then predict within-lap cross-team differences on held-out laps; unknown
lap intercepts cancel. Non-estimable test contrasts are excluded. The metric is
the mean of each held-out lap's median absolute pair error, with a zero-difference
baseline. This is a check of observed differences, not ground truth for car-only
pace or future-race accuracy. Missing validation or a worse baseline comparison
produces a provisional-model warning.

Offline replay of the cached São Paulo race now represents **all 11 teams** using
781 slick-condition model laps: ten two-car estimates and Cadillac as a one-car
proxy. Held-out error is approximately 0.630 s versus 1.122 s for zero difference,
over 45 test laps. This is a single-race verification, not validation of an entire
season. The UI exposes each driver's usable and strict clear-air counts, interval
coverage and strict exclusion reason, plus the held-out check. The strict graph
remains available alongside the broader view.

## Automatic updates and cache

`GET /api/performance/{year}?round={optional_round}&condition=slick` only queues
metadata work and reads the durable cache. It does not download or analyse timing
on the request thread. A single background worker starts with FastAPI, discovers
the current season and catches up the most recent six eligible races. Opening an
older year/round queues that window on demand. The worker reads the public F1
schedule instead of a fixed list of rounds or dates.

The race is considered for fetching 150 minutes after its scheduled UTC start;
date-only schedules use a conservative next-day boundary. This is only an attempt
boundary: the provider's actual publication/live-window checks and completed-race
status still decide whether data may be stored. Provisional races cannot replace
completed-race evidence. Publication delays and failures retain cached results.

Season metadata is checked every ten minutes. Rankable boards are rechecked every
six hours, and insufficient-coverage boards or failed/pending work retry after
ten minutes or the provider's longer Retry-After delay. Existing OpenF1 caching
and its shared rate budget apply. Regular weekend analyses also populate the same
cache, reusing work already requested by the user.

The frontend checks the cached endpoint every ten seconds while work is queued/
running, then once per minute while visible. This does not reset job expiry or
download timing for every visitor. When a new race is pending, Overview explicitly
labels an older displayed cached round; an explicitly selected weekend never
substitutes an earlier board. The backend must be running for scheduled work;
restarting resumes from durable state. Year rollover selects the new year without
an annual code change.

State is stored in `$F1_DATA_DIR/performance.sqlite3`, with method/condition/year
separation, work leases, atomic snapshots and persisted retry times. Keep this
directory on durable storage when deploying. Use the existing single API worker
setting for the app's other in-process jobs. Set `F1_PERFORMANCE_AUTO_REFRESH=false`
only if background performance fetching should be disabled; existing snapshots
remain readable and direct completed-weekend analyses can still populate them.

The coverage method bumps the snapshot/job version. Restarting the backend
automatically queues fresh boards instead of reusing the old sparse graph as an
adjusted estimate. Old cache rows are retained under their previous version;
there is no database deletion or manual indexing step. The broader fit uses the
already loaded race observations and introduces no extra upstream data requests.
If optional model computation fails, the existing strict weekend analysis remains
available with a source notice.

## Apply and verify

```bash
git apply --check ~/Downloads/f1-performance-coverage-bridge.patch
git apply ~/Downloads/f1-performance-coverage-bridge.patch
python -m pip install -r backend/requirements.txt
python -m unittest discover -s backend/tests -q
cd frontend
npm run test:performance
npm run build
```

Restart the backend and refresh the browser. The first cold cache may take a few
minutes while six race windows are prepared; there is no manual indexing step.
Open **Car performance** under Weekend by Weekend for the full matrix. Overview
shows the latest cached board automatically. Existing frontend regression tests
can also be run with `npm test` when `tests/ui.test.mjs` is present in the repo;
the uploaded text export omits that file, so the new feature has its own test
command and does not overwrite an existing test harness.

Validation covers controlled model recovery under unequal traffic exposure,
identity invariance, compound/driver confounding, disconnected timing, held-out
errors, missing-car proxies, missing condition data, optional model failure,
normalisation and fixed-reference comparisons, paired bootstrap
intervals, missing coverage, disconnected groups, changed membership, stale-lease
protection, persistent cache, publication retries, historical links, keyboard
inspection, replay, units and frontend refresh. A separate offline check uses
cached São Paulo 2026 observations; broader coverage is explicitly labelled as
model estimates and single-car proxies rather than fabricated matched evidence.
