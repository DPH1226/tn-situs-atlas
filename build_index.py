#!/usr/bin/env python3
"""Statewide atlas page: one row per county from out/<slug>/summary.json."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config

LINKS = {"wilson": "https://claude.ai/code/artifact/24f8283d-87ab-4811-a54b-c55d799e15d4",
         "sumner": "https://claude.ai/code/artifact/b69a5dc6-072c-49be-b5e5-4aecfbdf16e6",
         "rutherford": "https://claude.ai/code/artifact/4dadc775-c33a-459f-b56a-2136da0c214c",
         "davidson": "https://claude.ai/code/artifact/e6691a63-1d35-4fab-80d8-f0f342e20cee",
         "shelby": "https://claude.ai/code/artifact/d9d149a2-f81b-4de7-b497-81f5b543789a",
         "knox": "https://claude.ai/code/artifact/572e8b0f-f606-4443-bf62-3f72ca17ac43",
         "hamilton": "https://claude.ai/code/artifact/560ebc94-81e0-4f63-a9d0-0f5fcba9a37b",
         "williamson": "https://claude.ai/code/artifact/4249e6c7-94bd-411d-a926-f9b44d0a626e",
         "montgomery": "https://claude.ai/code/artifact/ba8e60f0-ea6a-4996-b5e2-81a2a77c16b7"}

rows, tot = [], {"rooftops": 0, "biz": 0, "seam_mi": 0.0, "xc_mi": 0.0, "E2": 0, "E5": 0, "E4": 0, "cc": 0, "pe": 0, "br": 0, "n": 0}
for c in config.all_counties():
    p = ROOT / "out" / c / "summary.json"
    cfg = config.county(c)
    if not p.exists():
        rows.append({"county": cfg["county"], "slug": c, "situs": len(cfg["situs"]), "pending": True}); continue
    s = json.loads(p.read_text()); t = s["totals"]; e = s["exceptions"]; f = s.get("business_flags", {})
    r = {"county": cfg["county"], "slug": c, "situs": len(s["situs_names"]), "rooftops": t["address_points"], "unplaced": t["unplaced"],
         "biz": t["business_points"], "seams": t["seams"], "seam_mi": t["seam_miles"], "xc_mi": t["cross_county_seam_miles"],
         "sst": t["sst_range_match_rate_pct"], "E2": e["E2_CROSS_COUNTY_POSTAL"], "E5": e["E5_DOR_INTERNAL_CONFLICT"], "E4": e["E4_LAYER_DISAGREEMENT"],
         "cc": f.get("CROSS_COUNTY_POSTAL", 0), "pe": f.get("POSTAL_CITY_EXPOSURE", 0), "br": f.get("BOUNDARY_RISK", 0), "cm": f.get("CODED_MISMATCH", 0),
         "link": LINKS.get(c), "pending": False}
    rows.append(r); tot["n"] += 1
    for k in ("rooftops", "biz", "seam_mi", "xc_mi", "E2", "E5", "E4", "cc", "pe", "br"): tot[k] += r[k]
(ROOT / "out" / "statewide_index.json").write_text(json.dumps({"totals": tot, "counties": rows}, indent=1))

def n(v): return "—" if v is None else f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
NOSOS = '<span class="nosos" title="No Secretary of State entity file loaded for this county yet; business layer pending">no roster yet</span>'
def bizcell(r): return n(r["biz"]) if r["biz"] else NOSOS
trs = []
for r in sorted(rows, key=lambda r: -(r.get("rooftops") or 0)):
    if r["pending"]:
        trs.append(f'<tr class="pend"><td>{r["county"].title()}</td><td class="n">{r["situs"]}</td><td colspan="10" class="pendtxt">data pull in progress</td></tr>'); continue
    name = f'<a href="{r["link"]}" target="_blank" rel="noopener">{r["county"].title()} ↗</a>' if r["link"] else r["county"].title()
    trs.append(f'<tr><td>{name}</td><td class="n">{r["situs"]}</td><td class="n">{n(r["rooftops"])}</td><td class="n">{bizcell(r)}</td>'
               f'<td class="n">{r["seam_mi"]:.0f}</td><td class="n">{r["xc_mi"]:.0f}</td><td class="n">{r["sst"]:.0f}%</td>'
               f'<td class="n crit">{n(r["cc"])}</td><td class="n high">{n(r["br"])}</td><td class="n watch">{n(r["pe"])}</td><td class="n">{n(r["E5"])}</td><td class="n">{n(r["E4"])}</td></tr>')

# ---- statewide map: every county, shaded by cross-county-postal businesses per 1,000 businesses, linked
MAP = json.loads((ROOT / "configs" / "tn_county_paths.json").read_text())
# dollars leaving each county across county lines per year (Tier A+B, county averages, both halves) - from build_flows.py
FLOWS = {}
_fp = ROOT / "out" / "flows_index.json"
if _fp.exists():
    _fj = json.loads(_fp.read_text()); _ver = _fj.get("verification", {})
    for _c in _fj.get("counties", []):
        _w = (_ver.get(_c["jurisdiction"]) or {}).get("verdict", "").split(" ")[0] or "none"
        FLOWS[_c["jurisdiction"].upper().replace(" ", "")] = {"owed": _c["owed_val_A"] + _c["owed_val_B"], "err": _c["err_val_A"] + _c["err_val_B"],
                                                              "owed_n": _c["owed_A"] + _c["owed_B"], "err_n": _c["err_A"] + _c["err_B"], "ver": _w}
BANDS_USD = ((50_000, "#dfe6ec", "<$50K"), (250_000, "#b9cad8", "$50–250K"), (1_000_000, "#d6a29e", "$250K–1M"), (5_000_000, "#b25a55", "$1–5M"))
def _shade(rate):
    # quantized so the legend is honest; dollars when the flows model exists, else the old per-1,000 rate
    if rate is None: return "var(--surface-2)"
    if FLOWS:
        for cut, col, _ in BANDS_USD:
            if rate < cut: return col
        return "#8f2f2a"
    for cut, col in ((5, "#dfe6ec"), (15, "#b9cad8"), (40, "#d6a29e"), (90, "#b25a55")):
        if rate < cut: return col
    return "#8f2f2a"
_by = {r["county"].upper().replace(" ", ""): r for r in rows}
svg_paths, labels = [], []
for key, m in MAP["counties"].items():
    r = _by.get(key); nm = key.title()
    if r and not r["pending"]:
        fl = FLOWS.get(key)
        if FLOWS:
            rate = fl["owed"] if fl else 0
            tip = (f'{r["county"].title()} — leaving the county: ${fl["owed"]:,.0f}/yr across {fl["owed_n"]:,} businesses · '
                   f'arriving in error: ${fl["err"]:,.0f}/yr across {fl["err_n"]:,} · {r["biz"]:,} businesses located · '
                   f'address-file class: {fl["ver"]}') if fl else f'{r["county"].title()} — no cross-county flows · {r["biz"]:,} businesses located'
        else:
            rate = (r["cc"] / r["biz"] * 1000) if r["biz"] else None
            tip = f'{r["county"].title()} — {r["rooftops"]:,} rooftops · {r["biz"]:,} businesses · {r["cc"]:,} cross-county postal · {r["br"]:,} boundary risk'
        href = r["link"] or ""
        dash = ' class="unv"' if (FLOWS and (not fl or fl["ver"] != "REAL")) else ""
        inner = f'<path d="{m["d"]}" fill="{_shade(rate)}"{dash}><title>{tip}</title></path>'
        svg_paths.append(f'<a href="{href}">{inner}</a>' if href else inner)
    else:
        svg_paths.append(f'<path d="{m["d"]}" fill="var(--surface-2)"><title>{nm} — pending</title></path>')
    if r and not r["pending"] and r["biz"] > 20000:
        labels.append(f'<text x="{m["cx"]}" y="{m["cy"]}">{r["county"].title()}</text>')
MAP_SVG = (f'<svg class="tnmap" viewBox="0 0 {MAP["w"]} {MAP["h"]}" role="img" aria-label="Tennessee counties shaded by estimated local sales tax leaving each county">'
           + "".join(svg_paths) + "".join(labels) + "</svg>")
if FLOWS:
    MAP_LEGEND = ('<div class="maplegend">' + "".join(f'<span><i style="background:{col}"></i>{lab}</span>' for _, col, lab in BANDS_USD) +
                  '<span><i style="background:#8f2f2a"></i>$5M+</span><span><i style="background:transparent;border:1.5px dashed var(--ink-3)"></i>in-county address-file class not yet verified</span>'
                  '<em>local sales tax appearing to leave the county across county lines each year — cross-county businesses (Tier B, mailing-address mechanism) at county averages, both halves · hover for detail · click to open the county workbench</em></div>')
    MAP_TITLE = "Statewide view — estimated dollars leaving each county per year"
else:
    MAP_LEGEND = ('<div class="maplegend"><span><i style="background:#dfe6ec"></i>&lt;5</span><span><i style="background:#b9cad8"></i>5–15</span>'
                  '<span><i style="background:#d6a29e"></i>15–40</span><span><i style="background:#b25a55"></i>40–90</span><span><i style="background:#8f2f2a"></i>90+</span>'
                  '<em>cross-county-postal businesses per 1,000 placed businesses · hover for counts · click to open the county workbench</em></div>')
    MAP_TITLE = "Statewide view"

html = f'''<title>Tennessee Situs Atlas</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--paper:#F4F5F2;--surface:#fff;--surface-2:#EDEFEB;--ink:#16202B;--ink-2:#3D4B57;--ink-3:#6B7A86;--rule:#D2D8DB;--rule-2:#E3E7E6;--accent:#1F5C7A;--crit:#A8322D;--high:#B0722A;--watch:#5E7686;--clear:#3A7358}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}}}}
:root[data-theme="dark"]{{--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;font-size:15px;line-height:1.55}}
.wrap{{max-width:1240px;margin:0 auto;padding-inline:20px;padding-block:0 60px}}
header{{border-bottom:2px solid var(--ink);background:var(--surface)}} .hin{{max-width:1240px;margin:0 auto;padding:26px 20px 18px}}
.eyebrow{{font-family:Archivo,sans-serif;font-size:.68rem;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}}
h1{{font-family:Archivo,sans-serif;font-size:2rem;font-weight:700;letter-spacing:-.02em;margin:.15em 0 .2em}}
.sub{{color:var(--ink-2);max-width:70ch}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border:1px solid var(--rule);background:var(--surface);margin:26px 0}}
.tiles div{{padding:14px 16px;border-right:1px solid var(--rule-2)}} .tiles div:last-child{{border-right:0}}
.k{{font-family:Archivo,sans-serif;font-size:.66rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}} .v{{font-family:"IBM Plex Mono",monospace;font-size:1.4rem;margin-top:4px}}
.tbox{{border:1px solid var(--rule);background:var(--surface);overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:.82rem}} th{{position:sticky;top:0;background:var(--surface-2);font-family:Archivo,sans-serif;font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}}
td{{padding:7px 10px;border-bottom:1px solid var(--rule-2)}} td.n{{font-family:"IBM Plex Mono",monospace;text-align:right;font-variant-numeric:tabular-nums}} tr:hover{{background:var(--surface-2)}}
td.crit{{color:var(--crit);font-weight:600}} td.high{{color:var(--high)}} td.watch{{color:var(--watch)}} tr.pend td{{color:var(--ink-3)}} .nosos{{font-family:Archivo,sans-serif;font-size:.68rem;color:var(--ink-3);font-style:italic}}
.pendtxt{{font-style:italic;font-family:"Source Serif 4",serif}}
.mapwrap{{margin:26px 0 8px}} .tnmap path.unv{{stroke:var(--ink-3);stroke-width:1.2;stroke-dasharray:3 2}} .mapwrap h2{{font-family:Archivo,sans-serif;font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin:0 0 8px}}
.tnmap{{width:100%;height:auto;max-width:100%;display:block;background:var(--surface);border:1px solid var(--rule-2);border-radius:6px}}
.tnmap path{{stroke:var(--surface);stroke-width:1.2;transition:opacity .15s}} .tnmap a:hover path,.tnmap a:focus path{{opacity:.75;stroke:var(--ink);stroke-width:1.6;cursor:pointer}}
.tnmap text{{font-family:Archivo,sans-serif;font-size:11px;fill:var(--ink);text-anchor:middle;pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:3px}}
.maplegend{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;font-family:Archivo,sans-serif;font-size:.7rem;color:var(--ink-2);margin-top:8px}}
.maplegend i{{display:inline-block;width:14px;height:10px;margin-right:5px;vertical-align:middle;border:1px solid var(--rule)}} .maplegend em{{font-style:normal;color:var(--ink-3)}}
a{{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}} a:hover{{border-bottom-color:var(--accent)}}
.explain{{width:100%;box-sizing:border-box;border:1px solid var(--rule);border-left:4px solid var(--accent);background:var(--surface);padding:18px 22px 12px;margin:24px 0;font-size:.95rem;color:var(--ink)}}.explain h3{{font-family:Archivo,sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}}.explain ul{{margin:0;padding-left:1.15em;columns:2;column-gap:40px}} @media(max-width:820px){{.explain ul{{columns:1}}}}.explain li{{margin:0 0 9px;break-inside:avoid;line-height:1.5}} .explain li b{{color:var(--ink)}}
footer{{margin-top:36px;font-size:.8rem;color:var(--ink-3);max-width:80ch}}
</style>
<header><div class="hin"><div class="eyebrow">Civvix · Tennessee · public data only · $0 acquisition cost</div><h1>Tennessee Situs Atlas</h1>
<div class="sub">Every Tennessee county's rooftops placed inside the Department of Revenue's own sales-tax situs polygons, measured to the nearest jurisdictional seam, and cross-checked against the Comptroller's certified city limits and the 911 addressing authority. No confidential data was used. Counties with a published workbench are linked.</div></div></header>
<div class="wrap">
<div class="tiles"><div><div class="k">Counties run</div><div class="v">{tot["n"]} / 95</div></div><div><div class="k">Rooftops placed</div><div class="v">{tot["rooftops"]:,}</div></div><div><div class="k">Business points</div><div class="v">{tot["biz"]:,}</div></div><div><div class="k">Seam miles</div><div class="v">{tot["seam_mi"]:,.0f}</div></div><div><div class="k">Cross-county miles</div><div class="v">{tot["xc_mi"]:,.0f}</div></div><div><div class="k">Cross-county postal (biz)</div><div class="v" style="color:var(--crit)">{tot["cc"]:,}</div></div><div><div class="k">DOR file ≠ polygon</div><div class="v">{tot["E5"]:,}</div></div></div>
<div class="explain"><h3>How to read this</h3><ul><li><b>The map</b> — each county shaded by the local sales tax that appears to leave it across county lines each year: Tier A and B businesses at the county's average per business, both halves counted. A dashed outline means the county's <i>in-county</i> address-file class has not yet passed verification — that affects the Revenue flows figures, not this map. Hover for the figure; the Revenue flows view has the detail.</li><li><b>Cross-county postal</b> — a named business physically inside the county whose mailing city belongs to another county. A registration keyed to the mailing address codes it to that county, and <b>both halves</b> of the local option tax leave.</li><li><b>Boundary risk</b> — a business within 250 ft of a jurisdictional seam, where geocoder error alone can flip the jurisdiction. A control, not an error.</li><li><b>Postal exposure</b> — a city mailing address on a rooftop outside that city. The population in which miscoding occurs, not a finding by itself.</li><li><b>DOR file ≠ polygon</b> — rooftops where the State's own address-range file and the State's own tax polygon disagree by more than 250 ft. State data contradicting state data; needs no confidential file to prove.</li><li><b>DOR range match</b> — the share of rooftops the State's address-range file can place at all. Low values usually mean street-name conventions in the 911 layer, not errors.</li><li><b>None of these is a finding</b> until a situs report is compared. All of them rank where findings will be. The <b>Revenue flows</b> view sizes them in dollars.</li><li><b>No roster yet</b> — the Secretary of State entity file for that county has not been loaded, so no business points exist there; the rooftop-level columns are complete regardless.</li></ul></div>
<section class="mapwrap"><h2>{MAP_TITLE}</h2>{MAP_SVG}{MAP_LEGEND}</section>

<div class="tbox"><table><thead><tr><th>County</th><th>Situs codes</th><th>Rooftops</th><th>Businesses</th><th>Seam mi</th><th>Cross-county mi</th><th>DOR range match</th><th>Cross-county postal</th><th>Boundary risk</th><th>Postal exposure</th><th>DOR file ≠ polygon</th><th>Layers disagree</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>
<footer>Sources: TN Department of Revenue sales-tax rate boundaries and SST address-range file; TN Comptroller municipal boundaries; TN Emergency Communications Board NG911 address points; TN Secretary of State entity records; county 911 districts and city GIS where published. All distance math in EPSG:2274 (Tennessee State Plane, US ft). Business counts are named businesses only — subdivision, lot, utility and institutional labels are excluded. Prototype; not an audit finding.</footer>
</div>'''
(ROOT / "artifact" / "atlas.html").write_text(html)
print(f"atlas: {tot['n']} counties, {tot['rooftops']:,} rooftops, {tot['cc']:,} cross-county-postal businesses")
