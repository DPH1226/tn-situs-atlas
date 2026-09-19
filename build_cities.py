#!/usr/bin/env python3
"""
City layer for the Tennessee Situs Atlas.

Every incorporated city already has a situs code and a polygon in the DOR layer, and every rooftop
and business in out/<county>/ already carries its situs. A city page is therefore a scoped view of
the county run, not a new run: same rubric, same evidence, same workbench. This script builds it.

    python3 build_cities.py                 # every city in every county that has out/<slug>/summary.json
    python3 build_cities.py --city lebanon  # one city (slug)

Writes
    artifact/cities/<city-slug>/{workbench.html, wb.js, wbdata.js}
    artifact/cities.html                    the cities index (mirrors the county atlas)
    out/cities_index.json

What a city sees that a county view does not separate:
    inside      businesses and rooftops inside the city's DOR polygon(s) — its own tax base
    file-says-elsewhere
                rooftops inside the polygon that the State's own address-range file codes to
                somewhere else (usually the county's unincorporated code). This is the city's
                counter-finding: corrected, money moves TO the city.
    postal exposure
                businesses OUTSIDE the polygon carrying the city's mailing address — where a
                mailing-address registration would have coded them to the city.
    file-claims-city
                rooftops outside the polygon that the address file codes TO the city.

Multi-county cities (Goodlettsville, Portland, Oak Ridge, ...) have one situs code per county;
they are merged by name into one page with every part.

No confidential data is read here.
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

import geopandas as gpd, pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config
from warehouse.store import Warehouse
from engine.situs_core import TN_STATE_PLANE as TN_SP
from build_workbench import geo, cv, _situs4, compact_notes

ART = ROOT / "artifact"; OUTD = ROOT / "out"
CTX_FT = 2 * 5280          # jurisdictions and roads drawn this far beyond the city polygon
SEAM_FT = 2640             # seams kept if within half a mile of the polygon
MAX_CLEAR = 3000           # unflagged inside-city businesses beyond this are thinned to points (page cap)
MAX_ROADS = 7000
MAX_BAND = 12000

PTS_COLS = ["dor_situs", "sst_situs", "sst_city", "comp_city", "risk_band", "E5_DOR_INTERNAL_CONFLICT", "E4_LAYER_DISAGREEMENT", "lon", "lat"]


def norm(v) -> str:
    """Same normalization run_county applies to city names, so names match across layers."""
    if v is None or (isinstance(v, float) and pd.isna(v)): return ""
    s = str(v).strip().upper().replace(".", "").replace("(", "").replace(")", "").replace("MOUNT ", "MT ")
    return "UNINCORPORATED" if s in {"UNINCORPORATED", "NONE", ""} else s


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def is_county_code(code: str) -> bool:
    return str(code).endswith("00")


# ----------------------------------------------------------------------------- data
def load_dor(wh: Warehouse) -> gpd.GeoDataFrame:
    """DOR polygons with every county's situs_merge applied (Davidson 1900 -> 1901 etc.)."""
    d = wh.load("dor_tax_rate_boundaries", "TN").copy()
    d["SITUS"] = d["SITUS"].astype(str).str.zfill(4)
    merges = {}
    for c in config.all_counties():
        for k, v in (config.county(c).get("situs_merge") or {}).items():
            merges[str(k).zfill(4)] = str(v).zfill(4)
    if merges:
        m = d["SITUS"].isin(merges)
        d.loc[m, "SITUS"] = d.loc[m, "SITUS"].map(merges)
        canon = d[d["SITUS"].isin(merges.values())].groupby("SITUS")["CITY"].first()
        d.loc[m, "CITY"] = d.loc[m, "SITUS"].map(canon)
        d = d.dissolve(by=["SITUS", "COUNTY", "CITY"], aggfunc="first").reset_index()
    if d.crs is None or d.crs.to_string() != TN_SP:
        d = d.to_crs(TN_SP)
    return d


