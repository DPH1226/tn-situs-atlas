# Tennessee Situs Engine + Atlas

A boundary-first sales tax situs audit for every Tennessee county, built entirely from free public
data, with **no confidential Department of Revenue file used or required**. One pipeline, 95 county
config files, one static site:

- **Tennessee Situs Atlas** — `site/index.html`: every county's rooftops placed inside the Department
  of Revenue's own situs polygons, measured to the nearest jurisdictional seam, cross-checked against
  the Comptroller's certified city limits and the 911 addressing authority.
- **County workbenches** — `site/<county>/`: the operator's console for each county: pan/zoom map,
  every rooftop-placed business, a per-business evidence packet, adjudication, and a DOR-file slot
  that matches the situs report against measured rooftops without the file ever leaving the browser.

Deploying it (GitHub Pages at navigationholdings.com, weekly refresh on GitHub Actions, Railway as
an alternative): **`deploy/DEPLOY.md`**. Current statewide status: `docs/STATEWIDE-STATUS.md`.

```
python3 fetch/fetch_county.py --statewide --live        # DOR polygons, SST counties/cities
python3 fetch/fetch_county.py --county wilson --live     # NG911 points, SST address ranges, city layers
python3 fetch/sos_refresh.py --increments data/sos_monthly/*.txt   # SOS business roster, monthly
python3 fetch/postal_map.py                              # postal city -> home county, from all 95
python3 run_all.py --skip-ingest --workers 4             # score every county, bulletins, workbenches
python3 build_index.py && python3 build_site.py          # atlas + site/
```

---

## Origin: the Wilson County prototype

A boundary-first sales tax situs audit, built entirely from free public data, with **no confidential
Department of Revenue file used or required**. Two published artifacts:

- **Wilson County Situs Control** — the report: boundary QA, findings, exception queue, sources.
- **Situs Workbench** — the operator's console: pan/zoom map with NG911 roads, all 4,769 rooftop-placed
  businesses, a per-business evidence packet, shared adjudication (status + notes persist across
  viewers), and a DOR-file slot that matches the situs report against measured rooftops without the
  file ever leaving the browser tab.

**Data acquisition cost: $0.00.** The six-layer, $450 Wilson County GIS purchase was not made and is
not needed — see `docs/01-GIS-SPEND-DECISION.md`.

## What it does

Places every address in Wilson County inside the Department of Revenue's own tax-rate polygon,
measures it in feet against every jurisdictional seam, cross-checks it against three independent
official layers, and produces a scored exception queue — before any taxpayer data is requested.

Geography first, taxpayers second. That ordering is deliberate: before telling a Finance Director
that the Department has miscoded a business, the geography underneath the claim should be provable.

## Results, this run

| | |
|---|---|
| Rooftops placed | **88,196** — every one inside a DOR polygon, zero unplaced |
| Jurisdictional seams | 13, **360.3 linear miles**, of which **141.4 miles are county seams** |
| DOR address-range match | **87.0%** of rooftops matched a published DOR address range |
| Businesses located | **4,769** rooftop-placed public business points |
| Business exceptions queued | **1,215** — 92 cross-county postal, 152 boundary risk, 971 postal-city exposure |

### Findings from public data alone

| Class | Count | What it costs Wilson County |
|---|---|---|
| **E2** Wilson rooftop, another county's mailing city | 5,149 addresses / **92 businesses** | **Both halves** — situs and education |
| **E5** DOR address file contradicts DOR's own polygon, >250 ft from any seam | 12,691 | Depends on direction |
| **E5B** Same conflict, within 250 ft — precision may explain it | 2,184 | Adjudicate, do not assert |
| **E4** 911 authority + Comptroller both say city, DOR says unincorporated | 1,883 | Runs **against** the county — see below |
| **E6** Inside a Mt. Juliet annexation the DOR polygon does not reflect | 1,004 | Situs half, time-limited |
| **E3** Within 250 ft of a seam | 7,480 | Risk control, not a loss |
| **E1** City mailing address, rooftop outside that city | 30,521 | **Exposure population, not a finding** |

### Three things worth saying out loud

