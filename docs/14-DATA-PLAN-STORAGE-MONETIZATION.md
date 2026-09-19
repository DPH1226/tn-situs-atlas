# The business universe beyond the Secretary of State — acquisition plan, where the data lives, and what else it is worth

*13 September 2026. Companion to document 13 (combined program pricing) and the statewide status doc.*

## 1. Is the pricing one-time or ongoing?

Ongoing. The program fee in document 13 is an **annual subscription** (per resident, fixed for the term), because the thing being sold is monitoring: boundaries move, annexations happen, 1,700 net new Wilson entities register every year, and the Department's one-year correction window means an error found late is money gone. Work product (situs packets, verified leads) is billed per unit as it is produced, so year one is the heaviest and the fee then settles. Wilson: ~$284K in year one, ~$210K a year after — against a first cycle the Friday deck already sizes at $2.1–3.9M on TPP alone.

## 2. The free sources, and a plan to pull and normalize them for all 95 counties

Every source below is public, free, and either already in the pipeline or reachable with the same fetcher. They are ranked by what they add to the placed universe: the SOS register is the spine; the rest catch what never registers with the SOS (sole proprietors, out-of-state sellers, franchise units under a parent control number) and add the attributes the forms need.

| # | Source | What it adds | Coverage | Access | Cadence | Normalize to |
|---|---|---|---|---|---|---|
| 1 | **TN Secretary of State** business extract (base + monthly increments) | The entity spine: control number, status, principal address, county | 95 counties (done) | Monthly file from SOS | Monthly | `entity` |
| 2 | **County Clerk business-license registers** (secure.tncountyclerk.com; the consolidated portal serves most counties) | Licensed vs. unlicensed; license class (minimal / standard); the TPP denominator | ~90 counties on the portal; the rest by TPRA request | Per-county portal export or records request in a TN resident's name (OORC 15-01) | Monthly | `license` |
| 3 | **Municipal business-license rosters** (where a city publishes one — Hendersonville does, with situs codes) | City-side license status; a calibration file for situs where the roster carries the code | Sparse; grows with each city contract | Open-data portal / ArcGIS Online | Monthly | `license` (scope = city) |
| 4 | **E-911 district business/point-of-interest layers** on ArcGIS Online (Wilson, Sumner already in) | Named business points from the addressing authority itself | ~30 of 95 districts publish | ArcGIS REST | Monthly | `poi` |
| 5 | **TN Alcoholic Beverage Commission** licensee list; county/city **beer permits** (Nashville publishes; most boards will furnish a list) | Every bar, restaurant, package store, grocery with alcohol — high-value sales-tax situs population | Statewide (ABC); per board (beer) | ABC public search / open data / TPRA | Quarterly | `permit` |
| 6 | **TN Department of Health** food-service, hotel/motel, pool and tattoo establishment permits | Restaurants and lodging — the other high-volume sales-tax population; lodging also drives hotel/motel tax | Statewide | Public inspection database | Quarterly | `permit` |
| 7 | **TN Commerce & Insurance** licensees (contractors, home improvement, cosmetology, funeral, auto dealers, etc.) | Trades and services that hold equipment (TPP) and rarely file a schedule | Statewide | Public license verification / bulk request | Quarterly | `permit` |
| 8 | **TDEC** permits (air, water, UST/fuel tanks) | Fuel stations, manufacturers, car washes — heavy TPP and heavy sales tax | Statewide | Public data viewer / TPRA | Quarterly | `permit` |
| 9 | **Comptroller parcel data** (CAMA/parcels by property class, the Tier A source in the GIS decision memo) | Commercial/industrial parcels; owner and parcel fields for the forms; commercial parcel with no business on the map = a lead in itself | 86 counties free from the Comptroller; the 9 excluded counties from their own GIS | Comptroller download / county GIS | Annual (reappraisal cycle) | `parcel` |
| 10 | **Census County Business Patterns** and **BEACON / NAICS** | Establishment counts by NAICS per county — the denominator for "how many should there be"; NAICS assignment for the IRS TPP estimator | Statewide | Census API | Annual | `benchmark` |
| 11 | **OpenStreetMap** points of interest (ODbL) | Storefronts with names and coordinates, including chains and sole proprietors | Statewide, uneven | Overpass / planet extract | Quarterly | `poi` |
| 12 | **USPS / NCOA-style address validation** (free tier) | Deliverability and unit-level normalization for the mail-ready form | Statewide | Web tools | On demand | attribute |
| 13 | **TN Department of Revenue** public lists — SST address ranges (done), tax-rate boundaries (done), the Business Tax comprehensive list of municipalities that levy | Which cities levy business tax; the situs surface | Statewide | tnmap.tn.gov / tn.gov/revenue | Quarterly | `boundary` |
| 14 | **Hotel/motel and short-term-rental registrations** (city and county portals, Airbnb/VRBO listing scrapes are *not* free of terms — use registrations only) | Lodging tax population; STRs are the fastest-growing unregistered class | Per jurisdiction | Portals / TPRA | Quarterly | `permit` |

