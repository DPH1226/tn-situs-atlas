#!/usr/bin/env python3
"""
Revenue flows: for every named business the county runs flagged, where its local tax appears to
be going now, where the geography says it should go, and how confident that is.

    python3 build_flows.py            # every county with out/<slug>/business_exceptions.csv

Writes
    out/<slug>/business_flows.csv     one row per flagged business: current -> correct, tier, confidence
    out/flows_index.json              per-jurisdiction aggregates (counties, county treasuries, cities)
    artifact/flows.html               the Revenue flows page (build_site.py ships it as site/flows/)

Confidence is a MODEL SCORE, not a measured rate. Its rubric:

    placement   the run's evidence score (0-100): DOR polygon, 911 rooftop, layer agreement, address-range
                match, business point, seam distance. For E4 the -20 layer-conflict penalty is restored,
                because there the conflict IS the evidence.
    tier        A  the State's own instruments contradict each other, so the misdirection does not depend
                   on any taxpayer's behaviour: DOR's address-range file assigns a different situs than
                   DOR's polygon (E5, >250 ft from any seam), or DOR's polygon leaves a rooftop outside a
                   city that both the 911 authority and the Comptroller's CERTIFIED limits put inside it
                   (E4, >250 ft). Prior 0.90.
                B  mailing-address mechanism: the business sits inside this county but its mailing city
                   belongs to another county (E2), >250 ft from any seam, official layers agree. Situs codes
                   are keyed from whatever address the registrant wrote down. Prior 0.60.
                C  exposure: a city mailing address on a rooftop outside that city (E1), an address-file
                   conflict within 250 ft of a seam (E5B), or A/B evidence at the seam. Prior 0.25.
    confidence  round(prior x placement / 100). The priors are stated assumptions. The first situs report
                loaded into a workbench measures each class's actual precision (calibrate.py) and those
                measured rates replace the priors.

Direction:
    E5   current = DOR address file's situs        correct = DOR polygon's situs
    E4   current = DOR polygon's situs             correct = the city both other layers name
    E2   current = the mailing city's jurisdiction  correct = DOR polygon's situs
         (the mailing city's own code if it is an incorporated city, else that county's unincorporated code)
    E1   current = the mailing city's code          correct = DOR polygon's situs

Share at stake: a flow that crosses a county line moves both halves of the local option tax (the
education half stays with the collecting county); a flow inside one county moves the situs half only.
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT))
from fetch import config

OUTD = ROOT / "out"; ART = ROOT / "artifact"
PRIOR = {"A": 0.90, "B": 0.60, "C": 0.25}
AVG: dict = {}          # county -> average local option tax per located business (set in main)
DEEP_FT = 250


def norm(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)): return ""
    s = str(v).strip().upper().replace(".", "").replace("(", "").replace(")", "").replace("MOUNT ", "MT ")
    return "UNINCORPORATED" if s in {"UNINCORPORATED", "NONE", ""} else s


def s4(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    t = str(v).strip()
    if t in ("", "None", "nan"): return None
    try: return str(int(float(t))).zfill(4)
    except ValueError: return t[:4]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ----------------------------------------------------------------------------- valuation
def valuation():
    """Average local option sales tax per located business, per county: DOR's fiscal-year county total
    divided by the county run's business count. A mean, and a skewed one - a single big-box store
    outweighs a hundred salons - so it sizes a population, not a business."""
    cfg = json.loads((ROOT / "configs" / "local_option_sales_tax.json").read_text())
    avg, base = {}, {}
    for c in config.all_counties():
        sp = OUTD / c / "summary.json"
        if not sp.exists(): continue
        sm = json.loads(sp.read_text()); C = sm["county"]
        n = sm.get("totals", {}).get("business_points") or 0
        tot = cfg["counties"].get(C)
        if tot and n: avg[C] = tot / n; base[C] = dict(collections=tot, businesses=n)
    return avg, base, cfg


# ----------------------------------------------------------------------------- code book
def codebook():
    """code -> (county, name); (county, normalized city) -> code; county -> its unincorporated code."""
    code_of, name_of, county_code = {}, {}, {}
    for c in config.all_counties():           # configs cover all 95 counties whether or not they have been run
        cfg = config.county(c); C = cfg["county"]
        merge = {str(k).zfill(4): str(v).zfill(4) for k, v in (cfg.get("situs_merge") or {}).items()}
        for k, v in cfg["situs"].items():
            k = merge.get(str(k).zfill(4), str(k).zfill(4))
            name_of.setdefault(k, (C, v)); code_of[(C, norm(v))] = k
            if k.endswith("00"): county_code[C] = k
        if C not in county_code:              # consolidated metro: the merged code stands for the treasury
            county_code[C] = min(name_of[k][0] == C and k or "9999" for k in name_of) if any(name_of[k][0] == C for k in name_of) else None
    return code_of, name_of, county_code


def parse_disagreement(v):
    """'DOR=UNINCORPORATED | E911=MT JULIET | COMP=MT JULIET' -> dict"""
    out = {}
    if not isinstance(v, str): return out
    for part in v.split("|"):
        if "=" in part:
            k, val = part.split("=", 1); out[k.strip().upper()] = norm(val)
    return out


# ----------------------------------------------------------------------------- per business
def classify(r, C, code_of, county_code):
    """-> (tier, confidence, current_code, correct_code, cls) or None"""
    deep = float(r.nearest_seam_ft or 0) >= DEEP_FT
    score = float(r.evidence_score or 0)
    agree = bool(r.layers_agree) if not pd.isna(r.layers_agree) else True
    band = str(r.risk_band or "")
    dor = s4(r.dor_situs); sst = s4(r.sst_situs)
    if dor is None: return None
    # E4 in its city form: DOR polygon says elsewhere, 911 + Comptroller both say the same city
    if not agree:
        d = parse_disagreement(r.disagreement)
        if d.get("E911") and d.get("E911") == d.get("COMP") and d.get("COMP") != d.get("DOR"):
            corr = code_of.get((C, d["COMP"]))
            if corr and corr != dor:
                tier = "A" if deep else "C"
                return tier, round(PRIOR[tier] * min(100, score + 20)), dor, corr, "E4"
    # E5: DOR's own file against DOR's own polygon
    if sst and sst != dor:
        tier = "A" if (deep and score >= 85 and band != "CRITICAL") else "C"
        return tier, round(PRIOR[tier] * score), sst, dor, "E5" if deep else "E5B"
    # E2: mailing city belongs to another county
    home = str(r.postal_home_county) if not pd.isna(r.postal_home_county) else ""
    if bool(r.E2_CROSS_COUNTY_POSTAL) and home and home != C:
        cur = code_of.get((home, norm(r.post_city_n))) or county_code.get(home)
        if cur and cur != dor:
            tier = "B" if (deep and agree and score >= 85 and band != "CRITICAL") else "C"
            return tier, round(PRIOR[tier] * score), cur, dor, "E2"
    # E1: a city mailing address on a rooftop outside that city
    if bool(r.E1_POSTAL_CITY_OVERSTATES):
        cur = code_of.get((C, norm(r.post_city_n)))
        if cur and cur != dor:
            return "C", round(PRIOR["C"] * score), cur, dor, "E1"
    return None


NEED = ["id", "business", "kind", "dor_situs", "dor_county", "sst_situs", "post_city_n", "postal_home_county", "evidence_score", "risk_band",
        "nearest_seam_ft", "layers_agree", "disagreement", "E2_CROSS_COUNTY_POSTAL", "E1_POSTAL_CITY_OVERSTATES", "Add_Number", "StNam_Full",
        "Zip_Code", "lon", "lat"]


def run_county(c: str, code_of, name_of, county_code) -> tuple[pd.DataFrame, str] | None:
    bz = OUTD / c / "business_exceptions.csv"
    if not bz.exists(): return None
    s = json.loads((OUTD / c / "summary.json").read_text()); C = s["county"]
    b = pd.read_csv(bz, low_memory=False, usecols=lambda k: k in NEED)
    for k in NEED:
        if k not in b.columns: b[k] = None
    b = b[(b["kind"].fillna("business") == "business")]
    rows = []
    for r in b.itertuples(index=False):
        x = classify(r, C, code_of, county_code)
        if not x: continue
        tier, conf, cur, corr, cls = x
        cc, cn = name_of.get(cur, ("?", cur)); rc, rn = name_of.get(corr, ("?", corr))
        rows.append(dict(id=r.id, business=r.business, address=" ".join(str(v) for v in (r.Add_Number, r.StNam_Full) if not pd.isna(v)),
                         zip=r.Zip_Code, tier=tier, confidence=conf, cls=cls,
                         current=cur, current_name=cn, current_county=cc, correct=corr, correct_name=rn, correct_county=rc,
                         share="both halves" if cc != rc else "situs half",
                         value=round(AVG.get(rc, 0) * (1.0 if cc != rc else 0.5)),
                         placement=r.evidence_score, seam_ft=r.nearest_seam_ft, lon=r.lon, lat=r.lat))
    df = pd.DataFrame(rows, columns=["id", "business", "address", "zip", "tier", "confidence", "cls", "current", "current_name", "current_county",
                                     "correct", "correct_name", "correct_county", "share", "value", "placement", "seam_ft", "lon", "lat"])
    df = df.sort_values(["tier", "confidence"], ascending=[True, False])
    df.to_csv(OUTD / c / "business_flows.csv", index=False)
    return df, C


# ----------------------------------------------------------------------------- aggregation
def aggregate(frames: dict[str, pd.DataFrame], name_of, county_code):
    """Per jurisdiction: owed (correct == J, current != J) and in-error (current == J, correct != J), by tier."""
    allf = pd.concat(frames.values(), ignore_index=True) if frames else pd.DataFrame()
    tiers = ["A", "B", "C"]

    def bucket(sub_owed, sub_err):
        d = {}
        for t in tiers:
            d[f"owed_{t}"] = int((sub_owed.tier == t).sum()); d[f"err_{t}"] = int((sub_err.tier == t).sum())
            d[f"owed_val_{t}"] = int(sub_owed.loc[sub_owed.tier == t, "value"].sum()) if len(sub_owed) else 0
            d[f"err_val_{t}"] = int(sub_err.loc[sub_err.tier == t, "value"].sum()) if len(sub_err) else 0
        d["owed"] = int(len(sub_owed)); d["err"] = int(len(sub_err))
        return d

    def flows(sub, key_from, key_to):
        g = sub.groupby([key_from, key_to, "tier"]).size().reset_index(name="n")
        return [dict(zip(("frm", "to", "tier", "n"), row)) for row in g.itertuples(index=False)]

    out = {"counties": [], "treasuries": [], "cities": []}
    # counties as a whole: cross-county flows only (both halves)
    for C in sorted({v[0] for v in name_of.values()}):
        owed = allf[(allf.correct_county == C) & (allf.current_county != C)]
        err = allf[(allf.current_county == C) & (allf.correct_county != C)]
        d = dict(jurisdiction=C, slug=C.lower().replace(" ", ""), **bucket(owed, err))
        d["owed_from"] = flows(owed, "current_county", "correct_name")
        d["err_to"] = flows(err, "correct_county", "correct_name")
        out["counties"].append(d)
    # every situs code: county treasuries (…00) and cities
    for code, (C, nm) in sorted(name_of.items()):
        owed = allf[(allf.correct == code) & (allf.current != code)]
        err = allf[(allf.current == code) & (allf.correct != code)]
        if not len(owed) and not len(err): continue
        d = dict(code=code, jurisdiction=nm, county=C, **bucket(owed, err))
        d["owed_from"] = flows(owed, "current_name", "current_county")
        d["err_to"] = flows(err, "correct_name", "correct_county")
        (out["treasuries"] if code == county_code.get(C) else out["cities"]).append(d)
    # multi-county cities: merge by normalized name
    merged = defaultdict(list)
    for d in out["cities"]: merged[norm(d["jurisdiction"])].append(d)
    cities = []
    for k, parts in merged.items():
        m = dict(jurisdiction=parts[0]["jurisdiction"], slug=slugify(parts[0]["jurisdiction"]), codes=[p["code"] for p in parts], counties=sorted({p["county"] for p in parts}))
        for f in [x for x in parts[0] if x.startswith(("owed", "err")) and x not in ("owed_from", "err_to")]:
            m[f] = sum(p[f] for p in parts)
        m["owed_from"] = [x for p in parts for x in p["owed_from"]]; m["err_to"] = [x for p in parts for x in p["err_to"]]
        cities.append(m)
    out["cities"] = cities
    out["totals"] = {t: {"owed": int((allf.tier == t).sum()), "value": int(allf.loc[allf.tier == t, "value"].sum()),
                         "cross": int(((allf.tier == t) & (allf.share == "both halves")).sum()),
                         "cross_value": int(allf.loc[(allf.tier == t) & (allf.share == "both halves"), "value"].sum())} for t in tiers} if len(allf) else {}
    out["totals"]["businesses_flagged"] = int(len(allf))
    return out


# ----------------------------------------------------------------------------- page
CSS = """
:root{--paper:#F4F5F2;--surface:#fff;--surface-2:#EDEFEB;--ink:#16202B;--ink-2:#3D4B57;--ink-3:#6B7A86;--rule:#D2D8DB;--rule-2:#E3E7E6;--accent:#1F5C7A;--crit:#A8322D;--high:#B0722A;--watch:#5E7686;--clear:#3A7358}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}}
:root[data-theme="dark"]{--paper:#10161C;--surface:#171F27;--surface-2:#1E2831;--ink:#E8EDEF;--ink-2:#AFBCC5;--ink-3:#7E8D98;--rule:#2C3843;--rule-2:#222D36;--accent:#6FB3D2;--crit:#E9827C;--high:#DFA862;--watch:#9CB0BD;--clear:#6FBE96}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Source Serif 4",Georgia,serif;font-size:15px;line-height:1.55}
.wrap{max-width:1240px;margin:0 auto;padding-inline:20px;padding-block:0 60px}
header{border-bottom:2px solid var(--ink);background:var(--surface)} .hin{max-width:1240px;margin:0 auto;padding:26px 20px 18px}
.eyebrow{font-family:Archivo,sans-serif;font-size:.68rem;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}
h1{font-family:Archivo,sans-serif;font-size:2rem;font-weight:700;letter-spacing:-.02em;margin:.15em 0 .2em}
h2{font-family:Archivo,sans-serif;font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin:30px 0 8px}
.sub{color:var(--ink-2);max-width:70ch}
.views{display:flex;gap:2px;margin:14px 0 0;font-family:Archivo,sans-serif;font-size:.74rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
.views a{padding:7px 14px;border:1px solid var(--rule);border-bottom:0;color:var(--ink-3);background:var(--surface-2);text-decoration:none}
.views a.on{color:var(--ink);background:var(--surface);border-color:var(--ink);border-bottom:2px solid var(--surface);margin-bottom:-2px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border:1px solid var(--rule);background:var(--surface);margin:26px 0}
.tiles div{padding:14px 16px;border-right:1px solid var(--rule-2)} .tiles div:last-child{border-right:0}
.k{font-family:Archivo,sans-serif;font-size:.66rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)} .v{font-family:"IBM Plex Mono",monospace;font-size:1.4rem;margin-top:4px}
.tools{display:flex;gap:10px;align-items:center;margin:0 0 10px;font-family:Archivo,sans-serif;font-size:.78rem}
.tools input{font:inherit;padding:6px 9px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);min-width:240px}
.tbox{border:1px solid var(--rule);background:var(--surface);overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.82rem} th{position:sticky;top:0;background:var(--surface-2);font-family:Archivo,sans-serif;font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
th.n{text-align:right} td{padding:7px 10px;border-bottom:1px solid var(--rule-2);vertical-align:top} td.n{font-family:"IBM Plex Mono",monospace;text-align:right;font-variant-numeric:tabular-nums}
td.owed{color:var(--clear);font-weight:600} td.err{color:var(--crit);font-weight:600} td.dim{color:var(--ink-3)} td.cty{color:var(--ink-3);font-size:.78rem}
th.grp{text-align:center;border-left:1px solid var(--rule)} td.gl{border-left:1px solid var(--rule)}
details{border:1px solid var(--rule);background:var(--surface);margin:8px 0} summary{cursor:pointer;padding:9px 12px;font-family:Archivo,sans-serif;font-size:.8rem;font-weight:600}
details table{font-size:.78rem} details .in{padding:0 12px 10px}
.flow{display:grid;grid-template-columns:1fr 1fr;gap:16px} @media(max-width:800px){.flow{grid-template-columns:1fr}}
.flow h4{font-family:Archivo,sans-serif;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;margin:8px 0 4px;color:var(--ink-3)}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent} a:hover{border-bottom-color:var(--accent)}
.note{border-left:3px solid var(--accent);background:var(--surface);padding:12px 16px;margin:22px 0;color:var(--ink-2);max-width:78ch;font-size:.92rem}
.rubric{border:1px solid var(--rule);background:var(--surface);padding:12px 16px;margin:14px 0;font-size:.86rem;max-width:90ch}
.rubric b.t{font-family:"IBM Plex Mono",monospace}
footer{margin-top:36px;font-size:.8rem;color:var(--ink-3);max-width:80ch}
"""
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">'
JS = """
(function(){function wire(tid,qid,cid){var q=document.getElementById(qid),rows=[].slice.call(document.querySelectorAll("#"+tid+" tbody tr")),cnt=document.getElementById(cid);
function f(){var v=q.value.trim().toLowerCase(),k=0;rows.forEach(function(r){var on=!v||(r.dataset.q||"").indexOf(v)>=0;r.style.display=on?"":"none";if(on)k++;});cnt.textContent=k+" of "+rows.length;}
q.addEventListener("input",f);f();
[].forEach.call(document.querySelectorAll("#"+tid+" thead tr:last-child th"),function(th,i){th.addEventListener("click",function(){var tb=th.closest("table").tBodies[0],rs=[].slice.call(tb.rows),num=th.classList.contains("n"),asc=th.dataset.asc!=="1";
rs.sort(function(a,b){var x=a.cells[i].textContent.replace(/[,—↗]/g,"").trim(),y=b.cells[i].textContent.replace(/[,—↗]/g,"").trim();if(num){x=parseFloat(x)||0;y=parseFloat(y)||0;return asc?y-x:x-y;}return asc?x.localeCompare(y):y.localeCompare(x);});
rs.forEach(function(r){tb.appendChild(r);});[].forEach.call(th.parentNode.children,function(h){delete h.dataset.asc;});th.dataset.asc=asc?"1":"0";});});}
wire("tc","qc","cc");wire("tt","qt","ct");wire("ty","qy","cy");})();
"""


def n(v): return f"{v:,.0f}" if v else "—"
def usd(v): return "$" + f"{v:,.0f}" if v else "—"


EXPLAIN_CSS = """
.explain{border:1px solid var(--rule);border-left:4px solid var(--accent);background:var(--surface);padding:18px 22px 12px;margin:24px 0;font-size:.95rem;color:var(--ink)}
.explain h3{font-family:Archivo,sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}
.explain ul{margin:0;padding-left:1.15em;columns:2;column-gap:40px} @media(max-width:820px){.explain ul{columns:1}}
.explain li{margin:0 0 9px;break-inside:avoid;line-height:1.5} .explain li b{color:var(--ink)} .explain .t{font-family:"IBM Plex Mono",monospace;font-weight:600}
.scen{border:1px solid var(--ink);background:var(--surface);padding:18px 22px;margin:24px 0}
.scen h3{font-family:Archivo,sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0 0 12px}
.scen .ctl{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px 28px;align-items:end}
.scen label{display:block;font-family:Archivo,sans-serif;font-size:.74rem;font-weight:600;color:var(--ink-2);margin-bottom:6px}
.scen input[type=range]{width:100%} .scen output{font-family:"IBM Plex Mono",monospace;font-weight:600;color:var(--ink)}
.scen select,.scen input[type=number]{font:inherit;padding:6px 8px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);width:100%}
.scen .res{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));border-top:1px solid var(--rule-2);margin-top:16px;padding-top:14px;gap:12px}
.scen .res .k{margin-bottom:3px} .scen .res .v{font-size:1.25rem}
td.money{font-family:"IBM Plex Mono",monospace;text-align:right;font-variant-numeric:tabular-nums} td.pos{color:var(--clear)} td.neg{color:var(--crit)}
th.sc{background:var(--surface-2);border-left:1px solid var(--rule)} td.sc{border-left:1px solid var(--rule)}
"""

SCEN_JS = """
(function(){
  var tiersOf={A:["A"],AB:["A","B"],ABC:["A","B","C"]};
  var pin=document.getElementById("pin"),pout=document.getElementById("pout"),tsel=document.getElementById("tsel"),grow=document.getElementById("grow");
  var oIn=document.getElementById("pin_v"),oOut=document.getElementById("pout_v");
  function fmt(v){var a=Math.abs(v);var s=a>=1e6?(a/1e6).toFixed(2)+"M":a>=1e3?(a/1e3).toFixed(0)+"K":a.toFixed(0);return (v<0?"\u2212$":"$")+s;}
  function sum(el,pfx,ts){var t=0;ts.forEach(function(k){t+=parseFloat(el.dataset[pfx+k.toLowerCase()]||0);});return t;}
  function run(){
    var a=pin.value/100,b=pout.value/100,ts=tiersOf[tsel.value],g=parseFloat(grow.value)||1;
    oIn.textContent=pin.value+"%";oOut.textContent=pout.value+"%";
    var TR=0,TL=0;
    document.querySelectorAll("tr[data-owed_val_a]").forEach(function(tr){
      var rec=sum(tr,"owed_val_",ts)*a*g,lost=sum(tr,"err_val_",ts)*b*g,net=rec-lost;
      var c=tr.querySelectorAll("td.sc");if(c.length<3)return;
      c[0].textContent=rec?fmt(rec):"\u2014";c[1].textContent=lost?fmt(lost):"\u2014";c[2].textContent=fmt(net);
      c[2].className="sc money "+(net>0?"pos":net<0?"neg":"");
      if(tr.dataset.kind==="county"){TR+=rec;TL+=lost;}
    });
    var A=parseFloat(document.getElementById("stw").dataset.tierA)*g;
    document.getElementById("r_gross").textContent=fmt(A);
    document.getElementById("r_prior").textContent=fmt(A*0.9);
    document.getElementById("r_cycle").textContent=fmt(A*2);
    document.getElementById("r_scen").textContent=fmt(TR);
    document.getElementById("r_cede").textContent=fmt(TL);
  }
  [pin,pout,tsel,grow].forEach(function(e){e.addEventListener("input",run);e.addEventListener("change",run);});
  run();
})();
"""


def flow_table(rows, head_from, head_to):
    if not rows: return '<span class="dim" style="color:var(--ink-3)">none</span>'
    agg = defaultdict(int)
    for r in rows: agg[(r["frm"], r["to"], r["tier"])] += r["n"]
    items = sorted(agg.items(), key=lambda kv: -kv[1])
    trs = "".join(f'<tr><td>{a}</td><td class="cty">{b}</td><td class="n">{t}</td><td class="n">{n(c)}</td></tr>' for (a, b, t), c in items[:40])
    return f'<table><thead><tr><th>{head_from}</th><th>{head_to}</th><th class="n">Tier</th><th class="n">Businesses</th></tr></thead><tbody>{trs}</tbody></table>'


def write_page(agg: dict):
    T = agg["totals"]; V = agg.get("valuation", {}); FY = V.get("fiscal_year", "")
    tierA_val = T.get("A", {}).get("value", 0); tierA_n = T.get("A", {}).get("owed", 0)
    tierA_x = T.get("A", {}).get("cross", 0); tierA_xv = T.get("A", {}).get("cross_value", 0)
    W = V.get("counties", {}).get("WILSON", {})

    VER = agg.get("verification", {}); AV = T.get("A_verified", {}); AU = T.get("A_unverified", {})
    def vtag(C):
        v = VER.get(C); 
        if not v: return '<span class="cty">not run</span>'
        w = v["verdict"].split(" ")[0]; col = {"REAL": "var(--clear)", "MIXED": "var(--high)", "SUSPECT": "var(--crit)"}.get(w, "var(--ink-3)")
        return f'<span style="color:{col};font-family:Archivo,sans-serif;font-size:.7rem;font-weight:700;letter-spacing:.06em" title="streets {v["systematic_pct"]}% systematic · labels {v["label_pct"]}% · referee {v["referee_pct"]}%">{w}</span>'
    def hdr(): return ('<tr><th rowspan="2">Jurisdiction</th><th rowspan="2">County</th>'
                       '<th class="n grp" colspan="4">Owed to it — businesses inside, appearing to pay elsewhere</th>'
                       '<th class="n grp" colspan="4">Receiving in error — businesses outside, appearing to pay it</th>'
                       '<th class="n sc" colspan="3">At the scenario above (per year)</th></tr>'
                       '<tr><th class="n gl">A</th><th class="n">B</th><th class="n">C</th><th class="n">All</th><th class="n gl">A</th><th class="n">B</th><th class="n">C</th><th class="n">All</th>'
                       '<th class="n sc">Recovered</th><th class="n">Ceded</th><th class="n">Net</th></tr>')
    def attrs(d): return " ".join(f'data-{k}="{d[k]}"' for k in d if k.startswith(("owed_val_", "err_val_")))
    def cells(d): return (f'<td class="n gl owed">{n(d["owed_A"])}</td><td class="n">{n(d["owed_B"])}</td><td class="n dim">{n(d["owed_C"])}</td><td class="n">{n(d["owed"])}</td>'
                          f'<td class="n gl err">{n(d["err_A"])}</td><td class="n">{n(d["err_B"])}</td><td class="n dim">{n(d["err_C"])}</td><td class="n">{n(d["err"])}</td>'
                          '<td class="sc money"></td><td class="sc money"></td><td class="sc money"></td>')
    def details(d, kind):
        nm = d["jurisdiction"] if kind != "county" else d["jurisdiction"].title() + " County (cross-county flows)"
        return (f'<details><summary>{nm}{" · " + ", ".join(x.title() for x in d.get("counties", [])) if d.get("counties") else ""} — owed {n(d["owed"])} · receiving in error {n(d["err"])}</summary>'
                f'<div class="in"><div class="flow"><div><h4>Owed: currently appearing to go to</h4>{flow_table(d["owed_from"], "From", "Where it belongs")}</div>'
                f'<div><h4>Receiving in error: should be going to</h4>{flow_table(d["err_to"], "To", "County")}</div></div></div></details>')

    cty_rows = sorted(agg["counties"], key=lambda d: -(d["owed_val_A"] + d["err_val_A"]))
    trs_c = "".join(f'<tr data-kind="county" data-q="{d["jurisdiction"].lower()}" {attrs(d)}><td><a href="../{d["slug"]}/">{d["jurisdiction"].title()} ↗</a> {vtag(d["jurisdiction"])}</td><td class="cty">cross-county</td>{cells(d)}</tr>' for d in cty_rows if d["owed"] or d["err"])
    tre_rows = sorted(agg["treasuries"], key=lambda d: -(d["owed_val_A"] + d["err_val_A"]))
    trs_t = "".join(f'<tr data-kind="treasury" data-q="{d["county"].lower()} {d["jurisdiction"].lower()}" {attrs(d)}><td>{d["county"].title()} — {d["jurisdiction"]} <span class="cty">{d["code"]}</span> {vtag(d["county"])}</td><td class="cty">situs half</td>{cells(d)}</tr>' for d in tre_rows)
    city_rows = sorted(agg["cities"], key=lambda d: -(d["owed_val_A"] + d["err_val_A"]))
    trs_y = "".join(f'<tr data-kind="city" data-q="{d["jurisdiction"].lower()} {" ".join(d["counties"]).lower()}" {attrs(d)}><td><a href="../cities/{d["slug"]}/">{d["jurisdiction"]} ↗</a></td><td class="cty">{", ".join(c.title() for c in d["counties"])}</td>{cells(d)}</tr>' for d in city_rows)
    det = "".join(details(d, "county") for d in cty_rows if d["owed"] or d["err"]) + "".join(details(d, "treasury") for d in tre_rows) + "".join(details(d, "city") for d in city_rows)

    html = f"""<title>Tennessee Situs Atlas — Revenue flows</title>
{FONTS}
<style>{CSS}{EXPLAIN_CSS}</style>
<header><div class="hin"><div class="eyebrow">Civvix · Tennessee · public data only · model scores, not measured rates</div><h1>Tennessee Situs Atlas</h1>
<div class="sub">For every named business the county runs flagged: where its local option sales tax appears to be going now, where the geography says it should go, what that is worth, and how confident that is. Two directions for every jurisdiction — what it is owed, and what it is receiving in error.</div>
<nav class="views"><a href="../">Counties</a><a href="../cities/">Cities</a><a class="on" href="./">Revenue flows</a></nav></div></header>
<div class="wrap">