def read_pts(slug: str) -> pd.DataFrame:
    p = OUTD / slug / "address_points_scored.csv"
    if not p.exists(): return pd.DataFrame(columns=PTS_COLS)
    d = pd.read_csv(p, low_memory=False, usecols=lambda c: c in PTS_COLS)
    for c in PTS_COLS:
        if c not in d.columns: d[c] = None
    d["dor4"] = d["dor_situs"].map(_situs4); d["sst4"] = d["sst_situs"].map(_situs4)
    d["sst_n"] = d["sst_city"].map(norm); d["comp_n"] = d["comp_city"].map(norm)
    for c in ("E5_DOR_INTERNAL_CONFLICT", "E4_LAYER_DISAGREEMENT"):
        d[c] = d[c].fillna(False).astype(bool)
    return d


def read_biz(slug: str) -> pd.DataFrame:
    p = OUTD / slug / "business_exceptions.csv"
    if not p.exists(): return pd.DataFrame()
    d = pd.read_csv(p, low_memory=False)
    d["dor4"] = d["dor_situs"].map(_situs4); d["sst4"] = d.get("sst_situs", pd.Series([None] * len(d))).map(_situs4)
    d["post_n"] = d.get("post_city_n", pd.Series([None] * len(d))).map(norm)
    d["sst_n"] = d.get("sst_city", pd.Series([None] * len(d))).map(norm)
    d["fl_"] = d.get("flag", pd.Series([""] * len(d))).fillna("")
    if "kind" not in d.columns: d["kind"] = "business"
    return d


def roads_for(wh: Warehouse, slug: str) -> gpd.GeoDataFrame | None:
    try:
        r = wh.load("ng911_roads", slug)
    except FileNotFoundError:
        return None
    r = r[r.geometry.notna()].copy()
    if "cls" not in r.columns:
        src = r["CFCC"].astype(str).str[:2] if "CFCC" in r.columns else pd.Series([""] * len(r), index=r.index)
        r["cls"] = src.map({"A1": 1, "A2": 2, "A3": 3}).fillna(4).astype(int)
    if "LABEL" not in r.columns: r["LABEL"] = None
    return r.to_crs(TN_SP) if r.crs and r.crs.to_string() != TN_SP else r


# ----------------------------------------------------------------------------- rows
BIZ_FIELDS = ["id", "business", "kind", "source", "house_no", "street", "unit", "zip", "post_city", "e911_muni", "census_place", "placement",
              "parcel_id", "dor_situs", "dor_city", "sst_situs", "sst_city", "comp_city", "in_annexation", "layers_agree", "disagreement",
              "seam_ft", "seam_a", "seam_b", "risk_band", "score", "score_notes", "disposition", "flag", "postal_county", "addr_match_ft",
              "coded_situs", "lon", "lat"]


def full_row(r, rid) -> list:
    g = lambda k, d=1: cv(getattr(r, k, None), d)
    if getattr(r, "kind", "business") != "business":
        return [rid, g("business"), g("kind"), g("source")] + [None] * 9 + [_situs4(getattr(r, "dor_situs", None))] + [None] * 17 + [g("lon", 6), g("lat", 6)]
    return [rid, g("business"), g("kind"), g("source"), g("Add_Number"), g("StNam_Full"), g("Unit"), g("Zip_Code"), g("post_city_n") or None,
            g("Inc_Muni"), g("Census_Plc"), None, g("Parcel_ID"), _situs4(getattr(r, "dor_situs", None)), g("dor_city"),
            _situs4(getattr(r, "sst_situs", None)), g("sst_city"), g("comp_city"), g("in_annexation"), g("layers_agree"), g("disagreement") or None,
            g("nearest_seam_ft"), _situs4(getattr(r, "seam_side_a", None)), _situs4(getattr(r, "seam_side_b", None)), g("risk_band"),
            g("evidence_score"), compact_notes(getattr(r, "evidence_notes", None)), g("disposition"), g("flag") or None, g("postal_home_county"),
            g("addr_match_ft"), _situs4(getattr(r, "coded_situs", None)), g("lon", 6), g("lat", 6)]


