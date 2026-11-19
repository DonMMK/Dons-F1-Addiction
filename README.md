# Don's F1 Addiction

A React / TypeScript frontend and FastAPI backend for championship context,
empirical weekend comparisons, recorded lap replay and auditable race predictions.

## Pages

| Route | What it does |
| --- | --- |
| `/` | Latest cached car-performance grid, driver / constructor standings, previous-round movement, animated championship order, F1 calendar and next local session |
| `/weekend` | Six analysis views: track/weather overview, car-performance grid and recent-weekend matrix, matched pace, strategy/tyre plots, selected-lap track dominance, FIA upgrades; supporting teammate comparisons |
| `/prediction` | Version descriptions, saved winner distributions, post-race Brier / log-loss scores and trained-iteration validation metrics |
| `/ghost-car` | Two recorded fastest laps with play / pause / scrub controls and speed, throttle, brake, gear, DRS and cumulative time traces |
| `/looking-back` | Cited W11 / RB19 / MCL39 engineering context, conceptual car diagrams, signed qualifying advantage and recorded lap comparisons |
| `/not-just-f1` | Mixed-series calendar: F1, WEC / Hypercar, IMSA, all ten 2026 NLS races, GT Europe and Supercars; browser-local calendar imports |
| `/best-car` | Redirect to `/looking-back` for existing bookmarks |

See [expanded weekend evidence](docs/WEEKEND_EVIDENCE.md) for sources, matching,
uncertainty and FIA history refresh commands.

See [the free analysis workbench notes](docs/FREE_INSIGHTS_WORKBENCH.md) for the
competitor comparison, data sources, new views, fuel assumptions and remaining gaps.

See [the car-performance grid notes](docs/CAR_PERFORMANCE_GRID.md) for the
image-inspired layout, weekly updates, normalisation, uncertainty and coverage rules.
The default adjusted race-pace view broadens coverage using tyre, race-lap and
traffic controls. Strict matched evidence remains separate; single-car proxies
and unsupported team rows are labelled, with per-driver coverage diagnostics.

FIA documents now refresh automatically when the backend starts and while it runs.
Open Upgrades to see publication/check status and discovered official documents.
No annual PDF list or indexing command is required. See
[automatic FIA discovery](docs/AUTOMATIC_FIA_DOCUMENTS.md) for behaviour and deployment.

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

## Deploy on an existing Oracle Ubuntu VM

The public link uses **HTTPS port 443** via
[Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel).
It works in an ordinary browser and can be forwarded. The VM builds and serves
React, runs FastAPI and its refresh workers, and stores SQLite locally. Funnel
is available on the free Personal plan and has bandwidth limits. Use port 8443
if 443 is assigned to another Tailscale route.

### Check the OCI subscription before deployment

In OCI, check **Billing & Cost Management** for your subscription and **Compute
→ Instances → your VM** for its shape, boot volume and region. This walkthrough
reuses those resources. It provisions no additional OCI compute or storage.

- Oracle's [current Free Tier page](https://www.oracle.com/cloud/free/) lists
  1,500 Ampere A1 OCPU-hours and 9,000 GB-hours of memory per month, equivalent
  to 2 OCPUs and 12 GB total across A1 instances running all month. A 4 OCPU /
  24 GB VM can run the app, but do not assume that configuration is free all
  month. The shape's eligibility label alone does not confirm monthly coverage.
- Oracle says it will not charge your card on an unupgraded Free Tier account.
  Resources beyond the Always Free limits can be reclaimed at the end of a
  trial, and idle Always Free instances may be reclaimed. On Pay As You Go,
  check **Cost Analysis** and your actual allowance before keeping 4 OCPUs /
  24 GB running. Installing or limiting the app does not change the provisioned
  shape. Saving a shape without changes does not change billing.
- For the conservative Always Free configuration, keep the total A1 allocation
  at 2 OCPUs / 12 GB or below in the tenancy's home region, total boot and
  block volume capacity within 200 GB, and outbound transfer within the free
  allowance. Back up important files off the VM before resizing because a
  restart may affect existing services. If the current VM already fits your
  confirmed allowance, leave its shape as it is.

