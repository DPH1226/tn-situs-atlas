# Statewide build — status as of 13 Sep 2026 (updated: SOS roster + deploy)

Companion to `wilson-situs-prototype-state.md` and `situs-platform-plan.md`. This is the "county as
config" plan executed end to end: all 95 Tennessee counties have been run through one pipeline on
public data only, with no confidential DOR roster and $0 spent on data.

## Published pages

- **Tennessee Situs Atlas** (statewide index, links to every published workbench):
  https://claude.ai/code/artifact/9ff0b320-ff3f-40d2-8161-9d31608705ea
- County workbenches (operator console: map, evidence packets, shared adjudication, DOR-file paste):
  - Wilson https://claude.ai/code/artifact/24f8283d-87ab-4811-a54b-c55d799e15d4
  - Sumner https://claude.ai/code/artifact/b69a5dc6-072c-49be-b5e5-4aecfbdf16e6
  - Rutherford https://claude.ai/code/artifact/4dadc775-c33a-459f-b56a-2136da0c214c
  - Davidson https://claude.ai/code/artifact/e6691a63-1d35-4fab-80d8-f0f342e20cee
  - Shelby https://claude.ai/code/artifact/d9d149a2-f81b-4de7-b497-81f5b543789a
  - Knox https://claude.ai/code/artifact/572e8b0f-f606-4443-bf62-3f72ca17ac43
  - Hamilton https://claude.ai/code/artifact/560ebc94-81e0-4f63-a9d0-0f5fcba9a37b
  - Williamson https://claude.ai/code/artifact/4249e6c7-94bd-411d-a926-f9b44d0a626e
  - Montgomery https://claude.ai/code/artifact/ba8e60f0-ea6a-4996-b5e2-81a2a77c16b7
  - The other 86 are built (`artifact/<slug>/`) and can be published on demand; nothing about them
    is different, they are just not yet given a URL.
- Wilson County Situs Control (report page): https://claude.ai/code/artifact/ce5e7367-3f04-45e1-b66f-69783f3b1622

## Statewide totals (public data, rubric v2)

| Measure | Value |
|---|---|
| Counties run | 95 / 95 (0 failures) |
| Rooftops placed in DOR situs polygons | 3,943,392 |
| Business points (SOS entities + E-911 labels, rooftop-geocoded) | 359,077 across all 95 counties |
| Jurisdictional seam miles | 18,246 (9,298 cross-county) |
| Cross-county postal businesses (both halves of the tax at risk) | 5,786 |
| Boundary-risk businesses (≤250 ft of a seam) | 11,222 |
| Postal-city exposure businesses | 61,170 |
| DOR file ≠ DOR polygon (E5, >250 ft) | 58,550 rooftops |
| Official-layer disagreement (E4) | 19,111 rooftops |

Top counties by business universe: Davidson 58,950 · Rutherford 39,862 · Shelby 39,443 · Knox 39,209 ·
Williamson 27,253 · Hamilton 21,152 · Sumner 14,899 · Wilson 13,306.

Highest cross-county-postal counts: Davidson 1,310, Wilson 521, Shelby 257, Rutherford 208, Hamilton 97.

## What was built this pass

- Chrome-driven pull of every county's NG911 address points and DOR SST address ranges (91 counties,
  3.11M points, 1.97 GB, 0 errors) into `data/raw/` on Dan's Mac, staged into the warehouse with
  SHA-256 provenance and dated, never-overwritten snapshots.
- `configs/<county>.yaml` for all 95 (generated from the DOR polygon layer; Wilson, Sumner, Rutherford,
  Davidson hand-enriched; Moore and Trousdale metro merges; Davidson 1900→1901 dissolve).
- `configs/postal_home_county.json` now derived from **all 95 counties** (654 postal cities, 2,910
  city/ZIP pairs, 93 multi-county postal cities). Cross-county postal (E2) is computed from this
  statewide map, not a hand-typed list — this replaced the provisional 4-county map and every county
  was re-run against it.
