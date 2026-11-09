# Expanded weekend evidence

This patch applies to the supplied `f1-addiction-llm-latest.txt` export, after the
OpenF1 and pending-session patches. It preserves the existing teammate analysis
and adds track context, weather history, matched package-pace estimates,
execution records, a speed-zone map and a sourced upgrade timeline.

## Run and select evidence

```bash
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
npm --prefix frontend run dev
```

Open Weekend by Weekend and choose a round. The new pace selector defaults to
slick-tyre laps. Wet/intermediate, cool (<30°C), warm (≥40°C), and all matched
conditions can be selected separately. Rain sensor readings do not measure road
grip. The original teammate sample remains separate and is not changed by this
new ranking filter. The old peer-relative table remains descriptive, with varying
peer sets; it is not the reference used for the new graph estimates.

Practice and the corner-speed comparison load only when requested. This avoids
downloading high-frequency streams for every driver whenever a weekend opens.
The existing pending-data notice handles unpublished/future sessions.

## What is estimated

The site does **not** claim to identify pure car speed or separate driver skill,
fuel, energy deployment, damage, tyre management and strategy from one weekend.
No driver name, team reputation, finishing position or upgrade count is a pace
feature or bonus. Race classification and actual starting grid are displayed
alongside the estimates, not used to fit them. There is no automated luck score.

The race sample requires the existing quality screen plus:

- Finite timestamped weather within 90 seconds of the lap midpoint.
- Known gap observations covering the lap, with no interval gap above 10 seconds
  and no observed close-following gap ≤1.5 seconds. A leader's numeric zero gap
  to the leader identifies clear-ahead status; lapped-string/unknown intervals
  are not fabricated as clear air. This screen cannot rule out every traffic or
  backmarker effect.
- Same race lap, compound, tyre age within one lap, midpoint clock time within
  90 seconds, track temperature within 2°C and the same rain report for each
  pair. Timing/date approximations and wetness remain limitations.

For practice, compare three-minute clock windows instead of race lap numbers.
Only stints with at least three screened laps contribute; an observed lap nearest
the driver/window median is used. Fuel loads and practice traffic remain
uncontrolled, prominently labelled as such. Practice estimates are not merged
into the race result.

Driver pairwise median differences form a graph. An edge needs at least eight
matched windows spanning three three-window blocks. An equal-edge-weight least
squares fit sets the component mean to zero. Reported graph-fit RMS measures how
well that additive summary agrees with its pairwise observations. It is not a
mechanical car measurement.

Team scores equally average **both** fitted driver observations from the same
connected component, then use a team-group zero-mean reference. A missing second
car or drivers in disconnected components prevents a team rank. A race winner
can be unranked if no sufficiently comparable peers exist; that does not mean the
car was slow. It prevents a best driver from being silently substituted for an
entire team.

Two hundred shared block-bootstrap draws resample three-window blocks across
the comparison group. Report exploratory 95% score intervals and rank ranges only
when at least 100 connected draws survive. Ranks rounded to a millisecond share
ties; rank ranges include both ends of tied ranks. These are sample/model
uncertainty summaries, not probabilities that a team owns the fastest car.
Disconnected groups are labelled and never share one ranking chart.

Sector summaries reuse the matched pair observations and graph reference.
Different corner-speed minima, entry/exit trade-offs and higher straight speed
do not by themselves identify downforce, horsepower or driver contribution.

## Track and weather context

