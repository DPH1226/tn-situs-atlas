#!/usr/bin/env python3
"""Payload for the Situs Workbench: every business with its full evidence record,
the boundary-band rooftops, and display geometry tight enough to survive zoom."""
import json, sys
from pathlib import Path
import geopandas as gpd, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from engine.situs_core import load_layer, TN_STATE_PLANE
from engine.boundary_qa import build_seams, assign_situs, distance_to_seams

ROOT = Path(__file__).parent; RAW, OUT, DER = ROOT/"data/raw", ROOT/"out", ROOT/"data/derived"
dor,_ = load_layer(RAW/"dor_tax_rate_boundaries_wilson_region.geojson", layer="d", role="a", custodian="TN DOR", source_url="")
biz,_ = load_layer(RAW/"wilson_business_points.geojson", layer="b", role="u", custodian="ECD", source_url="")
annex,_ = load_layer(RAW/"mtjuliet_annexations.geojson", layer="x", role="x", custodian="MJ", source_url="")
seams = build_seams(dor, "WILSON")

def geo(gdf, cols, tol):
    g = gdf.copy(); g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
    g = g.to_crs("EPSG:4326")
    j = json.loads(g[cols+["geometry"]].to_json())
    # trim coordinate precision: 6 dp ≈ 4 inches
    def rnd(a):
        return [rnd(x) for x in a] if isinstance(a, list) and a and isinstance(a[0], (list,)) else \
               [round(v, 6) for v in a] if isinstance(a, list) else a
    for f in j["features"]:
        gm = f["geometry"]
        if gm.get("type") == "GeometryCollection":
            for sg in gm["geometries"]: sg["coordinates"] = rnd(sg["coordinates"])
        else: gm["coordinates"] = rnd(gm["coordinates"])
    return j

wil = dor[dor.COUNTY=="WILSON"].copy()
nbr = dor[dor.COUNTY!="WILSON"].dissolve(by="COUNTY").reset_index()
P = {
  "wilson_situs": geo(wil, ["SITUS","CITY"], 20),
  "neighbors": geo(nbr, ["COUNTY"], 150),
  "seams": geo(seams, ["side_a","side_b","seam_type"], 15),
  # Annex_Num is the ordinance number, e.g. "1979-26": the year is the first four
  # characters, which is the effective-date evidence the audit actually needs.
  "annexations": geo(annex[annex.geometry.notna()], ["Annex_Num"], 20),
}

# scored rooftops
sc = pd.read_csv(DER/"wilson_address_points_scored.csv", low_memory=False)
scg = gpd.GeoDataFrame(sc, geometry=gpd.points_from_xy(sc.lon, sc.lat), crs="EPSG:4326").to_crs(TN_STATE_PLANE)

# businesses -> DOR polygon, seams, nearest scored rooftop
biz = assign_situs(biz, dor); biz = biz[biz.dor_county=="WILSON"].copy()
biz = biz.join(distance_to_seams(biz, seams))
keep = ["Add_Number","StNam_Full","Unit","Zip_Code","Post_City","Inc_Muni","Census_Plc","Placement","Parcel_ID",
        "sst_situs","sst_city","comp_city","in_mtjuliet_annexation","layers_agree","disagreement",
        "primary_class","evidence_score","evidence_notes","disposition","dor_situs"]
near = gpd.sjoin_nearest(biz[["OBJECTID","BUSINESS_NAME","dor_situs","dor_city","nearest_seam_ft","seam_side_a","seam_side_b","risk_band","geometry"]],
                         scg[keep+["geometry"]].rename(columns={"dor_situs":"addr_dor_situs"}),
                         how="left", distance_col="addr_match_ft", max_distance=500)
near = near[~near.index.duplicated(keep="first")].copy()
USPS = {"HERMITAGE":"DAVIDSON","OLD HICKORY":"DAVIDSON","ANTIOCH":"DAVIDSON","MADISON":"DAVIDSON","DONELSON":"DAVIDSON","NASHVILLE":"DAVIDSON",
        "MILTON":"RUTHERFORD","LASCASSAS":"RUTHERFORD","MURFREESBORO":"RUTHERFORD","ALEXANDRIA":"DEKALB","LIBERTY":"DEKALB","AUBURNTOWN":"CANNON",
        "GLADEVILLE":"WILSON","NORENE":"WILSON"}