1. **The money is cross-county, and the public data proves it independently.** 5,149 Wilson rooftops
   carry another county's postal city, concentrated in one corridor — Lebanon Road, ZIP 37138, where
   the Old Hickory delivery area crosses the Davidson County line. Named businesses there include
   Adam's Auto Shop, Tim Leeper Roofing, State Farm, Pet Center and Meraki Salon, all 52–130 feet
   from the county line. This confirms the strategy memo's central claim from a completely
   independent direction.

2. **The city/unincorporated axis appears to run in the county's favour, not against it.** DOR's
   address file says "unincorporated" where its polygon says "city" 11,446 times, against 3,409 the
   other way; and on 1,883 addresses both the 911 authority and the Comptroller place the rooftop
   inside a city while DOR calls it unincorporated. **Corrected, those move money away from Wilson
   County and toward Lebanon and Mt. Juliet.** A competent audit is bidirectional. The engagement
   letter has to say plainly what gets reported and who decides what is submitted — getting this
   wrong is how a vendor ends up in a Comptroller finding.

3. **E1 is not a finding and must never be presented as one.** 30,521 addresses is the *exposure
   population* — where a mailing-address-driven registration would land wrong. Which of them actually
   did cannot be known until the situs report arrives.

## Layout

```
run_wilson.py            boundary QA + exception pass          -> out/
build_demo_data.py       join the business universe            -> out/
build_map_payload.py     compact payload for the report        -> artifact/data.js
build_workbench_payload.py full evidence payload for the console -> artifact/wbdata.js
engine/situs_core.py     provenance, reprojection, seam extraction
engine/boundary_qa.py    situs assignment, seam distance, layer agreement
engine/exceptions.py     DOR address-range matching, classes, scoring
ingest/acquire_county.js portable acquisition — any TN county, browser console
artifact/                the published client demo
docs/                    GIS spend decision, insurance memo, request pack
data/raw/                source layers, unmodified
out/                     results + SHA-256 source manifest
```

## Running it

```bash
pip install geopandas shapely pyproj
python3 run_wilson.py          # ~80s, 88k points
python3 build_demo_data.py
python3 build_map_payload.py
python3 build_workbench_payload.py
```

Refreshing the data, or standing up a new county: open any `https://tnmap.tn.gov` page, paste
`ingest/acquire_county.js` into the DevTools console, and run `await civvixAcquire("WILSON")`.
It is a browser script because the egress proxy blocks `tn.gov` and `arcgis.com` from both shells;
a browser is the only route. Allow multiple downloads for the site when Chrome asks.

## Method notes that matter

- **All distance math runs in EPSG:2274**, NAD83 Tennessee State Plane, US survey feet. Never measure
  feet in degrees.
- **A seam is where two different situs codes meet**, not where a polygon ends, and every seam carries
  both sides — so a finding reads "41 ft outside Mt. Juliet, inside unincorporated Wilson" rather
  than the useless "near a boundary."
- **Geometry is validated, not silently repaired.** Every fix is counted and described in
  `out/source_manifest.json`, alongside a SHA-256 of each source file and its download timestamp.
- **Address-range matching respects odd/even parity.** Chandler Road in 37122 is split by house
  number across situs 9500 and 9503; ignoring parity produces false matches on exactly the streets
  that run along a city line.
- **Postal city is excluded from layer-agreement scoring** and given its own class. It is a USPS
  delivery convenience and is not a statement about jurisdiction — but it is what registrations are
  keyed off, which is why it predicts where errors are.

## Known limits — state these to the client

- The business universe is the Wilson County 911 district's public **label** layer: a business name
  and a rooftop coordinate, with no address, NAICS code or licence linkage. Names are matched to the
  nearest public address point within 500 ft (median match distance 32.5 ft). 351 of 4,769 had no
  address point within 500 ft. Some entries are subdivision or utility labels rather than businesses.
- No statewide file of Tennessee business tax licensees exists. Licences are issued county by county
  by county clerks; building a licensed-business denominator requires a records request to the
  Wilson County Clerk.
- Map geometry in the demo is simplified for display. All measurement ran on full-precision geometry.
- Situs codes shown are the Department's published tax-rate polygons. **They are not taxpayer coding.**
  Nothing here establishes how any business is actually coded — that requires the situs report.
