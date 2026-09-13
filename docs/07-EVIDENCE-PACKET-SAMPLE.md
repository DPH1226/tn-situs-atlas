# Situs correction — evidence packet (demonstration)

*Every value below is real and comes from public sources. The roster row is from the City of
Hendersonville's published business-tax roster, not from a Department of Revenue situs report; the
packet format is identical. This is what one finding looks like when it is ready to send.*

---

| | |
|---|---|
| **Submitting jurisdiction** | Sumner County, Tennessee |
| **Prepared by** | Civvix Inc., under contract to Sumner County pursuant to T.C.A. § 67-1-1704(e) |
| **Packet ID** | SUMNER-2026-09-0001 |
| **Reviewed by / date** | ________________ (analyst) · ____________ |
| **Approved for transmittal / date** | ________________ (Finance Director) · ____________ |

## 1. Account

| | |
|---|---|
| Business name | TOOL PLANNERS, INC. |
| Location address | 1780 SHELL RD, HENDERSONVILLE TN 37075-8457 |
| Account / location ID (as shown on roster) | 103789037 |
| Roster source | City of Hendersonville business-tax roster, public GIS table, snapshot 2026-09-12 |
| **Coded situs (per roster)** | **8305 — Hendersonville** |
| **Measured situs** | **8300 — Sumner County, unincorporated** |

## 2. Where the business physically sits — four independent official sources

| Source | Custodian | Says |
|---|---|---|
| Sales Tax Rate Boundary polygon | TN Department of Revenue | **8300 — Unincorporated** |
| Streamlined Sales Tax address-range file (1780 Shell Rd, 37075) | TN Department of Revenue | **8300 — Unincorporated** |
| NG911 address point, `Inc_Muni` field | TN Emergency Communications Board / Sumner County ECD | **Unincorporated** |
| Certified municipal boundary | TN Comptroller, Office of Local Government | **Outside every municipality** |

All four agree. There is no official source that places this address inside Hendersonville.

## 3. Boundary analysis

| | |
|---|---|
| Rooftop coordinate | 36.399306, −86.651799 (NAD83; measured in EPSG:2274, TN State Plane, US ft) |
| Nearest jurisdictional seam | **4,802 ft** — the seam between 8300 (unincorporated) and 8308 (Millersville) |
| Distance to the Hendersonville (8305) boundary | greater than 4,802 ft |
| Risk band | NORMAL (>1,000 ft) — boundary precision cannot explain the discrepancy |
| Address match | rooftop address point at 0 ft from the business location |

## 4. Evidence score — 100 / 100

| Component | Points |
|---|---|
| Inside a Department tax-rate polygon | +30 |
| 911-authority rooftop address point | +20 |
| All official sources agree on jurisdiction | +20 |
| Department address-range file matches the polygon | +15 |
| Business point within 100 ft of the rooftop | +10 |
| Address current in 911 layer | +5 |
| Penalties (seam proximity, source conflict, mailing-only address) | 0 |

Disposition: **READY — analyst sign-off then submit.** Auto-submit floor is 85 with no unresolved
source conflict.

## 5. Direction of correction

Correcting this account moves the situs half of local option sales tax on this account's sales
**from the City of Hendersonville to Sumner County**. The education half is unaffected (both are in
Sumner County). This packet is reported to the County whether or not the County elects to submit it.

## 6. Source provenance

| Layer | Snapshot | Features | SHA-256 (first 16) |
|---|---|---|---|
| DOR Sales Tax Rate Boundaries | 2026-09-12 | 473 | 7ef2e86c000c3bea |
| SST address-range file (Sumner) | 2026-09-12 | 15,102 | f2a2059fae8eeca9 |
| Comptroller municipal boundaries | 2026-09-12 | 345 | 5dec8de70e3dafe3 |
| NG911 address points (Sumner) | 2026-09-12 | 107,113 | 0686a0240fff6509 |
| Hendersonville business-tax roster | 2026-09-12 | 3,270 | bc3f1edde8b17c8a |

Every layer is retained unaltered so that this finding can be reproduced against the geography in
force on the date above.

## 7. Attachments

- Map: rooftop, situs polygons, nearest seam with measured distance (exported from the workbench).
- Street-level verification: Google Maps / Street View link (human verification only; not used in
  any measurement).

---

## Cover correspondence — for the County's signature

> Tennessee Department of Revenue, Financial Control Division
> 500 Deaderick Street, Nashville, TN 37242 · revenue.financialcontrol@tn.gov · (615) 532-8944
>
> Re: Situs correction — Sumner County — [N] accounts
>
> Pursuant to Tenn. Code Ann. § 67-1-1704(d), Sumner County has reviewed its situs report dated
> [date] and identified the accounts listed on the attached marked-up report as coded to a situs
> other than the jurisdiction in which the business location physically sits. For each account the
> County attaches an evidence packet showing the location's position relative to the Department's
> published sales tax rate boundaries, the Department's Streamlined Sales Tax address-range file, the
> Comptroller's certified municipal boundary, and the 911 addressing authority's records, together
> with the measured distance to the nearest jurisdictional boundary.
>
> The County requests that the Department verify these accounts, correct the situs code of each
> account found to be miscoded, and adjust distributions for the period permitted from the date of
> this notification. The County is prepared to furnish proof of corporate boundaries on request.
>
> [Finance Director], Sumner County

---

## The process, as best it can be documented

1. **The County pulls the situs report** from the Revenue External Portal. County officials only;
   their credentials; no vendor involvement in that step.
2. **The vendor matches and adjudicates** — in the County's environment. The roster never lands on
   vendor infrastructure. Each candidate gets a packet like the one above and a named reviewer.
3. **The County decides what to submit.** Both directions are reported; the County chooses.
4. **The County sends.** There is no Department form, no portal function and no statute governing
   corrections. MTAS's documented procedure is to mark the corrections on the situs report itself,
   keep a copy, and send it to Financial Control with each business's sales-tax account number. The
   vendor prepares the marked-up report, the packets and the cover letter; the County signs and
   transmits. This is also how Knox County structured its 2020 procurement: the vendor prepares
   correspondence, the Senior Director of Finance approves and sends.
5. **The Department verifies.** Per the Knox County RFP, the Department sends a request for
   verification; the other party may concur, not reply (treated as concurrence), or dispute. No
   appeal process is documented anywhere. Turnaround is unpublished.
6. **Adjustment.** Small amounts are netted against the next month's distribution; larger amounts
   are spread over the following year. Corrections reach back one year from the date of
   notification — Department practice, not statute.

**Why the County sends and not the vendor.** Two reasons. § 67-1-1704(e) forbids the contractor from
disclosing roster information "to any other person," and while the Department is the source of the
data, keeping the County as the sole channel removes any argument. And the Department's process is
built around the local government as the party of record — the notification date that starts the
one-year clock is the County's notification. Vendors in California file petitions directly under
written authorization; Tennessee has no equivalent mechanism, and none is needed.
