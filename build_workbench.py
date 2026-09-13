#!/usr/bin/env python3
"""Per-county workbench: artifact/<slug>/{workbench.html, wb.js, wbdata.js}."""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path
import geopandas as gpd, pandas as pd
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config
from warehouse.store import Warehouse
from engine.boundary_qa import build_seams


def geo(gdf, cols, tol):
    g = gdf[gdf.geometry.notna()].copy(); g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
    j = json.loads(g.to_crs("EPSG:4326")[cols + ["geometry"]].to_json())
    def rnd(a):
        if isinstance(a, list):
            return [round(v, 6) for v in a] if a and isinstance(a[0], (int, float)) else [rnd(x) for x in a]
        return a
    for f in j["features"]:
        gm = f["geometry"]
        if gm is None: continue
        if gm.get("type") == "GeometryCollection":
            for sg in gm["geometries"]: sg["coordinates"] = rnd(sg["coordinates"])
        else: gm["coordinates"] = rnd(gm["coordinates"])
    return j


_NOTE_MAP = {"DOR tax polygon": "P", "911-authority address point": "A", "official layers agree": "L", "DOR address-range match": "R",
             "business point within 100 ft": "B", "address current": "C", "parcel id": "I", "within 50 ft of a seam": "s50",
             "within 250 ft of a seam": "s250", "conflicting official layers": "X", "mailing-only address": "M"}
