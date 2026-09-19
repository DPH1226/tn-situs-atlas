#!/usr/bin/env python3
"""
Readiness report: what you can say in a county or city finance office, and what you cannot.

    python3 tools/readiness.py wilson              # county
    python3 tools/readiness.py wilson --city lebanon
    python3 tools/readiness.py --all               # one-line status for every county

Reads out/<slug>/{summary.json, e5_verification.json, business_flows.csv, address_points_scored.csv}
and writes out/<slug>/readiness.md (or readiness-<city>.md). Nothing here is new analysis; it is the
existing evidence arranged as a pre-meeting brief with data vintage and a sample you can check by hand.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from fetch import config

OUTD = ROOT / "out"


def usd(v): return f"${v:,.0f}"


def norm(s): return str(s or "").upper().replace(".", "").replace("MOUNT ", "MT ").strip()


def report(slug: str, city: str | None = None) -> str | None:
    sp = OUTD / slug / "summary.json"
    if not sp.exists(): return None
    S = json.loads(sp.read_text()); C = S["county"]
    V = json.loads((OUTD / slug / "e5_verification.json").read_text()) if (OUTD / slug / "e5_verification.json").exists() else {}
    verdict = V.get("verdict", "NOT RUN"); w = verdict.split(" ")[0]
    fl = pd.read_csv(OUTD / slug / "business_flows.csv") if (OUTD / slug / "business_flows.csv").exists() else pd.DataFrame()
    codes = {str(k).zfill(4): v for k, v in S["situs_names"].items()}
    scope_codes = None; title = f"{C.title()} County"
    if city:
        scope_codes = [k for k, v in codes.items() if norm(v) == norm(city)]
        if not scope_codes: return f"# {city}: not a situs code in {C.title()} County\n"
        title = f"{codes[scope_codes[0]]} ({', '.join(scope_codes)}), {C.title()} County"
    L = []
    L.append(f"# Readiness — {title}\n")
    L.append(f"Generated from the county run of {S.get('generated_utc', '')[:10]}, rubric {S.get('rubric', '')}. No confidential data used.\n")
    # vintage
    L.append("## Data vintage\n")
    for k, d in (S.get("sources") or {}).items(): L.append(f"- {k}: snapshot {d}")
    L.append("- Local sales tax collections used for valuation: FY2025 (DOR June 2025 collections book, p.13)\n")
    # verification
    L.append("## Verification of the address-file signal\n")
    L.append(f"**Verdict: {verdict}**\n")
    if V.get("referee"):
        R, St, Lb, M, G = V["referee"], V["streets"], V["labels"], V["match_quality"], V["geography"]
        L.append(f"- Referee: on {R['measured_on_all_deep_e5']:,} rooftops where DOR's address file disagrees with DOR's polygon, the Comptroller's certified limits side with the polygon {R['comptroller_with_polygon_pct']}% of the time and the 911 authority {R['e911_with_polygon_pct']}%; both together {R['both_pct']}%.")
        L.append(f"- Streets: {St['all_or_nothing_streets']} of {St['streets_with_e5']} affected streets flip whole (>=90%); {St['e5_on_systematic_streets_pct']}% of disagreeing rooftops sit on them, {St['e5_scattered_pct']}% are scattered.")
        L.append(f"- Labels: on the {Lb['file_says_unincorporated']:,} rooftops the file codes unincorporated, its own city label names the polygon's city {Lb['file_city_label_matches_polygon_city_pct']}% of the time.")
        L.append(f"- Geography: disagreement share is {G['e5_share_pct_by_distance_ft'].get('250-500')}% within 500 ft of a boundary and {G['e5_share_pct_by_distance_ft'].get('>10000')}% deep in the interior (fringe/core x{G['fringe_vs_core_ratio']}).")
        L.append(f"- Match quality: file label contradicts the rooftop's own postal city on {M['file_label_differs_from_postal_city_pct']}%; ZIP-less fallback used on {M['zip_blank_pct']}%.\n")
        meaning = {"REAL": "The State's address-range file is the odd one out: three independent authorities place these addresses where the polygon does. Dollar figures for this county are shown on the atlas.",
                   "MIXED": "The disagreement is real but its pattern does not look like bulk annexation lag, or the boundary authorities disagree among themselves. Counts are reliable; dollar figures are withheld until a sample is inspected.",
                   "SUSPECT": "The file's labels do not match the places these rooftops are in - the signature of a wrong-street match in the address-range lookup. Do not quote counts or dollars for the address-file class until the match is fixed."}.get(w, "Verification has not been run for this county.")
        L.append(f"*{meaning}*\n")
    # counts and, if verified, dollars
    if len(fl):
        f = fl if scope_codes is None else fl[fl.correct.astype(str).str.zfill(4).isin(scope_codes) | fl.current.astype(str).str.zfill(4).isin(scope_codes)]
        if scope_codes is None:
            owed = f[(f.correct_county == C) & (f.current_county != C)]; err = f[(f.current_county == C) & (f.correct_county != C)]
            L.append("## Cross-county flows (both halves of the local option tax)\n")
        else:
            cc = f.correct.astype(str).str.zfill(4).isin(scope_codes); cu = f.current.astype(str).str.zfill(4).isin(scope_codes)
            owed = f[cc & ~cu]; err = f[cu & ~cc]
            L.append("## Flows for this city\n")
        L.append("| | Tier A | Tier B | Tier C | Total |\n|---|---|---|---|---|")
        L.append(f"| Owed — businesses inside, appearing to pay elsewhere | {int((owed.tier=='A').sum()):,} | {int((owed.tier=='B').sum()):,} | {int((owed.tier=='C').sum()):,} | {len(owed):,} |")
        L.append(f"| Receiving in error — businesses outside, appearing to pay it | {int((err.tier=='A').sum()):,} | {int((err.tier=='B').sum()):,} | {int((err.tier=='C').sum()):,} | {len(err):,} |")
        if w == "REAL":
            L.append(f"\nAt county averages: owed {usd(owed[owed.tier.isin(['A','B'])].value.sum())}/yr (A+B), receiving in error {usd(err[err.tier.isin(['A','B'])].value.sum())}/yr (A+B). A correction pays the one-year lookback once, then every year.\n")
        else:
            L.append(f"\nDollar figures withheld: verification verdict is {w}.\n")
        if scope_codes is None:
            # county treasury against its own cities
            cty = config.county(slug)["county"]
            uninc = [k for k in codes if k.endswith("00")]
            if uninc:
                u = uninc[0]; ow = f[(f.correct.astype(str).str.zfill(4) == u) & (f.current.astype(str).str.zfill(4) != u)]; er = f[(f.current.astype(str).str.zfill(4) == u) & (f.correct.astype(str).str.zfill(4) != u)]
                L.append("## County treasury against its own cities (situs half only)\n")
                L.append(f"- Owed to the county's unincorporated code: {len(ow):,} businesses (Tier A {int((ow.tier=='A').sum()):,})")
                L.append(f"- Coded to the county that the geography places inside a city: {len(er):,} businesses (Tier A {int((er.tier=='A').sum()):,}) — corrected, these move money **to** the cities. Say so before anyone else does.\n")
        # sample to check by hand
        top = owed[owed.tier == "A"].sort_values("confidence", ascending=False).head(12)
        if len(top):
            L.append("## Twelve Tier A businesses to check by hand before the meeting\n")
            L.append("Open each in the workbench; the evidence sheet shows all four authorities.\n")
            L.append("| Business | Address | Appears to pay | Geography says | Confidence |\n|---|---|---|---|---|")
            for r in top.itertuples():
                L.append(f"| {r.business} | {str(r.address).replace('.0 ', ' ')} {int(r.zip) if pd.notna(r.zip) else ''} | {r.current_name} ({r.current}) | {r.correct_name} ({r.correct}) | {int(r.confidence)} |")
            L.append("")
    # what to say
    L.append("## What you can say\n")
    if w == "REAL":
        L.append("- The Department of Revenue's address-range file and the Department's own boundary polygon disagree about where these addresses sit; the Comptroller's certified limits and the 911 authority side with the polygon.")
        L.append("- The counts above are measured from public data and can be reproduced from the sources listed.")
        L.append("- The dollar figures are county averages applied to counts — a size, not a finding for any named business.")
    elif w == "MIXED":
        L.append("- The counts above are measured from public data.")
        L.append("- The address-file disagreement is real but its pattern needs a sample inspected before it is quoted as a scale.")
    else:
        L.append("- Only the cross-county postal and boundary-risk counts; the address-file class is not yet reliable here.")
    L.append("\n## What you cannot say\n")
    L.append("- That any named business is miscoded. Only the situs report shows how a business is coded; until it is loaded, every number here is exposure.")
    L.append("- That the dollar figures are recoverable amounts. They are averages; the mean is skewed by large retailers and includes remote sales no situs code controls.")
    L.append("- That the 0.90 / 0.60 / 0.25 priors are measured. They are stated assumptions until the first roster calibration.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("county", nargs="?"); ap.add_argument("--city"); ap.add_argument("--all", action="store_true"); a = ap.parse_args()
    if a.all:
        for c in config.all_counties():
            vp = OUTD / c / "e5_verification.json"; sp = OUTD / c / "summary.json"
            if not sp.exists(): continue
            v = json.loads(vp.read_text()).get("verdict", "NOT RUN") if vp.exists() else "NOT RUN"
            print(f"  {c:<12} {v}")
        return
    md = report(a.county.lower(), a.city)
    if md is None: print("no run for", a.county); return
    out = OUTD / a.county.lower() / (f"readiness-{a.city.lower().replace(' ', '-')}.md" if a.city else "readiness.md")
    out.write_text(md); print(md); print(f"-> {out}")


if __name__ == "__main__":
    main()
