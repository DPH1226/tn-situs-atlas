#!/usr/bin/env python3
"""Compact geometry + point payload for the client demo. Simplified for the
browser, but every simplification is stated: the analysis ran on full-precision
geometry in TN State Plane, not on this."""
import json, sys
from pathlib import Path
import geopandas as gpd, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from engine.situs_core import load_layer
from engine.boundary_qa import build_seams

ROOT = Path(__file__).parent; RAW, OUT = ROOT/"data/raw", ROOT/"out"
dor, _ = load_layer(RAW/"dor_tax_rate_boundaries_wilson_region.geojson", layer="d",
                    role="a", custodian="TN DOR", source_url="")
seams = build_seams(dor, "WILSON")
TOL = 60  # feet, display only

def geo(gdf, cols, tol=TOL):
    g = gdf.copy()
    g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
    g = g.to_crs("EPSG:4326")
    return json.loads(g[cols+["geometry"]].to_json())

wil = dor[dor.COUNTY=="WILSON"].copy()
nbr = dor[dor.COUNTY!="WILSON"].dissolve(by="COUNTY").reset_index()

payload = {
    "wilson_situs": geo(wil, ["SITUS","CITY","TAXRATE"]),
    "neighbors":    geo(nbr, ["COUNTY"], tol=200),
    "seams":        geo(seams, ["side_a","side_b","seam_type"], tol=40),
}

biz = pd.read_csv(OUT/"wilson_business_exceptions.csv")

def _i(v):
    return None if pd.isna(v) else int(v)
def _s(v):
    return None if pd.isna(v) else str(v)
def _f(v, d=1):
    return None if pd.isna(v) else round(float(v), d)

def pack(df):
    return [[_s(r.business), _i(r.house_no), _s(r.street), _i(r.zip), _s(r.post_city),
             _s(r.dor_situs), _s(r.dor_city), _s(r.postal_county), _f(r.nearest_seam_ft),
             _s(r.risk_band), _s(r.flag), _f(r.lon, 6), _f(r.lat, 6)]
            for r in df.itertuples()]
flagged = biz[biz.flag.notna() & (biz.flag != "")]
payload["biz_fields"] = ["business","house_no","street","zip","post_city","situs","dor_city",
                         "postal_county","seam_ft","risk_band","flag","lon","lat"]
payload["biz_flagged"] = pack(flagged)
payload["biz_clear_sample"] = pack(biz[(biz.flag.isna())|(biz.flag=="")].sample(
    min(700, int(((biz.flag.isna())|(biz.flag=="")).sum())), random_state=7))

payload["summary"] = json.loads((OUT/"boundary_qa_summary.json").read_text())
payload["biz_summary"] = json.loads((OUT/"business_exception_summary.json").read_text())
p = OUT/"demo_payload.json"; p.write_text(json.dumps(payload, separators=(",",":")))
print("wrote", p, round(p.stat().st_size/1e6,2), "MB",
      "| flagged", len(payload["biz_flagged"]), "| clear sample", len(payload["biz_clear_sample"]))
