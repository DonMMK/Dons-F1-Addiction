# Automatic FIA documents

Apply this patch after `f1-free-insights-workbench.patch`. There are no new
dependencies or required environment variables. Startup commands stay the same.

## Runtime behaviour

Starting `python -m uvicorn backend.app:app --reload --port 8000` starts a background
FIA indexer through FastAPI's lifespan. The API starts serving without waiting for
FIA downloads. The worker reads the current year's public F1 schedule and queues
completed weekends and races within the next seven days. It repeats the schedule
check hourly, including when the year rolls over. During January it also checks
the previous season. Opening another year's weekend queues that season and
prioritises the selected event. Past years are discovered on demand rather than
downloading the entire FIA archive at every startup.

For each event, the worker discovers the **season identifier and event spelling**
from FIA's public dropdowns, follows the selected season/event catalogue and saves
the published PDF links. It does not maintain an annual list of PDF filenames or
copy the current season's records into a missing year. Historical spelling aliases
remain compatibility mappings. Constructor names are read from Jolpica's public
season catalogue and enriched by the actual weekend roster when available; a new
constructor does not require adding a fixed roster to source code.

There is no dependency on an undocumented FIA JSON API. FIA provides public HTML
catalogues and linked PDFs; the backend consumes them over HTTPS and exposes its
own stable cached REST response:

```
GET /api/documents/{year}/{round}
```

For example, `/api/documents/2026/20` returns upgrade evidence, discovered official
documents, indexed season history and `refresh` status. This endpoint only reads
cache/queues work. It never downloads or parses a PDF on the HTTP request thread.
The main weekend response includes the same refresh metadata. There is no public
endpoint that accepts arbitrary URLs or bypasses cache expiry.

## Checks, states and persistence

| Situation | Runtime behaviour |
| --- | --- |
| First start or new season | Discover eligible events in the background; unknown data remains unknown until indexed |
| Known submission | Recheck every six hours; compare the PDF hash and reuse the parsed content when unchanged |
| Missing season/event/submission | Show not published/not discoverable and retry hourly; never substitute another year or infer zero upgrades |
| New or changed PDF layout | Show needs review and retain the previous validated snapshot with its original evidence date |
| Network/HTTP/parser failure | Retain cached evidence; persist exponential retry delay, starting at ten minutes and capped at six hours |
| FIA 429/503 | Honour Retry-After (up to one day) and pause other FIA requests through the shared rate budget |
| Backend restart | Reload cache, retry times and pending jobs; expired work leases recover automatically |
| Backend stopped | No checks run; the next start catches up from the schedule |

The worker spaces FIA requests by at least 2.5 seconds. Root/season HTML and PDF
bytes are cached for at most an hour, so backfilling a season reuses the catalogues.
Published document titles and publication labels come from the event page. Only
the supported car-presentation tables become structured upgrade records; maps,
Pirelli notes, classifications, decisions and other PDFs are linked as source
documents. New catalogues remain available even if a PDF cannot be parsed.

The Upgrades tab polls **our cached status** every 30 seconds while visible. This
does not trigger an FIA request every 30 seconds or reset the backend's retry
delay. It shows the last publication check, next eligible check, state, source
links and the date of the retained evidence. Manual “Check cached document status”
has the same cache/rate-limit behaviour.

State lives in `$F1_DATA_DIR/weekend_evidence/fia_documents.sqlite3`. Validated
snapshots retain the existing `{year}-{round}.json` format, replaced atomically
with unique temporary files. Shipped historical snapshots are optional offline
seed data, rather than a list the application requires for future seasons.
Existing indexed records are preserved.

For containers, mount `F1_DATA_DIR` on durable storage. Local API workers sharing
the same SQLite files share leases and rate limits. Run one application replica
with a local durable volume; independent replicas or unreliable network-file
locking need a shared database/queue and provider budget before scaling out.
Existing prediction jobs still have their own in-process constraints.

Automatic discovery is enabled by default. `F1_FIA_AUTO_REFRESH=false` disables
network work if offline operation is needed, while cached evidence remains
readable. The old `python -m backend.refresh_weekend_sources ...` command remains
an optional diagnostic tool and is no longer part of normal operation.

## What is still curated

Raw timing, weather observations, standings and the F1 schedule already use
runtime providers. FIA document links, declaration tables and indexed history
now update automatically too. Reviewed track-demand descriptions and engineering
articles remain attributed, year-scoped editorial context; a newly downloaded
PDF is not automatically a validated explanation of a car's aerodynamic behaviour.
For an unreviewed year, the app shows measured telemetry context and discovered
FIA Pirelli/map links without carrying forward a previous year's tyre allocation.
Other-series calendars still use the existing snapshot/ICS import workflow; this
patch automates FIA F1 documents, not every motorsport publisher.

Future public data can only be used after publication. FIA may change its HTML,
event naming or PDF templates; unsupported changes are reported for review rather
than guessed. The code is year-independent, but cannot guarantee compatibility
with an unseen future publisher format.

## Verify

```bash
python -m unittest discover -s backend/tests -q
cd frontend
npm test
npm run build
```

Start the backend, open a completed weekend and select Upgrades. On a cold cache,
queued/checking is expected while the worker retrieves the catalogue and PDF.
Opening `/api/documents/{year}/{round}` directly provides the same status without
loading race telemetry. A page refresh is not needed for the Upgrades tab to pick
up new evidence. The main pace/track summary can be refreshed separately.

Automated tests use simulated future seasons/new constructor names and cover
missing publication, wrong event rejection, identical-hash reuse, persistent TTLs,
restart recovery, worker leases, HTTP cache reuse, Retry-After, preservation of
cached evidence, and a nonblocking cached API. No tests need an F1TV account.
