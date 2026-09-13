"""
Snapshot warehouse: never overwrite, always diff.

Layout:
  warehouse/raw/<layer>/<county|TN>/<YYYY-MM-DD>/data.(geojson|json) + meta.json   -- untouched source
  warehouse/parquet/<layer>/<county|TN>/<YYYY-MM-DD>.parquet                          -- GeoParquet, EPSG:2274
  warehouse/catalog.duckdb                                                            -- snapshots table

A finding made in March must be reproducible in October against March geometry.
That is the whole reason this exists.
"""
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WH = ROOT / "warehouse"
TN_SP = "EPSG:2274"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Warehouse:
    def __init__(self, root: Path = WH):
        self.root = root
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "parquet").mkdir(parents=True, exist_ok=True)
        self._db = None

    # The DuckDB catalog is the queryable index; the meta.json files are the
    # source of truth. Readers never need the lock -- several county runs can
    # read while one fetch writes.
    @property
    def db(self):
        if self._db is None:
            self._db = duckdb.connect(str(self.root / "catalog.duckdb"))
            self._db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            layer VARCHAR, scope VARCHAR, snap_date VARCHAR, fetched_utc VARCHAR,
            source_url VARCHAR, where_clause VARCHAR, feature_count BIGINT, sha256 VARCHAR,
            last_edit_date BIGINT, raw_path VARCHAR, parquet_path VARCHAR, geom BOOLEAN,
            geometry_repairs INTEGER, notes VARCHAR,
            PRIMARY KEY (layer, scope, snap_date))""")
        return self._db

    def _fs_snapshots(self, layer: str | None = None, scope: str | None = None) -> list[dict]:
        out = []
        for m in (self.root / "raw").glob("*/*/*/meta.json"):
            d = json.loads(m.read_text())
            if layer and d["layer"] != layer: continue
            if scope and d["scope"] != scope: continue
            out.append(d)
        return sorted(out, key=lambda d: (d["layer"], d["scope"], d["snap_date"]))

    # ---------------------------------------------------------------- ingest
    def ingest(self, layer: str, scope: str, src: Path, *, source_url: str = "", where: str = "1=1",
               last_edit_date: int | None = None, notes: str = "", snap_date: str | None = None) -> dict:
        """Register a downloaded file as a snapshot. Idempotent on identical hash."""
        src = Path(src)
        snap_date = snap_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        digest = sha256(src)
        prev = self.latest(layer, scope)
        if prev and prev["sha256"] == digest:
            return {**prev, "unchanged": True}
        rawdir = self.root / "raw" / layer / scope / snap_date
        rawdir.mkdir(parents=True, exist_ok=True)
        ext = ".geojson" if src.suffix == ".geojson" else ".json"
        raw = rawdir / f"data{ext}"
        if raw.resolve() != src.resolve():
            shutil.copy2(src, raw)
        geom = ext == ".geojson"
        repairs = 0
        pq = self.root / "parquet" / layer / scope
        pq.mkdir(parents=True, exist_ok=True)
        pqp = pq / f"{snap_date}.parquet"
        if geom:
            g = gpd.read_file(raw)
            if g.crs is None:
                g = g.set_crs("EPSG:4326")
            bad = ~g.geometry.is_valid & g.geometry.notna()
            repairs = int(bad.sum())
            if repairs:
                g.loc[bad, "geometry"] = g.loc[bad, "geometry"].make_valid()
            g = g.to_crs(TN_SP)
            g.to_parquet(pqp)
            n = len(g)
        else:
            rows = json.loads(raw.read_text())
            df = pd.DataFrame(rows)
            df.to_parquet(pqp)
            n = len(df)
        meta = dict(layer=layer, scope=scope, snap_date=snap_date,
                    fetched_utc=datetime.now(timezone.utc).isoformat(), source_url=source_url,
                    where_clause=where, feature_count=n, sha256=digest, last_edit_date=last_edit_date,
                    raw_path=str(raw.relative_to(self.root)), parquet_path=str(pqp.relative_to(self.root)),
                    geom=geom, geometry_repairs=repairs, notes=notes)
        (rawdir / "meta.json").write_text(json.dumps(meta, indent=2))
        self._catalog_insert(meta)   # best-effort; meta.json is authoritative, reindex() rebuilds the catalog
        return {**meta, "unchanged": False}

    def _catalog_insert(self, meta: dict, tries: int = 8) -> bool:
        import time
        for t in range(tries):
            try:
                self.db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                [meta[k] for k in ("layer", "scope", "snap_date", "fetched_utc", "source_url", "where_clause",
                                                   "feature_count", "sha256", "last_edit_date", "raw_path", "parquet_path",
                                                   "geom", "geometry_repairs", "notes")])
                return True
            except Exception:  # noqa: BLE001 - lock contention from a parallel ingest
                self._db = None; time.sleep(0.5 + t)
        return False

    def reindex(self) -> int:
        """Rebuild the DuckDB catalog from every meta.json on disk."""
        n = 0
        for m in self._fs_snapshots():
            if self._catalog_insert(m): n += 1
        return n

    # ----------------------------------------------------------------- reads
    def latest(self, layer: str, scope: str) -> dict | None:
        s = self._fs_snapshots(layer, scope)
        return s[-1] if s else None

    def load(self, layer: str, scope: str, snap_date: str | None = None):
        rec = self.latest(layer, scope) if snap_date is None else next(
            (d for d in self._fs_snapshots(layer, scope) if d["snap_date"] == snap_date), None)
        if rec is None:
            raise FileNotFoundError(f"no snapshot for {layer}/{scope}")
        p = self.root / rec["parquet_path"]
        return gpd.read_parquet(p) if rec["geom"] else pd.read_parquet(p)

    def snapshots(self, layer: str | None = None, scope: str | None = None) -> pd.DataFrame:
        cols = ["layer", "scope", "snap_date", "feature_count", "geometry_repairs", "last_edit_date", "sha256"]
        return pd.DataFrame([{k: d.get(k) for k in cols} for d in self._fs_snapshots(layer, scope)], columns=cols)

    # ------------------------------------------------------------------ diff
    def diff(self, layer: str, scope: str, a: str, b: str, key: str = "OBJECTID") -> dict:
        """What changed between two snapshots of a layer: added / removed / moved / attribute-changed."""
        A, B = self.load(layer, scope, a), self.load(layer, scope, b)
        if key not in A.columns or key not in B.columns:
            return {"added": len(B) - len(A), "note": f"no shared key '{key}'; count delta only"}
        A = A.set_index(key); B = B.set_index(key)
        added = sorted(set(B.index) - set(A.index)); removed = sorted(set(A.index) - set(B.index))
        common = sorted(set(A.index) & set(B.index))
        moved, changed = [], []
        if "geometry" in A.columns:
            ga, gb = A.loc[common, "geometry"], B.loc[common, "geometry"]
            mv = ~ga.geom_equals_exact(gb, tolerance=0.5)  # half a foot
            moved = list(ga.index[mv])
        attr_cols = [c for c in A.columns if c != "geometry" and c in B.columns]
        if attr_cols:
            da, db_ = A.loc[common, attr_cols].astype(str), B.loc[common, attr_cols].astype(str)
            changed = list(da.index[(da != db_).any(axis=1)])
        return {"a": a, "b": b, "added": added, "removed": removed, "moved": moved,
                "attr_changed": [c for c in changed if c not in moved],
                "counts": {"added": len(added), "removed": len(removed), "moved": len(moved),
                           "attr_changed": len([c for c in changed if c not in moved])}}
