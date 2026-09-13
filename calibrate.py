#!/usr/bin/env python3
"""
Calibration: how well do the public-data exception classes predict actual miscoding?

Input: any roster with a coded situs per business — the DOR situs report when it
arrives, or (today) a city-published business-tax roster. The roster never
leaves the machine this runs on. Output: a confusion matrix per exception
class, which is the honest number to put in front of a county.

    python3 calibrate.py --county SUMNER --source hendersonville_business_licenses --exclude-class4
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from warehouse.store import Warehouse


def calibrate(county: str, source: str, exclude_class4: bool) -> dict:
    slug = county.lower()
    b = pd.read_csv(ROOT / "out" / slug / "business_exceptions.csv", low_memory=False)
    b = b[(b.source == source) & b.coded_situs.notna()].copy()
    b["coded_situs"] = b.coded_situs.astype(str).str[:4]; b["dor_situs"] = b.dor_situs.astype(str).str[:4]
    if exclude_class4:
        h = Warehouse().load(source, slug)
        cls = h.drop_duplicates("Doing_Business_As").set_index("Doing_Business_As")["Classification_Type"].astype(str)
        b = b[~b.business.map(cls).eq("4")]
    b["truth_mismatch"] = b.coded_situs != b.dor_situs
    # Use the class columns, never `flag`: a roster match overwrites flag with CODED_MISMATCH,
    # which would hide exactly the rows a calibration exists to count.
    b["exposure"] = b.E1_POSTAL_CITY_OVERSTATES.fillna(False).astype(bool) | b.E2_CROSS_COUNTY_POSTAL.fillna(False).astype(bool)
    b["boundary"] = b.risk_band.isin(["CRITICAL", "HIGH"])
    b["any_flag"] = b.exposure | b.boundary | b.E4_LAYER_DISAGREEMENT.fillna(False) | b.E5_DOR_INTERNAL_CONFLICT.fillna(False)
    def cm(col):
        tp = int((b[col] & b.truth_mismatch).sum()); fp = int((b[col] & ~b.truth_mismatch).sum())
        fn = int((~b[col] & b.truth_mismatch).sum()); tn = int((~b[col] & ~b.truth_mismatch).sum())
        prec = tp / (tp + fp) if tp + fp else None; rec = tp / (tp + fn) if tp + fn else None
        return {"flagged": tp + fp, "true_positive": tp, "false_positive": fp, "missed": fn, "true_negative": tn,
                "precision": None if prec is None else round(prec, 3), "recall": None if rec is None else round(rec, 3)}
    out = {"county": county, "source": source, "rows_compared": int(len(b)), "exclude_class4": exclude_class4,
           "base_rate_mismatch": round(float(b.truth_mismatch.mean()), 4), "mismatches": int(b.truth_mismatch.sum()),
           "by_class": {"postal_exposure (E1+E2)": cm("exposure"), "boundary_band (E3)": cm("boundary"), "any_flag": cm("any_flag")},
           "direction": {f"{a} -> {c}": int(n) for (a, c), n in b[b.truth_mismatch].groupby(["coded_situs", "dor_situs"]).size().items()},
           "mismatch_rows": b.loc[b.truth_mismatch, ["business", "Add_Number", "StNam_Full", "post_city_n", "coded_situs", "dor_situs", "dor_city",
                                                     "Inc_Muni", "comp_city", "nearest_seam_ft", "risk_band", "flag"]].round(0).to_dict("records")}
    (ROOT / "out" / slug / f"calibration_{source}.json").write_text(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--county", required=True); ap.add_argument("--source", required=True)
    ap.add_argument("--exclude-class4", action="store_true")
    r = calibrate(**{k.replace("-", "_"): v for k, v in vars(ap.parse_args()).items()})
    print(json.dumps({k: r[k] for k in ("rows_compared", "mismatches", "base_rate_mismatch", "by_class", "direction")}, indent=1))
