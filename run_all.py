#!/usr/bin/env python3
"""Ingest, run, build and bulletin every county that has data. Parallel by process."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config


def one(county: str, raw: str, skip_ingest: bool) -> dict:
    t0 = time.time(); log = ROOT / "out" / f"{county.lower()}_run.log"; log.parent.mkdir(exist_ok=True)
    steps = ([] if skip_ingest else [["python3", "fetch/fetch_county.py", "--county", county, "--from-dir", raw]]) + [
        ["python3", "run_county.py", "--county", county], ["python3", "build_workbench.py", "--county", county],
        ["python3", "bulletin.py", "--county", county]]
    with open(log, "w") as fh:
        for cmd in steps:
            r = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
            if r.returncode:
                return {"county": county, "ok": False, "step": cmd[1], "secs": round(time.time() - t0)}
    s = json.loads((ROOT / "out" / county.lower() / "summary.json").read_text())
    return {"county": county, "ok": True, "secs": round(time.time() - t0), "rooftops": s["totals"]["address_points"],
            "biz": s["totals"]["business_points"], "E2": s["exceptions"]["E2_CROSS_COUNTY_POSTAL"], "E5": s["exceptions"]["E5_DOR_INTERNAL_CONFLICT"],
            "flags": s.get("business_flags", {})}


def ensure_sos():
    """data/sos/*.tsv are not in git (340 MB); data/sos_parts/*.zip are. Unpack on first use."""
    import zipfile
    sos = ROOT / "data" / "sos"; sos.mkdir(parents=True, exist_ok=True)
    if not list(sos.glob("*_county_all_records_from_SOS.tsv")):
        for z in sorted((ROOT / "data" / "sos_parts").glob("*.zip")):
            with zipfile.ZipFile(z) as zf: zf.extractall(sos)
            print("unpacked", z.name, flush=True)


if __name__ == "__main__":
    ensure_sos()
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", default="data/raw"); ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--counties", nargs="*"); ap.add_argument("--skip-ingest", action="store_true"); a = ap.parse_args()
    raw = Path(a.raw)
    todo = a.counties or [c.upper() for c in config.all_counties() if (raw / f"{c}_ng911_address_points.geojson").exists()]
    print(f"{len(todo)} counties with data", flush=True)
    results = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(one, c, str(raw), a.skip_ingest): c for c in todo}
        for f in as_completed(futs):
            r = f.result(); results.append(r); print(json.dumps(r), flush=True)
    (ROOT / "out" / "run_all_results.json").write_text(json.dumps(results, indent=1))
    print(f"done: {sum(r['ok'] for r in results)}/{len(results)} ok")
