# Local Option Sales Tax Situs Verification and Monitoring — Scope of Services

*Drafted for a Tennessee county or municipal finance office to adapt into a solicitation or a
sole-source justification. Written as requirements a vendor must meet, not as marketing copy.*

## 1. Purpose

The [County/City] seeks a vendor to verify that every business physically located within its
jurisdiction is coded to the correct Department of Revenue situs code, so that local option sales tax
collected under T.C.A. § 67-6-712 is distributed to the correct unit of local government; to identify
and document miscoded accounts; to prepare correction submissions for the [County/City]'s approval
and transmittal to the Department; and to monitor the jurisdiction continuously so that no
miscoding persists beyond the Department's one-year correction window.

## 2. Background

Every sales-tax registrant carries a four-digit situs code assigned at registration from the address
on the application. The code determines where the situs half of local option sales tax is
distributed and, for cross-county errors, where the education half is distributed as well. The
Department does not reconcile accounts against jurisdictional boundaries after registration; a
wrong code persists until the affected local government identifies it and notifies the Department.
The Department corrects distributions back one year from the date of notification.

## 3. Required approach

The vendor shall:

**3.1 Establish the jurisdiction's geography before examining any taxpayer record.** Place every
address point in the jurisdiction within the Department's published sales tax rate boundary polygon
using rooftop-level address points from the 911 addressing authority, not street-interpolated
geocoding. Measure every address point's distance in feet to the nearest boundary between two
different situs codes, in Tennessee State Plane coordinates. Produce a boundary quality report that
states the number of address points placed, the number that fell in no polygon, and the linear miles
of jurisdictional boundary examined, before any exception is reported.

**3.2 Compare independent official sources.** For each address point, record the jurisdiction
assigned by (a) the Department's sales tax rate boundary polygon, (b) the 911 addressing authority's
municipality field, (c) the Comptroller of the Treasury's certified municipal boundary, and (d) the
Department's Streamlined Sales Tax address-range file. Report every address where these sources
disagree, and treat any such address as requiring human adjudication before submission.

**3.3 Classify exposure using public data only, before requesting confidential data.** Identify and
rank, from public sources, the addresses most likely to carry a miscoded registration: physical
locations inside the jurisdiction whose USPS postal city belongs to another county; locations whose
postal city names a municipality the location is not inside; and locations within 250 feet of a
jurisdictional boundary. Deliver this ranked queue to the [County/City] before the situs report is
requested, so that the [County/City] can evaluate the method on its own geography at no risk.

**3.4 Obtain and match the situs report.** Assist the [County/City] in requesting the situs report
and City/County Detail reports through the Revenue External Portal under T.C.A. § 67-1-1704(d).
Match each roster row to a placed address point by normalized business name and address. Report
match rate. Compare each matched account's coded situs to its measured situs.

**3.5 Score and adjudicate every finding.** Assign each candidate a documented evidence score using a
published rubric that credits agreement among official sources and penalizes proximity to a
boundary and mailing-only addresses. No finding within 50 feet of a boundary, and no finding on
which official sources disagree, shall be submitted without individual human review recorded by
name and date.

**3.6 Report in both directions.** Report every account whose correction would move revenue *to* the
[County/City] and every account whose correction would move revenue *away from* it, in the same
format and with the same evidence standard. The [County/City] alone decides what is submitted.

**3.7 Prepare correction packets.** For each finding approved by the [County/City], prepare an
evidence packet containing: business name and address; sales-tax account number as shown on the
situs report; coded situs; measured situs; the jurisdiction assigned by each official source; distance
in feet to the nearest boundary; the effective date, custodian and cryptographic hash of every source
layer used; a map; and the reviewer's name and date. Prepare the cover correspondence to the
Department for the [County/City]'s signature.

**3.8 Monitor continuously.** Re-acquire the Department's boundary polygons quarterly, the
Comptroller's municipal boundaries monthly, and the 911 address points monthly; re-place every
address point when any boundary changes; and report new, resolved and changed exceptions in a
written bulletin at least quarterly, so that no miscoding persists beyond the Department's one-year
window.

**3.9 Reproducibility.** Retain every source snapshot with its effective date and hash so that any
finding can be reproduced against the geography in force on the date it was made.

## 4. Data handling

The vendor shall receive from the [County/City] only the name, address and situs of taxpayers, as
permitted by T.C.A. § 67-1-1704(e), and no returns, receipts, income, liability, payment or other
financial information. The vendor shall not disclose such information to any other person. The
vendor shall name every individual with access, each of whom shall acknowledge in writing that
unauthorized disclosure is a Class E felony under T.C.A. § 67-1-1709 and that the obligation survives
the engagement. The vendor shall not store the situs report on infrastructure outside the
[County/City]'s control, shall not use any third-party processing service on it, and shall certify
its destruction at the end of the engagement. The vendor shall not use information derived from the
[County/City]'s situs report in work for any other jurisdiction.

## 5. Deliverables

1. Boundary quality report (before any taxpayer data is requested).
2. Ranked exposure queue from public data.
3. Situs report request package for the [County/City]'s transmittal.
4. Matched roster with coded-versus-measured comparison and match rate.
5. Adjudicated findings, both directions, with evidence packets.
6. Cover correspondence to the Department for signature.
7. Quarterly monitoring bulletin.
8. A calibration report after the first correction cycle: the precision and recall of each exposure
   class against actual coding.

## 6. Pricing

Fixed annual fee for the monitoring service, inclusive of all deliverables. No contingency on
recovery. *(See separate pricing schedule.)*

## 7. Insurance

Commercial general liability $1,000,000 per occurrence / $2,000,000 aggregate; technology errors and
omissions $1,000,000; cyber liability $1,000,000; the [County/City] named additional insured on
general liability; carriers rated A- VII or better.

## 8. What distinguishes a conforming response

A response that relies on ZIP code or mailing-city matching, on commercial geocoding, or on
examining the situs report before the geography has been independently verified does not conform to
sections 3.1–3.3. A response that reports findings in one direction only does not conform to 3.6. A
response that cannot reproduce a finding against a dated source snapshot does not conform to 3.9.
