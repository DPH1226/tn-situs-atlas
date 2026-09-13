"""
Boundary QA: prove the geography before anyone's tax coding is questioned.

This runs BEFORE taxpayer analysis, on purpose. Telling a Finance Director that
the Department of Revenue has miscoded a business is a serious claim. It should
never rest on geometry nobody has checked.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString

from .situs_core import TN_STATE_PLANE, band_for, jurisdiction_seams


def assign_situs(points: gpd.GeoDataFrame, dor: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Spatially place each point in the authoritative DOR tax-rate polygon."""
    keep = ["SITUS", "COUNTY", "COUNTYFIPS", "CITY", "CITYFIPS", "TAXRATE", "geometry"]
    d = dor[[c for c in keep if c in dor.columns]].copy()
    out = gpd.sjoin(points, d, how="left", predicate="within")
    out = out.drop(columns=[c for c in out.columns if c.startswith("index_")])
    out = out.rename(columns={
        "SITUS": "dor_situs", "COUNTY": "dor_county", "COUNTYFIPS": "dor_county_fips",
        "CITY": "dor_city", "CITYFIPS": "dor_city_fips", "TAXRATE": "dor_rate",
    })
    # A point that lands in no polygon is not a small problem. It means the
    # authoritative layer does not cover it, and nothing downstream is safe.
    return out[~out.index.duplicated(keep="first")]


def distance_to_seams(
    points: gpd.GeoDataFrame, seams: gpd.GeoDataFrame
) -> pd.DataFrame:
    """
    For every point: distance in feet to the nearest jurisdictional seam, and
    which two jurisdictions that seam divides.

    This is the "both sides" calculation. Knowing a point is 41 ft from a line
    is useless; knowing it is 41 ft OUTSIDE Mt. Juliet and inside unincorporated
    Wilson is an audit finding.
    """
    if seams.empty:
        return pd.DataFrame(index=points.index, data={
            "nearest_seam_ft": pd.NA, "seam_side_a": pd.NA, "seam_side_b": pd.NA,
            "risk_band": "NORMAL", "risk_action": "normal automated processing",
        })
    j = gpd.sjoin_nearest(
        points[["geometry"]], seams[["side_a", "side_b", "geometry"]],
        how="left", distance_col="nearest_seam_ft",
    )
    j = j[~j.index.duplicated(keep="first")]
    bands = j["nearest_seam_ft"].apply(lambda d: band_for(float(d)) if pd.notna(d) else ("NORMAL", "normal automated processing"))
    j["risk_band"] = [b[0] for b in bands]
    j["risk_action"] = [b[1] for b in bands]
    return j[["nearest_seam_ft", "side_a", "side_b", "risk_band", "risk_action"]].rename(
        columns={"side_a": "seam_side_a", "side_b": "seam_side_b"}
    )


def layer_agreement(df: pd.DataFrame, aliases: dict | None = None) -> pd.DataFrame:
    """
    Rule 5: escalate where the official layers disagree.

    Three independent statements about the same rooftop:
      dor_city   - TN Dept of Revenue tax-rate polygon (what DOR bills against)
      Inc_Muni   - the local 911 addressing authority's municipality
      comp_city  - TN Comptroller OLG certified municipal boundary

    Post_City is deliberately EXCLUDED from agreement scoring. It is a USPS
    delivery convenience and is not a statement about jurisdiction at all. It
    earns its own exception class instead, because it is what taxpayers
    actually key their registrations off.
    """
    def norm(v):
        if pd.isna(v):
            return ""
        # DOR writes the unincorporated area as the literal string
        # "(Unincorporated)". The Comptroller layer simply has no polygon there,
        # so the field arrives null. The 911 layer says "Unincorporated".
        # All three mean the same thing; only the punctuation differs, and
        # failing to strip it manufactures a disagreement on every rural
        # address in the county.
        s = str(v).strip().upper().replace(".", "").replace("(", "").replace(")", "")
        s = s.replace("MOUNT ", "MT ").strip()
        if s in {"UNINCORPORATED", "UNINCORPORATED AREA", "NONE", "NULL", ""}:
            s = "UNINCORPORATED"
        return (aliases or {}).get(s, s)

    dor = df.get("dor_city", pd.Series(index=df.index, dtype=object)).apply(norm)
    e911 = df.get("Inc_Muni", pd.Series(index=df.index, dtype=object)).apply(norm)
    comp = df.get("comp_city", pd.Series(index=df.index, dtype=object)).apply(norm)

    out = pd.DataFrame(index=df.index)
    out["muni_dor"] = dor
    out["muni_e911"] = e911
    out["muni_comptroller"] = comp
    stated = pd.concat([dor, e911, comp], axis=1)
    out["layers_available"] = (stated != "").sum(axis=1)
    out["layers_agree"] = stated.apply(
        lambda r: len({v for v in r if v != ""}) <= 1, axis=1
    )
    out["disagreement"] = out.apply(
        lambda r: "" if r["layers_agree"] else
        f"DOR={r['muni_dor'] or '-'} | E911={r['muni_e911'] or '-'} | COMP={r['muni_comptroller'] or '-'}",
        axis=1,
    )
    return out


def build_seams(dor: gpd.GeoDataFrame, county: str | None = None) -> gpd.GeoDataFrame:
    """
    Jurisdictional seams relevant to one county's audit.

    Includes seams between two Wilson situs codes (city/unincorporated errors)
    AND seams where Wilson meets another county (cross-county errors, which cost
    both halves of the local option tax and are therefore worth far more).
    """
    seams = jurisdiction_seams(dor, "SITUS")
    if county is None:
        return seams
    lookup = dor.set_index("SITUS")["COUNTY"].to_dict()
    seams["county_a"] = seams["side_a"].map(lookup)
    seams["county_b"] = seams["side_b"].map(lookup)
    rel = (seams["county_a"] == county) | (seams["county_b"] == county)
    seams = seams[rel].copy()
    seams["seam_type"] = seams.apply(
        lambda r: "INTRA_COUNTY" if r["county_a"] == r["county_b"] else "CROSS_COUNTY",
        axis=1,
    )
    # Cross-county seams cost both the situs half and the education half.
    seams["loss_exposure"] = seams["seam_type"].map(
        {"CROSS_COUNTY": "both halves", "INTRA_COUNTY": "situs half only"}
    )
    return seams