**The normalized model (one table per kind, one `place` table joining them):**

- `entity` — control number, name, type, status, effective/inactive dates, principal and mailing address, county (SOS).
- `license` — issuer (county/city), license number, class, holder name, address, issue/expiry (clerk and city rosters).
- `permit` — issuer, permit type, holder, address, dates (ABC, Health, C&I, TDEC, beer, lodging).
- `poi` — source, name, coordinates, category (E-911, OSM).
- `parcel` — parcel id, owner, class, address, geometry (Comptroller / county).
- `place` — one row per rooftop-placed business: the NG911 address point it sits on, the situs polygon, the seam distance, and foreign keys to every record above that resolved to it. This is the table the queue, the TPP screen and the license screen all read from; a business is "in the universe" when at least one source places it on a rooftop.

**Resolution rules (the part that makes it defensible):** every source is placed by the same geocoder (exact house number + street + ZIP against NG911, with the directional/suffix variants and the ZIP-less fallback already in the engine), never by third-party geocoding. Names are normalized (punctuation, suffixes, "DBA"), but a name match alone never merges two records — a match needs the same rooftop or the same control/license number. Every record keeps its source, snapshot date and hash, so a county can ask "why is this business here?" and get the source document.

**Execution plan (all 95):**

1. *Weeks 1–2:* clerk registers for the counties on the consolidated portal, pulled the way the SOS file was (browser-side script, one county at a time), normalized to `license`. This alone converts the TPP screen from "no schedule on file" to "licensed, no schedule" — the forced-assessment population.
2. *Weeks 2–3:* ABC licensees, Health permits, C&I licensees, TDEC permits — four statewide pulls, four normalizers, all quarterly.
3. *Week 3:* Comptroller parcels for the 86 free counties, commercial classes only; the nine excluded counties by county GIS (Davidson, Knox, Shelby, Hamilton, Rutherford, Williamson, Montgomery already located).
4. *Week 4:* Census CBP + NAICS assignment; OSM POIs; the `place` join; the per-county coverage report ("we can see X of the Y establishments the Census says exist").
5. *Ongoing:* every source on its cadence through the same fetcher and warehouse, with the weekly refresh already running on GitHub Actions.

TPRA requests go out in a Tennessee resident's name (OORC 15-01), never Civvix Inc.'s; no custodian may require a license agreement (OORC 09-02).

## 3. Where the data lives

Two tiers, deliberately separate:

**Public tier (Civvix-owned, hostable anywhere).** Everything above is public data. Today it lives in the warehouse (`warehouse/raw/<layer>/<scope>/<date>/`, dated and hashed, never overwritten, with GeoParquet and a DuckDB catalog) in the repo and on the GitHub Actions runners, and the outputs are served as a static site. As volume grows past what a git repo should carry (the raw layers are already 2 GB), the raw tier moves to object storage — Cloudflare R2 or Backblaze B2 at roughly $6/TB/month, S3 if a county's procurement wants a name it knows — with the same path layout, and DuckDB reads it in place. Compute stays where it is (a runner or a Railway cron job); there is no server to keep up. Per-county JSON feeds into Supabase for the Civvix platform, the pattern already used for the ROI model.