<div class="explain"><h3>How to read this</h3><ul>
<li><b>Owed to it</b> — named businesses physically inside the jurisdiction whose evidence says their local tax is going somewhere else. If corrected, this money comes <b>in</b>.</li>
<li><b>Receiving in error</b> — named businesses physically outside the jurisdiction whose evidence says their local tax is going to it. If a neighbour corrects them, this money goes <b>out</b>.</li>
<li><b>Every flow appears twice</b> — once as owed to the jurisdiction it belongs to, once as received in error by the jurisdiction currently getting it. Statewide, the two columns describe the same dollars.</li>
<li><b>Tier A</b> — the State's own instruments contradict each other. The Department's address-range file assigns a different situs than the Department's own polygon, or the Department's polygon leaves a rooftop outside a city that both the 911 authority and the Comptroller's certified limits place inside it. More than 250 ft from any seam. This does not depend on any taxpayer's behaviour.</li>
<li><b>Tier B</b> — the mechanism that produces miscoding is present: the business sits inside this county but its mailing city belongs to another county. Situs codes are keyed from whatever address the registrant wrote down. More than 250 ft from any seam, official layers in agreement.</li>
<li><b>Tier C</b> — exposure: a city mailing address on a rooftop outside that city, or A/B evidence within 250 ft of a seam, where boundary precision alone could explain it.</li>
<li><b>County rows</b> show cross-county flows only. <b>Treasury rows</b> show the county's unincorporated code against its own cities. <b>City rows</b> show each city against everything around it.</li>
<li><b>None of this is a finding</b> until a situs report is compared. The counts rank where findings will be; the dollars size them.</li>
</ul></div>

