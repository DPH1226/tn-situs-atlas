#!/usr/bin/env python3
"""
Is a county's Tier-A "DOR file ≠ polygon" signal real, or a matching artifact?

    python3 tools/verify_e5.py wilson            # one county
    python3 tools/verify_e5.py --all             # every county with out/<slug>/address_points_scored.csv

The E5 class says: the State's address-range file assigns situs X, the State's own polygon says Y.
That is a disagreement by construction. What matters is whether the FILE is the thing that is wrong,
or whether our match to the file is. Five tests separate those:

  1. Referee.  For each disagreeing rooftop, where do the two other authorities put it - the 911
     addressing authority and the Comptroller's certified municipal limits?  If both side with the
     polygon, the file is the odd one out: three independent sources against one.
  2. Geography.  A stale file is stale where boundaries moved - the annexation fringe.  Matching
     noise scatters evenly.  The E5 share should fall with distance from the nearest seam.
  3. Streets.  A stale range table mis-codes whole street segments.  A bad match hits rooftops at
     random.  Streets with any E5 should be mostly all-or-nothing.
  4. Labels.  If the file's own city label names the polygon's city while its code says unincorporated,
     the record is internally coherent - it describes the address as it was before annexation - and
     the match is to the right street.  Random labels would mean a wrong-street match.
  5. Commerce.  If the disagreement follows annexed commercial corridors, E5 rooftops should carry
     business points at least as often as rooftops in general.

A county passes when (1) >= 90% referee agreement with the polygon, (3) >= 50% of E5 rooftops sit on
streets that are >= 90% E5, and (4) >= 85% label coherence.  Verdicts are printed with the numbers so
the reasoning is inspectable, and written to out/<slug>/e5_verification.json.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from fetch import config

OUTD = ROOT / "out"
COLS = ["dor_situs", "sst_situs", "sst_city", "muni_dor", "muni_e911", "muni_comptroller", "risk_band", "nearest_seam_ft",
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
    for c in ("muni_dor", "muni_e911", "muni_comptroller", "sst_city"): a[c] = norm(a[c])
    a["E5"] = a.E5_DOR_INTERNAL_CONFLICT.fillna(False).astype(bool)
    a["biz"] = a.biz_within_100ft.fillna(False).astype(bool)
    a["seam"] = pd.to_numeric(a.nearest_seam_ft, errors="coerce").fillna(0)
    deep = a[(a.seam >= 250)]
    e5 = deep[deep.E5 & (deep.evidence_score >= 85) & (deep.risk_band != "CRITICAL")].copy()
    r = {"county": slug, "rooftops": int(len(a)), "tierA_e5": int(len(e5)), "tierA_e5_pct": round(100 * len(e5) / max(1, len(a)), 2)}
    if len(e5) < 20:
        r["verdict"] = "TOO FEW TO JUDGE"; return r
    # 1. referee
    comp = (e5.muni_comptroller == e5.muni_dor).mean(); e911 = (e5.muni_e911 == e5.muni_dor).mean()
    both = ((e5.muni_comptroller == e5.muni_dor) & (e5.muni_e911 == e5.muni_dor)).mean()
    r["referee"] = {"comptroller_with_polygon_pct": round(100 * comp, 1), "e911_with_polygon_pct": round(100 * e911, 1), "both_pct": round(100 * both, 1)}
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
    # verdict
    ok1 = both >= .90; ok3 = r["streets"]["e5_on_systematic_streets_pct"] >= 50; ok4 = (coh >= .85) if len(x) else True
    r["checks"] = {"referee": bool(ok1), "streets": bool(ok3), "labels": bool(ok4)}
    r["verdict"] = "REAL - the State's address file is the odd one out" if (ok1 and ok3 and ok4) else \
                   "MIXED - inspect before quoting" if (ok1 and (ok3 or ok4)) else "SUSPECT - likely a matching artifact"
    return r


def show(r: dict):
    print(f"\n{r['county'].upper()}: {r['tierA_e5']:,} Tier-A E5 rooftops of {r['rooftops']:,} ({r['tierA_e5_pct']}%)  ->  {r['verdict']}")
    if "referee" not in r: return
    R = r["referee"]; print(f"  1 referee   Comptroller sides with polygon {R['comptroller_with_polygon_pct']}% · 911 {R['e911_with_polygon_pct']}% · both {R['both_pct']}%")
    print("             directions:", ", ".join(f"{k} = {v:,}" for k, v in r["directions"].items()))
    G = r["geography"]; print(f"  2 geography E5 share by ft from seam: " + "  ".join(f"{k} {v}%" for k, v in G["e5_share_pct_by_distance_ft"].items()) + f"   fringe/core x{G['fringe_vs_core_ratio']}")
    S = r["streets"]; print(f"  3 streets   {S['all_or_nothing_streets']} of {S['streets_with_e5']} affected streets are >=90% E5; {S['e5_on_systematic_streets_pct']}% of E5 rooftops sit on them, {S['e5_scattered_pct']}% scattered")
    L = r["labels"]; print(f"  4 labels    file says unincorporated on {L['file_says_unincorporated']:,}; its own city label names the polygon's city {L['file_city_label_matches_polygon_city_pct']}%")
    C = r["commerce"]; print(f"  5 commerce  business point on {C['e5_with_business_point_pct']}% of E5 rooftops vs {C['all_deep_rooftops_pct']}% overall")


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
            print(f"  {r['county']:<12} {r['tierA_e5']:>7,} ({r['tierA_e5_pct']:>5}%)  {r.get('referee', {}).get('both_pct', '—'):>6}  {r.get('streets', {}).get('e5_on_systematic_streets_pct', '—'):>6}  {r['verdict']}")
        print("  columns: Tier-A E5 · referee both% · systematic-street% · verdict")


if __name__ == "__main__":
    main()
