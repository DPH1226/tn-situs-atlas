# The $450 question, and the 95-county version of it

**Recommendation: do not buy the six Wilson County GIS layers. Not now, and probably not ever.**
The prototype in this repository was built without them, from free public sources, and it produced a
placed rooftop for all 88,196 addresses in Wilson County and a 1,215-row business exception queue.
Total data acquisition cost: **$0.00**.

---

## 1. What was proposed, and what it would actually have bought

The six-layer plan was Parcels, Address Points, Road Centerlines, and the three city-limit files, at
$75 each. Set against what is published free:

| Proposed purchase | Free equivalent actually used | Verdict |
|---|---|---|
| Address Points | **TN NG911 Address Points** (TN Emergency Communications Board), 88,240 Wilson records, monthly refresh — *and* Wilson County's own E-911 district publishes 88,295 address points publicly on ArcGIS Online with Extract enabled, last edited 8 Sep 2026 | Free version is **better**: it carries `Inc_Muni`, `Post_City` and `Census_Plc` on the same record, which is the exact three-way distinction the audit turns on |
| Road Centerlines | TN NG911 Road Centerlines, monthly; Wilson E-911 street centerlines, public | Equivalent |
| Lebanon / Mt. Juliet / Watertown city limits | **TN Comptroller, Office of Local Government** — all 345 Tennessee municipalities, aggregated monthly from local assessors, free | Free version is **better**: statewide, monthly, and carries per-feature currency dates |
| Parcels | TN Comptroller statewide parcel shapefiles, weekly, free for 86 of 95 counties (Wilson included), with an `Assessment_Data` table joinable on `GISLINK` | Equivalent, plus assessment attributes the county layer may not include |

**Wilson County is selling three layers its own 911 district already gives away, and three the State
of Tennessee publishes for every county in the state.** That is not a criticism of the county — it is
a normal artifact of GIS cost-recovery policy written before open data portals existed.

### One important correction to the earlier plan

The earlier draft pointed at the TNMap `ADMINISTRATIVE_BOUNDARIES` city layer as the comparison
boundary. **Do not use it.** Its own metadata dates the product to **June 2017**, which would miss
every annexation in the last nine years — and Mt. Juliet has annexed aggressively over exactly that
period. Use the Comptroller's SST `Cities` layer instead, which is aggregated monthly and carries
`TDOT_DATE` / `OIR_DATE` per feature. This prototype uses the latter.

### The layer nobody thought to ask for

**Mt. Juliet publishes 221 dated annexation polygons, free.** Nothing at state or federal level
captures annexation history, and annexation is the single most common cause of a stale situs
assignment. This layer found 1,004 Wilson rooftops inside a Mt. Juliet annexation that the
Department's tax polygon does not code to Mt. Juliet. It was not on the $450 list, and it is worth
more than anything that was.

---

## 2. If you ever do pay, know these two things first

**(a) A $75-per-layer price is legally defensible — attacking the fee is a losing argument.**
T.C.A. § 10-7-506(c) expressly lets a political subdivision charge development-cost recovery for
"a computer generated map or other similar geographic data developed with public funds" when the
request "has commercial value," which a request from a business is by definition. GIS is the one
record type where Tennessee permits this. The Office of Open Records Counsel's Schedule of
Reasonable Charges does not cap it. Do not send a records request expecting to get the data for the
cost of a CD.

**(b) But the county cannot make you sign a licence.**
OORC Advisory Opinion 09-02 (the Memphis Daily News / KGIS opinion) holds that a GIS custodian
"cannot require a requestor to complete and sign a licensing agreement as a condition to acquiring
particular GIS data," because Tennessee law does not authorize it. **This converts a recurring annual
licence into a one-time purchase**, and it is the single most valuable fact in the fee analysis. It
is an advisory opinion from 2009, not binding precedent, so treat it as persuasive rather than
settled — but it is the right thing to cite.

**(c) A procedural trap worth knowing before the first request goes out.**
OORC Advisory Opinion 15-01: *"the term 'citizen' does not include corporations."* **Civvix Inc. has
no standing under the Tennessee Public Records Act, and being incorporated in Tennessee does not
cure it.** Every TPRA request must go out in the name of a named Tennessee-resident individual who
can produce a Tennessee photo ID — not on Civvix letterhead. Getting this wrong hands any county a
clean, correct basis to refuse. It is a paperwork detail with a 100% failure rate if missed.

---

