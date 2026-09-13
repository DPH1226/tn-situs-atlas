# Insurance and data handling for confidential situs data

*Prepared for Civvix Inc. Not legal advice and not an insurance quote — a licensed Tennessee broker
must place any coverage, and a Tennessee attorney should review the statutory reads flagged below.*

---

## The short version

Your biggest exposure on this engagement is **not insurable**, and your second biggest is **not a
data breach**.

1. **T.C.A. § 67-1-1709 is a Class E felony** — 1 to 6 years and a fine up to $3,000 — and
   § 67-1-1704(e) expressly imports it onto contractors by name. It attaches to *individual human
   beings*, and it attaches **permanently**: the statute reaches "any person who has, **or had at any
   time**, access." It does not end when the contract ends or when an employee leaves. No policy
   transfers this. Controls, contract structure and keeping the number of people small are what
   mitigate it.
2. **The data is boring, and that is worth money.** Business name, business address, four-digit situs
   code. That is **not "personal information"** under Tennessee's breach-notification statute
   (T.C.A. § 47-18-2107), which requires a name *plus* an SSN, driver licence number, or a financial
   account number with its access code. If a laptop holding the full county file is stolen tomorrow,
   **no notification is required**. Say this explicitly on every insurance application — vague
   applications get priced defensively.
3. **Buy technology E&O first, cyber second.** Your realistic claim is "your situs analysis was wrong
   and it cost the county money" — a pure economic loss that commercial general liability does not
   cover. That is an E&O claim, not a breach claim.
4. **Budget roughly $2,300–$5,000 a year** for CGL + tech E&O + cyber at $1M limits. The cyber market
   has now posted twelve consecutive quarters of rate declines. Get three quotes and push back on
   the first number.

---

## What to buy, and what is theatre

| Coverage | Verdict | Why |
|---|---|---|
| **Technology E&O / Professional Liability** | **Buy first** | Your actual work-product exposure. CGL will not touch a pure economic loss. |
| **Cyber liability** | **Buy second** | Value is *not* notification (≈ zero here). It is (a) breach counsel within hours of any incident touching this data, and (b) the **governmental-investigation defence-cost grant**. |
| **Commercial General Liability** | **Buy — contractually mandatory, functionally irrelevant to the data** | Since 2014 the ISO forms carry the CG 21 06 / CG 21 07 exclusions, which strip data-breach liability out of CGL entirely. Every county contract still requires it, and it is cheap. |
| **Social engineering fraud endorsement** | **Buy — cheapest real protection you will own** | Wire fraud triggered by a spoofed vendor or a spoofed CEO is the single most common actual loss at a 3–10 person company. The State of Tennessee's own pro forma requires $250,000. |
| **Crime / fidelity** | Skip unless a contract demands it | Protects against employees stealing funds. You do not handle county money. |
| **D&O** | **Defer — but ask one question** | Not needed at this stage. However, D&O is the one policy that can advance **individual criminal defence costs**, which cyber and E&O (entity-focused) generally will not. Raise it with your broker as a deliberate question rather than a default purchase. |

### The two questions to put to a broker in writing

1. **Does the cyber policy's "protected information" definition reach third-party confidential
   *corporate* information**, not just PII? Standard forms usually do, via the corporate-confidential-
   data prong — but this is the wording that decides whether your policy responds at all, because
   your file contains no PII.
2. **Does the regulatory / governmental-proceeding grant reach a criminal investigation by a state
   District Attorney, and does it cover individual insured persons** — or only the entity, and only
   civil regulators? Most small-business forms are entity-focused and civil-regulator-focused. Get
   the answer in writing before relying on it.

### What insurance cannot do, stated plainly

Criminal fines and imprisonment are uninsurable as a matter of public policy. **Defence costs are a
different question** and are generally coverable — the insurability analysis does not reach
investigatory and defence expense, and D&O conduct exclusions typically require a *final,
nonappealable adjudication* before they bite, so fees get advanced through the proceeding. If the
disclosure was intentional, the conduct exclusion eventually claws even those back. That is not a
term you can negotiate away.

---

## What Tennessee counties actually require

There is **no statewide standard**. Neither CTAS nor MTAS publishes vendor insurance or data-security
guidance — I checked both, and the absence is the finding. Requirements live in each entity's
standard bid text and are negotiable. **Ask for the county's standard terms before you quote.**

**Knox County's posted vendor requirements** are the best available benchmark for a Tennessee county:

- Workers Compensation — Tennessee statutory limits
- Employers Liability — $100,000 / $100,000 / $500,000
- Commercial General Liability — **$1,000,000 per occurrence / $2,000,000 aggregate**
- Automobile Liability — $1,000,000 CSL
- Umbrella — **$2,000,000**
- **Professional Liability — $1,000,000 per occurrence/claim**
- County named additional insured on all policies except workers' comp and auto
- **Endorsement pages required with the certificate**, referencing the RFP number
- Carriers rated **A- VII or better** by A.M. Best
- **Cyber liability is not required at all**

So the answer to "$1M/$2M or $2M/$5M" for a Tennessee county is **$1M/$2M with a $2M umbrella**.

