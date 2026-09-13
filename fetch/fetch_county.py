#!/usr/bin/env python3
"""
Fetch (or ingest) every layer a county needs, into the snapshot warehouse.

Two transports, one result:
  --live            pull from the ArcGIS endpoints (needs internet: GitHub Actions, a laptop)
  --from-dir DIR    ingest files a browser already downloaded (the egress-blocked case)

Either way every layer lands as a hashed, dated snapshot with a manifest, and
the catalog knows whether anything actually changed.

    python3 fetch/fetch_county.py --county WILSON --live
    python3 fetch/fetch_county.py --county SUMNER --from-dir ~/Downloads/civvix-wilson-situs/data/raw
    python3 fetch/fetch_county.py --statewide --live
"""
from __future__ import annotations
import argparse, json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import config, arcgis
from warehouse.store import Warehouse

# Filenames the browser script (ingest/acquire_county.js) and the Chrome pulls used.
# Keeps the two transports interchangeable.
BROWSER_NAMES = {
    "dor_tax_rate_boundaries": ["dor_tax_rate_boundaries_TN_statewide.geojson"],
    "dor_cbid": ["dor_cbid_boundaries.geojson"],
    "dor_tdz": ["dor_tdz_boundaries.geojson"],
    "comptroller_cities": ["tn_sst_city_boundaries.geojson"],
    "sst_counties": ["sst_counties.geojson"],
    "sst_address_lookup": ["sst_address_lookup_{slug}.json"],
    "ng911_address_points": ["{slug}_ng911_address_points.geojson"],
    "ng911_roads": ["{slug}_ng911_roads.geojson"],
}
STATEWIDE_SCOPE = {"dor_tax_rate_boundaries", "dor_cbid", "dor_tdz", "comptroller_cities", "sst_counties"}


def _scope(layer_id: str, slug: str) -> str:
    return "TN" if layer_id in STATEWIDE_SCOPE else slug


def plan(county_cfg: dict | None) -> list[dict]:
    """Every (layer, url, where, scope) this run must consider."""
    sw = config.statewide()
    items = []
    for L in sw["layers"]:
        scope = "TN" if L["id"] in STATEWIDE_SCOPE else (county_cfg["slug"] if county_cfg else None)
        if scope is None:
            continue
        where = "1=1"
        if county_cfg and L["id"] not in STATEWIDE_SCOPE:
            if "county_where" in L:
                where = L["county_where"].format(county=county_cfg["county"])
            elif "county_field" in L:
                where = f"{L['county_field']}='{county_cfg['county']}'"
        items.append(dict(id=L["id"], url=L["url"], where=where, scope=scope, geom=L.get("geom", True),
                          out_fields=L.get("out_fields", "*"), custodian=L.get("custodian", ""),
                          files=[n.format(slug=scope) for n in BROWSER_NAMES.get(L["id"], [])]))
    if county_cfg:
        for L in county_cfg.get("business_layers", []) + county_cfg.get("city_layers", []):
            if L.get("path"):        # file-based source (e.g. SOS TSV) - not fetched
                continue
            items.append(dict(id=L["id"], url=L["url"], where=L.get("where", "1=1"), scope=county_cfg["slug"],
                              geom=L.get("geom", True), out_fields=L.get("out_fields", "*"),
                              custodian=L.get("name", ""), files=[L["id"] + (".geojson" if L.get("geom", True) else ".json")]))
        if county_cfg.get("parcel_layer"):
            items.append(dict(id="parcels", url=county_cfg["parcel_layer"]["url"], where="1=1", scope=county_cfg["slug"],
                              geom=True, out_fields="*", custodian="county", files=[f"{county_cfg['slug']}_parcels.geojson"]))
    return items


def run(county: str | None, live: bool, from_dir: Path | None, force: bool, only: set[str] | None) -> list[dict]:
    wh = Warehouse()
    cfg = config.county(county) if county else None
    results = []
    for it in plan(cfg):
        if only and it["id"] not in only:
            continue
        rec = None
        if live:
            info = arcgis.layer_info(it["url"])
            prev = wh.latest(it["id"], it["scope"])
            n = arcgis.count(it["url"], it["where"])
            if prev and not force and prev.get("last_edit_date") == info.get("lastEditDate") and prev["feature_count"] == n:
                results.append({"layer": it["id"], "scope": it["scope"], "status": "unchanged (edit date + count)"})
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".geojson" if it["geom"] else ".json", delete=False) as tmp:
                pass
            got = arcgis.fetch_to_file(it["url"], tmp.name, it["where"], it["out_fields"], it["geom"])
            rec = wh.ingest(it["id"], it["scope"], Path(tmp.name), source_url=it["url"], where=it["where"],
                            last_edit_date=info.get("lastEditDate"), notes=it["custodian"])
            rec["fetched"] = got
        elif from_dir:
            src = next((from_dir / f for f in it["files"] if (from_dir / f).exists()), None)
            if src is None:
                results.append({"layer": it["id"], "scope": it["scope"], "status": "no file in dir",
                                "expected": it["files"]})
                continue
            rec = wh.ingest(it["id"], it["scope"], src, source_url=it["url"], where=it["where"], notes=it["custodian"])
        else:
            results.append({"layer": it["id"], "scope": it["scope"], "status": "dry-run", "url": it["url"], "where": it["where"]})
            continue
        results.append({"layer": it["id"], "scope": it["scope"],
                        "status": "unchanged (hash)" if rec.get("unchanged") else "ingested",
                        "features": rec["feature_count"], "repairs": rec.get("geometry_repairs"), "snap": rec["snap_date"]})
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--county")
    ap.add_argument("--statewide", action="store_true", help="statewide layers only")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--from-dir")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if not a.county and not a.statewide:
        ap.error("--county NAME or --statewide")
    res = run(None if a.statewide else a.county, a.live, Path(a.from_dir).expanduser() if a.from_dir else None,
              a.force, set(a.only) if a.only else None)
    for r in res:
        print(json.dumps(r))
