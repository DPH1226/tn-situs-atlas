#!/usr/bin/env python3
"""
Join the public business universe to the scored rooftop surface and emit a
compact payload for the client-facing demo.

Every business point here is rooftop-placed by the Wilson County 911 district,
so there is no geocoding step and no street-interpolation error -- the failure
mode that puts a business on the wrong side of a city line.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import geopandas as gpd, pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from engine.situs_core import load_layer, TN_STATE_PLANE
from engine.boundary_qa import build_seams, assign_situs, distance_to_seams

ROOT = Path(__file__).parent
RAW, OUT, DER = ROOT/"data/raw", ROOT/"out", ROOT/"data/derived"

dor, _ = load_layer(RAW/"dor_tax_rate_boundaries_wilson_region.geojson", layer="dor",
                    role="auth", custodian="TN DOR", source_url="")
biz, _ = load_layer(RAW/"wilson_business_points.geojson", layer="biz", role="universe",
                    custodian="Wilson County ECD", source_url="")
pts, _ = load_layer(RAW/"wilson_ng911_address_points.geojson", layer="pts", role="rooftop",
                    custodian="TN ECB", source_url="")
seams = build_seams(dor, "WILSON")

# The rooftop layer only needs its postal/municipal attributes here; the full
# scoring already happened in run_wilson.py and is not re-derived.
pts = pts[["Post_City", "Inc_Muni", "Add_Number", "StNam_Full", "Zip_Code", "geometry"]].copy()

biz = assign_situs(biz, dor)
biz = biz[biz["dor_county"]=="WILSON"].copy()
biz = biz.join(distance_to_seams(biz, seams))

# Nearest rooftop address to each business point: inherits the postal city,
# which is the attribute that drives miscoding.
near = gpd.sjoin_nearest(
    biz[["BUSINESS_NAME","dor_situs","dor_city","nearest_seam_ft","seam_side_a",
         "seam_side_b","risk_band","geometry"]],
    pts[["Post_City","Inc_Muni","Add_Number","StNam_Full","Zip_Code","geometry"]],
    how="left", distance_col="addr_match_ft", max_distance=500)
near = near[~near.index.duplicated(keep="first")].copy()

USPS_HOME = {"HERMITAGE":"DAVIDSON","OLD HICKORY":"DAVIDSON","ANTIOCH":"DAVIDSON",
             "MADISON":"DAVIDSON","DONELSON":"DAVIDSON","NASHVILLE":"DAVIDSON",
             "MILTON":"RUTHERFORD","LASCASSAS":"RUTHERFORD","MURFREESBORO":"RUTHERFORD",
             "ALEXANDRIA":"DEKALB","LIBERTY":"DEKALB","AUBURNTOWN":"CANNON",
             "GLADEVILLE":"WILSON","NORENE":"WILSON"}
def n(v):
    return "" if pd.isna(v) else str(v).strip().upper().replace(".","").replace("MOUNT ","MT ")
near["post_city"] = near["Post_City"].apply(n)
near["postal_county"] = near["post_city"].map(USPS_HOME)
near["cross_county_postal"] = near["postal_county"].notna() & (near["postal_county"]!="WILSON")
near["city_postal_mismatch"] = (
    near["post_city"].isin({"LEBANON","MT JULIET","WATERTOWN"})
    & (near["post_city"] != near["dor_city"].apply(n)))

near["flag"] = ""
near.loc[near["risk_band"].isin(["CRITICAL","HIGH"]), "flag"] = "BOUNDARY_RISK"
near.loc[near["city_postal_mismatch"], "flag"] = "POSTAL_CITY_EXPOSURE"
near.loc[near["cross_county_postal"], "flag"] = "CROSS_COUNTY_POSTAL"

g = near.to_crs("EPSG:4326")
g["lon"], g["lat"] = g.geometry.x, g.geometry.y
cols = ["BUSINESS_NAME","Add_Number","StNam_Full","Zip_Code","post_city","Inc_Muni",
        "dor_situs","dor_city","postal_county","nearest_seam_ft","seam_side_a",
        "seam_side_b","risk_band","flag","addr_match_ft","lon","lat"]
out = pd.DataFrame(g[cols]).rename(columns={"BUSINESS_NAME":"business","Add_Number":"house_no",
        "StNam_Full":"street","Zip_Code":"zip","Inc_Muni":"e911_muni"})
out.to_csv(OUT/"wilson_business_exceptions.csv", index=False)

summary = {
    "businesses_placed": int(len(out)),
    "flags": {str(k): int(v) for k, v in out["flag"].value_counts().items() if k},
    "unflagged": int((out["flag"]=="").sum()),
    "cross_county_postal_by_city": {
        str(k): int(v) for k, v in
        out.loc[out.flag=="CROSS_COUNTY_POSTAL","post_city"].value_counts().items()},
    "boundary_risk_by_band": {
        str(k): int(v) for k, v in
        out.loc[out.flag=="BOUNDARY_RISK","risk_band"].value_counts().items()},
    "situs_distribution": {str(k): int(v) for k, v in out["dor_situs"].value_counts().items()},
}
(OUT/"business_exception_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
