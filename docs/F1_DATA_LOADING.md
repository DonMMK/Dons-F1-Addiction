# Historical data without an F1TV account

## Pending sessions in the frontend

HTTP 425 means the selected session has not started, its results are not yet
published, or its free historical data is still pending. The UI shows an
informational status with the provider's explanation and suggests selecting an
earlier completed session. For GET requests, **Check again** retries manually;
when `Retry-After` is supplied, its earliest retry time appears in the user's
local time and the button stays disabled until then. This is not a promise of
publication at that time. The frontend never polls automatically. Changing the
selection or leaving the page clears the previous notice and cancels its timer.
Prediction submissions use the same status notice; **Run & save** remains the
explicit action. Other HTTP errors retain their error styling. HTTP 425 entries
in the backend access log remain expected; no results are fabricated to hide them.

This patch applies after `f1-backend-data-loading-fix.patch`. No F1TV account,
API key, login, or environment variable is required for the default historical
route. Install requirements and restart the backend:

```bash
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
```

## Provider selection

| `F1_TIMING_PROVIDER` | Behaviour |
| --- | --- |
| omitted / `auto` | Existing usable FastF1 cache, then public OpenF1 historical timing. Optional authenticated archive fallback only when credentials already exist. |
| `openf1` | Use public OpenF1 historical timing directly; no archive fallback. |
| `fastf1` | Previous native cache/archive behaviour; uncached protected data requires eligible archive access. |

Published Q/R/Sprint classifications, standings and result scoring continue to
use Jolpica. Public schedule resolution tries the FastF1 schedule repository and
Jolpica, never the protected timing backend. The OpenF1 session is matched by
session name and a unique UTC start within 12 hours, not by assuming its meeting
key equals an F1 round. Cancelled, future, ambiguous and live sessions return
specific errors. A delayed session's observed finish extends the historical
waiting window. The source's actual availability still governs every channel.

OpenF1 history starts in 2023. Free access excludes the live window (until 30
minutes after a session ends). Earlier timing needs an existing cache or optional
native access. W11-era published qualifying charts still use Jolpica; this patch
does not invent 2020 telemetry.

## Empirical analysis and replay

OpenF1 laps are mapped into the existing backend schema: lap and sector times,
roster, compound, stint, completed-lap tyre age, pit exclusions, weather and
race-control screening. Known stale race-control messages outside the session
window are removed. Reported deleted laps use the affected lap in message text,
not the leader's lap at message publication. An unassignable deletion fails
closed. Overlapping stint ranges and duplicate lap identities are excluded.

`IsAccurate` remains unknown and `TrackStatus` remains `UNKNOWN`: OpenF1's screen
is not FastF1's accuracy flag. A separate OpenF1 eligibility column requires
consistent positive sectors, known pit coverage, no opening/pit/reported-deleted
lap, and a whole-lap interval without outstanding race-control hazards. Missing
coverage is excluded. Sector CLEAR cannot end SC/VSC or a red flag; uncertain
restarts remain excluded until an explicit track GREEN. This intentionally loses
some usable laps. Unreported deletions/incidents, approximate timestamps, traffic,
fuel and setup remain limitations. Sources, counts and warnings are returned and
shown on Weekend by Weekend and Ghost Car. Qualifying gaps use published shared
Q1/Q2/Q3 results; phases are never guessed from OpenF1 lap timing.

Replay fetches only the requested driver and selected lap's time window from
`car_data` and `location`. It matches position within 0.5 seconds, rejects long
sample gaps, normalizes brake to 0/1 and integrates speed for estimated distance.
Recorded positions are approximate (~3.7 Hz); replay and distance-aligned time
deltas are illustrative, not precise engineering measurements. Missing gear, speed or location is reported rather than filled with fabricated
channels. Missing DRS (notably the 2026 aero feed) remains null and plots as gaps;
it does not discard otherwise usable car/position samples.

The web practice-model adapters and v13 feature extraction accept these sessions.
V13 input metadata and training manifests include source provenance. Train a new
iteration to use newly available practice evidence; existing model artifacts are
not silently rewritten. Legacy CLI entry points still use their original native
FastF1 loaders; this patch changes the web backend and its training command.

## Cache, limits and diagnostics