# ----------------------------------------------------------------------------- per city
def collect(wh: Warehouse, dor: gpd.GeoDataFrame, only: set[str] | None):
    """One pass over the county outputs; returns {city_key: [part, ...]} with only city-scoped data kept."""
    cities: dict[str, list] = defaultdict(list)
    for c in config.all_counties():
        sp = OUTD / c / "summary.json"
        if not sp.exists(): continue
        cfg = config.county(c); C = cfg["county"]; s = json.loads(sp.read_text())
        SIT = {str(k).zfill(4): v for k, v in s["situs_names"].items()}
        own = {k: v for k, v in SIT.items() if not is_county_code(k)}
        if only is not None:
            own = {k: v for k, v in own.items() if slugify(v) in only or slugify(norm(v)) in only}
        if not own: continue
        pts = read_pts(c); biz = read_biz(c)
        seams = None
        sf = OUTD / c / "seams.geojson"
        if sf.exists():
            seams = gpd.read_file(sf); seams = seams.to_crs(TN_SP)
            for k in ("side_a", "side_b"): seams[k] = seams[k].map(_situs4)
        roads = roads_for(wh, c)
        annex = []
        for L in cfg.get("city_layers", []):
            if L["role"] != "annexations": continue
            try: a = wh.load(L["id"], c)
            except FileNotFoundError: continue
            a = a[a.geometry.notna()].copy()
            df_ = L.get("date_field")
            a["Annex_Num"] = a[df_].astype(str) if df_ in a.columns else L.get("name", L["id"])
            a["city"] = L.get("name", L["id"]); annex.append((norm(L.get("name", "")), a[["Annex_Num", "city", "geometry"]].to_crs(TN_SP)))
        county_codes = {k for k in SIT if is_county_code(k)}

        for code, name in own.items():
            key = norm(name)
            poly = dor[(dor["COUNTY"] == C) & (dor["SITUS"] == code)]
            if poly.empty:
                print(f"  {C} {code} {name}: no DOR polygon, skipped"); continue
            hull = poly.geometry.union_all() if hasattr(poly.geometry, "union_all") else poly.geometry.unary_union
            ctx_geom = hull.buffer(CTX_FT); ctx_bbox = box(*ctx_geom.bounds)
            # rooftops
            inside = pts["dor4"] == code
            e5 = inside & pts["E5_DOR_INTERNAL_CONFLICT"] & pts["sst4"].notna() & (pts["sst4"] != code)
            e5_county = e5 & pts["sst4"].isin(county_codes)
            claims = (~inside) & (pts["sst4"] == code)
            # the city's strongest counter-finding: DOR says elsewhere, but the 911 authority and the
            # Comptroller's certified limits both put the rooftop inside this city (E4, outside the polygon)
            e4 = (~inside) & pts["E4_LAYER_DISAGREEMENT"] & (pts["comp_n"] == key)
            bb = pts[pts["risk_band"].isin(["CRITICAL", "HIGH"]) & pts["lon"].notna()]
            # bbox in degrees for the band sample: cheap and good enough for a display layer
            b4 = gpd.GeoSeries([ctx_bbox], crs=TN_SP).to_crs("EPSG:4326").total_bounds
            bb = bb[(bb.lon >= b4[0]) & (bb.lon <= b4[2]) & (bb.lat >= b4[1]) & (bb.lat <= b4[3])]
            # businesses: inside, plus outside rows that name or are coded to this city
            if len(biz):
                b_in = biz[biz["dor4"] == code]
                b_post = biz[(biz["dor4"] != code) & (biz["post_n"] == key)]
                b_claim = biz[(biz["dor4"] != code) & (biz["sst4"] == code)]
                keep = pd.concat([b_in, b_post, b_claim]).drop_duplicates(subset=["id"])
            else:
                b_in = b_post = b_claim = keep = biz
            # context geometry
            ctx = dor[dor.intersects(ctx_geom) & ~((dor["COUNTY"] == C) & (dor["SITUS"] == code))].copy()
            ctx = gpd.clip(ctx, ctx_bbox) if len(ctx) else ctx
            ctx["LABEL"] = ctx.apply(lambda r: f"{r['COUNTY']} · {r['CITY']}" if is_county_code(r["SITUS"]) else str(r["CITY"]), axis=1) if len(ctx) else None
            sm = seams[seams.intersects(hull.buffer(SEAM_FT))].copy() if seams is not None and len(seams) else None
            rd = None
            if roads is not None and len(roads):
                rd = roads.cx[ctx_bbox.bounds[0]:ctx_bbox.bounds[2], ctx_bbox.bounds[1]:ctx_bbox.bounds[3]]
                if len(rd) > MAX_ROADS: rd = rd[rd.cls <= 3] if (rd.cls <= 3).sum() >= 200 else rd.sample(MAX_ROADS, random_state=3)
            ax = [a for (n_, a) in annex if n_ == key]
            cities[key].append(dict(
                county=C, slug=c, code=code, name=name, poly=poly[["SITUS", "CITY", "geometry"]], ctx=ctx, seams=sm, roads=rd, annex=ax,
                sitnames=SIT, band=bb, biz=keep, b_in=b_in, b_post=b_post, b_claim=b_claim,
                stats=dict(rooftops=int(inside.sum()), file_elsewhere=int(e5.sum()), file_uninc=int(e5_county.sum()),
                           file_claims=int(claims.sum()), layers_claim=int(e4.sum()),
                           biz=int((b_in["kind"] == "business").sum()) if len(b_in) else 0,
                           cc=int(((b_in["kind"] == "business") & (b_in["fl_"] == "CROSS_COUNTY_POSTAL")).sum()) if len(b_in) else 0,
                           br=int(((b_in["kind"] == "business") & (b_in["fl_"] == "BOUNDARY_RISK")).sum()) if len(b_in) else 0,
                           pe=int((b_post["kind"] == "business").sum()) if len(b_post) else 0)))
        print(f"  {C}: {len(own)} cities collected", flush=True)
    return cities