See [Oracle Free Tier and trial rules](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
and [Always Free resource limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

### 1. Connect to the VM

If you are already at the `ubuntu@jarvis-vnc` prompt, continue with the Ubuntu
steps below. Otherwise run this on your Mac. Set both placeholders to the
VM's public IP and your existing key path. Reuse the same OCI SSH key that
already works for the VM. The `.key` private key stays on your Mac. The
`.pub` file is for authorizing an SSH account. If SSH already works, skip
copying either file. Friends use the web link and need no SSH credentials.

```bash
OCI_HOST=149.118.70.167
OCI_KEY="$HOME/GitHub/Dons-F1-Addiction/ssh-key-2026-05-17.key"
chmod 600 "$OCI_KEY"
ssh -i "$OCI_KEY" -o IdentitiesOnly=yes "ubuntu@$OCI_HOST"
```

### 2. Build the app on Ubuntu

The examples use `/home/ubuntu/f1-addiction` as the checkout. Keep existing
repositories and services in their own directories. Check the local listener
ports first. This guide uses 8765 and 8081. If either is occupied, pick unused
ports and update their references throughout these steps.

```bash
sudo ss -ltnp
sudo apt update
sudo apt install -y git curl rsync python3-venv caddy
```

Use Node 24 LTS, for example via [nvm](https://github.com/nvm-sh/nvm#installing-and-updating)
and `nvm install 24`. Skip the clone if the checkout already exists. For a
private repo, use your usual repository access. The OCI SSH key only gets
you into the VM.

```bash
git clone https://github.com/DonMMK/Dons-F1-Addiction /home/ubuntu/f1-addiction
cd /home/ubuntu/f1-addiction
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt

if [ -f frontend/package-lock.json ]; then
    npm --prefix frontend ci
else
    npm --prefix frontend install
fi
npm --prefix frontend run build &&
    sudo install -d -m 0755 /srv/f1-addiction/web &&
    sudo rsync -a frontend/dist/ /srv/f1-addiction/web/
```

### 3. Start FastAPI under systemd

Open `sudoedit /etc/systemd/system/f1-addiction.service` and add the unit
below. Use a single worker for the app's in-process jobs. The state directory
holds prediction history, trained models, timing caches and refresh data
outside the checkout.

```ini
[Unit]
Description=F1 Addiction API
Wants=network-online.target
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/f1-addiction
StateDirectory=f1-addiction
StateDirectoryMode=0750
Environment=F1_DATA_DIR=/var/lib/f1-addiction
ExecStart=/home/ubuntu/f1-addiction/.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now f1-addiction
curl -fsS http://127.0.0.1:8765/api/health
```

### 4. Serve React and the API on the same address

Add this site to `/etc/caddy/Caddyfile` using `sudoedit`. Preserve any existing
site blocks. On a fresh install, replace the example site. Caddy listens only
on loopback here. It serves the React build, supports direct links to pages
like `/weekend`, and proxies `/api/*` with the prefix intact.

For a small preview, use one shared browser password. Run `caddy hash-password`
and enter a strong password at the prompt. Replace `PASTE_PASSWORD_HASH_HERE`
with the resulting hash. Use `basicauth` in place of `basic_auth` for Caddy
before v2.8. The account name is `preview`. For an open preview, omit the
entire auth block. Anyone reaching that preview can then read shared prediction
history and submit expensive requests, so use the shared login unless you intend
to make those available to everyone.

```caddyfile
:8081 {
    bind 127.0.0.1

    basicauth {
        preview PASTE_PASSWORD_HASH_HERE
    }

    handle /api/* {
        reverse_proxy 127.0.0.1:8765 {
            header_up -Authorization
        }
    }

    handle {
        root * /srv/f1-addiction/web
        try_files {path} /index.html
        file_server
    }
}
```

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile &&
    sudo systemctl enable caddy &&
    sudo systemctl reload-or-restart caddy
```

### 5. Publish and verify the HTTPS link

Install [Tailscale on Linux](https://tailscale.com/docs/install/linux) and
run `sudo tailscale up` if the VM has not already joined your Tailscale
network. Check both Serve and Funnel status so you can avoid replacing an
existing route. Enable Funnel on port 443 and follow its admin prompt.

```bash
sudo tailscale serve status
sudo tailscale funnel status
sudo tailscale funnel --bg --https=443 http://127.0.0.1:8081
sudo tailscale funnel status
```

Share the exact `https://…ts.net` URL from the output. If you chose 8443,
replace 443 in the Funnel command and keep `:8443` in the shared URL.
The public port is on the Funnel endpoint, so this setup needs no new OCI
inbound rules. Leave the Ubuntu and OCI SSH rules for your own administration.
Keep Uvicorn and Caddy's local port off the public interface.

On a device without an active Tailscale connection, open the URL, sign in
if you enabled the preview password, then test `/weekend` and `/api/health`
on that host. The health URL should return JSON. With the login enabled,
`/api/health` should also return HTTP 401 when requested without credentials.
Give friends the link and the preview login over a separate channel if enabled.
If you prefer a direct OCI endpoint and already have a domain, point an A record
at the VM, use the hostname in Caddy in place of `:8081`, remove the loopback
bind in the Caddy site, and allow inbound TCP 80 and 443 on both the VM firewall
and the instance's OCI security rules. Caddy then handles HTTPS directly.
Check for an existing reverse proxy before binding those ports.

For updates, pull the approved revision, repeat the dependency install and
frontend build/copy commands, and run `sudo systemctl restart f1-addiction`.
Use `sudo journalctl -u f1-addiction -n 100 --no-pager` to check startup or
upstream errors. Keep an off-VM backup of `/var/lib/f1-addiction`. Use SQLite's
backup facilities or stop the app before copying live database files. To stop
public access, run `sudo tailscale funnel --https=443 off`, substituting the
port you used.

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


## AI-Driven Development

Use the command below to generate the code files to do some development

```
find . \
  -type f \
  ! -path '*/node_modules/*' \
  ! -path '*/.git/*' \
  ! -path '*/f1-venv/*' \
  ! -path '*/f1_cache/*' \
  ! -path '*/cache/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/dist/*' \
  ! -name 'f1-addiction-llm.txt' \
  ! -name 'package-lock.json' \
  \( \
    -name '*.py' \
    -o -name '*.ts' \
    -o -name '*.tsx' \
    -o -name '*.js' \
    -o -name '*.jsx' \
    -o -name '*.json' \
    -o -name '*.html' \
    -o -name '*.css' \
    -o -name '*.md' \
    -o -name '*.txt' \
  \) \
  -print0 |
while IFS= read -r -d '' file; do
  echo "============================================================"
  echo "FILE: $file"
  echo "============================================================"
  cat "$file"
  echo
  echo
done > f1-addiction-llm.txt
```
