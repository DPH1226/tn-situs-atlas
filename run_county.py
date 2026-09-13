#!/usr/bin/env python3
"""
Generic county situs run, driven by configs/<county>.yaml and the snapshot warehouse.

    python3 run_county.py --county SUMNER

Geography first, taxpayers second. No confidential data is read here.
Outputs land in out/<slug>/ so counties never overwrite each other.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from fetch import config
from warehouse.store import Warehouse, TN_SP
from engine.boundary_qa import assign_situs, distance_to_seams, layer_agreement, build_seams
from engine import exceptions as EX

# ------------------------------------------------------------------ helpers
_SUF = {"AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "CIRCLE": "CIR", "COURT": "CT", "DRIVE": "DR", "HIGHWAY": "HWY",
        "LANE": "LN", "PARKWAY": "PKWY", "PLACE": "PL", "ROAD": "RD", "STREET": "ST", "TERRACE": "TER",
        "TRAIL": "TRL", "PIKE": "PIKE", "WAY": "WAY", "COVE": "CV", "LOOP": "LOOP", "RUN": "RUN", "PATH": "PATH",
        "SQUARE": "SQ", "PLAZA": "PLZ", "POINT": "PT", "PASS": "PASS", "CROSSING": "XING", "BEND": "BND", "ROW": "ROW",
        "ALLEY": "ALY", "CIRCLE": "CIR", "BYPASS": "BYP", "EXPRESSWAY": "EXPY", "TRACE": "TRCE", "HOLLOW": "HOLW", "MILL": "ML"}
_SUFFIXES = set(_SUF.values()) | {"AVE", "BLVD", "CIR", "CT", "DR", "HWY", "LN", "PKWY", "PL", "RD", "ST", "TER", "TRL", "PIKE",
                                  "WAY", "CV", "LOOP", "RUN", "PATH", "SQ", "PLZ", "PT", "PASS", "XING", "BND", "ROW", "ALY", "BYP",
                                  "EXPY", "TRCE", "HOLW", "ML", "BLF", "CRK", "RDG", "VLY", "HTS", "CRST", "MDW", "MNR", "ESTS", "GRV"}
_DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
_UNIT = {"STE", "SUITE", "UNIT", "APT", "#", "BLDG", "FL", "FLOOR", "RM", "SPC", "LOT", "TRLR"}
_TN_RE = re.compile(r"\s+TN\s+(\d{5})(?:-\d{4})?\s*$")


def parse_single_line(addr: str):
    """'242 W MAIN ST # 275 HENDERSONVILLE TN 37075-3318' -> (242, 'W MAIN', 'ST', '37075').
    Walks from the right: city tokens accumulate until a street suffix (optionally followed by a
    post-directional) is found. Unit designators are stripped first."""
    if not isinstance(addr, str):
        return None
    m = _TN_RE.search(addr.upper())
    if not m:
        return None
    z = m.group(1); body = addr.upper()[:m.start()].replace(",", " ")
    toks = body.split()
    # drop unit designator and everything after it
    for i, t in enumerate(toks):
        if t in _UNIT or (t.startswith("#") and i > 0):
            toks = toks[:i]; break
    if not toks or not re.match(r"^\d+[A-Z]?$", toks[0]):
        return None
    num = int(re.match(r"^(\d+)", toks[0]).group(1)); toks = toks[1:]
    # find the rightmost suffix token; allow one trailing directional
    suf_i = None
    for i in range(len(toks) - 1, 0, -1):
        t = _SUF.get(toks[i], toks[i])
        if t in _SUFFIXES:
            suf_i = i; break
    if suf_i is None:
        # no suffix (e.g. "HIGHWAY 109" style already covered; else assume last-1 is street, rest city)
        return (num, " ".join(toks[:-1]), "", z) if len(toks) >= 2 else None
    street = " ".join(toks[:suf_i]); suf = _SUF.get(toks[suf_i], toks[suf_i])
    # a post-directional right after the suffix belongs to the street ("MAIN ST E")
    return num, street, suf, z


def parse_parts(line1: str, zipcode) -> tuple | None:
    """'639 E MAIN ST STE B204', '37075-2670' -> (639, 'E MAIN', 'ST', '37075')"""
    if not isinstance(line1, str) or not line1.strip():
        return None
    m = re.match(r"^\s*(\d+)[A-Z]?\s+(.+)$", line1.upper())
    if not m:
        return None
    num, rest = int(m.group(1)), m.group(2)
    toks = rest.replace(",", " ").split()
    for i, t in enumerate(toks):
        if t in {"STE", "SUITE", "UNIT", "APT", "#", "BLDG", "FL", "FLOOR", "RM"} or t.startswith("#"):
            toks = toks[:i]; break
    if not toks:
        return None
    z = str(zipcode or "")[:5]
    if len(toks) >= 2:
        return num, " ".join(toks[:-1]), _SUF.get(toks[-1], toks[-1]), z
    return num, toks[0], "", z


def load_sos(path: Path, county: str) -> pd.DataFrame:
    """Active for-profit entities from a TN Secretary of State county extract."""
    d = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    d = d[d["Status"].str.startswith("Active") & ~d["EntityType"].str.contains("Nonprofit", case=False)]
    d = d[d["PrincipalAddressStateCode"].str.upper().eq("TN")]
    return d.rename(columns={"EntityName": "business"})[[
        "business", "ControlNumber", "EntityType", "Status", "PrincipalAddressLine1", "PrincipalAddressCity",
        "PrincipalAddressPostalCode", "PrincipalAddressCounty", "MailingAddressCity", "MailingAddressCounty"]].reset_index(drop=True)


CITY_ALIASES: dict[str, str] = {}   # set per run from config: alias -> canonical (both upper)


def norm_city(v):
    if pd.isna(v): return ""
    s = str(v).strip().upper().replace(".", "").replace("(", "").replace(")", "").replace("MOUNT ", "MT ")
    if s in {"UNINCORPORATED", "NONE", ""}: s = "UNINCORPORATED"
    return CITY_ALIASES.get(s, s)


def geocode_by_range(table: pd.DataFrame, pts: gpd.GeoDataFrame, addr_field: str, zip_field: str | None = None) -> gpd.GeoDataFrame:
    """Place table rows on NG911 rooftops by exact house number + street + zip.

    The NG911 index is built with every plausible spelling of each street
    (with/without pre- and post-directionals) so that '242 W MAIN ST' and
    'HIGHWAY 109 S' both resolve. Single-line addresses parse themselves;
    two-part addresses need zip_field."""
    def key(n, s, z): return f"{str(n).upper().strip()}|{str(s).upper().strip()}|{str(z)[:5]}"
    def clean(v): return "" if pd.isna(v) else str(v).upper().strip()
    idx: dict = {}
    for r in pts.itertuples():
        num = int(r.Add_Number) if pd.notna(r.Add_Number) else -1
        nm, pre, post, suf, z = clean(r.St_Name), clean(r.St_PreDir), clean(r.St_PosDir), clean(r.St_PosTyp), r.Zip_Code
        variants = {nm, f"{pre} {nm}".strip(), f"{nm} {post}".strip(), f"{pre} {nm} {post}".strip()}
        for v in variants:
            for sf in {suf, ""}:
                idx.setdefault(key(v, sf, z), {}).setdefault(num, r.geometry)
                # ZIP-less key for 911 authorities that leave Zip_Code blank (DeKalb):
                # accepted only when the street+number is unique county-wide.
                zl = idx.setdefault(key(v, sf, "NOZIP"), {})
                zl[num] = None if (num in zl and zl[num] is not r.geometry) else r.geometry
    geoms, hit = [], 0
    zips = table[zip_field] if zip_field else [None] * len(table)
    for a, zc in zip(table[addr_field], zips):
        p = parse_parts(a, zc) if zip_field else parse_single_line(a)
        g = None
        if p:
            num, name, suf, z = p
            for cand in (key(name, suf, z), key(name, "", z), key(name, suf, "NOZIP"), key(name, "", "NOZIP")):
                g = idx.get(cand, {}).get(num)
                if g is not None: break
        geoms.append(g); hit += g is not None
    out = gpd.GeoDataFrame(table.copy(), geometry=gpd.GeoSeries(geoms, crs=pts.crs))
    out["geocoded"] = out.geometry.notna()
    return out


# --------------------------------------------------------------------- main
def run(county: str) -> dict:
    t0 = time.time(); log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    cfg = config.county(county); slug = cfg["slug"]; C = cfg["county"]
    wh = Warehouse()
    OUT = ROOT / "out" / slug; OUT.mkdir(parents=True, exist_ok=True)
    SITNAME = {str(k): v for k, v in cfg["situs"].items()}
    CITY_ALIASES.clear()
    for canon, aliases in cfg.get("city_aliases", {}).items():
        for a in aliases: CITY_ALIASES[str(a).upper()] = str(canon).upper()
    # Postal home counties: derived statewide from rooftops (fetch/postal_map.py), overridden by config.
    USPS = {}
    pm = ROOT / "configs" / "postal_home_county.json"
    if pm.exists():
        pmap = json.loads(pm.read_text())["by_city"]
        for city, v in pmap.items():
            USPS[city] = v["home"]   # majority county; Old Hickory -> DAVIDSON even though it spills into Wilson
    USPS.update({k.upper(): v.upper() for k, v in cfg.get("usps_only_places", {}).items()})
    munis = {norm_city(v) for k, v in SITNAME.items() if not k.endswith("00")}

    log(f"{C}: loading snapshots")
    dor_all = wh.load("dor_tax_rate_boundaries", "TN")
    dor_all["SITUS"] = dor_all["SITUS"].astype(str)
    # Consolidated governments: codes that pay the same treasury are one jurisdiction for
    # audit purposes (Davidson 1900 "unincorporated" = the GSD, paid to Metro like 1901).
    MERGE = {str(k): str(v) for k, v in cfg.get("situs_merge", {}).items()}
    if MERGE:
        m = dor_all["SITUS"].isin(MERGE)
        dor_all.loc[m, "SITUS"] = dor_all.loc[m, "SITUS"].map(MERGE)
        canon_city = dor_all[dor_all["SITUS"].isin(MERGE.values())].groupby("SITUS")["CITY"].first()
        dor_all.loc[m, "CITY"] = dor_all.loc[m, "SITUS"].map(canon_city)
        dor_all = dor_all.dissolve(by=["SITUS", "COUNTY", "CITY"], aggfunc="first").reset_index()
        SITNAME = {MERGE.get(k, k): v for k, v in SITNAME.items() if k not in MERGE}
    cities = wh.load("comptroller_cities", "TN")
    pts = wh.load("ng911_address_points", slug)
    try:
        sst = wh.load("sst_address_lookup", slug)
    except FileNotFoundError:
        log("  (no SST address-range snapshot yet; E5 skipped this run)"); sst = pd.DataFrame(columns=["streetname"])
    # verify config situs list against DOR
    dor_codes = set(dor_all.loc[dor_all.COUNTY == C, "SITUS"])
    if dor_codes != set(SITNAME):
        log(f"  WARNING config situs {sorted(SITNAME)} != DOR {sorted(dor_codes)}")
    # neighbours: counties whose polygons touch this county's
    mine = dor_all[dor_all.COUNTY == C]
    touching = dor_all[dor_all.intersects(mine.unary_union.buffer(50))]
    dor = touching.copy()
    log(f"  DOR polygons in region {len(dor)} ({dor.COUNTY.nunique()} counties) | rooftops {len(pts):,} | SST ranges {len(sst):,}")

    seams = build_seams(dor, C)
    log(f"  seams {len(seams)} — cross-county {int((seams.seam_type=='CROSS_COUNTY').sum())}, "
        f"{seams.seam_len_ft.sum()/5280:,.1f} mi")

    pts = assign_situs(pts, dor)
    unplaced = int(pts["dor_situs"].isna().sum())
    pts = pts[pts["dor_county"] == C].copy()
    pts["dor_situs"] = pts["dor_situs"].astype(str)
    log(f"  placed {len(pts):,} rooftops in {C}; {unplaced} matched no polygon")
    pts = pts.join(distance_to_seams(pts, seams))

    cj = gpd.sjoin(pts[["geometry"]], cities[["NAME", "geometry"]], how="left", predicate="within")
    pts["comp_city"] = cj[~cj.index.duplicated(keep="first")]["NAME"].fillna("Unincorporated")

    # annexation layers from config
    pts["in_annexation"] = False; pts["annexation_of"] = None
    for L in cfg.get("city_layers", []):
        if L["role"] != "annexations": continue
        try:
            ax = wh.load(L["id"], slug)
        except FileNotFoundError:
            log(f"  (no snapshot for {L['id']})"); continue
        ax = ax[ax.geometry.notna()]
        aj = gpd.sjoin(pts[["geometry"]], ax[["geometry"]], how="left", predicate="within")
        hit = ~aj[~aj.index.duplicated(keep="first")]["index_right"].isna()
        pts.loc[hit, "in_annexation"] = True; pts.loc[hit, "annexation_of"] = L.get("name", L["id"])
    pts = pts.join(layer_agreement(pts, CITY_ALIASES))

    log("  DOR address-range join")
    idx = EX.build_sst_index(sst.to_dict("records"))
    m = [EX.sst_situs_for(idx, nm, sf, z, n) for n, nm, sf, z in zip(pts.Add_Number, pts.St_Name, pts.St_PosTyp, pts.Zip_Code)]
    pts["sst_situs"] = [MERGE.get(x["situs"], x["situs"]) if x else None for x in m]
    pts["sst_city"] = [x["city"] if x else None for x in m]
    matched = int(pts["sst_situs"].notna().sum())

    # ---------------------------------------------------------- business universe
    log("  business universe")
    biz_frames = []
    for L in cfg.get("business_layers", []):
        if L.get("type") == "sos_tsv":
            b = load_sos(ROOT / L["path"], C)
            b = geocode_by_range(b, pts, "PrincipalAddressLine1", "PrincipalAddressPostalCode")
            log(f"    {L['id']}: {int(b.geocoded.sum()):,}/{len(b):,} active for-profit entities geocoded to a rooftop")
            b = b[b.geocoded]
        else:
            try:
                b = wh.load(L["id"], slug)
            except FileNotFoundError:
                log(f"  (no snapshot for {L['id']})"); continue
        if not isinstance(b, gpd.GeoDataFrame):
            b = geocode_by_range(b, pts, L["address_field"])
            log(f"    {L['id']}: {int(b.geocoded.sum())}/{len(b)} rows geocoded to a rooftop")
            b = b[b.geocoded]
        nf = "business" if "business" in b.columns else L["name_field"]
        if nf not in b.columns:   # ArcGIS field aliases with spaces arrive as "Business Name" or "Business_Name"
            alt = {c.replace(" ", "_").lower(): c for c in b.columns}
            nf = alt.get(nf.replace(" ", "_").lower(), nf)
        if nf not in b.columns:
            log(f"    {L['id']}: name field '{L['name_field']}' not found; columns {list(b.columns)[:8]}"); continue
        b = b.rename(columns={nf: "business"})
        if L.get("situs_field"): b = b.rename(columns={L["situs_field"]: "coded_situs"})
        b["source"] = L["id"]
        keep = ["business", "source", "geometry"] + (["coded_situs"] if "coded_situs" in b.columns else [])
        biz_frames.append(b[keep])
    biz = gpd.GeoDataFrame(pd.concat(biz_frames, ignore_index=True), crs=pts.crs) if biz_frames else \
        gpd.GeoDataFrame(columns=["business", "source", "geometry"], geometry="geometry", crs=pts.crs)
    biz = biz[biz.geometry.notna()].reset_index(drop=True)
    biz["id"] = range(1, len(biz) + 1)
    # Only named businesses are audit items. Everything else stays on the map, labelled.
    biz["kind"] = biz["business"].apply(EX.classify_label)
    if len(biz):
        biz = assign_situs(biz, dor); biz = biz[biz.dor_county == C].copy(); biz["dor_situs"] = biz["dor_situs"].astype(str)
        biz = biz.join(distance_to_seams(biz, seams))
        near = gpd.sjoin_nearest(biz[["id", "geometry"]],
                                 pts[["Add_Number", "StNam_Full", "Unit", "Zip_Code", "Post_City", "Inc_Muni", "Census_Plc",
                                      "Parcel_ID", "sst_situs", "sst_city", "comp_city", "in_annexation", "annexation_of",
                                      "layers_agree", "disagreement", "geometry"]],
                                 how="left", distance_col="addr_match_ft", max_distance=500)
        near = near[~near.index.duplicated(keep="first")].drop(columns=["index_right", "geometry"])
        biz = biz.join(near.drop(columns=["id"]))
        # rooftops get +10 when a business point sits on them
        bj = gpd.sjoin_nearest(pts[["geometry"]], biz[["geometry"]], how="left", distance_col="d", max_distance=100)
        pts["biz_within_100ft"] = ~bj[~bj.index.duplicated(keep="first")]["index_right"].isna()
    else:
        pts["biz_within_100ft"] = False
    log(f"    {len(biz):,} business points placed in {C}")

    # -------------------------------------------------------------- exceptions
    for df in (pts, biz):
        if not len(df): continue
        df["post_city_n"] = df["Post_City"].apply(norm_city)
        df["dor_city_n"] = df["dor_city"].apply(norm_city)
        df["postal_home_county"] = df["post_city_n"].map(USPS)
        e5 = df["sst_situs"].notna() & (df["sst_situs"] != df["dor_situs"])
        deep = df["nearest_seam_ft"].fillna(0) >= 250
        # Cross-county exposure: the mailing city's home county is not this one, AND the mailing
        # city is not one of this county's own municipalities (Goodlettsville is a real city in
        # both Davidson and Sumner; Old Hickory is a Davidson post office that spills into Wilson).
        df["E2_CROSS_COUNTY_POSTAL"] = (df["postal_home_county"].notna() & (df["postal_home_county"] != C)
                                        & ~df["post_city_n"].isin(munis)).fillna(False)
        df["E5_DOR_INTERNAL_CONFLICT"] = (e5 & deep).fillna(False)
        df["E5B_DOR_CONFLICT_AT_BOUNDARY"] = (e5 & ~deep).fillna(False)
        df["E1_POSTAL_CITY_OVERSTATES"] = (df["post_city_n"].isin(munis) & (df["post_city_n"] != df["dor_city_n"])
                                          & ~df["E2_CROSS_COUNTY_POSTAL"]).fillna(False)
        df["E6_ANNEXATION_LAG"] = (df["in_annexation"].fillna(False).astype(bool)
                                   & ~df.apply(lambda r: norm_city(r.get("annexation_of")) == r["dor_city_n"], axis=1)).fillna(False) if len(df) else False
        df["E4_LAYER_DISAGREEMENT"] = (~df["layers_agree"].fillna(True).astype(bool))
        df["E3_BOUNDARY_PROXIMITY"] = df["risk_band"].isin(["CRITICAL", "HIGH"])
        df["primary_class"] = ""
        for k in ["E5_DOR_INTERNAL_CONFLICT", "E2_CROSS_COUNTY_POSTAL", "E6_ANNEXATION_LAG", "E4_LAYER_DISAGREEMENT",
                  "E5B_DOR_CONFLICT_AT_BOUNDARY", "E3_BOUNDARY_PROXIMITY", "E1_POSTAL_CITY_OVERSTATES"]:
            df.loc[df[k] & (df["primary_class"] == ""), "primary_class"] = k
    sc = pts.apply(EX.score_evidence, axis=1)
    pts["evidence_score"] = [x[0] for x in sc]; pts["evidence_notes"] = [x[1] for x in sc]
    pts["disposition"] = [EX.disposition(s, a, b) for s, a, b in zip(pts.evidence_score, pts.layers_agree, pts.risk_band)]
    if len(biz):
        # business rows inherit the rooftop's score context
        biz["biz_within_100ft"] = True; biz["Lifecycle"] = None
        sc = biz.apply(EX.score_evidence, axis=1)
        biz["evidence_score"] = [x[0] for x in sc]; biz["evidence_notes"] = [x[1] for x in sc]
        biz["disposition"] = [EX.disposition(s, a, b) for s, a, b in zip(biz.evidence_score, biz.layers_agree.fillna(True), biz.risk_band)]
        biz["flag"] = ""
        biz.loc[biz.risk_band.isin(["CRITICAL", "HIGH"]), "flag"] = "BOUNDARY_RISK"
        biz.loc[biz.E1_POSTAL_CITY_OVERSTATES, "flag"] = "POSTAL_CITY_EXPOSURE"
        biz.loc[biz.E2_CROSS_COUNTY_POSTAL, "flag"] = "CROSS_COUNTY_POSTAL"
        if "coded_situs" in biz.columns:
            biz["coded_situs"] = biz["coded_situs"].astype(str).str.slice(0, 4)
            biz.loc[biz.coded_situs.notna() & (biz.coded_situs != "None") & (biz.coded_situs != biz.dor_situs), "flag"] = "CODED_MISMATCH"

    # ------------------------------------------------------------------ write
    log("  writing")
    p4 = pts.to_crs("EPSG:4326"); p4["lon"] = p4.geometry.x.round(6); p4["lat"] = p4.geometry.y.round(6)
    pd.DataFrame(p4.drop(columns="geometry")).to_csv(OUT / "address_points_scored.csv", index=False)
    if len(biz):
        b4 = biz.to_crs("EPSG:4326"); b4["lon"] = b4.geometry.x.round(6); b4["lat"] = b4.geometry.y.round(6)
        pd.DataFrame(b4.drop(columns="geometry")).to_csv(OUT / "business_exceptions.csv", index=False)
    seams4 = seams.to_crs("EPSG:4326"); seams4.to_file(OUT / "seams.geojson", driver="GeoJSON")
    summary = {
        "county": C, "slug": slug, "generated_utc": pd.Timestamp.now("UTC").isoformat(), "rubric": "v2",
        "confidential_dor_data_used": False, "situs_names": SITNAME,
        "tiers": cfg["tiers"], "sources": {k: v["snap_date"] for k, v in
            {L: wh.latest(L, s) for L, s in [("dor_tax_rate_boundaries", "TN"), ("comptroller_cities", "TN"),
             ("ng911_address_points", slug), ("sst_address_lookup", slug)]}.items() if v},
        "totals": {"address_points": int(len(pts)), "unplaced": unplaced,
                   "sst_range_match_rate_pct": round(matched / max(len(pts), 1) * 100, 1),
                   "business_points": int(len(biz)), "seams": int(len(seams)),
                   "seam_miles": round(float(seams.seam_len_ft.sum()) / 5280, 1),
                   "cross_county_seam_miles": round(float(seams.loc[seams.seam_type == "CROSS_COUNTY", "seam_len_ft"].sum()) / 5280, 1)},
        "situs_distribution": {k: int(v) for k, v in pts.dor_situs.value_counts().items()},
        "risk_bands": {k: int(v) for k, v in pts.risk_band.value_counts().items()},
        "exceptions": {k: int(pts[k].sum()) for k in ["E2_CROSS_COUNTY_POSTAL", "E5_DOR_INTERNAL_CONFLICT", "E5B_DOR_CONFLICT_AT_BOUNDARY",
                                                       "E1_POSTAL_CITY_OVERSTATES", "E6_ANNEXATION_LAG", "E4_LAYER_DISAGREEMENT", "E3_BOUNDARY_PROXIMITY"]},
        "dispositions": {k: int(v) for k, v in pts.disposition.value_counts().items()},
        "postal_city_profile": {k: int(v) for k, v in pts.post_city_n.value_counts().head(25).items()},
        "cross_county_postal_by_city": {k: int(v) for k, v in pts.loc[pts.E2_CROSS_COUNTY_POSTAL, "post_city_n"].value_counts().items()},
        "layer_disagreement_detail": {k: int(v) for k, v in pts.loc[~pts.layers_agree, "disagreement"].value_counts().head(12).items()},
        "dor_conflict_direction": {f"polygon {a} -> file {b}": int(n) for (a, b), n in
                                   pts[pts.E5_DOR_INTERNAL_CONFLICT | pts.E5B_DOR_CONFLICT_AT_BOUNDARY].groupby(["dor_situs", "sst_situs"]).size().sort_values(ascending=False).items()},
        "business_flags": {k: int(v) for k, v in biz.loc[biz.kind == "business", "flag"].value_counts().items()} if len(biz) else {},
        "label_kinds": {k: int(v) for k, v in biz["kind"].value_counts().items()} if len(biz) else {},
    }
    if len(biz) and "coded_situs" in biz.columns:
        cm = biz[biz.coded_situs.notna() & (biz.coded_situs != "None")]
        summary["calibration_source"] = {"rows_with_coded_situs": int(len(cm)),
                                         "coded_equals_measured": int((cm.coded_situs == cm.dor_situs).sum()),
                                         "coded_ne_measured": int((cm.coded_situs != cm.dor_situs).sum())}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    log(f"done -> {OUT}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--county", required=True)
    s = run(ap.parse_args().county)
    print(json.dumps({k: s[k] for k in ("totals", "exceptions", "dispositions", "business_flags")}, indent=1))