def build_city(key: str, parts: list, template_html: str, wbjs: str) -> dict:
    display = parts[0]["name"]; counties = sorted({p["county"] for p in parts}); codes = sorted({p["code"] for p in parts})
    slug = slugify(display); dst = ART / "cities" / slug; dst.mkdir(parents=True, exist_ok=True)
    polys = gpd.GeoDataFrame(pd.concat([p["poly"] for p in parts]), crs=TN_SP)
    ctx = gpd.GeoDataFrame(pd.concat([p["ctx"] for p in parts if len(p["ctx"])]), crs=TN_SP) if any(len(p["ctx"]) for p in parts) else None
    if ctx is not None and len(ctx):
        ctx = (ctx[~ctx["SITUS"].isin(codes)].dissolve(by="LABEL", aggfunc="first").reset_index()
               .drop(columns=["COUNTY"], errors="ignore").rename(columns={"LABEL": "COUNTY"}))
    seams = [p["seams"] for p in parts if p["seams"] is not None and len(p["seams"])]
    roads = [p["roads"] for p in parts if p["roads"] is not None and len(p["roads"])]
    annex = [a for p in parts for a in p["annex"] if len(a)]
    empty = {"type": "FeatureCollection", "features": []}
    sitnames = {}
    for p in parts: sitnames.update(p["sitnames"])
    if ctx is not None:
        for r in pd.concat([p["ctx"] for p in parts if len(p["ctx"])]).itertuples():
            sitnames.setdefault(r.SITUS, r.CITY)
    # businesses across parts (multi-county cities: ids are per-county, so key by (county,id))
    rows, mins = [], []; clear_total = clear_kept = 0; fc = {}
    seen = set()
    for p in parts:
        b = p["biz"]
        if not len(b): continue
        b = b.copy(); b["rid"] = b["id"].astype(str) if len(parts) == 1 else p["slug"][:3] + "-" + b["id"].astype(str)
        clear = b[(b["kind"] == "business") & (b["fl_"] == "") & (b["dor4"] == p["code"])]
        clear_total += len(clear)
        keep_ids = set(clear.sample(min(MAX_CLEAR, len(clear)), random_state=11)["rid"]) if len(clear) > MAX_CLEAR else set(clear["rid"])
        clear_kept += len(keep_ids)
        for r in b.itertuples():
            if r.rid in seen: continue
            seen.add(r.rid)
            if r.kind == "business" and r.fl_ == "" and r.dor4 == p["code"] and r.rid not in keep_ids:
                mins.append([r.rid, cv(r.business), cv(r.source), r.dor4, cv(r.lon, 6), cv(r.lat, 6)]); continue
            row = full_row(r, r.rid); rows.append(row)
            if r.kind == "business":
                k = row[BIZ_FIELDS.index("flag")] or "CLEAR"; fc[k] = fc.get(k, 0) + 1
        for r in b.itertuples():
            sitnames.setdefault(r.dor4, str(getattr(r, "dor_city", "") or ""))
    band = pd.concat([p["band"] for p in parts]) if parts else pd.DataFrame()
    band_total = int(len(band))
    if band_total > MAX_BAND: band = band.sample(MAX_BAND, random_state=3)
    st = {k: sum(p["stats"][k] for p in parts) for k in parts[0]["stats"]}
    P = {"county": display.upper(), "slug": "city-" + slug, "county_label": display, "homes": counties, "own_codes": codes,
         "chip": f"{display.upper()} · {' / '.join(c.title() for c in counties)} · {' '.join(codes)}",
         "situs_names": {k: sitnames[k] for k in sorted(sitnames) if k},
         "wilson_situs": geo(polys, ["SITUS", "CITY"], 15),
         "neighbors": geo(ctx, ["COUNTY"], 50) if ctx is not None and len(ctx) else empty,
         "seams": geo(gpd.GeoDataFrame(pd.concat(seams), crs=TN_SP), ["side_a", "side_b", "seam_type"], 15) if seams else empty,
         "annexations": geo(gpd.GeoDataFrame(pd.concat(annex), crs=TN_SP), ["Annex_Num", "city"], 20) if annex else empty,
         "roads": geo(gpd.GeoDataFrame(pd.concat(roads), crs=TN_SP), ["LABEL", "cls"], 30) if roads else empty,
         "band_pts": [[round(float(a), 6), round(float(b), 6), 0 if c == "CRITICAL" else 1] for a, b, c in zip(band.lon, band.lat, band.risk_band)] if len(band) else [],
         "band_total": band_total, "biz_fields": BIZ_FIELDS, "biz": rows,
         "biz_min_fields": ["id", "business", "source", "dor_situs", "lon", "lat"], "biz_min": mins,
         "flag_counts": fc, "clear_total": clear_total, "clear_kept": clear_kept,
         "summary": {"city": display, "counties": counties, "situs": codes, "stats": st, "rubric": "v2", "confidential_dor_data_used": False}}
    (dst / "wbdata.js").write_text("window.WB=" + json.dumps(P, separators=(",", ":")) + ";")
    html = re.sub(r"<title>Situs Workbench[^<]*</title>", f"<title>Situs Workbench — {display}</title>", template_html, count=1)
    html = re.sub(r'(class="county">)[^<]*', lambda m: m.group(1) + P["chip"], html, count=1)
    (dst / "workbench.html").write_text(html)
    (dst / "wb.js").write_text(wbjs)
    size = (dst / "wbdata.js").stat().st_size / 1e6
    return {"city": display, "slug": slug, "counties": counties, "codes": codes, **st, "labels": len(rows), "mb": round(size, 2)}