**By contrast, a State of Tennessee pro forma contract requires $10,000,000 cyber liability**,
$1M crime with a $250K social-engineering endorsement, FIPS 140-2/140-3 encryption at rest and in
transit, and all state data held inside the United States. *(That figure is from one procurement's
pro forma; state limits scale with data sensitivity and contract value — treat it as directional.)*

**The gap between $0 cyber at the county and $10M at the state is the most useful number in this
memo.** Choose limits based on whether you intend to sell to state agencies later, not on what
Wilson County will ask for.

---

## The document worth reading twice

**Knox County Procurement RFP #2969, "Tax Consulting Services."** Its scope is your fact pattern
almost verbatim: audit the situs reports of local governments, identify taxpayers whose situs code
belongs in Knox County but whose collections were reported elsewhere, prepare correspondence,
coordinate with the Department of Revenue, report to Knox County Finance.

**That RFP contains no insurance requirements section, no confidentiality clause, no data-security
requirements, no NDA, no background checks, no data-destruction protocol, and no reference to
§ 67-1-1704 or § 67-1-1709 at all.**

Two things follow. First, competitively: **a large Tennessee county has already procured this exact
service**, which settles the open question of whether counties buy situs audits — they do — and
tells you what the incumbent procurement looks like. Second, defensively: the county's silence
creates no defence for you. The felony statute applies whether or not the contract mentions it.

---

## What actually blocks a small vendor, and what does not

In rough order of what stops a contract from executing at a county:

1. **A certificate of insurance with the county correctly named as additional insured, with the
   endorsement pages attached.** This is the gate, it is administrative, and it is where small
   vendors most often stall — wrong legal entity name, missing endorsements, carrier below A- VII,
   no RFP number on the certificate.
2. W-9 and vendor registration.
3. **References from other Tennessee local governments.** Underweighted by vendors, heavily weighted
   by finance directors.
4. A signed contract with indemnification. Refusing to indemnify loses the deal.
5. **A named, accountable human.** "Who specifically will have access to this data?" — answer it
   before it is asked.

**What a county will generally *not* ask a small vendor for:** SOC 2 Type II, penetration test
reports, StateRAMP/GovRAMP authorization, ISO 27001. A SOC 2 audit takes 6–12 months and real money;
no county is conditioning a modest professional-services contract on it. A state agency is a
different conversation entirely.

---

## The two-page protocol nobody will ask for — write it anyway

This is the actual mitigation for the uninsurable exposure in section 1, it costs an afternoon, and
it is reusable at every subsequent county.

1. **Minimise at the source.** Demand in writing, *before any transfer*, an extract containing only
   **name, address and situs code**. Refuse anything more. If a file arrives carrying revenue figures
   or account numbers, you are holding data § 67-1-1704(e) never permitted you to receive — and the
   statute reaches anyone who *has access*, not only anyone who misuses it. **The exposure attaches
   on receipt.** Have a written procedure: do not open it, notify the county immediately in writing,
   have it destroyed and re-cut.
2. **Minimise the humans.** Every person with access is a separate, permanent, personal felony
   exposure. Keep it to two or three. Name them in the contract. Being small is an advantage here —
   use it.
3. **Individual written acknowledgment**, citing § 67-1-1704(e) and § 67-1-1709, stating the Class E
   felony penalty explicitly, and acknowledging that the obligation survives employment. Re-signed
   annually. Partly a control, partly evidence of good faith.
4. **No subcontractors, no offshore, no third-party AI tools on this data.** § 67-1-1704(e) says flatly
   that no contractor "shall disclose such information to any other person." **Pasting this data into
   a third-party service is a disclosure.** Treat it as a bright line. Whether a properly structured
   subcontract could ever work is an attorney question — do not improvise it.
5. **Technical controls you will be asked about and that are free to adopt:** encryption at rest and
   in transit (FIPS 140-2/140-3 — the State's own standard), MFA everywhere, no county data on
   personal devices or removable media, one defined storage location, access logging, US-only
   residency.
6. **Defined retention and certified destruction.** Specify how long you hold it, destroy on
   schedule, certify in writing to the county. Data you no longer hold cannot be disclosed by you.
   This is the cheapest risk reduction available and finance directors notice it.
7. **Annual training, documented.**
8. **Contract structure** — mutual indemnification; an affirmative obligation on the county to limit
   its transfer to the § 67-1-1704(e) fields; limitation of liability tied to fees; incident-
   notification timelines running both ways. Have a Tennessee attorney draft this.

---

## Flags for professional sign-off

**A Tennessee attorney should confirm:** whether § 67-1-1709 can be charged against Civvix Inc. as a
corporate entity and not only against individuals; whether any civil cause of action exists (none
appears in Part 17, §§ 67-1-1701 to 1712); whether § 67-1-1704(e) permits *any* onward disclosure to
a subcontractor or cloud processor; and the sole-proprietor analysis under § 47-18-2107, which above
is a statutory reading rather than a cited holding.

**One phone call worth making:** the **Local Government Insurance Pool**, (615) 872-3554 — the risk
pool serving Tennessee counties. Ask whether it imposes vendor insurance requirements on member
counties' contractors. Nothing is published, and if Wilson is a member, the pool's loss-control
bulletin may be the real source of whatever the county eventually asks you for.
