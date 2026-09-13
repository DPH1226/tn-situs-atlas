"""Load and validate county + statewide configs."""
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "configs"


def statewide() -> dict:
    return yaml.safe_load((CONF / "statewide.yaml").read_text())


def county(name: str) -> dict:
    p = CONF / f"{name.lower()}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"no config for county '{name}' at {p}")
    c = yaml.safe_load(p.read_text())
    for k in ("county", "fips", "situs", "tiers"):
        if k not in c:
            raise ValueError(f"{p.name}: missing required key '{k}'")
    if not c["fips"].startswith("47"):
        raise ValueError(f"{p.name}: fips must be a Tennessee county (47xxx)")
    for lyr in c.get("business_layers", []):
        need = ("id", "path", "name_field") if lyr.get("type") == "sos_tsv" else ("id", "url", "name_field")
        for k in need:
            if k not in lyr:
                raise ValueError(f"{p.name}: business layer missing '{k}'")
    for lyr in c.get("city_layers", []):
        for k in ("id", "url", "role"):
            if k not in lyr:
                raise ValueError(f"{p.name}: city layer missing '{k}'")
        if lyr["role"] not in ("limits", "annexations", "ugb"):
            raise ValueError(f"{p.name}: city layer role must be limits|annexations|ugb")
    c["slug"] = c["county"].lower().replace(" ", "")
    return c


def all_counties() -> list[str]:
    return sorted(p.stem for p in CONF.glob("*.yaml") if p.stem not in ("schema", "statewide"))