# ----------------------------------------------------------------------------- wb.js for cities
def city_wbjs(src: str) -> str:
    """Four targeted patches to the county wb.js. Each must match exactly once or the build stops."""
    def sub1(s, old, new, label, regex=False):
        n = len(re.findall(old, s, re.S)) if regex else s.count(old)
        if n != 1: raise SystemExit(f"wb.js patch '{label}' matched {n} times; template changed — update build_cities.city_wbjs")
        return re.sub(old, new, s, count=1, flags=re.S) if regex else s.replace(old, new)
    s = src.replace("/* Situs Workbench — Wilson County.", "/* Situs Workbench — city view.", 1)
    s = sub1(s, 'if (cc) cc.textContent = W.county + " · TN · " + SITCODES[0] + "–" + SITCODES[SITCODES.length - 1];',
             'if (cc) cc.textContent = W.chip || (W.county + " · TN · " + SITCODES[0] + "–" + SITCODES[SITCODES.length - 1]);', "chip")
    s = sub1(s, 'q[F.postal_county] !== "WILSON"', '(W.homes || ["WILSON"]).indexOf(q[F.postal_county]) < 0', "home county")
    s = sub1(s, r"'<div class=\"sec\"><h3>What the request asks for</h3>.*?</div></div>';",
             "'<div class=\"sec\"><h3>What the request asks for</h3><ul><li>Situs code' + ((W.own_codes||[]).length===1?'':'s') + ' for ' + esc(W.county_label||W.county) + ': <span class=\"mono\">' + (W.own_codes||[]).join(' ') + '</span></li>"
             "<li>Name · DBA · account id · physical address · mailing address · ZIP · situs · status · registration date · location id · as-of date</li>"
             "<li>Situs-code table, correction procedure, lookback authority, REP access, contractor requirements</li></ul>"
             "<p>Cities request their own situs report from the Department under T.C.A. § 67-1-1704(d); the ZIP list is the city\\'s ZIPs plus the surrounding ring.</p></div>';",
             "request pack", regex=True)
    s = sub1(s, "not physically in Wilson County", 'not physically in " + esc(W.county_label || W.county) + "', "county name 1")
    s = sub1(s, "a Wilson-coded business with no Wilson rooftop", 'a business coded to " + esc(W.county_label || W.county) + " with no rooftop there', "county name 2")
    return s


