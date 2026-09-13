#!/usr/bin/env python3
"""
Wilson County situs audit - boundary QA and public-data exception pass.

Run order is deliberate and is the opposite of the obvious one:
    geography first, taxpayers second.
We prove the boundary surface is sound BEFORE anyone claims a business is
miscoded. No confidential DOR data is required or used anywhere in this file.
"""
from __future__ import annotations

import json, sys, time
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from engine.situs_core import TN_STATE_PLANE, load_layer, write_manifest, band_for
from engine.boundary_qa import assign_situs, distance_to_seams, layer_agreement, build_seams
from engine import exceptions as EX

ROOT = Path(__file__).parent
RAW, DER, OUT = ROOT / "data/raw", ROOT / "data/derived", ROOT / "out"
for d in (DER, OUT):
    d.mkdir(parents=True, exist_ok=True)
COUNTY = "WILSON"
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

# ---------------------------------------------------------------- 1. ingest
log("Loading layers (reproject -> TN State Plane ftUS, validate geometry)")
sources = []

dor, r = load_layer(
    RAW / "dor_tax_rate_boundaries_wilson_region.geojson",
    layer="TN DOR Sales Tax Rate Boundaries (Wilson + neighbours)",
    role="AUTHORITATIVE tax boundary (tier 1)", custodian="Tennessee Department of Revenue",
    source_url="https://tnmap.tn.gov/arcgis/rest/services/COMMUNITY/REVENUE_TAX_RATE_BOUNDARIES/MapServer/0",
    cadence="Quarterly",
    notes="What DOR actually bills against. Ground truth for sales-tax situs.")
sources.append(r)

cities, r = load_layer(
    RAW / "tn_sst_city_boundaries.geojson",
    layer="TN municipal boundaries (all 345 cities)",
    role="reference boundary (tier 3)", custodian="TN Comptroller, Office of Local Government",
    source_url="https://tnmap.tn.gov/arcgis/rest/services/COMMUNITY/SST/MapServer/2",
    cadence="Monthly aggregation from local assessors",
    notes="Use THIS, not ADMINISTRATIVE_BOUNDARIES/0 - that layer's own metadata "
          "dates it to June 2017 and would miss every annexation since.")
sources.append(r)

pts, r = load_layer(
    RAW / "wilson_ng911_address_points.geojson",
    layer="TN NG911 Address Points (Wilson)",
    role="rooftop location evidence (tier 4)", custodian="TN Emergency Communications Board",
    source_url="https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services/Tennessee_NG911_Address_Points/FeatureServer/0",
    cadence="Monthly",
    notes="Carries Inc_Muni, Post_City and Census_Plc on the same record - the "
          "three-way distinction the whole audit turns on.")
sources.append(r)

biz, r = load_layer(
    RAW / "wilson_business_points.geojson",
    layer="Wilson County E-911 business points",
    role="public business universe", custodian="Wilson County Emergency Communications District",
    source_url="https://services1.arcgis.com/ai5RqMP3xEKGv0of/arcgis/rest/services/Business_Labels/FeatureServer/53",
    cadence="Continuous",
    notes="Rooftop-placed, so no geocoding step and no interpolation error. "
          "Name + geometry only; no address, NAICS or licence linkage.")
sources.append(r)

annex, r = load_layer(
    RAW / "mtjuliet_annexations.geojson",
    layer="Mt. Juliet annexations",
    role="annexation history", custodian="City of Mt. Juliet",
    source_url="https://utility.arcgis.com/usrsvcs/servers/5e2f5bfd27984da89b2e45a726d0e37b/rest/services/Planning___Zoning/FeatureServer/0",
    notes="Dates the boundary changes that move situs. Nothing at state or "
          "federal level captures this.")
sources.append(r)

sst_rows = json.loads((RAW / "sst_address_lookup_wilson.json").read_text())
log(f"  DOR polygons {len(dor)} | cities {len(cities)} | address pts {len(pts):,} "
    f"| business pts {len(biz):,} | annexations {len(annex)} | SST ranges {len(sst_rows):,}")

# ------------------------------------------------- 2. jurisdictional seams
log("Building jurisdictional seams (both sides named)")
seams = build_seams(dor, COUNTY)
wilson_dor = dor[dor["COUNTY"] == COUNTY].copy()
log(f"  {len(seams)} seams touching Wilson "
    f"({(seams.seam_type=='CROSS_COUNTY').sum()} cross-county, "
    f"{(seams.seam_type=='INTRA_COUNTY').sum()} intra-county); "
    f"{seams.seam_len_ft.sum()/5280:,.1f} linear miles")

# ----------------------------------------------------- 3. place the points
log("Placing address points in the authoritative DOR polygon")
pts = assign_situs(pts, dor)
unplaced = int(pts["dor_situs"].isna().sum())
pts = pts[pts["dor_county"] == COUNTY].copy()
log(f"  {len(pts):,} points inside Wilson DOR polygons; {unplaced:,} matched no polygon at all")

