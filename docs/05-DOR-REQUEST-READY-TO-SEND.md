# DOR situs data request — ready to send

**Send from:** Aaron Maynard, Finance Director, Wilson County, Tennessee
**To:** Tennessee Department of Revenue, Financial Control Division —
revenue.financialcontrol@tn.gov · (615) 532-8944
**Authority:** Tenn. Code Ann. § 67-1-1704(d)
**Portal:** Revenue External Portal, tntap.tn.gov/rep

> *Make the Financial Control call in `03-FINANCIAL-CONTROL-CALL-SCRIPT.md` first. Two answers from
> that call — the contractor-designation mechanics and the lookback authority — may change what goes
> in sections 5 and 6 below.*

---

Wilson County is conducting a systematic review to ascertain whether allocations from state- and
local-levied taxes are being distributed to the correct unit of local government. The County has
already completed the geographic phase of this work using public data: every address point in Wilson
County has been placed within the Department's published sales tax rate boundary polygons in
Tennessee State Plane coordinates, compared against the Comptroller's certified municipal boundaries
and the State NG911 address file, and measured in feet against every jurisdictional boundary
touching the County. The County is now requesting the taxpayer situs information necessary to
complete the review.

## 1. ZIP code universe

**Tier 1 — ZIP codes wholly or partly within Wilson County, including the County's PO-Box-only ZIPs**
37012, 37016, 37071, 37085, 37087, 37088, 37090, 37095, 37118, 37121, 37122, 37136, 37138, 37184
*(14 ZIPs)*

**Tier 2 — the first surrounding ring**
37030, 37031, 37057, 37059, 37066, 37074, 37075, 37076, 37086, 37115, 37129, 37130, 37149, 37151,
37166, 37167, 37190, 38547, 38563, 38567, 38569 *(21 ZIPs)*

**Total requested: 35 ZIP codes.**

Tier 2 comprises the ZIP areas immediately adjoining the geographic ZIPs that intersect Wilson
County. They are requested because incorrect situs assignment arises overwhelmingly from
postal-address convention rather than from taxpayer error, and the error is therefore concentrated
in exactly this ring.

**The County can be specific about why.** Its geographic review identified **5,149 address points
physically inside Wilson County whose USPS postal city belongs to another county** — principally the
Old Hickory and Hermitage delivery areas of Davidson County along the Lebanon Road corridor in ZIP
37138, and the Lascassas and Milton areas of Rutherford County. A taxpayer at one of these addresses
who registers using the address as it appears on their mail will be coded outside Wilson County.
Reviewing the surrounding ring is the only way to identify those registrations.

If the Department determines that a particular Tier 2 ZIP falls outside its ordinary
adjacent-jurisdiction production standard, the County requests that the Department either (a) include
it on the justification above, or (b) **identify the specific ZIPs requiring further factual
justification**, so that the County may supplement rather than resubmit.

## 2. Situs codes

All Wilson County situs codes: **9500** (unincorporated), **9501** (Lebanon), **9502** (Watertown),
**9503** (Mt. Juliet).

## 3. Fields requested

To the extent permitted by § 67-1-1704(d), in CSV or XLSX:

taxpayer/business legal name · DBA or trade name · sales tax registration or account identifier ·
physical business location address · mailing address where it differs · ZIP code · current situs
code · county and city represented by that code · registration/account status · registration or
effective date · location identifier for multi-location taxpayers · report as-of date · any other
non-financial field the Department ordinarily provides for situs review.

The County is **not** requesting returns, receipts, income, tax liability, tax payments, or other
financial information.

## 4. Also requested

1. Current situs-code table and field definitions for the report, machine-readable if available.
2. Current instructions and evidentiary requirements for submitting a situs correction.
3. Written confirmation of the maximum retroactive adjustment period currently applicable **and its
   authority** — statute or Department policy.
4. REP access for the authorized County personnel listed in section 5, for the situs report and for
   the City/County Detail and City/County Month Detail reports.
5. The Department's requirements for contractor access under § 67-1-1704(e).

## 5. Personnel and contractor designation

*[County to list authorized employees by name and title.]*

The County has engaged **Civvix Inc.** as its contractor for this review under
§ 67-1-1704(e). The County understands that the disclosure permitted to a contractor is limited on
its face to the **name, address and situs** of taxpayers and does not extend to returns, receipts,
income, tax liability, tax payments or other financial information, and the County will not transfer
anything beyond those fields.

The County further confirms that each individual at the contractor with access has executed a written
acknowledgment that, under § 67-1-1704(e), they are subject to all penalties and restrictions
applicable to an officer or employee of the State under § 67-1-1709, **including that unauthorized
disclosure is a Class E felony**, and that the obligation attaches to any person who has or has had
access at any time and survives the end of the engagement. Named individuals with access, their
written acknowledgments, and the County's data-handling requirements are available to the Department
on request.

## 6. Audit controls

For each proposed correction the County will retain: the source records relied on; the effective-dated
boundary geometry used, with its custodian, download timestamp and SHA-256 hash; the spatial analysis
result including the measured distance to the nearest jurisdictional boundary; supporting documentary
evidence; the reviewer's decision and date; the submission to the Department; and the Department's
disposition.

The County notes that its review is **bidirectional**. Where the evidence establishes that a
taxpayer currently coded to Wilson County should be coded elsewhere, that finding will be submitted
on the same basis as any other.

---

*Contact: Aaron Maynard, Finance Director, Wilson County, Tennessee.*