OpenF1 JSON responses live in `$F1_DATA_DIR/openf1/openf1.sqlite3` (default
`var/openf1/openf1.sqlite3`). Successful non-empty historical responses are cached
for seven days, session metadata for one hour, and empty responses for at most
60 seconds. SQLite shares a conservative 2.1-second request spacing across
workers on this data directory. HTTP 429 sets shared backoff; cached responses
remain readable. The budget cannot coordinate other applications or machines
sharing your public IP. Keep this cache directory persistent and out of Git.

No full-session high-frequency download, blanket cache clearing, or automatic
retry loop is performed. Optional missing channels give warnings; failed required
channels return typed 425/502/503 responses and `Retry-After` when applicable.
An uncached weekend can take tens of seconds. Production proxies should allow
sufficient request time; repeated refreshes consume the same shared budget.

```bash
python -m backend.check_data --year 2026 --round 19 --session R --timing
python -m backend.check_data --year 2026 --round 19 --session Q --timing --telemetry-driver VER
curl http://localhost:8000/api/data/status
```

`authentication.authenticated: false` is expected without F1TV. Check the actual
`timing.source` and any provider warnings. Set `F1_TIMING_PROVIDER=openf1` in the
backend process environment to force the public provider when diagnosing.

Sources: [OpenF1 API documentation](https://openf1.org/docs/) and
[access, historical window and limits](https://openf1.org/).

## Verification of the public provider patch

Backend regressions cover source selection without archive auth, public-only
metadata, published results, teammate matching, missing channels, ambiguous and
live sessions, deletion/pit/hazard screening, duplicate laps, approximate
telemetry matching, missing 2026 DRS, disk cache reuse and shared rate backoff.
Frontend checks compile TypeScript, build production assets and exercise all six
routes in the DOM, including source warnings and absent DRS. Browser rendering
and authenticated archive access are not claimed as tested here.

Live checks without credentials loaded 1,360 Mexico 2026 race laps, conservatively
retained 62 pace samples, and returned a successful VER/HAM replay comparison
with 298 samples per driver and null DRS. These counts describe one provider
snapshot, not guaranteed coverage for every session.

## Previous native archive follow-up (optional mode)

The following notes describe `F1_TIMING_PROVIDER=fastf1`; the default public route
above supersedes any statement below that raw timing always needs F1TV.

## Cause of the reported failures

FastF1 can return a driver/results list even when timing downloads fail. A
“Finished loading data for 22 drivers” log is not evidence that lap timing,
weather, race control or car position loaded. The previous shared loader then
turned missing laps into a generic ValueError, which routes labelled 404 / 422.

There are two relevant upstream changes:

- FastF1 3.9 added authenticated archive access after Formula 1 required login in
  October 2026. An active F1TV Access/Pro/Premium account is required for uncached
  protected timing downloads.
- FastF1 3.9.1 / 3.9.2 fixed the unexpected timestamp format in the 2026 Mexican
  Grand Prix archive, including telemetry. The backend now requires 3.9.2 and
  stays within the tested 3.9 release series.

Sources: [maintainer release notes](https://github.com/theOehrly/Fast-F1/releases)
and [authentication documentation](https://github.com/theOehrly/Fast-F1/blob/main/docs/api_reference/accounts_auth.rst).

## Optional native archive installation and authentication

Activate the same Python environment used by the backend, stop the server and run:

```bash
python -m pip install -r backend/requirements.txt
python -c "import fastf1; print(fastf1.__version__)"
python -m fastf1 auth f1tv --authenticate
python -m uvicorn backend.app:app --reload --port 8000
```

Enter account credentials in the FastF1 terminal prompt. The backend reuses the
locally stored token from the same OS user. A free Formula 1 account without an
eligible subscription does not grant protected archive access. Tokens expire;
authenticate again when asked. If direct sign-in fails, FastF1 also supports:

```bash
python -m fastf1 auth f1tv --authenticate --method browser
```

Follow FastF1's browser/addon instructions. There is no backend login form, no
hardcoded token and no account credential included in this patch. For unattended
native renewal, FastF1 supports `F1_USERNAME` / `F1_PASSWORD` in the server process
environment. Never put their values into a tracked file or a support log.

The server will not prompt for a password or open a browser inside an API worker.
The small internal FastF1 auth bridge and cache-existence adapter are isolated in
`backend/services/f1_access.py`, covered by tests, and constrained to FastF1 3.9.x.

## What works without protected timing access

Published Q / R / Sprint classifications are fetched directly through Jolpica,
without calling `Session.load()` on the protected F1 streams. These support driver
lists, qualifying-anchor legacy models, result scoring, era qualifying charts and
the qualifying part of Weekend by Weekend. Their source is explicitly recorded.

A partial weekend response includes qualifying teammate gaps from the deepest
shared published Q segment, warnings and `dataSources`. Race gaps, tyre trends,
weather and matched-lap counts are not fabricated when raw race timing is absent.

Practice-based predictions and detailed race/telemetry analysis require session data, now supplied by OpenF1 by default.
The empirical model uses its existing missing-practice indicator if raw practice
cannot be loaded; its input metadata states that omission. Training outcome labels
now use published race classifications, with a conservative next-day availability
cutoff when the exact publication time is unknown. No future result is used in a
prediction's features.

## Cache handling

Existing caches from `f1_cache/`, `formula1-prediction/f1_cache/`,
`formula1-ghost-car/.fastf1_cache/` and `formula1-best-car/cache/` are discovered.
A populated existing parsed cache is preferred; otherwise `var/fastf1` is used.
Missing parsed files from other known locations are copied without overwriting
or deleting originals. `F1_CACHE_DIR` explicitly selects the cache location;
`F1_DATA_DIR` controls prediction history, model storage and the separate OpenF1 cache.

There is no blanket cache clearing and no `ignore_version=True`. FastF1's cache
version checks still apply. Cache-only attempts are request-context scoped rather
than changing global offline mode for other threads. An entirely cold session is
not passed through every parser just to produce repeated “Failed to load” logs.
Only usable timing sessions enter the in-memory success cache. Short failure
memoization avoids repeated downloads; CLI token-file changes are detected.

Weather and race-control properties can raise DataNotLoadedError instead of
returning an empty DataFrame. They are treated as missing optional channels, with
warnings. Their absence does not discard valid lap timing. Missing race-control
information still limits deleted-lap verification; warnings retain that caveat.
A FastF1 SystemExit on a bad cache update is converted into a data error rather
than terminating the API worker.

## Diagnostics

```bash
python -m backend.check_data --year 2026 --round 19 --session Q
python -m backend.check_data --year 2026 --round 19 --session Q --timing
python -m fastf1 auth f1tv --status
```

The first command verifies public results. The second also verifies raw laps.
The diagnostic prints version, selected cache, counts, warnings and status only;
it does not print a password or token. `GET /api/data/status` provides a minimal
status response without triggering login or archive requests.

Upstream failures carry an `X-F1-Data-Error` header and a readable `detail`:

| Code | Meaning |
| --- | --- |
| `fastf1_upgrade_required` | Old FastF1 runtime is still loaded; install and restart |
| `archive_auth_required` | No usable cached timing and no valid login |
| `archive_auth_rejected` | Archive rejected authentication; log in again |
| `archive_access_denied` | Upstream HTTP 403; check entitlement / network |
| `archive_network_error` | Archive connection failed |
| `session_not_started` / `session_not_published` | Timing is not available yet (425) |
| `archive_rate_limited` | Provider requested a pause |
| `timing_data_incomplete` | Archive responded, but required timing channels failed |

Archive authentication is a server-side data dependency, so its failure is 503,
not an app-login 401 or a missing-route 404. Invalid model choices remain 422.
Scoring uses current published classifications and preserves genuine provider
errors rather than reporting every failure as “race not finished”.

## Verification

```bash
python -m unittest discover -s backend/tests -v
```

Regression tests cover cold/partial/warm caches, native auth without prompts,
HTTP failure classification, cache migration, timezone-safe result loading,
public qualifying fallback and the existing model/analysis contracts.

Live checks from this execution environment loaded 22 classified drivers and a
normalized v12 Q forecast for Mexico 2026, plus 11 published teammate Q comparisons.
No F1TV account was available here, so authenticated raw lap/position downloads
are not claimed as verified. The diagnostic / auth commands above verify that
last dependency on the machine running the backend.
