# Tennessee tip to tip — building the situs service for 95 counties and 345 cities

*What it takes to go from four proven counties to a statewide service any jurisdiction can sign up
for, delivered quarterly, with business-license and TPP support bundled on top.*

## Where this stands today

Four counties run through one config-driven pipeline in two days: Wilson (88k rooftops), Sumner
(107k), Rutherford (180k), Davidson (463k). Every one produced a placed rooftop surface, seams
measured in feet, a ranked exception queue, a per-county workbench, and a bulletin — from free data,
with one calibration against a real coded roster. The statewide layers are already in the warehouse:
473 DOR situs polygons (every code in Tennessee), 345 certified city boundaries, 95 county polygons.
Secretary of State entity files for ~75 counties are already in hand. **The method is proven; what
remains is scale, automation and operations.**

## What "tip to tip" consists of

Four assets, each built once, then maintained:

1. **The statewide surface** — every rooftop in Tennessee placed in its DOR polygon, measured to
   its nearest seam, cross-checked against the Comptroller and 911 layers, and scored. Roughly 3.3
   million address points across 95 counties. Refreshed quarterly.
2. **The business universe** — every active for-profit entity (SOS) plus every 911 business label,
   city roster and permit layer that exists, geocoded to a rooftop. Refreshed quarterly.
3. **The jurisdiction views** — 95 county workbenches and 345 city workbenches cut from the same
   surface (a city's view is the same data filtered to its situs code, with both directions shown).
4. **The operating loop** — roster intake, adjudication, correction packets, bulletins, calibration.

## The build, by phase

### Phase 1 — statewide surface (weeks 1–4)

| Task | How | Effort |
|---|---|---|
| Pull NG911 address points + roads for 91 remaining counties | `fetch_county.py --live` on a machine with internet (GitHub Actions or a $20/mo VM); ~3M points, ~1.5 GB | 1 engineer-week, mostly wall-clock |
| Generate 91 county configs | Script: situs codes and names come straight from the DOR layer; USPS-only places derived automatically (below); city layers discovered by ArcGIS Online search per county | 1 engineer-week |
| **Automate the postal-county map** | For every `Post_City + ZIP` pair across all 3M rooftops, the majority county is the postal home county. Replaces every hand-typed list; also produces the multi-county-city exceptions (Goodlettsville, Portland, White House) automatically | 2 days |
| Consolidated-government rules | Only Davidson (Metro) and Moore (Lynchburg-Moore) need `situs_merge`; Hartsville-Trousdale is the third | 1 day |
| Run all 95; publish 95 free boundary reports | Batch; ~6 hours compute | automatic |

Deliverable: the free tier live for every county — the lead-generation engine.

### Phase 2 — business universe and municipal views (weeks 4–8)

| Task | How |
|---|---|
| SOS entity files for all 95 counties as the primary business layer | Already have ~75; obtain the rest through Civvix's existing SOS channel |
| Discover per-county 911 business labels, city rosters, permit layers | ArcGIS Online search script, reviewed by hand; Hendersonville-style situs rosters are gold when found |
| 345 city workbenches | Same pipeline, `--jurisdiction city:8305`; shows the city's coded-vs-measured both ways |
| Parcel join where free (86 Comptroller counties + Davidson, Montgomery, Rutherford) | Adds parcel ID to the evidence packet and +5 to the score |

### Phase 3 — operations (weeks 6–12)

| Task | How |
|---|---|
| Scheduled refresh | GitHub Actions cron (weekly signal poll; quarterly bulk); snapshots to S3; catalog in git |
| Roster intake | The workbench's browser-side join for small jurisdictions; a county-side script for big ones. Never on Civvix infrastructure |
| Adjudication capacity | Calibration says ~0.3% of placed licensed businesses are miscoded. Statewide (~350k active entities) that's ~1,000–1,500 findings a year at full penetration. One analyst handles that; two at scale |
| Correction packets + letters | Generated from the workbench; county signs and sends |
| Calibration reports | After each jurisdiction's first roster; published to the client |
| Financial Control relationship | One person owns it; the same three questions (contractor designation, lookback authority, PO Box rule) answered once for everyone |

### Phase 4 — the annual license and TPP check (parallel, from week 8)

The situs surface is also the denominator Civvix has been missing. Every business is now a rooftop
with a jurisdiction. That answers, per business:

- **Business license** — which county *and* which city should have issued one (T.C.A. § 67-4-708),
  and whether the clerk's roster shows it. The SOS entity file against the clerk's roster, placed on
  the map, is the discovery product Civvix already sells — now with jurisdiction certainty.
- **TPP** — which assessor's roll the personalty belongs on (§ 67-5-502 situs; home-base rule), and
  whether a schedule was filed. Same placed universe against the assessor's TPP roll.

One annual run per jurisdiction: placed universe × license roster × TPP roll → three exception
lists from one geography. The situs subscription is the quarterly relationship; the annual check is
the recovery event. They share every byte of infrastructure.

## What it costs

| | Year 1 | Ongoing |
|---|---|---|
| Engineering (Marty + one) | the phases above, ~3 engineer-months | 0.5 FTE maintenance |
| Analysts | 1 from month 3 | 2 at 40+ jurisdictions |
| Infrastructure | S3 + a small VM/Actions: **under $500/mo** at full scale | same |
| Data | **$0** for the surface; ~$2–3K one-time reserve for the three or four parcel gaps | $0 recurring |
| Insurance | ~$3–5K/yr (see insurance memo) | same |
| Legal | Tennessee counsel on the § 67-1-1704(e) reuse question and the engagement letter — once | — |

## Sequencing that compounds

Start from the Wilson seam outward. Every county line has two sides, and a finding on one side is a
finding on the other: the Lebanon Road / Old Hickory corridor is simultaneously a Wilson and a
Davidson matter; Brentwood's ZIP spilling into south Davidson (7,481 rooftops) is a Davidson and a
Williamson matter. Middle Tennessee's ring — Davidson, Williamson, Rutherford, Wilson, Sumner,
Robertson, Cheatham, Maury — is 8 counties, ~1.3M rooftops, and the densest seams in the state. Sign
those and the map sells itself to the next ring.

Then the other three metros (Knox, Hamilton, Shelby) — each is one county plus a city with its own
open data — then the rest by seam density.

## What "sign up" looks like

1. A finance director opens their county's free boundary report. It shows the seams, the exposure
   ranking, the State-data conflicts, and the count of named businesses in each class.
2. They click "Start monitoring." Fixed annual fee under the bid threshold (pricing memo). An
   engagement letter with the data-handling protocol and the client-furnishes-GIS clause.
3. They request their situs report through REP (we provide the request; they send it).
4. First roster join, adjudicated queue, correction packets — within two weeks of the roster.
5. Quarterly thereafter: refresh, re-measure, new/resolved/moved, packets, bulletin.
6. Annually: the license and TPP check against the same placed universe.

## What could stop it

- **§ 67-1-1704(e) reuse across jurisdictions** — get counsel's answer before the second county
  signs. The public surface is unaffected; the question is only about roster-derived facts.
- **Financial Control's three unanswered questions** — one phone call.
- **Business universe quality** — the SOS file has holding companies and stale addresses; the
  calibration loop is what keeps this honest, and it should be published to every client.
- **Adjudication discipline** — the felony exposure is personal. Two or three named people, a
  written protocol, no shortcuts.
