"""
Exception detection from PUBLIC data only.

Nothing in this module requires the confidential DOR situs report. That is the
design point: the county can see real, named, mapped candidate exceptions before
it ever sends a byte of taxpayer data to a contractor. When the situs report
does arrive, it becomes the seventh input, not the first.
"""
from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

# USPS place names that are NOT incorporated municipalities. A registration
# keyed to one of these mailing addresses has no city to be coded to, which is
# exactly when a clerk or a taxpayer guesses -- and guesses toward the postal
# city's county.
USPS_ONLY_PLACES = {
    "HERMITAGE": "DAVIDSON",
    "OLD HICKORY": "DAVIDSON",
    "ANTIOCH": "DAVIDSON",
    "MADISON": "DAVIDSON",
    "DONELSON": "DAVIDSON",
    "NASHVILLE": "DAVIDSON",
    "GLADEVILLE": "WILSON",
    "NORENE": "WILSON",
    "LASCASSAS": "RUTHERFORD",
    "MILTON": "RUTHERFORD",
    "CASTALIAN SPRINGS": "SUMNER",
}

_SUFFIX_ALIASES = {
    "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "CIRCLE": "CIR",
    "COURT": "CT", "DRIVE": "DR", "HIGHWAY": "HWY", "LANE": "LN",
    "PARKWAY": "PKWY", "PIKE": "PIKE", "PLACE": "PL", "ROAD": "RD",
    "STREET": "ST", "TERRACE": "TER", "TRAIL": "TRL", "WAY": "WAY",
    "MILL": "ML", "CREEK": "CRK", "RIDGE": "RDG", "POINT": "PT",
}