<div class="explain"><h3>Share at stake, and what a business is worth</h3><ul>
<li><b>Across a county line, both halves move.</b> Half of the local option tax goes to education and stays with the collecting county; the other half follows the situs code. A business coded to the wrong county takes both halves with it.</li>
<li><b>Inside a county, the situs half moves.</b> A business coded unincorporated that sits inside a city — or the reverse — shifts only the half that follows the code. The education half stays put either way.</li>
<li><b>A business is valued at its county's average.</b> {FY} local sales tax collected in the county (Department of Revenue June book, page 13) divided by the businesses the run located there. Wilson: {usd(W.get("collections", 0))} ÷ {n(W.get("businesses", 0))} = <b>{usd(W.get("avg_per_business", 0))} a year</b>. Cross-county flows count the whole average; in-county flows count half.</li>
<li><b>It is a mean, and a skewed one.</b> One big-box store outweighs a hundred salons. The average sizes a population of businesses; it says nothing about any one of them.</li>
<li><b>It is an upper bound.</b> Since 2020 county totals include remote sales sourced by delivery address, which no seller's situs code controls. The origin-sourced share — the part situs coding governs — is smaller.</li>
<li><b>A correction pays twice.</b> The Department goes back one year from notification, then the corrected code is permanent. First-cycle value is roughly two years' worth; every year after is the annual figure.</li>
</ul></div>