- Workbench queue banner: with no roster loaded the queue is labelled **ranked exposure, not findings**;
  once a DOR file is pasted it flips to findings mode with the Coded ≠ measured class.
- SST fallback for 911 authorities that leave ZIP blank (DeKalb: 0.5% → 82.8% address-range match).
- Atlas marks any county without a Secretary of State entity file as "no roster yet" (none today).

## SOS roster (added 13 Sep, second pass)

The business layer for all 95 counties now comes from the Secretary of State statewide RECORDS
extract (26 Aug 2026 master) with the Oct 2025 – Aug 2026 monthly increments applied, deduplicated
by ControlNumber (latest wins): 1,421,894 entities, 1,183,429 with a Tennessee principal-address
county, 388,375 active for-profit, 324,393 (83.5%) geocoded to an NG911 rooftop. County assignment
is the filer's own PrincipalAddressCounty, which is why cross-county postal rose from 1,089 to 5,786:
an entity that tells the State it sits in Wilson County while its address says Old Hickory is exactly
the population the audit is for (Wilson 136 → 521, Davidson 28 → 1,310). `fetch/sos_refresh.py`
applies each new monthly increment; `deploy/DEPLOY.md` §5 has the routine.

## Deployment (prepared, awaiting Dan's push)

- Repo `~/Downloads/tn-situs-atlas` on Dan's Mac (two commits on `main`, clean). `site/` holds the
  atlas + all 95 workbenches as a plain static site (172 MB); `site/CNAME` = navigationholdings.com.
- `.github/workflows/pages.yml` deploys `site/` to GitHub Pages on push; `refresh.yml` re-pulls and
  re-runs all 95 counties weekly and commits `site/`. `deploy/Dockerfile.site` + `railway.json`
  (Caddy) and `deploy/Dockerfile.refresh` + `refresh.sh` for Railway.
- Remaining steps are credentialed and Dan's: `gh repo create … --push`, Settings → Pages → source
  GitHub Actions, custom domain, four A records + www CNAME at the registrar. All in `deploy/DEPLOY.md`.

## Known gaps

- Low DOR address-range match rates worth a look before selling those counties: Obion 26%,
  Unicoi 27%, Cocke 36%, McMinn 41%, Marion 51%. Probably street-name conventions in the 911 layer.
- DeKalb's 911 layer has no ZIPs; a ZIP-less fallback (unique street+number) now carries it
  (SST match 0.5% → 82.8%, SOS geocode 5 → 690 of 810).
- Knox and Williamson show 0 cross-county postal — plausible but verify on the first roster.
- Wilson E5 (DOR file ≠ polygon) is 12,691 — the "counter-finding in the county's favour"; belongs in
  the engagement letter.
- Published claude.ai copies of the Hamilton, Williamson and Montgomery workbenches still show the
  pre-SOS-refresh numbers (republish was blocked); the site copies are current.

## Where everything lives

- Code, configs, docs, deliverables (Word/PDF), per-county summaries, bulletins, exception CSVs,
  seams, and the nine published workbenches are synced to `~/Downloads/civvix-wilson-situs/` on
  Dan's Mac (zips in `_sync/`, already extracted in place). Raw layers are in `data/raw/` there.
- The cloud workspace holds the full warehouse (`warehouse/raw/...`) and all 95 `out/<slug>/` and
  `artifact/<slug>/` directories for this session.
- Weekly boundary-change watch: scheduled task "Situs boundary-change watch (weekly)", Mondays
  13:00 UTC, writes `claude/situs-watch-state.md`.

## Next

1. Wilson meeting (week of 14 Sep): demo the Wilson workbench and the atlas; walk the queue banner.
2. Push the repo and turn on Pages + DNS (`deploy/DEPLOY.md`); then the site is the demo link.
3. First roster paste (Wilson) → `calibrate.py` → confusion matrix in the bulletin.
4. Municipal packages: every city already has a situs code and a polygon in the atlas; the
   county-and-cities package (doc 09) needs only the city list per county from `configs/`.