**Confidential tier (county-owned, never Civvix-held).** The DOR situs roster, the Assessor's TPP roll and the Clerk's license list with taxpayer identity are joined inside the county's browser session or inside county systems, exactly as the workbench does now. Civvix stores the *result* of a comparison only as a finding the county has adjudicated. This is what keeps the § 67-1-1709 exposure and the insurance requirements small, and it is a selling point, not a limitation.

## 4. What else the public tier is worth

The placed universe — every Tennessee business on a rooftop with its jurisdiction, its registrations, its permits and its parcel — is an asset with buyers beyond the three services in the county program:

- **Municipal packages** (already in the pricing): the 215 cities that levy business tax, each at 75% of the county formula.
- **Special districts and utilities:** fire, school and utility districts collect on the same boundaries; sewer and water utilities lose commercial accounts to mis-classification the same way counties lose situs.
- **State agencies:** the Department of Revenue itself is the natural buyer of the DOR-vs-DOR (E5) list — 58,550 addresses where its own files disagree; the Comptroller's Division of Property Assessments for TPP compliance rates by county.
- **Economic development:** county and regional EDOs pay for establishment counts, new-business formation by month, vacancies (commercial parcel, no business) and industry mix — the CBP benchmark layer turns into a local dashboard.
- **Commercial data buyers:** site-selection consultants, commercial brokers, insurers and lenders buy verified business-location data; a Tennessee-complete, rooftop-accurate, permit-linked file is better than anything the national aggregators sell for the state. Licensing terms have to respect the ODbL share-alike on any OSM-derived attributes (keep OSM in its own column or leave it out of the commercial product).
- **Address-quality services:** the 911 districts and the USPS both have an interest in the cross-county postal population; a county 911 board will pay to know which of its address points carry the wrong postal city.
- **Other states:** the engine is Tennessee-tuned only in its configs. Every state with local-option sales tax and a situs problem (Alabama, Georgia, Louisiana, Arizona, Colorado, Texas) has the same structure, and the SST address-range files exist for all 24 Streamlined states.

## 5. What would make it a better tool

For local governments:

- **Calibration on the first roster** — precision/recall of every exception class, published to the county; nothing sells the second county like a measured error rate from the first.
- **A four-role workflow** — Finance (situs), Assessor (TPP), Clerk (license), and Civvix analyst — with per-role queues on the same placed universe, so one screening feeds three offices without three exports.
- **Letter generation in the workbench** — the DOR correction letter (doc 10), the TPP forced-assessment notice and the license notice generated from the adjudicated finding, with the evidence packet attached, ready to sign.
- **Annexation and boundary alerts** pushed to the county (the weekly watch already runs), with the affected businesses listed.
- **Coverage reporting** — "we can see 8,537 of the ~9,900 establishments the Census says Wilson has, here is where the rest probably are."
- **An appeal-defense packet** — for every forced assessment, the evidence trail in the order an appeals board wants it.
- **Bulk adjudication with shared state** across county users (the `db` capability on the published pages already does this; the static site falls back to per-browser storage).
- **Accessibility and records-retention compliance** on the county-facing pages, since a county tool is a public record.

For non-government users:

- **Business owners:** a free "is my situs code right?" check by address — it generates goodwill and it surfaces the errors in the county's favour that no vendor will bring forward.
- **Accountants and payroll providers:** multi-client situs and license verification, priced per client.
- **Brokers, lenders, insurers:** the verified-location file with permits and parcels, priced per state or per query.
- **Utilities and 911 boards:** address-quality reports on the postal-city mismatch population.
- **Researchers and journalists:** the public atlas as-is; it is already the best public picture of Tennessee's local-option tax geography.