# ----------------------------------------------------------------------------- index
CSS = """
:root{--paper:#F4F5F2;--surface:#fff;--surface-2:#EDEFEB;--ink:#16202B;--ink-2:#3D4B57;--ink-3:#6B7A86;--rule:#D2D8DB;--rule-2:#E3E7E6;--accent:#1F5C7A;--crit:#A8322D;--high:#B0722A;--watch:#5E7686;--clear:#3A7358}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}}
:root[data-theme="dark"]{--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;font-size:15px;line-height:1.55}
.wrap{max-width:1240px;margin:0 auto;padding-inline:20px;padding-block:0 60px}
header{border-bottom:2px solid var(--ink);background:var(--surface)} .hin{max-width:1240px;margin:0 auto;padding:26px 20px 18px}
.eyebrow{font-family:Archivo,sans-serif;font-size:.68rem;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}
h1{font-family:Archivo,sans-serif;font-size:2rem;font-weight:700;letter-spacing:-.02em;margin:.15em 0 .2em}
.sub{color:var(--ink-2);max-width:70ch}
.views{display:flex;gap:2px;margin:14px 0 0;font-family:Archivo,sans-serif;font-size:.74rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
.views a{padding:7px 14px;border:1px solid var(--rule);border-bottom:0;color:var(--ink-3);background:var(--surface-2);text-decoration:none}
.views a.on{color:var(--ink);background:var(--surface);border-color:var(--ink);border-bottom:2px solid var(--surface);margin-bottom:-2px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border:1px solid var(--rule);background:var(--surface);margin:26px 0}
.tiles div{padding:14px 16px;border-right:1px solid var(--rule-2)} .tiles div:last-child{border-right:0}
.k{font-family:Archivo,sans-serif;font-size:.66rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)} .v{font-family:"IBM Plex Mono",monospace;font-size:1.4rem;margin-top:4px}
.tools{display:flex;gap:10px;align-items:center;margin:0 0 10px;font-family:Archivo,sans-serif;font-size:.78rem}
.tools input{font:inherit;padding:6px 9px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);min-width:240px}
.tbox{border:1px solid var(--rule);background:var(--surface);overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.82rem} th{position:sticky;top:0;background:var(--surface-2);font-family:Archivo,sans-serif;font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);white-space:nowrap;cursor:pointer}
th.n{text-align:right} td{padding:7px 10px;border-bottom:1px solid var(--rule-2)} td.n{font-family:"IBM Plex Mono",monospace;text-align:right;font-variant-numeric:tabular-nums} tr:hover{background:var(--surface-2)}
td.crit{color:var(--crit);font-weight:600} td.high{color:var(--high)} td.watch{color:var(--watch)} td.fav{color:var(--clear);font-weight:600} td.cty{color:var(--ink-3);font-size:.78rem}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent} a:hover{border-bottom-color:var(--accent)}
.note{border-left:3px solid var(--accent);background:var(--surface);padding:12px 16px;margin:22px 0;color:var(--ink-2);max-width:78ch;font-size:.92rem}
footer{margin-top:36px;font-size:.8rem;color:var(--ink-3);max-width:80ch}
"""
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">'