<div class="explain"><h3>How confidence is scored</h3><ul>
<li><b>Placement</b> — the run's evidence score for the rooftop, 0 to 100: DOR polygon, 911 rooftop, layer agreement, address-range match, business point, distance from the seam. For Tier A's layer-conflict case the −20 conflict penalty is restored, because there the conflict <i>is</i> the evidence.</li>
<li><b>Prior</b> — a stated assumption per tier: <span class="t">A 0.90 · B 0.60 · C 0.25</span>.</li>
<li><b>Confidence</b> = prior × placement ÷ 100. Every business carries it in <span class="t">business_flows.csv</span>.</li>
<li><b>Verification.</b> Each county's address-file signal is tested by <span class="t">tools/verify_e5.py</span>: do the 911 authority and the Comptroller side with the polygon against the file, do whole streets flip together, and does the file's own city label name the annexing city? <b style="color:var(--clear)">REAL</b> passes all three; <b style="color:var(--high)">MIXED</b> passes the referee and one other; <b style="color:var(--crit)">SUSPECT</b> looks like a matching artifact and is excluded from the verified headline.</li>
<li><b>The priors are assumptions, not measurements.</b> The first situs report loaded into a workbench measures each tier's actual precision, and those measured rates replace the priors on this page. Until then, Tier A means "the State disagrees with itself here" and Tier B means "the mechanism is present here" — not a probability that any named business is miscoded.</li>
</ul></div>

