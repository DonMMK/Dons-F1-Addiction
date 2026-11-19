# Free insights workbench

This patch is based on the exact source in `f1-addiction-llm(5).txt` (also byte-identical to `(4)` for code files). Apply it after the weekend evidence patch and the Barcelona FIA event-name alias. It preserves existing runtime caches and indexed FIA documents. There are no new dependencies, account requirements or paywalls.

## What the comparison showed

Reviewed on 9 November 2026. Public pages and UI were inspected; Formula Insights' paid tools were not tested. Advertised features are not independent evidence of accuracy.

| Area | Formula Insights | F1 Insights Hub | This repository |
| --- | --- | --- | --- |
| Prediction | Free beta league for fans submitting picks; paid practice-pace tools advertised | Model forecasts with uncertainty, plus separate analysis tools | Saved model forecasts, post-race Brier/log-loss scoring, model version notes and empirical model workflow; no fan league |
| Telemetry | Advertises multiple drivers/laps, speed/throttle/brake traces, dominance and corner summaries | Session analysis exposes driver/lap selection and credits OpenF1/FastF1 | Existing two-driver Ghost Car replay and control traces; this patch adds selected-lap speed/time comparisons and estimated mini-sector dominance |
| Strategy and tyres | Advertises stint visualisation and fuel-adjusted degradation charts | Session analysis includes stints; car breakdown discusses race pace and tyre behaviour | This patch adds an observed-stint timeline, selectable driver/compound plots, raw data inspection and optional assumed fuel-burn normalisation |
| Car comparisons | Advertises speed traps, sectors and braking comparisons | Public car breakdown describes corner bands, straight-line comparisons and inferred characteristics, with limitations | Existing weather/traffic/compound/age-matched package pace, equal weighting of both cars, comparison groups and uncertainty. Sector and corner-speed observations remain associations |
| Upgrades | Not established in the reviewed public pages | Not established in the reviewed public pages | Existing sourced FIA component declarations, coverage status and indexed season history |
| Presentation | Focused feature demonstrations and a polished public landing page | Compact next-race cards, clear analysis entry points and separated workspaces | This patch adds a two-column home overview, quick tool links, evidence summary cards and five weekend tabs, with supporting detail collapsed |

Sources: https://formula-insights.com/#features , https://formula-insights.com/Race_Pace , https://f1insightshub.com/home , https://f1insightshub.com/analysis , https://f1insightshub.com/car_breakdown . Do not copy their charts, text or proprietary models; these changes implement independent views over this app's own data pipeline.

## Where the data comes from

F1 Insights Hub's session-selection UI explicitly links **OpenF1** and **FastF1** under “DATA”. Its home page credits Open-Meteo for weather forecasts. These observations establish those displayed credits, not the complete server architecture or exact provider of every metric.

Formula Insights' public pages reviewed here do not establish its telemetry provider or its fuel-correction formula. FastF1/OpenF1 could supply many advertised channels, but that is a technical possibility, not verified attribution.

This app already uses:

- OpenF1 for free historical timing/telemetry from 2023 onwards: https://openf1.org/docs/ . Historical access needs no account; live access is paid. The app does not turn on live subscriptions.
- FastF1 for its supported native/cached session path: https://docs.fastf1.dev/ . Availability of historical archives depends on upstream access and cache coverage; the app's public fallback remains OpenF1.
- Jolpica-F1 for published classifications and championship data: https://api.jolpi.ca/ergast/ .
- FIA documents for declared component changes, and linked publisher documents for reviewed circuit context. A declaration neither verifies both cars' fitment nor supplies a measured lap-time gain.

No new provider is needed for the views added here. Actual fuel mass, physical tyre wear, setup, brake pressure and aerodynamic loads are not supplied by these public channels. No field in this patch claims to measure them.

## New API views

- `GET /api/weekend/{year}/{round}/strategy`: observed lap/compound/stint spans, screened tyre-age points, coverage and limitations. No telemetry download is needed.
- `GET /api/weekend/{year}/{round}/laps/{Q|R|FP1|FP2|FP3}/{driver}`: quality-screened timed-lap options; telemetry coverage is checked when selected.
- Existing `GET /api/weekend/{year}/{round}/track/{session}/{first}/{second}` accepts optional positive integer `lap_a` and `lap_b`. Omission keeps the fastest-screened-lap default. An unavailable requested lap returns a structured 422; it is never silently replaced.

The strategy endpoint deliberately does not apply the page's **pace conditions** selector: it shows the whole recorded race, with an independent compound selector for its tyre plots. Practice and team-pace views retain their existing condition matching.

## Strategy, tyre and dominance methods

Strategy bars join **consecutive observed laps** sharing reported stint and compound. Missing lap records remain blank. Unknown compounds are grey. Pit and neutralised laps remain visible in the timeline; quality-screened tyre plots exclude them. Same-stint data are split by compound before estimating any trend.

