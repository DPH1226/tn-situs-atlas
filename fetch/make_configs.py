#!/usr/bin/env python3
"""
Generate a config for every Tennessee county from the DOR tax-rate layer.

Situs codes and names come straight from the Department's own polygons, so
they cannot be mistyped. County-specific extras (business layers, city GIS,
consolidated-government merges) are preserved when a config already exists;
otherwise the SOS entity file is wired in when present, and everything else
is left for discovery. The postal-county map is NOT written here: it is
derived statewide from the rooftops themselves (fetch/postal_map.py).
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from warehouse.store import Warehouse

FIPS = {}  # county name -> fips, from the DOR layer's COUNTYFIPS
CONSOLIDATED = {"DAVIDSON": {"1900": "1901"}, "MOORE": None, "TROUSDALE": None}  # Lynchburg-Moore, Hartsville-Trousdale checked below


def main():
    dor = Warehouse().load("dor_tax_rate_boundaries", "TN")
    dor["SITUS"] = dor.SITUS.astype(str)
    made, kept = [], []
    for county, g in dor.groupby("COUNTY"):
        slug = county.lower().replace(" ", "")
        path = ROOT / "configs" / f"{slug}.yaml"
        fips = str(g["COUNTYFIPS"].iloc[0])
        situs = {row.SITUS: ("Unincorporated" if row.SITUS.endswith("00") else str(row.CITY).title().replace("Mt. ", "Mt. ")) for row in g.sort_values("SITUS").itertuples()}
        if path.exists():
            cfg = yaml.safe_load(path.read_text())
            cfg["situs"] = {**situs, **{k: v for k, v in cfg.get("situs", {}).items() if k in situs}}
            kept.append(slug)
        else:
            cfg = {"county": county, "fips": fips, "situs": situs,
                   "tiers": {"parcels": "comptroller", "business": "sos"}, "business_layers": [], "city_layers": []}
            if county in ("CHESTER", "HAMILTON", "HICKMAN", "KNOX", "MONTGOMERY", "SHELBY", "WILLIAMSON"):
                cfg["tiers"]["parcels"] = "county"
            # consolidated governments: two codes, one treasury
            if county == "MOORE" and {"6000", "6001"} <= set(situs): cfg["situs_merge"] = {"6000": "6001"}
            if county == "TROUSDALE" and len(situs) == 2: cfg["situs_merge"] = {min(situs): max(situs)}
            made.append(slug)
        sos = ROOT / "data" / "sos" / f"{slug}_county_all_records_from_SOS.tsv"
        if sos.exists() and not any(L.get("type") == "sos_tsv" for L in cfg["business_layers"]):
            cfg["business_layers"].insert(0, {"id": f"{slug}_sos_entities", "type": "sos_tsv", "path": str(sos.relative_to(ROOT)),
                                              "name_field": "EntityName", "notes": "TN SOS active for-profit entities geocoded to NG911 rooftops."})
        path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    print(f"configs: {len(made)} created, {len(kept)} updated; total {len(made)+len(kept)}")


if __name__ == "__main__":
    main()
