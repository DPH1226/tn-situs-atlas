#!/usr/bin/env python3
"""
Is a county's Tier-A "DOR file ≠ polygon" signal real, or a matching artifact?

    python3 tools/verify_e5.py wilson            # one county
    python3 tools/verify_e5.py --all             # every county with out/<slug>/address_points_scored.csv

Six tests. 1 Referee: on every deep E5 rooftop, do the 911 authority and the Comptroller side with the
polygon against the file? 2 Geography: does the E5 share fall with distance from the seam (annexation
fringe) rather than scatter? 3 Streets: do whole streets flip together (stale range table) or random
rooftops (bad match)? 4 Labels: does the file's own city label name the annexing city while its code
says unincorporated? 5 Commerce: do E5 rooftops carry business points at least as often as others?
6 Match quality: how much of the match used the ZIP-less fallback, and how often does the file's label
disagree with the rooftop's own postal city - the wrong-street signature.

REAL = referee >= 90% and >= 50% of E5 on all-or-nothing streets and >= 85% label coherence.
MIXED = referee passes plus one other. SUSPECT = looks like a matching artifact. Written to
out/<slug>/e5_verification.json; build_flows.py reads it and excludes SUSPECT from the verified headline.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from fetch import config

OUTD = ROOT / "out"
COLS = ["dor_situs", "sst_situs", "sst_city", "muni_dor", "muni_e911", "muni_comptroller", "risk_band", "nearest_seam_ft", "Post_City",
        "E5_DOR_INTERNAL_CONFLICT", "StNam_Full", "Zip_Code", "evidence_score", "biz_within_100ft"]


def norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.replace(".", "", regex=False).str.replace("MOUNT ", "MT ", regex=False).str.strip()


def s4(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).str.zfill(4).where(s.notna(), None)


def verify(slug: str) -> dict | None:
    p = OUTD / slug / "address_points_scored.csv"
    if not p.exists(): return None
    a = pd.read_csv(p, low_memory=False, usecols=lambda c: c in COLS)
    for c in COLS:
        if c not in a.columns: a[c] = None
    a["dor4"] = s4(a.dor_situs); a["sst4"] = s4(a.sst_situs)
    for c in ("muni_dor", "muni_e911", "muni_comptroller", "sst_city", "Post_City"): a[c] = norm(a[c])
    a["E5"] = a.E5_DOR_INTERNAL_CONFLICT.fillna(False).astype(bool)
    a["biz"] = a.biz_within_100ft.fillna(False).astype(bool)
    a["seam"] = pd.to_numeric(a.nearest_seam_ft, errors="coerce").fillna(0)
    deep = a[(a.seam >= 250)]
    e5 = deep[deep.E5 & (deep.evidence_score >= 85) & (deep.risk_band != "CRITICAL")].copy()
    r = {"county": slug, "rooftops": int(len(a)), "tierA_e5": int(len(e5)), "tierA_e5_pct": round(100 * len(e5) / max(1, len(a)), 2)}
    if len(e5) < 20:
        r["verdict"] = "TOO FEW TO JUDGE"; return r
    # 1. referee - on EVERY deep E5 rooftop, not the Tier-A subset (Tier A already requires layer agreement)
    e5all = deep[deep.E5]
    comp = (e5all.muni_comptroller == e5all.muni_dor).mean(); e911 = (e5all.muni_e911 == e5all.muni_dor).mean()
    both = ((e5all.muni_comptroller == e5all.muni_dor) & (e5all.muni_e911 == e5all.muni_dor)).mean()
    r["referee"] = {"measured_on_all_deep_e5": int(len(e5all)), "comptroller_with_polygon_pct": round(100 * comp, 1),
                    "e911_with_polygon_pct": round(100 * e911, 1), "both_pct": round(100 * both, 1)}
    r["directions"] = {f"{k[0]} polygon vs {k[1]} file": int(v) for k, v in e5.groupby(["dor4", "sst4"]).size().sort_values(ascending=False).head(6).items()}
    # 2. geography
    bins = [250, 500, 1000, 2000, 5000, 10000, 1e12]; lab = ["250-500", "500-1000", "1000-2000", "2000-5000", "5000-10000", ">10000"]
    de = pd.cut(e5.seam, bins, labels=lab, right=False).value_counts().reindex(lab).fillna(0)
    da = pd.cut(deep.seam, bins, labels=lab, right=False).value_counts().reindex(lab).fillna(0)
    share = (100 * de / da.replace(0, 1)).round(1)
    r["geography"] = {"e5_share_pct_by_distance_ft": {str(k): float(v) for k, v in share.items()},
                      "fringe_vs_core_ratio": round(float(share.iloc[:3].mean() / max(0.1, share.iloc[-2:].mean())), 1)}
    # 3. streets
    m = deep[deep.sst4.notna()].copy(); m["street"] = m.StNam_Full.astype(str) + "|" + m.Zip_Code.astype(str); m["isE5"] = m.index.isin(e5.index)
    st = m.groupby("street").agg(n=("isE5", "size"), e5=("isE5", "sum")); st = st[st.n >= 5]; st["share"] = st.e5 / st.n
    touched = st[st.e5 > 0]; sys_n = int(touched[touched.share >= .9].e5.sum()); scat_n = int(touched[touched.share < .25].e5.sum())
    r["streets"] = {"streets_with_e5": int(len(touched)), "all_or_nothing_streets": int((touched.share >= .9).sum()),
                    "e5_on_systematic_streets_pct": round(100 * sys_n / max(1, len(e5)), 1), "e5_scattered_pct": round(100 * scat_n / max(1, len(e5)), 1)}
    # 4. labels
    x = e5[e5.sst4.str.endswith("00", na=False)]
    coh = (x.sst_city == x.muni_dor).mean() if len(x) else float("nan")
    r["labels"] = {"file_says_unincorporated": int(len(x)), "file_city_label_matches_polygon_city_pct": round(100 * coh, 1) if len(x) else None}
    # 5. commerce
    r["commerce"] = {"e5_with_business_point_pct": round(100 * e5.biz.mean(), 1), "all_deep_rooftops_pct": round(100 * deep.biz.mean(), 1)}
    # 6. match quality
    zip_blank = e5.Zip_Code.isna() | (e5.Zip_Code.astype(str).str.strip().isin(["", "nan", "None"]))
    label_vs_postal = (e5.sst_city != e5.Post_City) & (e5.Post_City != "NAN")
    r["match_quality"] = {"zip_blank_pct": round(100 * zip_blank.mean(), 1), "file_label_differs_from_postal_city_pct": round(100 * label_vs_postal.mean(), 1),
                          "top_mismatches": {f"{k[0]} (postal) vs {k[1]} (file)": int(v) for k, v in e5[label_vs_postal].groupby(["Post_City", "sst_city"]).size().sort_values(ascending=False).head(4).items()}}
    # verdict
    ok1 = both >= .90; ok3 = r["streets"]["e5_on_systematic_streets_pct"] >= 50; ok4 = (coh >= .85) if len(x) else True
    r["checks"] = {"referee": bool(ok1), "streets": bool(ok3), "labels": bool(ok4)}
    r["verdict"] = "REAL - the State's address file is the odd one out" if (ok1 and ok3 and ok4) else \
                   "MIXED - inspect before quoting" if (ok1 and (ok3 or ok4)) else "SUSPECT - likely a matching artifact"
    return r


def show(r: dict):
    print(f"\n{r['county'].upper()}: {r['tierA_e5']:,} Tier-A E5 rooftops of {r['rooftops']:,} ({r['tierA_e5_pct']}%)  ->  {r['verdict']}")
    if "referee" not in r: return
    R = r["referee"]; print(f"  1 referee   on all {R['measured_on_all_deep_e5']:,} deep E5: Comptroller sides with polygon {R['comptroller_with_polygon_pct']}% · 911 {R['e911_with_polygon_pct']}% · both {R['both_pct']}%")
    print("             directions:", ", ".join(f"{k} = {v:,}" for k, v in r["directions"].items()))
    G = r["geography"]; print(f"  2 geography E5 share by ft from seam: " + "  ".join(f"{k} {v}%" for k, v in G["e5_share_pct_by_distance_ft"].items()) + f"   fringe/core x{G['fringe_vs_core_ratio']}")
    S = r["streets"]; print(f"  3 streets   {S['all_or_nothing_streets']} of {S['streets_with_e5']} affected streets are >=90% E5; {S['e5_on_systematic_streets_pct']}% of E5 rooftops sit on them, {S['e5_scattered_pct']}% scattered")
    L = r["labels"]; print(f"  4 labels    file says unincorporated on {L['file_says_unincorporated']:,}; its own city label names the polygon's city {L['file_city_label_matches_polygon_city_pct']}%")
    C = r["commerce"]; print(f"  5 commerce  business point on {C['e5_with_business_point_pct']}% of E5 rooftops vs {C['all_deep_rooftops_pct']}% overall")
    M = r["match_quality"]; print(f"  6 match     ZIP blank on {M['zip_blank_pct']}% (ZIP-less fallback); file label differs from rooftop's postal city on {M['file_label_differs_from_postal_city_pct']}%")
    if M["top_mismatches"]: print("             worst pairs:", "; ".join(f"{k} = {v:,}" for k, v in M["top_mismatches"].items()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("county", nargs="?"); ap.add_argument("--all", action="store_true"); a = ap.parse_args()
    slugs = config.all_counties() if a.all else [a.county.lower()]
    rows = []
    for c in slugs:
        r = verify(c)
        if r is None: continue
        (OUTD / c / "e5_verification.json").write_text(json.dumps(r, indent=1)); rows.append(r); show(r)
    if a.all and rows:
        print("\n" + "-" * 78)
        for r in sorted(rows, key=lambda r: -r["tierA_e5"])[:20]:
            print(f"  {r['county']:<12} {r['tierA_e5']:>7,} ({r['tierA_e5_pct']:>5}%)  {r.get('referee', {}).get('both_pct', '—'):>6}  {r.get('streets', {}).get('e5_on_systematic_streets_pct', '—'):>6}  {r.get('labels', {}).get('file_city_label_matches_polygon_city_pct', '—'):>6}  {r.get('match_quality', {}).get('file_label_differs_from_postal_city_pct', '—'):>6}  {r['verdict']}")
        print("  columns: Tier-A E5 · referee both% · systematic-street% · label-coherence% · label≠postal% · verdict")


if __name__ == "__main__":
    main()
