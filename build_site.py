#!/usr/bin/env python3
"""
Static site for the Tennessee Situs Atlas — deployable to GitHub Pages, Railway, or any
static host.

    site/index.html            the atlas (statewide table; every county links to its workbench)
    site/<slug>/index.html     the county workbench (self-contained page + wb.js + wbdata.js)
    site/cities/index.html     the cities index (build_cities.py); site/cities/<slug>/ per-city workbenches
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
    ap.add_argument("--domain", default="atlas.navigationholdings.com")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = ROOT / a.out; out.mkdir(parents=True, exist_ok=True)

    def fresh(d: Path) -> Path:
        """Replace one directory. The site is rebuilt piecewise: a county whose artifact is not on this
        machine keeps its existing page instead of vanishing."""
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True); return d

    # county workbenches
    built, kept = [], []
    for c in config.all_counties():
        src = ROOT / "artifact" / c
        if not (src / "workbench.html").exists():
            if (out / c / "index.html").exists(): kept.append(c)
            continue
        dst = fresh(out / c)
        (dst / "index.html").write_text(wrap((src / "workbench.html").read_text()))
        shutil.copy(src / "wb.js", dst / "wb.js")
        shutil.copy(src / "wbdata.js", dst / "wbdata.js")
        built.append(c)

    # city workbenches (build_cities.py) -> site/cities/<slug>/ ; cities index -> site/cities/index.html
    cities_built = 0
    csrc = ROOT / "artifact" / "cities"
    if csrc.is_dir():
        cdst = fresh(out / "cities")
        for d in sorted(p for p in csrc.iterdir() if p.is_dir() and (p / "workbench.html").exists()):
            t = cdst / d.name; t.mkdir()
            (t / "index.html").write_text(wrap((d / "workbench.html").read_text()))
            shutil.copy(d / "wb.js", t / "wb.js"); shutil.copy(d / "wbdata.js", t / "wbdata.js")
            cities_built += 1
        ci = ROOT / "artifact" / "cities.html"
        if ci.exists():
            (cdst / "index.html").write_text(wrap(ci.read_text()))

    # revenue flows page (build_flows.py) -> site/flows/index.html
    flows_built = (ROOT / "artifact" / "flows.html").exists()
    if flows_built:
        fdst = fresh(out / "flows")
        (fdst / "index.html").write_text(wrap((ROOT / "artifact" / "flows.html").read_text()))

    # atlas: rebuild with relative links to the county pages
    import importlib
    sys.argv = ["build_index.py"]
    bi = ROOT / "build_index.py"
    code = bi.read_text()
    code = code.replace('"link": LINKS.get(c)', '"link": (f"./{c}/" if c in BUILT else None)')
    ns = {"__name__": "build_site_atlas", "__file__": str(bi), "BUILT": set(built) | set(kept)}
    exec(compile(code, str(bi), "exec"), ns)
    atlas = (ROOT / "artifact" / "atlas.html").read_text()
    atlas = atlas.replace('target="_blank" rel="noopener"', "")
    if cities_built or flows_built:
        NAV_CSS = ('.views{display:flex;gap:2px;margin:14px 0 0;font-family:Archivo,sans-serif;font-size:.74rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase}'
                   '.views a{padding:7px 14px;border:1px solid var(--rule);border-bottom:0;color:var(--ink-3);background:var(--surface-2);text-decoration:none}'
                   '.views a.on{color:var(--ink);background:var(--surface);border-color:var(--ink);border-bottom:2px solid var(--surface);margin-bottom:-2px}')
        atlas = atlas.replace("</style>", NAV_CSS + "</style>", 1)
        tabs = '<a class="on" href="./">Counties</a>' + ('<a href="./cities/">Cities</a>' if cities_built else '') + ('<a href="./flows/">Revenue flows</a>' if flows_built else '')
        atlas = atlas.replace("</div></header>", '<nav class="views">' + tabs + '</nav></div></header>', 1)
    (out / "index.html").write_text(wrap(atlas))
    # restore the artifact atlas with claude.ai links for the published copy
    ns2 = {"__name__": "build_index_restore", "__file__": str(bi)}
    exec(compile(bi.read_text(), str(bi), "exec"), ns2)

    (out / "data").mkdir(exist_ok=True)
    shutil.copy(ROOT / "out" / "statewide_index.json", out / "data" / "statewide_index.json")
    if a.domain:
        (out / "CNAME").write_text(a.domain + "\n")
    (out / ".nojekyll").write_text("")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    for extra in ("cities_index.json", "flows_index.json"):
        if (ROOT / "out" / extra).exists(): shutil.copy(ROOT / "out" / extra, out / "data" / extra)
    print(f"site: {len(built)} county workbenches rebuilt, {len(kept)} kept + {cities_built} city workbenches + {'flows' if flows_built else 'no flows'} + atlas -> {out} ({size/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
