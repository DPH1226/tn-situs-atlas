"""
Minimal ArcGIS REST client: paged queries with retries, change signals.

Every public layer used by the platform is an ArcGIS FeatureServer/MapServer.
The paging rule is the same everywhere: maxRecordCount (usually 2000) and
resultOffset. This module is the only place that knows that.
"""
from __future__ import annotations
import json, time
from typing import Iterator
import requests

UA = {"User-Agent": "civvix-situs/1.0 (+https://civvix.ai)"}


def _get(url: str, params: dict, tries: int = 3, timeout: int = 120) -> dict:
    last = None
    for t in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(f"{url}: {json.dumps(j['error'])[:200]}")
            return j
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (t + 1))
    raise RuntimeError(f"{url} failed after {tries} tries: {last}")


def layer_info(url: str) -> dict:
    """lastEditDate, maxRecordCount, fields — the cheap change signal."""
    j = _get(url, {"f": "json"})
    ei = j.get("editingInfo") or {}
    return {
        "name": j.get("name"),
        "lastEditDate": ei.get("lastEditDate") or ei.get("dataLastEditDate"),
        "maxRecordCount": j.get("maxRecordCount", 2000),
        "fields": [f["name"] for f in j.get("fields", [])],
        "geometryType": j.get("geometryType"),
        "description": (j.get("description") or "")[:300],
    }


def count(url: str, where: str = "1=1") -> int:
    return int(_get(url + "/query", {"where": where, "returnCountOnly": "true", "f": "json"}).get("count", 0))


def query_all(url: str, where: str = "1=1", out_fields: str = "*", geom: bool = True,
              precision: int = 6, page: int | None = None) -> Iterator[dict]:
    """Yield features (GeoJSON features if geom else attribute dicts)."""
    info = layer_info(url)
    page = page or int(info.get("maxRecordCount") or 2000)
    offset = 0
    while True:
        params = {
            "where": where, "outFields": out_fields, "returnGeometry": str(geom).lower(),
            "outSR": "4326", "f": "geojson" if geom else "json",
            "resultOffset": str(offset), "resultRecordCount": str(page), "geometryPrecision": str(precision),
        }
        j = _get(url + "/query", params)
        feats = j.get("features") or []
        for f in feats:
            yield f if geom else f.get("attributes", {})
        if len(feats) < page:
            break
        offset += len(feats)


def fetch_to_file(url: str, path: str, where: str = "1=1", out_fields: str = "*", geom: bool = True) -> int:
    """Stream a whole layer to disk as GeoJSON (or a JSON array for tables). Returns count."""
    n = 0
    with open(path, "w") as fh:
        if geom:
            fh.write('{"type":"FeatureCollection","features":[')
        else:
            fh.write("[")
        for f in query_all(url, where, out_fields, geom):
            if n:
                fh.write(",")
            fh.write(json.dumps(f, separators=(",", ":")))
            n += 1
        fh.write("]}" if geom else "]")
    return n