def _norm_token(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = re.sub(r"[^A-Z0-9 ]", "", str(v).strip().upper())
    s = re.sub(r"\s+", " ", s)
    return _SUFFIX_ALIASES.get(s, s)


def street_key(name, suffix, zipcode) -> str:
    z = str(zipcode).strip()[:5] if zipcode is not None and str(zipcode).strip() else ""
    return f"{_norm_token(name)}|{_norm_token(suffix)}|{z}"


def build_sst_index(sst_rows: list[dict]) -> dict[str, list[dict]]:
    """Index DOR's own address-range -> situs table by street key."""
    idx: dict[str, list[dict]] = defaultdict(list)
    for r in sst_rows:
        k = street_key(r.get("streetname"), r.get("streetsuffixabbrev"), r.get("zipcode"))
        lo, hi = r.get("addrprimarylowno"), r.get("addrprimaryhighno")
        if lo is None or hi is None:
            continue
        rec = {
            "lo": int(lo), "hi": int(hi),
            "parity": (r.get("addrprmryoddevencod") or "B").strip().upper()[:1],
            "situs": str(r.get("situs") or "").strip(),
            "city": (r.get("city") or "").strip().upper(),
            "county": (r.get("county") or "").strip().upper(),
        }
        idx[k].append(rec)
        # ZIP-less fallback key for 911 authorities that leave Zip_Code blank
        # (DeKalb does). Used only when the query itself carries no ZIP, and a
        # match is accepted only if it is unambiguous across ZIPs.
        idx[street_key(r.get("streetname"), r.get("streetsuffixabbrev"), None)].append(rec)
    return idx


def sst_situs_for(idx, name, suffix, zipcode, number) -> dict | None:
    """
    What does DOR's OWN address-range table say the situs is for this address?

    Parity matters: 'O' ranges cover odd house numbers only, 'E' even only,
    'B' both. Ignoring it produces false matches on split-side streets, which
    are precisely the streets that run along a city line.
    """
    if number is None or (isinstance(number, float) and pd.isna(number)):
        return None
    try:
        n = int(number)
    except (TypeError, ValueError):
        return None
    zk = str(zipcode).strip()[:5] if zipcode is not None and str(zipcode).strip() and str(zipcode).strip().lower() != "nan" else ""
    hits = []
    for cand in idx.get(street_key(name, suffix, zk or None), []):
        if not (cand["lo"] <= n <= cand["hi"]):
            continue
        p = cand["parity"]
        if p == "O" and n % 2 == 0:
            continue
        if p == "E" and n % 2 == 1:
            continue
        if zk:
            return cand
        hits.append(cand)
    if not zk and hits and len({h["situs"] for h in hits}) == 1:
        return hits[0]
    return None


# --------------------------------------------------------------------------
# Exception classes. Ordered by what each costs Wilson County, not by count.
# --------------------------------------------------------------------------
CLASSES = {
    "E2_CROSS_COUNTY_POSTAL": dict(
        severity=1, loss="BOTH HALVES (situs + education)",
        title="Wilson rooftop carrying another county's mailing city",
        why=("The physical location is inside Wilson County, but the postal city "
             "on the address belongs to another county. A registration keyed to "
             "the mailing address codes to that county and Wilson loses both the "
             "situs half and the education half."),
    ),
    "E5_DOR_INTERNAL_CONFLICT": dict(
        severity=1, loss="depends on direction",
        title="DOR's address-range table disagrees with DOR's own boundary polygon",
        why=("The Streamlined Sales Tax address-range file assigns one situs to "
             "this address; the Department's own tax-rate polygon places the "
             "rooftop in a different one. This is an inconsistency inside the "
             "state's published data and needs no confidential file to prove."),
    ),
    "E5B_DOR_CONFLICT_AT_BOUNDARY": dict(
        severity=2, loss="depends on direction",
        title="DOR address-file / polygon conflict within 250 ft of a seam",
        why=("Same conflict as E5, but close enough to the line that boundary "
             "precision alone could explain it. Adjudicate; do not assert."),
    ),
    "E1_POSTAL_CITY_OVERSTATES": dict(
        severity=4, loss="EXPOSURE POPULATION, not a finding",
        title="City mailing address on a rooftop outside that city",
        why=("The rooftop is not in the municipality its mailing address names. "
             "This is NOT by itself an error - it is the population in which "
             "errors occur, because a registration keyed to the mailing address "
             "would be coded to the wrong jurisdiction. Whether any given "
             "business here is actually miscoded cannot be known until the "
             "situs report arrives. Report it as exposure, never as a finding."),
    ),
    "E6_ANNEXATION_LAG": dict(
        severity=2, loss="SITUS HALF, time-limited",
        title="Inside a municipal annexation the DOR polygon does not reflect",
        why=("The city's own annexation layer includes this rooftop but the "
             "Department's tax-rate polygon does not. Either the annexation has "
             "not propagated to DOR, or the city layer is ahead of its effective "
             "date. Both are findings; they point in opposite directions."),
    ),
    "E4_LAYER_DISAGREEMENT": dict(
        severity=2, loss="unknown until adjudicated",
        title="Official layers disagree about the municipality",
        why=("DOR, the 911 addressing authority and the Comptroller's certified "
             "boundary do not agree. Protocol Rule 5: no automated submission."),
    ),
    "E3_BOUNDARY_PROXIMITY": dict(
        severity=3, loss="risk, not yet a loss",
        title="Within the boundary-risk band of a jurisdictional seam",
        why=("Close enough to a seam that geocoder error alone can flip the "
             "jurisdiction. Not an error; a control. These are the locations "
             "where a competitor's ZIP-based method silently guesses."),
    ),
}


def _has(v) -> bool:
    """NaN-safe truthiness. A pandas row hands back float('nan') for a missing
    string, and NaN is truthy -- which silently awarded every rooftop in the
    county ten points for a DOR address-range match it did not have."""
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    return bool(str(v).strip()) and str(v).strip().lower() not in {"nan", "none"}


def score_evidence(row) -> tuple[int, str]:
    """
    100-point evidence score, additive then penalised.

    v2 (12 Sep 2026). v1 reserved 35 points for `Placement` and `Parcel_ID`,
    fields the statewide NG911 layer leaves empty in Wilson County -- so the
    rubric's ceiling there was 72 and nothing could ever reach the 85-point
    submission floor. A rubric that cannot be satisfied by evidence that exists
    is not conservative, it is broken. v2 scores what the sources actually
    carry; parcel and business corroboration add on top when present.

      +30  inside a DOR tax-rate polygon (the authoritative layer)
      +20  911-authority address point (rooftop-grade by construction)
      +20  every available official layer agrees on the municipality
      +15  DOR's own address-range file matches (range + parity)
      +10  a business point sits within 100 ft of the rooftop
      + 5  address is current in the 911 layer (NG911 publishes only current points)
      + 5  parcel identifier present (bonus; ceiling stays 100)
      -25  within 50 ft of a jurisdictional seam
      -10  within 250 ft of a seam
      -20  official layers conflict
      -20  mailing-only address type
    Auto-submit floor: >=85 AND no unresolved official-layer conflict.
    """
    s, notes = 0, []
    if _has(row.get("dor_situs")):
        s += 30; notes.append("+30 DOR tax polygon")
    if row.get("geometry") is not None:
        s += 20; notes.append("+20 911-authority address point")
    if bool(row.get("layers_agree")):
        s += 20; notes.append("+20 official layers agree")
    if _has(row.get("sst_situs")):
        s += 15; notes.append("+15 DOR address-range match")
    if _has(row.get("biz_within_100ft")) and bool(row.get("biz_within_100ft")):
        s += 10; notes.append("+10 business point within 100 ft")
    life = str(row.get("Lifecycle")).upper() if _has(row.get("Lifecycle")) else ""
    if life in {"ACTIVE", "CURRENT", ""}:
        s += 5; notes.append("+5 address current")
    if _has(row.get("Parcel_ID")):
        s += 5; notes.append("+5 parcel id")
    band = row.get("risk_band")
    if band == "CRITICAL":
        s -= 25; notes.append("-25 within 50 ft of a seam")
    elif band == "HIGH":
        s -= 10; notes.append("-10 within 250 ft of a seam")
    if not bool(row.get("layers_agree", True)):
        s -= 20; notes.append("-20 conflicting official layers")
    addr_type = str(row.get("Addr_Type")).upper() if _has(row.get("Addr_Type")) else ""
    if addr_type in {"PO BOX", "POBOX"}:
        s -= 20; notes.append("-20 mailing-only address")
    return max(0, min(100, s)), "; ".join(notes)


def disposition(score: int, layers_agree: bool, band: str) -> str:
    if band == "CRITICAL" or not layers_agree:
        return "HOLD - mandatory human adjudication"
    if score >= 85:
        return "READY - analyst sign-off then submit"
    if score >= 70:
        return "REVIEW - analyst"
    return "HOLD - insufficient evidence"


# --------------------------------------------------------------------------
# Business-label classification.
#
# A 911 district's "business" layer is a LABEL layer: whatever the addressing
# office found useful to name on a map. That includes subdivisions, lot numbers,
# pump stations, churches and blanks. An audit the county has to stand behind
# cannot carry a row called "Lot 19". Every label is kept on the map for
# transparency; only kind == "business" enters the queue.
# --------------------------------------------------------------------------
import re as _re

_PLACE = _re.compile(
    r"\b(SUBD\.?|SUBDIVISION|LOTS?\s*#?\s*\d+|PHASE\s*\d|SEC(TION)?\s*\d|APTS?\b|APARTMENTS?|CONDOS?|"
    r"CONDOMINIUMS?|TOWNHOMES?|TOWNHOUSES?|VILLAS?\b|ESTATES\b|PUMP STATION|LIFT STATION|WATER METER|"
    r"WATER TANK|SUBSTATION|(CELL|WATER|RADIO|COMM) TOWER|TOWER SITE|WELL\s*#?\s*\d|CEMETERY|CLUB ?HOUSE|POOL HOUSE|COMMUNITY (CENTER|CTR)|"
    r"STORED TRAILERS?|GATE\b|ENTRANCE|PARK\b|TRAILHEAD|GREENWAY|BOAT (RAMP|DOCK)|CAMPER SITE|CAMPGROUND|"
    r"DUMPSTER|MAILBOXES|KIOSK|MODEL HOME)\b")
_INSTITUTION = _re.compile(
    r"\b(CHURCH|BAPTIST|METHODIST|PRESBYTERIAN|CATHOLIC|LUTHERAN|CHAPEL|MINISTR(Y|IES)|FELLOWSHIP|"
    r"TEMPLE|MOSQUE|SYNAGOGUE|SCHOOL|ELEMENTARY|MIDDLE SCHOOL|HIGH SCHOOL|ACADEMY|COLLEGE|UNIVERSITY|"
    r"LIBRARY|FIRE (DEPT|DEPARTMENT|STATION|HALL)|POLICE|SHERIFF|COURTHOUSE|CITY HALL|POST OFFICE|"
    r"MASONIC|LODGE\b|VFW|AMERICAN LEGION|GOVERNMENT|COUNTY (OFFICE|BUILDING)|BOARD OF EDUCATION|"
    r"HEADSTART|HEAD START|CO-?OP\b|UTILITY DISTRICT|ELECTRIC (COOP|COOPERATIVE)|WATER (DEPT|AUTHORITY))\b")


def classify_label(name) -> str:
    """'business' | 'institution' | 'place' | 'unnamed'"""
    if name is None or (isinstance(name, float) and name != name):
        return "unnamed"
    s = str(name).strip().upper()
    if not s or _re.fullmatch(r"[\d\s\-#/A-Z]{0,3}\d[\d\s\-#/A-Z]{0,4}", s):
        return "unnamed"          # "118", "118 A", "B62", "142"
    if _PLACE.search(s):
        return "place"
    if _INSTITUTION.search(s):
        return "institution"
    return "business"