<div class="scen" id="stw" data-tier-a="{tierA_val}"><h3>Scenario</h3>
<div class="ctl">
<div><label for="pin">Share of <b>owed</b> businesses the jurisdiction recovers: <output id="pin_v">10%</output></label><input type="range" id="pin" min="0" max="50" step="1" value="10"></div>
<div><label for="pout">Share of <b>received-in-error</b> businesses a neighbour corrects: <output id="pout_v">10%</output></label><input type="range" id="pout" min="0" max="50" step="1" value="10"></div>
<div><label for="tsel">Tiers included</label><select id="tsel"><option value="A">A only — State contradicts itself</option><option value="AB" selected>A + B — plus cross-county mechanism</option><option value="ABC">A + B + C — everything flagged</option></select></div>
<div><label for="grow">Growth since {FY} (1.00 = as published)</label><input type="number" id="grow" min="0.5" max="2" step="0.01" value="1.00"></div>
</div>
<div class="res">
<div><div class="k">Tier A · verified counties · per year</div><div class="v" style="color:var(--clear)">{usd(AV.get("value", 0))}</div><small style="color:var(--ink-3)">{n(AV.get("owed", 0))} businesses in {AV.get("counties", 0)} counties whose address-file signal passed verification (tools/verify_e5.py)</small></div>
<div><div class="k">Tier A · all counties · per year</div><div class="v" id="r_gross">—</div><small style="color:var(--ink-3)">{n(tierA_n)} businesses; includes {usd(AU.get("value", 0))} in {n(AU.get("owed", 0))} businesses from counties marked MIXED, SUSPECT or not yet run</small></div>
<div><div class="k">× 0.90 prior</div><div class="v" id="r_prior">—</div><small style="color:var(--ink-3)">the stated-prior expectation</small></div>
<div><div class="k">Tier A · first cycle</div><div class="v" id="r_cycle">—</div><small style="color:var(--ink-3)">one-year lookback plus the first corrected year</small></div>
<div><div class="k">Cross-county · Tier A</div><div class="v" style="color:var(--crit)">{usd(tierA_xv)}</div><small style="color:var(--ink-3)">{n(tierA_x)} businesses, both halves at stake</small></div>
<div><div class="k">Recovered at scenario · all counties</div><div class="v" id="r_scen">—</div><small style="color:var(--ink-3)">cross-county flows, per year</small></div>
<div><div class="k">Ceded at scenario · all counties</div><div class="v" id="r_cede">—</div><small style="color:var(--ink-3)">the same dollars, seen from the losing side</small></div>
</div></div>