The initial reviewed track-demand profile covers Interlagos **in 2026**, based on
[Pirelli's preview](https://press.pirelli.com/pirelli-brings-the-softer-trio-back-to-interlagos/).
It includes the C3/C4/C5 allocation and resurfacing context. This is attributed
engineering context and is not a named-team advantage prior. Other tracks use
their measured sector evidence and optional speed map; missing reviewed demand
profiles are explicitly indicated. Extend `data/track_context.json` with sourced,
year-scoped records rather than hardcoding presumed team strengths.

The speed map compares two screened recorded laps. It detects speed minima with
a five-sample median filter, ≥25 km/h prominence and ≥2.5-second separation.
Slow/medium/fast use <120, 120–200, ≥200 km/h at the reference minimum. These are
**detected speed zones, not official turn numbers**. The other driver's minimum
within ±2% normalized distance is illustrative; sample rates, different lines,
approximate positions, tyres, fuel and track evolution limit precise comparison.
Sector labels use the reference lap's recorded sector boundaries when present.
Speed-only maps do not require throttle, brake, gear or DRS channels: unrelated
invalid control values cannot invalidate recorded speed/position evidence. They
are not clamped or fabricated.

## Upgrade declarations and history

The patch includes verified FIA car-presentation snapshots for 2026 rounds 18–20:
United States, Mexico City and São Paulo. Brazil's submission declares four
McLaren components: front wing, rear wing, beam wing and floor furniture. The
other ten teams submitted no updates in that document. Austin includes an Alpine
entry whose layout was not confidently parsed; it remains **Document needs
review**, not zero upgrades.

Each snapshot has an official source URL, page references, indexed timestamp and
document hash. Component names record a declaration, not proof of race fitment
or a measured lap-time benefit. PU replacements are not conflated with declared
aerodynamic/performance component updates. No gains are assigned from counts.

To refresh an event or backfill completed rounds using public FIA documents:

```bash
python -m backend.refresh_weekend_sources --year 2026 --round 20
python -m backend.refresh_weekend_sources --year 2026
```

This is an explicit ingestion task, not an unauthenticated public write endpoint.
It discovers the season identifier from the FIA index, checks PDF year/event
headers and parses the supported declaration table layout. Missing or changed
layouts stay unknown/unparsed. It does not guess counts. Downloads are restricted
to FIA HTTPS paths, bounded in size and checked at every redirect.

New snapshots go to `$F1_DATA_DIR/weekend_evidence/`, overriding the shipped
snapshot for that round. The UI shows indexed rounds only, up to the selected
round. Missing history is labelled unknown. A failed refresh preserves the last
snapshot; it does not convert absence into no upgrades. Parsing is conservative
and does not replace a human technical review of a changed FIA template.

## Sources and operational limits

- [OpenF1](https://openf1.org/docs/): laps/sectors, stints, timestamped weather,
  intervals, pits, race control and selected-lap telemetry. Public history from
  2023; the existing cache/rate limit and historical-access restrictions apply.
- Jolpica: classifications and starting grids, separately from the pace fit.
- [FIA documents](https://www.fia.com/documents/championships/fia-formula-one-world-championship-14):
  declared component changes and supporting circuit/Pirelli documents.
- Pirelli: reviewed, year-specific track/tyre context.

Native FastF1 cached race sessions can use public OpenF1 gap/pit observations for
this expanded analysis. Missing traffic/weather coverage yields an incomplete
ranking, not an invented substitute. No F1TV login is required for public history.

The interval endpoint adds one cached bulk request per race. Initial cold loads
can take over a minute. Keep one worker as documented for the current in-process
jobs. New analysis endpoints are read-only and source refresh is a CLI task.

## Verification

Regression tests cover identity invariance, equal two-car weighting, missing
second cars, disconnected groups, ties, weather/traffic exclusions, unmatched
tyre ages and timestamps, separate practice treatment, source/event validation,
unknown upgrade coverage, changed PDF layouts and approximate speed-zone output.
Frontend interaction checks exercise condition selection, practice loading,
corner map rendering, source links/status and the existing pending-session flow.

Live Brazil 2026 verification loaded 1,438 race laps, 29,368 interval observations
and 110 weather samples. The first slick-tyre screen retained 413 eligible samples;
only five teams met the two-car connected-ranking requirement. These describe
one provider snapshot under this policy, not a verified complete car order or a
prediction of what a different strategy would have achieved.

The live slick/wet weekend API responses and the VER/PIA race speed-zone endpoint
returned successfully. Production build and DOM interaction tests passed; a full
visual browser inspection is not claimed.