## 3. The better lever: make it a contract term, not a purchase

When the county is the client, there is no requester and no request — a county GIS department
handing data to the county finance department for county work is internal data sharing, and
§ 10-7-506(c) has no purchase on it. The fee provision is permissive (*"may* establish and impose"),
and the cost-recovery rationale collapses anyway: charging the county $450 to generate revenue for
the same county moves money between its own funds.

**Put this in every engagement letter:**

> *The County shall furnish to the Consultant, at no cost, the geographic information system layers
> reasonably necessary to perform the Services, including parcel geometry, address points, road
> centerlines and certified municipal boundaries, in a machine-readable format, together with the
> coordinate reference system, effective date and any adopted boundary changes not yet reflected in
> the delivered geometry.*

This is the cheapest lever in the entire analysis. It sidesteps the fee and the TPRA standing
problem at once. It fails only where the county's GIS is a separate legal entity with its own budget
— which is exactly Knox County (KGIS is a joint Knoxville / Knox County / KUB body) and plausibly
Shelby (ReGIS).

---

## 4. The 95-county answer

**Per-county GIS purchase is an avoidable cost, not a necessary recurring one.** Three findings
carry that:

1. **The situs-critical layer is statewide and free.** The Comptroller publishes municipal
   boundaries for all 345 Tennessee cities, with annexations and deannexations reported since 2016,
   launched as a public dashboard in December 2025. **No county exclusions at all.** For a sales-tax
   situs audit the boundary layer *is* the product; parcels are supporting context.
2. **The parcel exclusion list is not a paywall.** The Comptroller's free weekly parcel feed covers
   every county except Chester, Davidson, Hamilton, Hickman, Knox, Montgomery, Rutherford, Shelby
   and Williamson. Of those nine: Davidson publishes parcels free; Montgomery publishes a free public
   parcel MapServer; Rutherford runs a free CC0 data hub; the City of Chattanooga gives away parcels
   and city limits inside Hamilton; Shelby County 911 gives away address points and centerlines.
   Chester and Hickman are small rural counties with no GIS shop to charge you. **The genuinely hard
   cases are Knox, Williamson, and countywide parcels in Shelby and Hamilton — three or four
   counties, not nine.**
3. **Most Tennessee counties have nothing to sell.** A survey of small and mid-size counties (Maury,
   Robertson, Trousdale, Smith, DeKalb, Macon, Cannon, Grundy) found no county GIS storefront at
   all. The $75-per-layer model exists only in the minority that built GIS with local funds.

### The decision rule

Buy a county GIS layer only when **all three** hold:

1. **It is not obtainable free.** Check in this order — (a) the county's own ArcGIS Hub or public
   REST endpoint; (b) the largest *city* in the county (Chattanooga gives away what Hamilton sells);
   (c) the county's 911 / ECD, a separate entity that is routinely more open than the county;
   (d) the Comptroller statewide feed; (e) the statewide city-boundary layer.
2. **It materially changes a finding.** Municipal boundary: always — and free. Parcels: usually only
   as join context. The real purchase candidates are things the state does *not* publish — zoning,
   special tax districts, sub-address and unit-level points.
3. **The county will not furnish it as client**, or the county is not the client.

One independent trigger overrides all three:

4. **Defensibility.** Free data ships with disclaimers. If a situs finding will be contested by a
   taxpayer or by a city, a purchased dataset carrying the county's own imprimatur is worth $75 many
   times over. **This, not coverage, is the only strong argument for buying** — and it applies
   selectively, after a specific dispute arises, not as a standing line item.

### Cost of each path across 95 counties

| Path | Licence fees | Real cost |
|---|---|---|
| Buy everything | ~$3,000–$6,000 actual (the $28,500 nominal figure is fiction — most counties have nothing to sell) | **190–380 hours** of procurement, vendor setup, PO and follow-up across 95 jurisdictions, recurring every refresh |
| Free-first, buy on exception | **Under $2,000 one-time**, 3–4 counties | Engineering: maintaining ~6–10 ingest paths instead of one uniform purchase pipeline. Recurring licence cost approximately zero. |

**Budget a $2,000–$3,000 one-time exception reserve. Do not create a per-county line item.**

Two things to resolve before committing, both currently undetermined because neither publishes a
policy: **Knox County's actual KGIS price and terms**, and **Williamson County's policy**. Both are
high-value markets. One phone call each, made in the name of a Tennessee-citizen employee.