def n(v): return "—" if v is None else f"{v:,.0f}"


def write_index(rows: list[dict]) -> None:
    tot = {k: sum(r[k] for r in rows) for k in ("rooftops", "biz", "cc", "br", "pe", "file_elsewhere", "file_uninc", "file_claims", "layers_claim")}
    multi = sum(1 for r in rows if len(r["counties"]) > 1)
    trs = []
    for r in sorted(rows, key=lambda r: -r["biz"]):
        cty = ", ".join(c.title() for c in r["counties"])
        trs.append(f'<tr data-q="{r["city"].lower()} {cty.lower()}"><td><a href="./{r["slug"]}/">{r["city"]} ↗</a></td><td class="cty">{cty}</td>'
                   f'<td class="n">{" ".join(r["codes"])}</td><td class="n">{n(r["rooftops"])}</td><td class="n">{n(r["biz"])}</td>'
                   f'<td class="n crit">{n(r["cc"])}</td><td class="n high">{n(r["br"])}</td><td class="n watch">{n(r["pe"])}</td>'
                   f'<td class="n fav">{n(r["file_elsewhere"])}</td><td class="n">{n(r["file_claims"])}</td><td class="n fav">{n(r["layers_claim"])}</td></tr>')
    html = f'''<title>Tennessee Situs Atlas — Cities</title>
{FONTS}
<style>{CSS}</style>
<header><div class="hin"><div class="eyebrow">Civvix · Tennessee · public data only · $0 acquisition cost</div><h1>Tennessee Situs Atlas</h1>
<div class="sub">Every incorporated city, scoped from its county run: the businesses and rooftops inside the city's own Department of Revenue situs polygon, the businesses outside it that carry the city's mailing address, and the rooftops the State's own address file codes away from the city. Same rubric, same evidence, same workbench as the county pages. No confidential data was used.</div>
<nav class="views"><a href="../">Counties</a><a class="on" href="./">Cities</a></nav></div></header>
<div class="wrap">
<div class="tiles"><div><div class="k">Cities</div><div class="v">{len(rows)}</div></div><div><div class="k">Multi-county</div><div class="v">{multi}</div></div><div><div class="k">Rooftops inside cities</div><div class="v">{tot["rooftops"]:,}</div></div><div><div class="k">Businesses inside</div><div class="v">{tot["biz"]:,}</div></div><div><div class="k">Cross-county postal</div><div class="v" style="color:var(--crit)">{tot["cc"]:,}</div></div><div><div class="k">File says elsewhere</div><div class="v" style="color:var(--clear)">{tot["file_elsewhere"]:,}</div></div><div><div class="k">File claims city</div><div class="v">{tot["file_claims"]:,}</div></div><div><div class="k">Other layers say city</div><div class="v" style="color:var(--clear)">{tot["layers_claim"]:,}</div></div></div>
<div class="note"><b>How to read this.</b> <i>Cross-county postal</i> and <i>boundary risk</i> are businesses inside the city polygon flagged as on the county page. <i>Postal exposure</i> is a business <b>outside</b> the polygon carrying this city's mailing address — where a mailing-address registration would have coded it to the city. <i>File says elsewhere</i> is the city's counter-finding: rooftops inside the polygon that the State's own address-range file codes to another jurisdiction, usually the county's unincorporated code; corrected, those move money <b>to</b> the city. <i>File claims city</i> is the reverse — rooftops outside the polygon the file codes to the city. <i>Other layers say city</i> is the strongest counter-finding: rooftops the Department places outside the city while both the 911 authority and the Comptroller's certified limits place them inside it. None of these is a finding until the city's situs report is compared.</div>
<div class="tools"><input id="q" type="search" placeholder="Filter by city or county" aria-label="Filter cities"><span id="cnt"></span></div>
<div class="tbox"><table id="t"><thead><tr><th>City</th><th>County</th><th class="n">Situs</th><th class="n">Rooftops</th><th class="n">Businesses</th><th class="n">Cross-county postal</th><th class="n">Boundary risk</th><th class="n">Postal exposure</th><th class="n">File says elsewhere</th><th class="n">File claims city</th><th class="n">Other layers say city</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>
<footer>Sources as on the county atlas. City polygons are the Department of Revenue's own situs polygons; a city that spans counties has one code per county and is shown once with every part. Business counts are named businesses only. Public-data screening; not an audit finding.</footer>
</div>
<script>
(function(){{var q=document.getElementById("q"),rows=[].slice.call(document.querySelectorAll("#t tbody tr")),cnt=document.getElementById("cnt");
function f(){{var v=q.value.trim().toLowerCase(),k=0;rows.forEach(function(r){{var on=!v||r.dataset.q.indexOf(v)>=0;r.style.display=on?"":"none";if(on)k++;}});cnt.textContent=k+" of "+rows.length;}}
q.addEventListener("input",f);f();
[].forEach.call(document.querySelectorAll("#t th"),function(th,i){{th.addEventListener("click",function(){{var tb=th.closest("table").tBodies[0],rs=[].slice.call(tb.rows),num=th.classList.contains("n"),asc=th.dataset.asc!=="1";
rs.sort(function(a,b){{var x=a.cells[i].textContent.replace(/[,—↗]/g,"").trim(),y=b.cells[i].textContent.replace(/[,—↗]/g,"").trim();if(num){{x=parseFloat(x)||0;y=parseFloat(y)||0;return asc?y-x:x-y;}}return asc?x.localeCompare(y):y.localeCompare(x);}});
rs.forEach(function(r){{tb.appendChild(r);}});[].forEach.call(th.parentNode.children,function(h){{delete h.dataset.asc;}});th.dataset.asc=asc?"1":"0";}});}});}})();
</script>'''
    (ART / "cities.html").write_text(html)
    (OUTD / "cities_index.json").write_text(json.dumps({"totals": tot, "cities": rows}, indent=1))


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--city", nargs="*", help="city slug(s); default all"); a = ap.parse_args()
    only = {slugify(c) for c in a.city} if a.city else None
    wh = Warehouse(); dor = load_dor(wh)
    template = (ART / "workbench.html").read_text(); wbjs = city_wbjs((ART / "wb.js").read_text())
    print("collecting city parts from county outputs", flush=True)
    cities = collect(wh, dor, only)
    print(f"{len(cities)} cities; building pages", flush=True)
    rows = []
    for key in sorted(cities):
        r = build_city(key, cities[key], template, wbjs); rows.append(r)
        print(f"  {r['city']:<24} {'/'.join(c.title() for c in r['counties']):<22} biz {r['biz']:>6,}  cc {r['cc']:>4}  br {r['br']:>4}  pe {r['pe']:>5}  file→elsewhere {r['file_elsewhere']:>6,}  {r['mb']} MB")
    if only is None:
        write_index(rows)
        print(f"cities index: {len(rows)} cities -> {ART / 'cities.html'}")
    else:
        print("(partial run; index not rewritten)")


if __name__ == "__main__":
    main()