def compact_notes(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    out = []
    for part in str(v).split(";"):
        part = part.strip(); m = part.split(" ", 1)
        if len(m) == 2: out.append(m[0] + _NOTE_MAP.get(m[1], m[1][:6]))
    return " ".join(out)


def _situs4(v):
    """Situs codes are 4-character strings. A CSV round-trip turns 8305 into 8305.0; undo that."""
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    t = str(v).strip()
    if t in ("", "None", "nan"): return None
    try: return str(int(float(t))).zfill(4)
    except ValueError: return t[:4]


def cv(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    if hasattr(v, "item"): v = v.item()
    if isinstance(v, bool): return v
    if isinstance(v, float): return round(v, d)
    return v


def build(county: str) -> Path:
    cfg = config.county(county); slug = cfg["slug"]; C = cfg["county"]
    wh = Warehouse(); OUT = ROOT / "out" / slug; ART = ROOT / "artifact" / slug; ART.mkdir(parents=True, exist_ok=True)
    summary = json.loads((OUT / "summary.json").read_text())
    dor_all = wh.load("dor_tax_rate_boundaries", "TN"); dor_all["SITUS"] = dor_all.SITUS.astype(str)
    mine = dor_all[dor_all.COUNTY == C]
    dor = dor_all[dor_all.intersects(mine.unary_union.buffer(50))]
    seams = build_seams(dor, C)
    P = {"county": C, "slug": slug, "situs_names": summary["situs_names"],
         "wilson_situs": geo(mine, ["SITUS", "CITY"], 20),   # key name kept for wb.js compatibility
         "neighbors": geo(dor[dor.COUNTY != C].dissolve(by="COUNTY").reset_index(), ["COUNTY"], 150),
         "seams": geo(seams, ["side_a", "side_b", "seam_type"], 15)}
    # annexations: concat every configured annexation layer
    ax = []
    for L in cfg.get("city_layers", []):
        if L["role"] != "annexations": continue
        try: a = wh.load(L["id"], slug)
        except FileNotFoundError: continue
        a = a[a.geometry.notna()].copy(); a["Annex_Num"] = a[L.get("date_field", a.columns[0])].astype(str) if L.get("date_field") in a.columns else L.get("name", L["id"])
        a["city"] = L.get("name", L["id"]); ax.append(a[["Annex_Num", "city", "geometry"]])
    P["annexations"] = geo(gpd.GeoDataFrame(pd.concat(ax), crs=ax[0].crs), ["Annex_Num", "city"], 20) if ax else {"type": "FeatureCollection", "features": []}
    try:
        roads = wh.load("ng911_roads", slug); roads = roads[roads.geometry.notna()].copy()
        roads["cls"] = roads["CFCC"].astype(str).str[:2].map({"A1": 1, "A2": 2, "A3": 3}).fillna(4).astype(int)
        big = len(roads) > 15000
        if big:   # keep the page under the 16 MB cap: locals only where businesses cluster is a later refinement
            roads = roads[roads.cls <= 3]
        P["roads"] = geo(roads, ["LABEL", "cls"], 50 if big else 30)
    except FileNotFoundError:
        P["roads"] = {"type": "FeatureCollection", "features": []}
    sc = pd.read_csv(OUT / "address_points_scored.csv", low_memory=False)
    bb = sc[sc.risk_band.isin(["CRITICAL", "HIGH"])]
    if len(bb) > 12000: bb = bb.sample(12000, random_state=3)
    P["band_pts"] = [[round(float(a), 6), round(float(b), 6), 0 if c == "CRITICAL" else 1] for a, b, c in zip(bb.lon, bb.lat, bb.risk_band)]
    F = ["id", "business", "kind", "source", "house_no", "street", "unit", "zip", "post_city", "e911_muni", "census_place", "placement", "parcel_id",
         "dor_situs", "dor_city", "sst_situs", "sst_city", "comp_city", "in_annexation", "layers_agree", "disagreement",
         "seam_ft", "seam_a", "seam_b", "risk_band", "score", "score_notes", "disposition", "flag", "postal_county", "addr_match_ft", "coded_situs", "lon", "lat"]
    rows = []; mins = []
    bz = OUT / "business_exceptions.csv"
    MAX_CLEAR = 3000   # keep big counties under the 16 MB page cap: unflagged businesses beyond this are thinned to points
    clear_total = clear_kept = 0
    if bz.exists():
        b = pd.read_csv(bz, low_memory=False)
        b["fl_"] = b["flag"].fillna("")
        clear = b[(b.get("kind", "business") == "business") & (b.fl_ == "")]
        clear_total = len(clear)
        if clear_total > MAX_CLEAR:
            keep_ids = set(clear.sample(MAX_CLEAR, random_state=11)["id"])
        else:
            keep_ids = set(clear["id"])
        clear_kept = len(keep_ids)
        for r in b.itertuples():
            if getattr(r, "kind", "business") == "business" and r.fl_ == "" and r.id not in keep_ids:
                mins.append([cv(r.id), cv(r.business), cv(r.source), _situs4(r.dor_situs), cv(r.lon, 6), cv(r.lat, 6)]); continue
            g = lambda k, d=1: cv(getattr(r, k, None), d)
            if getattr(r, "kind", "business") != "business":
                rows.append([g("id"), g("business"), g("kind"), g("source")] + [None] * 9 + [_situs4(getattr(r, "dor_situs", None))]
                            + [None] * 17 + [g("lon", 6), g("lat", 6)]); continue
            rows.append([g("id"), g("business"), g("kind"), g("source"), g("Add_Number"), g("StNam_Full"), g("Unit"), g("Zip_Code"), g("post_city_n") or None,
                         g("Inc_Muni"), g("Census_Plc"), None, g("Parcel_ID"), _situs4(getattr(r, "dor_situs", None)), g("dor_city"),
                         _situs4(getattr(r, "sst_situs", None)), g("sst_city"), g("comp_city"),
                         g("in_annexation"), g("layers_agree"), g("disagreement") or None, g("nearest_seam_ft"), _situs4(getattr(r, "seam_side_a", None)), _situs4(getattr(r, "seam_side_b", None)), g("risk_band"), g("evidence_score"), compact_notes(getattr(r, "evidence_notes", None)), g("disposition"),
                         g("flag") or None, g("postal_home_county"), g("addr_match_ft"), _situs4(getattr(r, "coded_situs", None)), g("lon", 6), g("lat", 6)])
    P["biz_fields"] = F; P["biz"] = rows
    P["biz_min_fields"] = ["id", "business", "source", "dor_situs", "lon", "lat"]; P["biz_min"] = mins
    P["summary"] = summary
    fc = {}
    for r in rows:
        if r[2] != "business": continue
        k = r[F.index("flag")] or "CLEAR"; fc[k] = fc.get(k, 0) + 1
    P["flag_counts"] = fc
    P["clear_total"] = clear_total; P["clear_kept"] = clear_kept
    P["label_kinds"] = summary.get("label_kinds", {})
    (ART / "wbdata.js").write_text("window.WB=" + json.dumps(P, separators=(",", ":")) + ";")
    html = (ROOT / "artifact" / "workbench.html").read_text()
    html = html.replace("WILSON · TN · 9500–9503", f"{C} · TN · {min(summary['situs_names'])}–{max(summary['situs_names'])}")
    html = html.replace("<title>Situs Workbench</title>", f"<title>Situs Workbench — {C.title()} County</title>")
    (ART / "workbench.html").write_text(html)
    shutil.copy(ROOT / "artifact" / "wb.js", ART / "wb.js")
    print(f"{C}: {len(rows)} labels ({fc}), wbdata {round((ART/'wbdata.js').stat().st_size/1e6,2)} MB -> {ART}")
    return ART


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--county", required=True); build(ap.parse_args().county)