log("Distance to nearest jurisdictional seam")
pts = pts.join(distance_to_seams(pts, seams))

log("Comptroller certified municipal boundary")
cj = gpd.sjoin(pts[["geometry"]], cities[["NAME", "geometry"]], how="left", predicate="within")
cj = cj[~cj.index.duplicated(keep="first")]
# A null here is not a missing value. It means the rooftop falls outside every
# certified municipal polygon in Tennessee, which is an affirmative statement
# that the location is unincorporated.
pts["comp_city"] = cj["NAME"].fillna("Unincorporated")

log("Mt. Juliet annexation footprint")
aj = gpd.sjoin(pts[["geometry"]], annex[["geometry"]], how="left", predicate="within")
pts["in_mtjuliet_annexation"] = ~aj[~aj.index.duplicated(keep="first")]["index_right"].isna()

log("Official-layer agreement")
pts = pts.join(layer_agreement(pts))

# ------------------------------- 4. DOR's own address-range table vs polygon
log("Joining DOR's SST address-range table to rooftops")
idx = EX.build_sst_index(sst_rows)
sst_situs, sst_city = [], []
for num, nm, sfx, z in zip(pts["Add_Number"], pts["St_Name"], pts["St_PosTyp"], pts["Zip_Code"]):
    m = EX.sst_situs_for(idx, nm, sfx, z, num)
    sst_situs.append(m["situs"] if m else None)
    sst_city.append(m["city"] if m else None)
pts["sst_situs"], pts["sst_city"] = sst_situs, sst_city
matched = pts["sst_situs"].notna().sum()
log(f"  {matched:,} of {len(pts):,} rooftops matched a DOR address range ({matched/len(pts)*100:.1f}%)")

# ------------------------------------------------------ 5. classify exceptions
log("Classifying exceptions")
WILSON_MUNIS = {"LEBANON", "MT JULIET", "MOUNT JULIET", "WATERTOWN"}

def norm_city(v):
    if pd.isna(v): return ""
    return str(v).strip().upper().replace(".", "").replace("MOUNT ", "MT ")

pts["post_city_n"] = pts["Post_City"].apply(norm_city)
pts["inc_muni_n"] = pts["Inc_Muni"].apply(norm_city)
pts["dor_city_n"] = pts["dor_city"].apply(norm_city)
pts["postal_home_county"] = pts["post_city_n"].map(EX.USPS_ONLY_PLACES)

flags = {}
flags["E2_CROSS_COUNTY_POSTAL"] = (
    pts["postal_home_county"].notna() & (pts["postal_home_county"] != COUNTY))
_e5 = (pts["sst_situs"].notna() & pts["dor_situs"].notna()
       & (pts["sst_situs"] != pts["dor_situs"]))
# A conflict within 250 ft of a seam might be nothing more than where the line
# was drawn. A conflict a quarter-mile inside a polygon cannot be. Only the
# second kind is worth putting in front of a Finance Director unqualified.
_deep = pts["nearest_seam_ft"].fillna(0) >= 250
flags["E5_DOR_INTERNAL_CONFLICT"] = _e5 & _deep
flags["E5B_DOR_CONFLICT_AT_BOUNDARY"] = _e5 & ~_deep
flags["E1_POSTAL_CITY_OVERSTATES"] = (
    pts["post_city_n"].isin(WILSON_MUNIS) & (pts["post_city_n"] != pts["dor_city_n"])
    & ~flags["E2_CROSS_COUNTY_POSTAL"])
flags["E6_ANNEXATION_LAG"] = (
    pts["in_mtjuliet_annexation"] & (pts["dor_city_n"] != "MT JULIET"))
flags["E4_LAYER_DISAGREEMENT"] = ~pts["layers_agree"]
flags["E3_BOUNDARY_PROXIMITY"] = pts["risk_band"].isin(["CRITICAL", "HIGH"])

for k, v in flags.items():
    pts[k] = v.fillna(False)

order = ["E5_DOR_INTERNAL_CONFLICT", "E2_CROSS_COUNTY_POSTAL", "E6_ANNEXATION_LAG",
         "E4_LAYER_DISAGREEMENT", "E5B_DOR_CONFLICT_AT_BOUNDARY",
         "E3_BOUNDARY_PROXIMITY", "E1_POSTAL_CITY_OVERSTATES"]
pts["primary_class"] = ""
for k in order:  # most costly class wins
    pts.loc[pts[k] & (pts["primary_class"] == ""), "primary_class"] = k

log("Scoring evidence")
sc = pts.apply(EX.score_evidence, axis=1)
pts["evidence_score"] = [x[0] for x in sc]
pts["evidence_notes"] = [x[1] for x in sc]
pts["disposition"] = [
    EX.disposition(s, a, b)
    for s, a, b in zip(pts["evidence_score"], pts["layers_agree"], pts["risk_band"])
]

