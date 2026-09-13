# Deploying the Tennessee Situs Atlas

Two things get deployed: the **site** (static: atlas + 95 county workbenches, `site/`) and the
**refresh job** (Python pipeline that re-pulls layers and rebuilds `site/`). Everything in the site is
public data; the confidential DOR file never leaves the browser tab that pastes it.

Recommended split: **GitHub Pages** hosts the site at navigationholdings.com (free, custom domain,
deploys on every push), **GitHub Actions** runs the weekly refresh (the runners can reach TNMap /
ArcGIS Online directly, which the laptop-side sandbox cannot). Railway is wired up as an alternative
for either half if you'd rather keep it there.

## 1. Push the repo to GitHub (one time, from your Mac)

The credentialed steps below are yours to run — the tooling here doesn't hold your GitHub or
Railway logins.

```bash
cd ~/Downloads/civvix-wilson-situs
git init -b main
git add .
git commit -m "Tennessee situs engine + atlas, 95 counties"
# with the GitHub CLI (brew install gh; gh auth login):
gh repo create navigation-holdings/tn-situs-atlas --private --source . --push
# or without gh: create an empty private repo in the browser, then
#   git remote add origin git@github.com:<you>/tn-situs-atlas.git && git push -u origin main
```

`.gitignore` keeps the 2 GB of raw layers, the warehouse snapshots and the per-county CSVs out of
git. `site/` (~160 MB) is committed — that is what Pages serves.

## 2. Turn on GitHub Pages + the custom domain

1. Repo → **Settings → Pages** → *Build and deployment* → Source: **GitHub Actions**.
   The `pages` workflow (`.github/workflows/pages.yml`) runs on every push that touches `site/`.
2. Same page → *Custom domain* → `navigationholdings.com` → Save. `site/CNAME` already carries the
   name, so it survives redeploys. Tick **Enforce HTTPS** once the certificate issues (minutes to an
   hour).
3. At your DNS provider for navigationholdings.com:

   | Type  | Host | Value |
   |-------|------|-------|
   | A     | @    | 185.199.108.153 |
   | A     | @    | 185.199.109.153 |
   | A     | @    | 185.199.110.153 |
   | A     | @    | 185.199.111.153 |
   | CNAME | www  | `<your-github-user>.github.io` |

   If you'd rather keep the root for a company page later, use a subdomain instead: set
   `site/CNAME` to `atlas.navigationholdings.com` (`python3 build_site.py --domain atlas.navigationholdings.com`)
   and add one CNAME record `atlas → <your-github-user>.github.io`.

4. Private repo + Pages: Pages on a private repo requires GitHub Pro/Team; on a free account make the
   repo public or move the site to Railway (below). The site is public data either way.

## 3. Weekly refresh on GitHub Actions

`.github/workflows/refresh.yml` runs Mondays 04:17 Central. It polls the change signals
(`fetch/watch.py`); when a boundary or address layer has moved it re-pulls, runs all 95 counties,
rebuilds `site/` and commits it, which redeploys Pages. Run it by hand from the **Actions** tab
("situs-refresh → Run workflow"), optionally for one county or with *force*.

Runner budget: a full 95-county pull + run is roughly 2–3 hours; the job timeout is set to 340 min.

## 4. Railway (alternative)

Railway hosts the same two pieces as two services from this one repo:

- **atlas** (static site): New Service → Deploy from GitHub repo → it picks up `railway.json`, which
  builds `deploy/Dockerfile.site` (Caddy serving `site/`). Settings → Networking → Custom Domain →
  `navigationholdings.com` (or `atlas.navigationholdings.com`) and add the CNAME Railway shows you.
- **refresh** (cron): New Service from the same repo → Settings → Build → Dockerfile path
  `deploy/Dockerfile.refresh` → Settings → Cron Schedule `17 9 * * 1`. Give it a volume mounted at
  `/app/warehouse` so snapshots persist between runs, and env `GIT_PUSH=1` plus a deploy key if you
  want it to commit `site/` back (otherwise the atlas service simply rebuilds from the volume).

Railway CLI equivalent: `railway login && railway init && railway up` inside the repo.

## 5. The SOS roster feed

`data/sos/<county>_county_all_records_from_SOS.tsv` (95 files) is the business layer. The TSVs are
not in git (340 MB); the compressed parts are (`data/sos_parts/*.zip`, ~52 MB), and `run_all.py`
unpacks them on first use, so a fresh clone or a runner has the roster with no extra step.

Monthly: download the new `Extract_Business_MONTHLY_<yyyymmdd>/RECORDS.txt` from the SOS
(Drive folder "TN SOS up to date files"), then

```bash
python3 fetch/sos_refresh.py --increments data/sos_monthly/sos_monthly_<yyyymmdd>_RECORDS.txt
python3 - <<'PY'
import zipfile, glob, os
# re-pack the parts so the runner sees the new roster
z = zipfile.ZipFile("data/sos_parts/sos_part1.zip", "w", zipfile.ZIP_DEFLATED)
for f in sorted(glob.glob("data/sos/*.tsv")) + ["data/sos/_manifest.json"]: z.write(f, os.path.basename(f))
z.close(); open("data/sos_parts/sos_part2.zip", "wb").close()
PY
git add data/sos_parts && git commit -m "sos: <yyyymmdd> increment" && git push
```

Deduplication is by ControlNumber, latest increment wins; the current roster is the 26 Aug 2026
statewide master with the Oct 2025 – Aug 2026 increments applied (1,421,894 entities, 1,183,429
with a Tennessee principal-address county).