<h2>Counties — cross-county flows (both halves at stake)</h2>
<div class="tools"><input id="qc" type="search" placeholder="Filter counties" aria-label="Filter counties"><span id="cc"></span></div>
<div class="tbox"><table id="tc"><thead>{hdr()}</thead><tbody>{trs_c}</tbody></table></div>

<h2>County treasuries — unincorporated code against the county's own cities (situs half)</h2>
<div class="tools"><input id="qt" type="search" placeholder="Filter" aria-label="Filter treasuries"><span id="ct"></span></div>
<div class="tbox"><table id="tt"><thead>{hdr()}</thead><tbody>{trs_t}</tbody></table></div>

<h2>Cities</h2>
<div class="tools"><input id="qy" type="search" placeholder="Filter cities" aria-label="Filter cities"><span id="cy"></span></div>
<div class="tbox"><table id="ty"><thead>{hdr()}</thead><tbody>{trs_y}</tbody></table></div>

<h2>Where the revenue appears to be going — by jurisdiction</h2>
{det}
<footer>Valuation: {V.get("source", "")} — <a href="{V.get("source_url", "#")}">source</a>. Business-level detail, with each business's current and correct situs, tier, confidence and value, is in out/&lt;county&gt;/business_flows.csv and feeds the correction packet. Public-data screening; not an audit finding.</footer>
</div>
<script>{JS}{SCEN_JS}</script>"""
    (ART / "flows.html").write_text(html)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--county", nargs="*"); a = ap.parse_args()
    code_of, name_of, county_code = codebook()
    avg, base, taxcfg = valuation(); AVG.update(avg)
    frames = {}
    for c in config.all_counties():
        if a.county and c not in [x.lower() for x in a.county]: continue
        r = run_county(c, code_of, name_of, county_code)
        if r is None: continue
        df, C = r; frames[c] = df
        print(f"  {C:<12} flagged {len(df):>6,}  A {int((df.tier=='A').sum()):>5,}  B {int((df.tier=='B').sum()):>5,}  C {int((df.tier=='C').sum()):>5,}", flush=True)
    agg = aggregate(frames, name_of, county_code)
    ver = {}
    for c in config.all_counties():
        vp = OUTD / c / "e5_verification.json"
        if vp.exists():
            v = json.loads(vp.read_text()); C = config.county(c)["county"]
            ver[C] = {"verdict": v.get("verdict", ""), "systematic_pct": v.get("streets", {}).get("e5_on_systematic_streets_pct"),
                      "referee_pct": v.get("referee", {}).get("both_pct"), "label_pct": v.get("labels", {}).get("file_city_label_matches_polygon_city_pct")}
    agg["verification"] = ver
    allf = pd.concat(frames.values(), ignore_index=True) if frames else pd.DataFrame()
    if len(allf):
        real = {C for C, v in ver.items() if v["verdict"].startswith("REAL")}
        a_real = allf[(allf.tier == "A") & (allf.correct_county.isin(real))]
        a_unv = allf[(allf.tier == "A") & ~allf.correct_county.isin(real)]
        agg["totals"]["A_verified"] = {"owed": int(len(a_real)), "value": int(a_real.value.sum()), "counties": len(real)}
        agg["totals"]["A_unverified"] = {"owed": int(len(a_unv)), "value": int(a_unv.value.sum())}
    agg["valuation"] = {"fiscal_year": taxcfg["fiscal_year"], "source": taxcfg["source"], "source_url": taxcfg["source_url"],
                        "counties": {C: dict(base[C], avg_per_business=round(avg[C])) for C in avg}}
    (OUTD / "flows_index.json").write_text(json.dumps(agg, indent=1))
    write_page(agg)
    print(f"flows: {agg['totals'].get('businesses_flagged', 0):,} businesses -> {ART / 'flows.html'}")


if __name__ == "__main__":
    main()
