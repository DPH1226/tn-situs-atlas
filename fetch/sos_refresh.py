#!/usr/bin/env python3
"""
Tennessee Secretary of State business-entity roster: build and refresh the per-county files.

The SOS bulk extract is a statewide RECORDS table (tab-separated master; pipe-separated monthly
increments named Extract_Business_MONTHLY_<yyyymmdd>/RECORDS.txt). Every row is one entity keyed by
ControlNumber; an increment carries the current version of every entity that changed that month.

    # first build: original export + merged master + every increment
    python3 fetch/sos_refresh.py --base data/sos_base_RECORDS_20250706.txt --master data/sos_statewide_RECORDS_20260826.tsv --increments data/sos_monthly/*.txt

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


N_COLS = 40
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def _repair(fields: list[str], sep: str = "|") -> list[str] | None:
    """A row with more than 40 fields has a literal '|' inside a value. The SOS export does not
    quote, so fold the extra pieces back into the field they most plausibly came from — the
    entity name first (idx 8), then the principal or mailing address line — and accept the
    repair only if the fields that follow still look right (Domestic Y/N, a date, a 2-letter
    state). Rows that fit no repair are dropped and counted."""
    extra = len(fields) - N_COLS
    if extra <= 0:
        return fields
    for idx, check in ((8, lambda f: f[9] in ("Y", "N") and (f[10] == "" or _DATE.match(f[10]))),
                       (15, lambda f: len(f[19]) == 2 or f[19] == ""),
                       (24, lambda f: len(f[28]) == 2 or f[28] == "")):
        cand = fields[:idx] + [sep.join(fields[idx:idx + extra + 1])] + fields[idx + extra + 1:]
        if len(cand) == N_COLS and check(cand):
            return cand
    return None


def iter_rows(path: Path):
    """Stream a RECORDS extract (pipe-delimited, unquoted, latin-1) or a county TSV as lists of 40 fields."""
    sep = "\t" if path.suffix.lower() == ".tsv" else "|"
    dropped = 0
    with open(path, encoding="latin-1", newline="") as fh:
        header = fh.readline().rstrip("\r\n").split(sep)
        assert len(header) == N_COLS, f"{path}: {len(header)} columns, expected {N_COLS}"
        for line in fh:
            f = line.rstrip("\r\n").replace("\x00", "").split(sep)   # legacy rows carry NUL bytes for empty fields
            if len(f) < N_COLS:
                dropped += 1; continue
            f = _repair(f, sep)
            if f is None:
                dropped += 1; continue
            yield f
    if dropped:
        print(f"  {path.name}: {dropped} unparseable rows dropped", flush=True)


def read(path: Path) -> pd.DataFrame:
    return pd.DataFrame(list(iter_rows(path)), columns=HEADER, dtype=str)


HEADER = ["ControlNumber", "EntityType", "AdditionalDesignation", "DurationType", "Status", "AnnualReportStanding",
          "RegisteredAgentStanding", "OtherStanding", "EntityName", "Domestic", "EffectiveDate", "ExpirationDate",
          "InactiveDate", "BusinessState", "CommonShares", "PrincipalAddressLine1", "PrincipalAddressLine2",
          "PrincipalAddressAttn", "PrincipalAddressCity", "PrincipalAddressStateCode", "PrincipalAddressProvince",
          "PrincipalAddressPostalCode", "PrincipalAddressCountry", "PrincipalAddressCounty", "MailingAddressLine1",
          "MailingAddressLine2", "MailingAddressAttn", "MailingAddressCity", "MailingAddressStateCode",
          "MailingAddressProvince", "MailingAddressPostalCode", "MailingAddressCountry", "MailingAddressCounty",
          "ExemptAR", "ManagedByType", "MemberCount", "PublicBenefit", "Religious", "ARDueDate", "FiscalEndingMonth"]
I_CTRL, I_NAME, I_STATUS = 0, 8, 4
I_PA1, I_PCITY, I_PSTATE, I_PZIP, I_PCOUNTY = 15, 18, 19, 21, 23


def slug(county: str) -> str:
    return county.lower().replace(" ", "")


def county_path(county: str) -> Path:
    return SOS / f"{slug(county)}_county_all_records_from_SOS.tsv"


def load_existing() -> pd.DataFrame:
    frames = [pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)
              for p in sorted(SOS.glob("*_county_all_records_from_SOS.tsv"))]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="original full RECORDS.txt export (lowest priority; fills counties the later files left blank)")
    ap.add_argument("--master", help="statewide RECORDS.tsv (first build only)")
    ap.add_argument("--increments", nargs="*", default=[], help="monthly RECORDS.txt files, any order")
    a = ap.parse_args()
    SOS.mkdir(parents=True, exist_ok=True)

    # Inputs in priority order, lowest first: base, then master (or the existing county files), then increments by date.
    files: list[Path] = []
    if a.base: files.append(Path(a.base))
    if a.master: files.append(Path(a.master))
    elif not a.base: files += sorted(SOS.glob("*_county_all_records_from_SOS.tsv"))
    incs = sorted(f for pat in a.increments for f in glob.glob(pat)); files += [Path(f) for f in incs]
    if not files: sys.exit("nothing to do")

    # Pass 1: which file holds the winning (latest) row for each ControlNumber, and its county / address.
    win: dict[str, int] = {}; win_county: dict[str, str] = {}; win_addr: dict[str, str] = {}
    for ord_, f in enumerate(files):
        n = 0
        for r in iter_rows(f):
            c = r[I_CTRL]; win[c] = ord_
            win_county[c] = r[I_PCOUNTY].strip().upper()
            win_addr[c] = f"{r[I_PA1].upper().strip()}|{r[I_PCITY].upper().strip()}|{r[I_PZIP][:5]}"; n += 1
        print(f"{f.name}: {n:,} rows", flush=True)
    print(f"deduplicated -> {len(win):,} entities", flush=True)

    # Pass 2: county backfill for winners with a blank county — an earlier version of the SAME address with a county.
    need = {c for c, cty in win_county.items() if cty == ""}
    backfill: dict[str, str] = {}
    for f in files:
        for r in iter_rows(f):
            c = r[I_CTRL]
            if c in need and c not in backfill:
                cty = r[I_PCOUNTY].strip().upper()
                if cty in TN and f"{r[I_PA1].upper().strip()}|{r[I_PCITY].upper().strip()}|{r[I_PZIP][:5]}" == win_addr[c]:
                    backfill[c] = cty
    # ZIP fallback from the statewide postal map (unambiguous city/ZIP pairs only)
    pm_path = ROOT / "configs" / "postal_home_county.json"
    pm = json.loads(pm_path.read_text())["by_city_zip"] if pm_path.exists() else {}
    zipfill = 0

    # Pass 3: write the winning rows into county files.
    outs: dict[str, object] = {}
    def sink(name):
        if name not in outs:
            p = county_path(name) if name in TN else SOS / f"_{name}.tsv"
            outs[name] = open(p, "w", encoding="utf-8", newline="")
            outs[name].write("\t".join(HEADER) + "\n")
        return outs[name]
    counts: dict[str, int] = {}; tn_rows = 0; filled_prev = 0
    for ord_, f in enumerate(files):
        for r in iter_rows(f):
            c = r[I_CTRL]
            if win[c] != ord_: continue
            if r[I_PSTATE].strip().upper() != "TN": continue
            tn_rows += 1
            cty = r[I_PCOUNTY].strip().upper()
            if cty == "" and c in backfill:
                cty = backfill[c]; filled_prev += 1
            if cty == "" and pm:
                key = r[I_PCITY].upper().strip().replace(".", "").replace("MOUNT ", "MT ") + "|" + r[I_PZIP][:5]
                v = pm.get(key)
                if v and v["share"] >= 0.9: cty = v["home"]; zipfill += 1
            r[I_PCOUNTY] = cty
            name = cty if cty in TN else "no_county"
            sink(name).write("\t".join(x.replace("\t", " ") for x in r) + "\n")
            counts[name] = counts.get(name, 0) + 1
    for fh in outs.values(): fh.close()
    print(f"county backfilled from earlier version: {filled_prev:,}; from ZIP map: {zipfill:,}", flush=True)
    stamps = [re.search(r"(\d{8})", Path(f).name).group(1) for f in incs if re.search(r"(\d{8})", Path(f).name)]
    (SOS / "_manifest.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "inputs": [f.name for f in files],
        "entities": len(win), "tn_principal": tn_rows, "no_county": counts.get("no_county", 0),
        "backfilled_from_earlier_version": filled_prev, "backfilled_from_zip_map": zipfill,
        "increments_applied": stamps, "counties": {k: v for k, v in sorted(counts.items()) if k in TN}}, indent=1))
    written = [k for k in counts if k in TN]
    print(f"{len(written)} county files written to {SOS}; missing: {sorted(TN - set(written))}; no-county rows: {counts.get('no_county', 0):,}")


if __name__ == "__main__":
    main()