# --------------------------------------------------------------- 6. business
log("Placing the public business universe")
biz = assign_situs(biz, dor)
biz = biz.join(distance_to_seams(biz, seams))
bj = gpd.sjoin(biz[["geometry"]], cities[["NAME", "geometry"]], how="left", predicate="within")
biz["comp_city"] = bj[~bj.index.duplicated(keep="first")]["NAME"].fillna("Unincorporated")
biz_w = biz[biz["dor_county"] == COUNTY].copy()

# ------------------------------------------------------------------ 7. write
log("Writing outputs")
pts_out = pts.to_crs("EPSG:4326")
pts_out["lon"] = pts_out.geometry.x
pts_out["lat"] = pts_out.geometry.y
cols = ["Add_Number", "StNam_Full", "Unit", "Zip_Code", "Post_City", "Inc_Muni",
        "Census_Plc", "Uninc_Comm", "Placement", "Parcel_ID", "Lifecycle",
        "dor_situs", "dor_city", "dor_county", "dor_rate", "sst_situs", "sst_city",
        "comp_city", "in_mtjuliet_annexation", "nearest_seam_ft", "seam_side_a",
        "seam_side_b", "risk_band", "risk_action", "layers_agree", "disagreement",
        "primary_class", "evidence_score", "evidence_notes", "disposition", "lon", "lat"]
cols = [c for c in cols if c in pts_out.columns]
pd.DataFrame(pts_out[cols]).to_csv(DER / "wilson_address_points_scored.csv", index=False)

exc = pts_out[pts_out["primary_class"] != ""].copy()
pd.DataFrame(exc[cols]).sort_values(
    ["primary_class", "evidence_score"], ascending=[True, False]
).to_csv(OUT / "wilson_exceptions.csv", index=False)

bz = biz_w.to_crs("EPSG:4326")
bz["lon"], bz["lat"] = bz.geometry.x, bz.geometry.y
pd.DataFrame(bz[["BUSINESS_NAME", "dor_situs", "dor_city", "comp_city",
                 "nearest_seam_ft", "risk_band", "lon", "lat"]]).to_csv(
    OUT / "wilson_business_situs.csv", index=False)

write_manifest(sources, OUT / "source_manifest.json")

summary = {
    "county": COUNTY,
    "generated_utc": pd.Timestamp.now("UTC").isoformat(),
    "crs_for_distance": TN_STATE_PLANE,
    "confidential_dor_data_used": False,
    "totals": {
        "address_points_in_wilson": int(len(pts)),
        "address_points_matching_no_dor_polygon": unplaced,
        "sst_range_match_rate_pct": round(float(matched) / len(pts) * 100, 1),
        "business_points_in_wilson": int(len(biz_w)),
        "seams_touching_wilson": int(len(seams)),
        "seam_miles": round(float(seams.seam_len_ft.sum()) / 5280, 1),
        "cross_county_seam_miles": round(
            float(seams.loc[seams.seam_type == "CROSS_COUNTY", "seam_len_ft"].sum()) / 5280, 1),
    },
    "situs_distribution": {
        str(k): int(v) for k, v in pts["dor_situs"].value_counts().items()},
    "risk_bands": {str(k): int(v) for k, v in pts["risk_band"].value_counts().items()},
    "exceptions": {
        k: {"count": int(pts[k].sum()), **{kk: vv for kk, vv in EX.CLASSES[k].items()}}
        for k in order},
    "primary_class_counts": {
        str(k): int(v) for k, v in pts["primary_class"].value_counts().items() if k},
    "dispositions": {str(k): int(v) for k, v in pts["disposition"].value_counts().items()},
    "postal_city_profile": {
        str(k): int(v) for k, v in pts["post_city_n"].value_counts().head(20).items()},
    "business_risk_bands": {
        str(k): int(v) for k, v in biz_w["risk_band"].value_counts().items()},
    "dor_conflict_direction": {
        f"polygon {a} -> address-file {b}": int(n)
        for (a, b), n in pts[_e5].groupby(["dor_situs", "sst_situs"]).size()
                            .sort_values(ascending=False).items()},
    "e5_deep_vs_boundary": {
        "deep_conflict_over_250ft": int((_e5 & _deep).sum()),
        "conflict_within_250ft_of_seam": int((_e5 & ~_deep).sum()),
    },
    "layer_disagreement_detail": {
        str(k): int(v) for k, v in
        pts.loc[~pts["layers_agree"], "disagreement"].value_counts().head(15).items()},
}
(OUT / "boundary_qa_summary.json").write_text(json.dumps(summary, indent=2))
log("Done. -> out/boundary_qa_summary.json, out/wilson_exceptions.csv, "
    "out/wilson_business_situs.csv, out/source_manifest.json")
print(json.dumps(summary["totals"], indent=2))
