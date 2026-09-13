#!/usr/bin/env python3
"""
Static site for the Tennessee Situs Atlas — deployable to GitHub Pages, Railway, or any
static host.

    site/index.html            the atlas (statewide table; every county links to its workbench)
    site/<slug>/index.html     the county workbench (self-contained page + wb.js + wbdata.js)
    site/CNAME                 custom domain for GitHub Pages
    site/data/statewide_index.json

Public data only. The workbench's DOR-file paste stays in the browser tab; on a plain static
host the shared-adjudication store is absent and the page falls back to per-browser storage.

    python3 build_site.py [--domain navigationholdings.com] [--out site]
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config

HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n')


def wrap(fragment: str) -> str:
    """Artifact-style fragments start with <title>/<link>/<style>; give them a real document."""
    m = re.search(r"(<title>.*?</title>\s*(?:<link[^>]*>\s*)*<style>.*?</style>\s*)", fragment, re.S)
    if m:
        head, body = m.group(1), fragment[m.end():]
    else:
        head, body = "", fragment
    return f"{HEAD}{head}</head>\n<body>\n{body}\n</body>\n</html>\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="navigationholdings.com")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = ROOT / a.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # county workbenches
    built = []
    for c in config.all_counties():
        src = ROOT / "artifact" / c
        if not (src / "workbench.html").exists():
            continue
        dst = out / c; dst.mkdir()
        (dst / "index.html").write_text(wrap((src / "workbench.html").read_text()))
        shutil.copy(src / "wb.js", dst / "wb.js")
        shutil.copy(src / "wbdata.js", dst / "wbdata.js")
        built.append(c)

    # atlas: rebuild with relative links to the county pages
    import importlib
    sys.argv = ["build_index.py"]
    bi = ROOT / "build_index.py"
    code = bi.read_text()
    code = code.replace('"link": LINKS.get(c)', '"link": (f"./{c}/" if c in BUILT else None)')
    ns = {"__name__": "build_site_atlas", "__file__": str(bi), "BUILT": set(built)}
    exec(compile(code, str(bi), "exec"), ns)
    atlas = (ROOT / "artifact" / "atlas.html").read_text()
    atlas = atlas.replace('target="_blank" rel="noopener"', "")
    (out / "index.html").write_text(wrap(atlas))
    # restore the artifact atlas with claude.ai links for the published copy
    ns2 = {"__name__": "build_index_restore", "__file__": str(bi)}
    exec(compile(bi.read_text(), str(bi), "exec"), ns2)

    (out / "data").mkdir()
    shutil.copy(ROOT / "out" / "statewide_index.json", out / "data" / "statewide_index.json")
    if a.domain:
        (out / "CNAME").write_text(a.domain + "\n")
    (out / ".nojekyll").write_text("")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"site: {len(built)} county workbenches + atlas -> {out} ({size/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
