#!/usr/bin/env python3
"""
Cheap change signals, polled before any bulk pull. Writes warehouse/watch_state.json
and prints what changed. Exit code 3 when something changed (so a scheduler can branch).

Signals:
  - the SST boundary-file name on the DOR page (quarterly release marker)
  - the newest DOR sales-tax notice number (rate changes, CBID expansions)
  - lastEditDate + feature count of every layer in the county plan
"""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import config, arcgis
from fetch.fetch_county import plan

STATE = Path(__file__).resolve().parent.parent / "warehouse" / "watch_state.json"


def html_signal(url: str, pattern: str) -> str | None:
    try:
        html = requests.get(url, headers=arcgis.UA, timeout=60).text
    except Exception:  # noqa: BLE001
        return None
    m = sorted(set(re.findall(pattern, html)))
    return json.dumps(m[-3:]) if m else None


def main(counties: list[str]) -> int:
    prev = json.loads(STATE.read_text()) if STATE.exists() else {}
    cur, changes = {"checked_utc": datetime.now(timezone.utc).isoformat(), "signals": {}}, []
    for w in config.statewide().get("watch", []):
        v = html_signal(w["url"], w["pattern"])
        cur["signals"][w["id"]] = v
        if v is not None and prev.get("signals", {}).get(w["id"]) not in (None, v):
            changes.append(f"{w['id']}: {prev['signals'][w['id']]} -> {v}")
    seen = set()
    for c in counties:
        for it in plan(config.county(c)):
            k = f"{it['id']}/{it['scope']}"
            if k in seen:
                continue
            seen.add(k)
            try:
                info = arcgis.layer_info(it["url"]); n = arcgis.count(it["url"], it["where"])
                v = f"{info.get('lastEditDate')}|{n}"
            except Exception as e:  # noqa: BLE001
                v = f"ERR {str(e)[:80]}"
            cur["signals"][k] = v
            if prev.get("signals", {}).get(k) not in (None, v) and not v.startswith("ERR"):
                changes.append(f"{k}: {prev['signals'][k]} -> {v}")
    cur["changes"] = changes
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(cur, indent=2))
    for ch in changes:
        print("CHANGED", ch)
    print(f"{len(cur['signals'])} signals checked, {len(changes)} changed")
    return 3 if changes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or config.all_counties()))
