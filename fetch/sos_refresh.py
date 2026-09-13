#!/usr/bin/env python3
"""
Tennessee Secretary of State business-entity roster: build and refresh the per-county files.

The SOS bulk extract is a statewide RECORDS table (tab-separated master; pipe-separated monthly
increments named Extract_Business_MONTHLY_<yyyymmdd>/RECORDS.txt). Every row is one entity keyed by
ControlNumber; an increment carries the current version of every entity that changed that month.

    # first build: master + every increment -> data/sos/<county>_county_all_records_from_SOS.tsv
    python3 fetch/sos_refresh.py --master data/sos_statewide_RECORDS.tsv --increments data/sos_monthly/*.txt

    # monthly: apply one new increment to the existing county files
    python3 fetch/sos_refresh.py --increments data/sos_monthly/sos_monthly_20260901_RECORDS.txt

Dedup rule: latest increment wins per ControlNumber (increments are applied in filename order, which
sorts by date). County = PrincipalAddressCounty on rows whose principal address is in TN. Rows with no
county are written to data/sos/_no_county.tsv so nothing is silently dropped.
"""
from __future__ import annotations
import argparse, glob, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
SOS = ROOT / "data" / "sos"
TN = {"ANDERSON", "BEDFORD", "BENTON", "BLEDSOE", "BLOUNT", "BRADLEY", "CAMPBELL", "CANNON", "CARROLL", "CARTER", "CHEATHAM",
      "CHESTER", "CLAIBORNE", "CLAY", "COCKE", "COFFEE", "CROCKETT", "CUMBERLAND", "DAVIDSON", "DECATUR", "DEKALB", "DICKSON",
      "DYER", "FAYETTE", "FENTRESS", "FRANKLIN", "GIBSON", "GILES", "GRAINGER", "GREENE", "GRUNDY", "HAMBLEN", "HAMILTON",
      "HANCOCK", "HARDEMAN", "HARDIN", "HAWKINS", "HAYWOOD", "HENDERSON", "HENRY", "HICKMAN", "HOUSTON", "HUMPHREYS", "JACKSON",
      "JEFFERSON", "JOHNSON", "KNOX", "LAKE", "LAUDERDALE", "LAWRENCE", "LEWIS", "LINCOLN", "LOUDON", "MACON", "MADISON",
      "MARION", "MARSHALL", "MAURY", "MCMINN", "MCNAIRY", "MEIGS", "MONROE", "MONTGOMERY", "MOORE", "MORGAN", "OBION",
      "OVERTON", "PERRY", "PICKETT", "POLK", "PUTNAM", "RHEA", "ROANE", "ROBERTSON", "RUTHERFORD", "SCOTT", "SEQUATCHIE",
      "SEVIER", "SHELBY", "SMITH", "STEWART", "SULLIVAN", "SUMNER", "TIPTON", "TROUSDALE", "UNICOI", "UNION", "VAN BUREN",
      "WARREN", "WASHINGTON", "WAYNE", "WEAKLEY", "WHITE", "WILLIAMSON", "WILSON"}


def read(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else "|"
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False, quoting=3, on_bad_lines="warn",
                       encoding="latin-1", engine="c")


def slug(county: str) -> str:
    return county.lower().replace(" ", "")


def county_path(county: str) -> Path:
    return SOS / f"{slug(county)}_county_all_records_from_SOS.tsv"


def load_existing() -> pd.DataFrame:
    frames = [pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False, quoting=3, encoding="utf-8")
              for p in sorted(SOS.glob("*_county_all_records_from_SOS.tsv"))]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", help="statewide RECORDS.tsv (first build only)")
    ap.add_argument("--increments", nargs="*", default=[], help="monthly RECORDS.txt files, any order")
    a = ap.parse_args()
    SOS.mkdir(parents=True, exist_ok=True)

    parts, order = [], 0
    if a.master:
        m = read(Path(a.master)); parts.append(m.assign(_ord=order)); order += 1
        print(f"master {a.master}: {len(m):,} rows")
    elif SOS.exists():
        e = load_existing(); parts.append(e.assign(_ord=order)); order += 1
        print(f"existing county files: {len(e):,} rows")
    incs = sorted(f for pat in a.increments for f in glob.glob(pat))
    for f in incs:
        d = read(Path(f)); parts.append(d.assign(_ord=order)); order += 1
        print(f"increment {Path(f).name}: {len(d):,} rows")
    if not parts:
        sys.exit("nothing to do")
    cols = [c for c in parts[0].columns if c != "_ord"]
    a_ = pd.concat([p[cols + ["_ord"]] for p in parts], ignore_index=True)
    before = len(a_)
    a_ = a_.sort_values(["ControlNumber", "_ord"]).drop_duplicates("ControlNumber", keep="last").drop(columns="_ord")
    print(f"deduplicated {before:,} -> {len(a_):,} entities")
    a_["PrincipalAddressCounty"] = a_["PrincipalAddressCounty"].str.strip().str.upper()
    tn = a_[a_["PrincipalAddressStateCode"].str.upper().eq("TN")]
    counts = {}
    for cty, g in tn.groupby("PrincipalAddressCounty"):
        if cty in TN:
            g.to_csv(county_path(cty), sep="\t", index=False); counts[cty] = int(len(g))
    tn[~tn["PrincipalAddressCounty"].isin(TN)].to_csv(SOS / "_no_county.tsv", sep="\t", index=False)
    stamps = [re.search(r"(\d{8})", Path(f).name).group(1) for f in incs if re.search(r"(\d{8})", Path(f).name)]
    (SOS / "_manifest.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "entities": int(len(a_)),
        "tn_principal": int(len(tn)), "no_county": int((~tn["PrincipalAddressCounty"].isin(TN)).sum()),
        "increments_applied": stamps, "counties": counts}, indent=1))
    print(f"{len(counts)} county files written to {SOS}; missing: {sorted(TN - set(counts))}")


if __name__ == "__main__":
    main()