n = lambda v: "" if pd.isna(v) else str(v).strip().upper().replace(".","").replace("MOUNT ","MT ")
near["post_city"] = near.Post_City.apply(n); near["postal_county"] = near.post_city.map(USPS)
near["flag"] = ""
near.loc[near.risk_band.isin(["CRITICAL","HIGH"]), "flag"] = "BOUNDARY_RISK"
near.loc[near.post_city.isin({"LEBANON","MT JULIET","WATERTOWN"}) & (near.post_city != near.dor_city.apply(n)), "flag"] = "POSTAL_CITY_EXPOSURE"
near.loc[near.postal_county.notna() & (near.postal_county!="WILSON"), "flag"] = "CROSS_COUNTY_POSTAL"
g = near.to_crs("EPSG:4326"); g["lon"]=g.geometry.x.round(6); g["lat"]=g.geometry.y.round(6)

def cv(v, d=None):
    if v is None or (isinstance(v,float) and pd.isna(v)): return None
    if isinstance(v,(bool,)): return bool(v)
    if hasattr(v,"item"): v = v.item()
    if isinstance(v,float): return round(v, d) if d is not None else round(v,1)
    return v
F = ["id","business","house_no","street","unit","zip","post_city","e911_muni","census_place","placement","parcel_id",
     "dor_situs","dor_city","sst_situs","sst_city","comp_city","in_annexation","layers_agree","disagreement",
     "seam_ft","seam_a","seam_b","risk_band","score","score_notes","disposition","flag","postal_county","addr_match_ft","lon","lat"]
rows = []
for r in g.itertuples():
    rows.append([cv(r.OBJECTID), cv(r.BUSINESS_NAME), cv(r.Add_Number), cv(r.StNam_Full), cv(r.Unit) or None, cv(r.Zip_Code), cv(r.post_city) or None,
        cv(r.Inc_Muni), cv(r.Census_Plc), cv(r.Placement), cv(r.Parcel_ID), cv(r.dor_situs), cv(r.dor_city), cv(r.sst_situs), cv(r.sst_city),
        cv(r.comp_city), cv(r.in_mtjuliet_annexation), cv(r.layers_agree), cv(r.disagreement) or None, cv(r.nearest_seam_ft), cv(r.seam_side_a),
        cv(r.seam_side_b), cv(r.risk_band), cv(r.evidence_score), cv(r.evidence_notes), cv(r.disposition), cv(r.flag) or None, cv(r.postal_county),
        cv(r.addr_match_ft), cv(r.lon,6), cv(r.lat,6)])
P["biz_fields"] = F; P["biz"] = rows

# boundary-band rooftops, compact
bb = sc[sc.risk_band.isin(["CRITICAL","HIGH"])]
P["band_pts"] = [[round(float(a),6), round(float(b),6), 0 if c=="CRITICAL" else 1] for a,b,c in zip(bb.lon, bb.lat, bb.risk_band)]
# Roads: NG911 centerlines, class from CFCC (A1 interstate, A2 US, A3 state, A4 local).
# Simplified for display; not used in any measurement.
roads,_ = load_layer(RAW/"wilson_ng911_roads.geojson", layer="r", role="ctx", custodian="TN ECB", source_url="")
roads = roads[roads.geometry.notna()].copy()
roads["cls"] = roads["CFCC"].astype(str).str[:2].map({"A1":1,"A2":2,"A3":3}).fillna(4).astype(int)
rj = geo(roads, ["LABEL","cls"], 30)
P["roads"] = rj
P["summary"] = json.loads((OUT/"boundary_qa_summary.json").read_text())
P["flag_counts"] = {k:int(v) for k,v in g["flag"].value_counts().items() if k}
P["flag_counts"]["CLEAR"] = int((g["flag"]=="").sum())
out = ROOT/"artifact/wbdata.js"; out.write_text("window.WB=" + json.dumps(P, separators=(",",":")) + ";")
print("biz", len(rows), "| band pts", len(P["band_pts"]), "| annex", len(P["annexations"]["features"]), "| roads", len(P["roads"]["features"]), "| MB", round(out.stat().st_size/1e6,2))
print("flags", P["flag_counts"])