Tyre plots default to **raw lap times**. An optional user assumption normalises times to race lap 1:

```
displayed_seconds = raw_seconds + assumed_gain_per_race_lap * (race_lap - 1)
```

The editable `0.060 s/lap` example is not a circuit-, era- or driver-calibrated estimate. A positive rate reverses the assumed time gain as fuel burns off. It does not estimate kilograms of fuel. Raw points remain visible when an assumption is active; raw observations are never modified. Invalid input displays raw times with an explicit message.

Within each selected driver/stint/compound, descriptive time drift is the median of pairwise lap-time changes per tyre-age lap. It requires at least eight points spanning four tyre-age laps. No confidence interval or physical-wear claim is made, and this descriptive statistic does not feed team rankings or forecasts. Traffic, tyre warm-up, weather and management can dominate it.

The lap map splits normalised integrated distance into 25 equal bins and compares interpolated elapsed time in each bin. Negative A−B favours A; positive favours B; ±0.020 seconds per bin is displayed as neutral. This threshold is a display choice, not a statistical significance test. Colours are based on **time**, not merely higher minimum corner speed.

These are estimated mini-sectors, not official timing sectors. XY, integrated distance, sampling and different driving lines introduce alignment error. Bins cover each trace's observed span, including any missing boundary portion; their sum need not match the classified lap-time difference. Gaps over 2.5 seconds are rejected. Two selected laps cannot isolate car design or driver skill.

The existing Ghost Car page remains the place for animated cars plus speed, throttle, binary brake and gear traces. This patch's map uses the speed-only provider path, so malformed or missing control channels do not get fabricated to draw a map.

## Keeping access free

No login or payment workflow has been added. Serve shared cached responses from the backend; avoid having every visitor poll OpenF1 or fetch entire telemetry sessions. The strategy/lap lists are small, and expensive comparisons run after an explicit click. Existing SQLite caching, provider rate limits and 425/Retry-After handling remain in place. Analysis routes are loaded separately so home-page visitors do not immediately download every charting view.

Free user access still has hosting, storage and bandwidth costs. For a public deployment, the next scaling step is scheduled post-session preprocessing to small versioned JSON files in object storage/CDN, with a durable shared cache. This patch does not implement that deployment or guarantee zero running costs. Follow each data publisher's current terms when redistributing data; free API pricing does not by itself establish redistribution rights.

## Apply and verify

From the repository root:

```bash
git apply --check ~/Downloads/f1-free-insights-workbench.patch
git apply ~/Downloads/f1-free-insights-workbench.patch
python -m unittest discover -s backend/tests -q
cd frontend
npm test
npm run build
```

Use your activated backend environment for Python commands. Startup remains unchanged: `uvicorn backend.app:app --reload --port 8000` from the repository root and `npm run dev` from `frontend`. Restart the backend and refresh the browser after applying. No new environment variables, paid feed or F1TV account are required for the public historical path.

Open **Weekend by Weekend** and select **Pace**, **Strategy & tyres**, **Laps & track**, or **Upgrades**. Overview stays focused on track and recorded conditions. Arrow keys, Home and End navigate the tab strip. Advanced teammate comparisons and methods remain available in the supporting-evidence disclosure.

Validation covers missing/duplicate lap gaps, unknown tyre metadata, pit filtering, requested-lap selection, elapsed-time dominance, sparse telemetry rejection, typed publication delays, fuel-normalisation arithmetic, non-mutation of raw points, tab navigation, request parameters and stale-result clearing. The repository's pre-existing `npm run lint` command has no ESLint configuration in the uploaded source; it remains unconfigured. UI interaction tests use jsdom, not a full browser layout engine. A separate offline check against cached São Paulo 2026 observations produced 22 driver timelines, 1,438 observed laps and 1,072 screened tyre-age points; selected VER lap 48 and PIA lap 54 produced 25 estimated mini-sectors and finite JSON without upstream requests. Those two laps are a coverage check, not a controlled performance comparison.

## What remains beyond this patch

- Arbitrary multi-driver telemetry overlays (the current comparison stays at two).
- A season-wide car-characteristics workspace with comparable corner segments and uncertainty.
- Calibrated, out-of-sample practice-to-race pace forecasts. Existing practice evidence is descriptive, not a validated race-pace prediction.
- Archived forecast evaluation across many races before claiming that any new ML iteration improves accuracy.
- Weather forecasts for upcoming races; current weather analysis uses recorded session observations.
- A fan prediction league, if desired later. It is separate from automatic model predictions and would require its own user/accounts/scoring work.

These gaps should be evaluated with held-out races and explicit coverage before making claims about a “fastest car”, engine output or driver contribution.
