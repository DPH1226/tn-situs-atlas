#!/usr/bin/env python3
"""
Bulletin: what changed since the last run for a county.

Compares the current out/<slug>/summary.json + business_exceptions.csv with the
previous archived run and writes out/<slug>/bulletins/<date>.md. The first run
archives itself and writes a baseline bulletin. This is the monthly deliverable
that makes the service a subscription rather than a project: situs is a diff
problem over time, and only a diff catches errors inside the one-year window.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from datetime import date
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from warehouse.store import Warehouse


def bulletin(county: str) -> Path:
    slug = county.lower(); OUT = ROOT / "out" / slug; ARCH = OUT / "runs"; ARCH.mkdir(exist_ok=True)
    today = date.today().isoformat()
    cur = json.loads((OUT / "summary.json").read_text())
    bz = OUT / "business_exceptions.csv"
    curb = pd.read_csv(bz, low_memory=False) if bz.exists() else pd.DataFrame()
    prev_dirs = sorted(d for d in ARCH.iterdir() if d.is_dir() and d.name < today)
    prev = json.loads((prev_dirs[-1] / "summary.json").read_text()) if prev_dirs else None
    prevb = pd.read_csv(prev_dirs[-1] / "business_exceptions.csv", low_memory=False) if prev_dirs and (prev_dirs[-1] / "business_exceptions.csv").exists() else pd.DataFrame()

    L = [f"# Situs bulletin — {cur['county'].title()} County — {today}", ""]
    src = ", ".join(f"{k} {v}" for k, v in cur.get("sources", {}).items())
    L += [f"*Sources as of: {src}. Rubric {cur.get('rubric')}. No confidential data used.*", ""]
    if prev is None:
        L += ["## Baseline", "", "First run for this county. Future bulletins report changes against this baseline.", ""]
    else:
        L += [f"## Changes since {prev_dirs[-1].name}", ""]
        for k, lab in [("address_points", "Rooftops placed"), ("seam_miles", "Seam miles"), ("business_points", "Business points")]:
            a, b = prev["totals"].get(k), cur["totals"].get(k)
            if a != b: L.append(f"- {lab}: {a:,} → {b:,}")
        for k in cur["exceptions"]:
            a, b = prev["exceptions"].get(k, 0), cur["exceptions"][k]
            if a != b: L.append(f"- {k}: {a:,} → {b:,} ({b - a:+,})")
        # boundary geometry change signal
        wh = Warehouse(); snaps = wh.snapshots("dor_tax_rate_boundaries", "TN")
        if len(snaps) >= 2:
            d = wh.diff("dor_tax_rate_boundaries", "TN", snaps.snap_date.iloc[-2], snaps.snap_date.iloc[-1], key="SITUS")
            if any(d["counts"].values()):
                L.append(f"- **DOR tax-rate polygons changed**: {d['counts']} — every seam re-measured this run.")
        if len(curb) and len(prevb) and "business" in curb and "business" in prevb:
            key = lambda df: (df.business.astype(str) + "|" + df.Add_Number.astype(str) + "|" + df.StNam_Full.astype(str))
            cf, pf = curb.assign(k=key(curb)), prevb.assign(k=key(prevb))
            cf = cf[cf.kind.eq("business")] if "kind" in cf else cf; pf = pf[pf.kind.eq("business")] if "kind" in pf else pf
            new = cf[~cf.k.isin(pf.k) & cf.flag.notna() & (cf.flag != "")]
            gone = pf[~pf.k.isin(cf.k) & pf.flag.notna() & (pf.flag != "")]
            moved = cf.merge(pf[["k", "dor_situs"]], on="k", suffixes=("", "_prev")); moved = moved[moved.dor_situs.astype(str) != moved.dor_situs_prev.astype(str)]
            L += ["", f"## Exception queue: {len(new)} new, {len(gone)} resolved/removed, {len(moved)} changed jurisdiction", ""]
            for r in new.head(25).itertuples(): L.append(f"- NEW {r.flag}: {r.business} — {r.Add_Number} {r.StNam_Full} → {r.dor_situs}")
            for r in moved.head(25).itertuples(): L.append(f"- MOVED: {r.business} — {r.dor_situs_prev} → {r.dor_situs}")
        if len(L) and L[-1].startswith("## Changes") : L.append("- No changes.")
    L += ["", "## Current state", "",
          f"- Rooftops placed: **{cur['totals']['address_points']:,}** ({cur['totals']['unplaced']} unplaced)",
          f"- Seams: {cur['totals']['seams']} — {cur['totals']['seam_miles']} mi, {cur['totals']['cross_county_seam_miles']} mi cross-county",
          f"- Business points: {cur['totals']['business_points']:,}; flags: " + ", ".join(f"{k or 'clear'} {v:,}" for k, v in cur.get("business_flags", {}).items()),
          f"- Exceptions: " + ", ".join(f"{k} {v:,}" for k, v in cur["exceptions"].items()), ""]
    if cur.get("calibration_source"):
        c = cur["calibration_source"]; L += [f"- Calibration source on file: {c['rows_with_coded_situs']:,} coded rows, {c['coded_ne_measured']} coded≠measured", ""]
    # archive this run
    dest = ARCH / today; dest.mkdir(exist_ok=True)
    for f in ("summary.json", "business_exceptions.csv"):
        if (OUT / f).exists(): shutil.copy2(OUT / f, dest / f)
    bdir = OUT / "bulletins"; bdir.mkdir(exist_ok=True); p = bdir / f"{today}.md"; p.write_text("\n".join(L))
    print(p); return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--county", required=True); bulletin(ap.parse_args().county)
