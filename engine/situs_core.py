"""
Civvix situs engine - core geometry layer.

Ground-truth hierarchy for SALES TAX situs (highest first):
  1. TN DOR Sales Tax Rate Boundary polygon        (authoritative; what DOR bills against)
  2. TN SST address-range lookup                   (DOR's own address-level assignment)
  3. Certified municipal boundary from the custodian
  4. County parcel / address-point geometry
  5. Local parcel / building / permit evidence
  6. Commercial geocoders - corroboration only

ZIP codes and postal city names are NEVER jurisdictional proof. They are,
however, the single best predictor of WHERE a miscode will be found, because
registrations are keyed off mailing addresses.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from shapely.validation import explain_validity, make_valid

# NAD83 / Tennessee State Plane, US survey feet.
# All distance math happens here. Never measure feet in degrees.
TN_STATE_PLANE = "EPSG:2274"
WGS84 = "EPSG:4326"

# Boundary risk bands, in feet, per the GIS validation protocol.
BANDS = [
    (0, 50, "CRITICAL", "mandatory human adjudication"),
    (50, 250, "HIGH", "elevated review: verify every official layer before submission"),
    (250, 1000, "WATCH", "automated, but re-check on any boundary change"),
    (1000, float("inf"), "NORMAL", "normal automated processing"),
]


def band_for(distance_ft: float) -> tuple[str, str]:
    for lo, hi, name, action in BANDS:
        if lo <= distance_ft < hi:
            return name, action
    return "NORMAL", "normal automated processing"


@dataclass
class SourceRecord:
    """Provenance for one ingested layer. Rule 2: preserve effective dates."""
    layer: str
    role: str
    custodian: str
    source_url: str
    path: str
    sha256: str
    feature_count: int
    native_crs: str
    downloaded_utc: str
    stated_effective_date: str | None = None
    update_cadence: str | None = None
    notes: str = ""
    geometry_repairs: int = 0
    repair_detail: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_layer(
    path: str | Path,
    *,
    layer: str,
    role: str,
    custodian: str,
    source_url: str,
    effective_date: str | None = None,
    cadence: str | None = None,
    notes: str = "",
) -> tuple[gpd.GeoDataFrame, SourceRecord]:
    """
    Load a GeoJSON layer, record its hash and provenance, reproject to TN State
    Plane, and repair invalid polygons WITHOUT silently mutating the original.

    Every repair is counted and described. A layer that needed repairs is not
    disqualified, but the count belongs in the QA report -- if the county's
    certified boundary needed 40 fixes to become valid, the client should know.
    """
    path = Path(path)
    gdf = gpd.read_file(path)
    native = str(gdf.crs) if gdf.crs else "unknown"
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)

    repairs, detail = 0, []
    fixed = []
    for idx, geom in zip(gdf.index, gdf.geometry):
        if geom is None:
            fixed.append(None)
            continue
        if not geom.is_valid:
            repairs += 1
            if len(detail) < 25:
                detail.append(f"idx={idx}: {explain_validity(geom)[:120]}")
            fixed.append(make_valid(geom))
        else:
            fixed.append(geom)
    gdf = gdf.set_geometry(gpd.GeoSeries(fixed, index=gdf.index, crs=gdf.crs))
    gdf = gdf.to_crs(TN_STATE_PLANE)

    rec = SourceRecord(
        layer=layer,
        role=role,
        custodian=custodian,
        source_url=source_url,
        path=str(path),
        sha256=sha256_of(path),
        feature_count=len(gdf),
        native_crs=native,
        downloaded_utc=datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        stated_effective_date=effective_date,
        update_cadence=cadence,
        notes=notes,
        geometry_repairs=repairs,
        repair_detail=detail,
    )
    return gdf, rec


def jurisdiction_seams(polys: gpd.GeoDataFrame, key: str) -> gpd.GeoDataFrame:
    """
    Return the SEAMS between differently-coded jurisdictions, not every polygon
    edge.

    This is the distinction that makes the 50/250-ft rule mean something. The
    outer edge of the DOR Wilson County coverage where it meets Davidson County
    is a seam and it matters enormously. The edge of a polygon where it meets
    nothing (the data's outer hull) is not a jurisdictional fact.

    Returned rows carry both sides: side_a / side_b, so a finding can say
    "41 ft outside Mt. Juliet, inside unincorporated Wilson" rather than the
    useless "near a boundary".
    """
    rows = []
    idx = polys.sindex
    for i, a in polys.iterrows():
        for j in idx.query(a.geometry, predicate="intersects"):
            b = polys.iloc[j]
            if str(a[key]) >= str(b[key]):
                continue  # each unordered pair once
            shared = a.geometry.boundary.intersection(b.geometry.boundary)
            if shared.is_empty or shared.length == 0:
                continue
            rows.append({
                "side_a": a[key],
                "side_b": b[key],
                "seam_len_ft": shared.length,
                "geometry": shared,
            })
    if not rows:
        return gpd.GeoDataFrame(
            columns=["side_a", "side_b", "seam_len_ft", "geometry"],
            geometry="geometry", crs=polys.crs,
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=polys.crs)


def write_manifest(records: list[SourceRecord], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "crs_for_distance_math": TN_STATE_PLANE,
        "bands_ft": [
            {"low": lo, "high": None if hi == float("inf") else hi,
             "band": nm, "action": act} for lo, hi, nm, act in BANDS
        ],
        "sources": [r.to_dict() for r in records],
    }
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path
