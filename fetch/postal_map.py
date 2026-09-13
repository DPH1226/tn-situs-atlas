#!/usr/bin/env python3
"""
Derive the postal-city -> home-county map from the rooftops themselves.

For every (Post_City, ZIP) pair across every county's NG911 snapshot, the county
holding the majority of that pair's rooftops is its postal home county. A
rooftop whose county differs from its postal home county is cross-county
exposure. Multi-county cities fall out automatically: a (city, ZIP) pair whose
majority share is below 0.8 is recorded as split, and a mailing city that names
a municipality the rooftop's county also contains is never counted as
cross-county there.

Output: configs/postal_home_county.json — replaces every hand-typed list.
"""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from warehouse.store import Warehouse


def main():
    wh = Warehouse()
    tally: dict[tuple, Counter] = defaultdict(Counter)
    counties = []
    for s in wh.snapshots("ng911_address_points").itertuples():
        counties.append(s.scope)
        df = wh.load("ng911_address_points", s.scope)
        pc = df["Post_City"].astype(str).str.upper().str.strip().str.replace(".", "", regex=False).str.replace("MOUNT ", "MT ", regex=False)
        z = df["Zip_Code"].astype(str).str[:5]
        for (c, zz), n in Counter(zip(pc, z)).items():
            if c and c != "NAN" and zz.isdigit():
                tally[(c, zz)][s.scope.upper()] += n
    out = {"by_city_zip": {}, "by_city": {}, "counties_covered": sorted(c.upper() for c in counties)}
    bycity: dict[str, Counter] = defaultdict(Counter)
    for (c, zz), cnt in tally.items():
        tot = sum(cnt.values()); home, n = cnt.most_common(1)[0]
        out["by_city_zip"][f"{c}|{zz}"] = {"home": home, "share": round(n / tot, 3), "n": tot,
                                            "split": {k: v for k, v in cnt.items()} if n / tot < 0.8 else None}
        bycity[c].update(cnt)
    for c, cnt in bycity.items():
        tot = sum(cnt.values()); home, n = cnt.most_common(1)[0]
        out["by_city"][c] = {"home": home, "share": round(n / tot, 3), "n": tot,
                             "counties": {k: v for k, v in cnt.most_common()} if n / tot < 0.8 else None}
    p = ROOT / "configs" / "postal_home_county.json"; p.write_text(json.dumps(out, indent=1))
    splits = [c for c, v in out["by_city"].items() if v["counties"]]
    print(f"{len(out['by_city_zip'])} city/ZIP pairs, {len(out['by_city'])} postal cities from {len(counties)} counties; "
          f"{len(splits)} multi-county postal cities e.g. {splits[:12]}")


if __name__ == "__main__":
    main()
