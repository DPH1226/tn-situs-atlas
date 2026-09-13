/* Wilson County Situs Control - rendering and interaction.
   Data arrives as window.WILSON from data.js. */
(function () {
  "use strict";
  var W = window.WILSON, S = W.summary, B = W.biz_summary;
  var F = W.biz_fields, IX = {};
  F.forEach(function (n, i) { IX[n] = i; });

  var nf = function (n) { return (n == null ? "—" : Number(n).toLocaleString("en-US")); };
  var css = function (v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); };

  /* ---------- run header ---------- */
  document.getElementById("rundate").textContent =
    new Date(S.generated_utc).toLocaleDateString("en-US",
      { year: "numeric", month: "short", day: "2-digit" }).toUpperCase();

  /* ---------- 01 readout ---------- */
  var T = S.totals;
  [["Rooftops placed", nf(T.address_points_in_wilson), "address points, Wilson County"],
   ["Unplaced", nf(T.address_points_matching_no_dor_polygon), "outside every DOR polygon"],
   ["Jurisdictional seam", T.seam_miles.toFixed(1), "linear miles bounding Wilson"],
   ["Cross-county seam", T.cross_county_seam_miles.toFixed(1), "miles where both halves are at risk"],
   ["Businesses located", nf(T.business_points_in_wilson), "public rooftop business points"],
   ["DOR address file", T.sst_range_match_rate_pct + "%", "of rooftops matched a DOR range"]
  ].forEach(function (r) {
    var d = document.createElement("div");
    d.innerHTML = '<div class="k"></div><div class="v"></div><div class="u"></div>';
    d.children[0].textContent = r[0]; d.children[1].textContent = r[1]; d.children[2].textContent = r[2];
    document.getElementById("readout").appendChild(d);
  });

  /* ---------- 02 band ruler ---------- */
  var bands = [
    { k: "CRITICAL", lo: 0, hi: 50, c: "--sev-crit", bg: "--crit-bg", act: "mandatory human adjudication" },
    { k: "HIGH", lo: 50, hi: 250, c: "--sev-high", bg: "--high-bg", act: "elevated review of every layer" },
    { k: "WATCH", lo: 250, hi: 1000, c: "--sev-watch", bg: "--watch-bg", act: "automated, re-check on boundary change" },
    { k: "NORMAL", lo: 1000, hi: null, c: "--sev-clear", bg: "--clear-bg", act: "normal automated processing" }
  ];
  var total = bands.reduce(function (a, b) { return a + (S.risk_bands[b.k] || 0); }, 0);
  var bar = document.getElementById("rulerbar"), tick = document.getElementById("tickrow"),
      key = document.getElementById("bandkey");
  bands.forEach(function (b) {
    var n = S.risk_bands[b.k] || 0, pct = total ? n / total * 100 : 0;
    var i = document.createElement("i");
    i.style.cssText = "flex:" + Math.max(pct, 3) + " 0 auto;background:var(" + b.bg +
      ");border-right:1px solid var(--rule);display:flex;align-items:center;justify-content:center;" +
      "font-family:var(--mono);font-size:.7rem;font-weight:600;color:var(" + b.c + ")";
    i.textContent = pct >= 1.5 ? pct.toFixed(1) + "%" : "";
    i.title = b.k + " — " + nf(n) + " rooftops";
    bar.appendChild(i);
    var t = document.createElement("span");
    t.style.cssText = "flex:" + Math.max(pct, 3) + " 0 auto";
    t.textContent = b.hi === null ? "1000 ft +" : b.lo + "–" + b.hi + " ft";
    tick.appendChild(t);
    var s = document.createElement("span");
    s.innerHTML = '<span class="sw"></span><b style="font-family:var(--sans);font-weight:600"></b>' +
      '<span class="mono"></span> · <span></span>';
    s.children[0].style.background = "var(" + b.bg + ")";
    s.children[0].style.borderColor = "var(" + b.c + ")";
    s.children[1].textContent = b.k; s.children[1].style.color = "var(" + b.c + ")";
    s.children[2].textContent = nf(n);
    s.children[3].textContent = b.act;
    key.appendChild(s);
  });
  document.getElementById("seamct").textContent = T.seams_touching_wilson;

  /* ---------- 04 findings ---------- */
  var FIND = [
    { id: "E2_CROSS_COUNTY_POSTAL", sev: "crit", head: "Wilson rooftops carrying another county's mailing city",
      body: "These addresses are physically inside Wilson County, but the postal city on the mail belongs to " +
            "Davidson, Rutherford, DeKalb or Cannon. A registration keyed to the mailing address — which is " +
            "how situs codes are usually set, once, and never revisited — sends the money to that county. " +
            "Wilson loses the situs half and the education half. The concentration is stark: a single corridor " +
            "of Lebanon Road in ZIP 37138, where the Old Hickory delivery area crosses the Davidson line." },
    { id: "E5_DOR_INTERNAL_CONFLICT", sev: "high", head: "The Department's address file contradicts the Department's own boundary",
      body: "Tennessee publishes two things that should agree: a tax-rate polygon and a Streamlined Sales Tax " +
            "address-range file. For these rooftops they disagree, and not marginally — every one of these is " +
            "more than 250 feet from any seam, so boundary precision cannot explain it. The direction matters: " +
            "the address file says unincorporated far more often than the polygon does, which is what a file " +
            "lagging behind annexations looks like." },
    { id: "E4_LAYER_DISAGREEMENT", sev: "high", head: "Two official layers against one",
      body: "For these addresses the 911 addressing authority and the Comptroller's certified municipal boundary " +
            "both place the rooftop inside a city, while the Department's tax polygon calls it unincorporated. " +
            "Note the direction honestly: corrected, this moves money away from the county and toward Lebanon " +
            "and Mt. Juliet. A competent audit is bidirectional, and the engagement letter has to say so." },
    { id: "E6_ANNEXATION_LAG", sev: "high", head: "Inside a Mt. Juliet annexation the tax polygon does not reflect",
      body: "Mt. Juliet publishes 221 dated annexation polygons. These rooftops fall inside one of them but are " +
            "not coded to Mt. Juliet by the Department. Either the annexation has not propagated, or the city " +
            "layer runs ahead of its effective date. Both are findings, and they point in opposite directions — " +
            "which is exactly why the annexation ordinance date, not the polygon, is the controlling evidence." },
    { id: "E3_BOUNDARY_PROXIMITY", sev: "info", head: "Inside the boundary-risk band",
      body: "Close enough to a seam that geocoder error alone can flip the jurisdiction. Not an error — a control. " +
            "These are precisely the locations where a ZIP-code or centroid method silently guesses and never " +
            "reports that it guessed." },
    { id: "E1_POSTAL_CITY_OVERSTATES", sev: "info", head: "City mailing address, rooftop outside that city",
      body: "Large parts of unincorporated Wilson carry Lebanon and Mt. Juliet mailing addresses. This is not a " +
            "finding and must never be presented as one. It is the exposure population — the set of addresses " +
            "where a mailing-address-driven registration would land in the wrong jurisdiction. Which of them " +
            "actually did cannot be known until the situs report arrives." }
  ];
  var fw = document.getElementById("findings");
  FIND.forEach(function (f) {
    var meta = S.exceptions[f.id] || {};
    var el = document.createElement("article");
    el.className = "finding " + f.sev;
    el.innerHTML = '<div class="stripe"></div><div class="body">' +
      '<div class="top"><h3></h3><div style="display:flex;gap:12px;align-items:center">' +
      '<span class="loss"></span><span class="cnt"></span></div></div><p></p></div>';
    el.querySelector("h3").textContent = f.head;
    el.querySelector(".loss").textContent = meta.loss || "";
    el.querySelector(".cnt").textContent = nf(meta.count);
    el.querySelector("p").textContent = f.body;
    fw.appendChild(el);
  });

  /* ---------- 06 sources ---------- */
  [["TN DOR Sales Tax Rate Boundaries", "TN Dept. of Revenue", "Authoritative tax boundary", "Quarterly", "$0"],
   ["TN SST address-range lookup", "TN Dept. of Revenue", "DOR's own address-level situs", "Quarterly", "$0"],
   ["TN municipal boundaries, all 345 cities", "Comptroller, Office of Local Government", "Certified city limits", "Monthly", "$0"],
   ["TN NG911 Address Points", "TN Emergency Communications Board", "Rooftop location", "Monthly", "$0"],
   ["Wilson County 911 business points", "Wilson County ECD", "Public business universe", "Continuous", "$0"],
   ["Wilson County 911 address points", "Wilson County ECD", "Parcel join key (GISLINK)", "Continuous", "$0"],
   ["Mt. Juliet city limits, annexations, UGB", "City of Mt. Juliet", "Annexation history", "Continuous", "$0"],
   ["Wilson County parcels", "Wilson County GIS", "Parcel geometry — not used in this run", "On request", "$75"]
  ].forEach(function (r) {
    var tr = document.createElement("tr");
    r.forEach(function (c, i) {
      var td = document.createElement("td");
      td.textContent = c;
      if (i === 4) { td.className = "cost"; if (c !== "$0") td.style.color = "var(--sev-high)"; }
      tr.appendChild(td);
    });
    document.getElementById("srcbody").appendChild(tr);
  });

  /* ---------- map ---------- */
  var cv = document.getElementById("map"), ctx = cv.getContext("2d"), tip = document.getElementById("tip");
  var SIT = { "9500": "--s-9500", "9501": "--s-9501", "9502": "--s-9502", "9503": "--s-9503" };
  var SITNAME = { "9500": "Unincorporated", "9501": "Lebanon", "9502": "Watertown", "9503": "Mt. Juliet" };
  var FLAGCOL = { CROSS_COUNTY_POSTAL: "--sev-crit", BOUNDARY_RISK: "--sev-high", POSTAL_CITY_EXPOSURE: "--sev-watch" };
  var FLAGNAME = { CROSS_COUNTY_POSTAL: "Cross-county postal", BOUNDARY_RISK: "Boundary risk", POSTAL_CITY_EXPOSURE: "Postal city exposure" };

  var bb = { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9 };
  function scan(fc) {
    fc.features.forEach(function (f) { eachCoord(f.geometry, function (c) {
      if (c[0] < bb.x0) bb.x0 = c[0]; if (c[0] > bb.x1) bb.x1 = c[0];
      if (c[1] < bb.y0) bb.y0 = c[1]; if (c[1] > bb.y1) bb.y1 = c[1];
    }); });
  }
  /* Walks any GeoJSON geometry, including GeometryCollection - which is what a
     boundary-intersection produces when two jurisdictions meet along a line AND
     touch again at a separate point. Three of Wilson's thirteen seams are that
     shape, and a naive coordinate walker throws on them. */
  function eachCoord(g, fn) {
    if (!g) return;
    if (g.type === "GeometryCollection") {
      (g.geometries || []).forEach(function (sub) { eachCoord(sub, fn); });
      return;
    }
    (function walk(a) {
      if (!a) return;
      if (typeof a[0] === "number") { fn(a); return; }
      for (var i = 0; i < a.length; i++) walk(a[i]);
    })(g.coordinates);
  }
  scan(W.wilson_situs);
  var padDeg = 0.012;
  bb.x0 -= padDeg; bb.x1 += padDeg; bb.y0 -= padDeg; bb.y1 += padDeg;

  var VW = 1160, VH = 720, k = Math.cos((bb.y0 + bb.y1) / 2 * Math.PI / 180);
  var spanX = (bb.x1 - bb.x0) * k, spanY = bb.y1 - bb.y0;
  var sc = Math.min(VW / spanX, VH / spanY);
  var offX = (VW - spanX * sc) / 2, offY = (VH - spanY * sc) / 2;
  function px(c) { return [(c[0] - bb.x0) * k * sc + offX, (bb.y1 - c[1]) * sc + offY]; }

  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = VW * dpr; cv.height = VH * dpr;
  cv.style.aspectRatio = VW + "/" + VH;

  /* Trace one geometry into the current path. Dispatches on type rather than
     guessing from array nesting: Point and GeometryCollection both defeat the
     nesting heuristic. A bare Point contributes nothing drawable to a stroke,
     so it is skipped rather than mangled. */
  function trace(g) {
    if (!g) return;
    var t = g.type, c = g.coordinates, i, j;
    if (t === "GeometryCollection") { (g.geometries || []).forEach(trace); return; }
    if (t === "Point" || t === "MultiPoint") return;
    if (t === "LineString") { ring(c); return; }
    if (t === "MultiLineString" || t === "Polygon") { for (i = 0; i < c.length; i++) ring(c[i]); return; }
    if (t === "MultiPolygon") {
      for (i = 0; i < c.length; i++) for (j = 0; j < c[i].length; j++) ring(c[i][j]);
    }
  }
  function ring(a) {
    for (var i = 0; i < a.length; i++) {
      var p = px(a[i]);
      if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]);
    }
  }
  function path(g) { ctx.beginPath(); trace(g); }

  var activeFlags = { CROSS_COUNTY_POSTAL: true, BOUNDARY_RISK: true, POSTAL_CITY_EXPOSURE: true, CLEAR: true };
  var selected = null, hot = null, drawn = [];

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, VW, VH);
    ctx.fillStyle = css("--surface"); ctx.fillRect(0, 0, VW, VH);

    // neighbouring counties, quiet context
    ctx.fillStyle = css("--surface-2"); ctx.strokeStyle = css("--rule-2"); ctx.lineWidth = 1;
    W.neighbors.features.forEach(function (f) { path(f.geometry); ctx.fill(); ctx.stroke(); });

    // Wilson situs polygons
    W.wilson_situs.features.forEach(function (f) {
      var s = f.properties.SITUS;
      ctx.fillStyle = css(SIT[s] || "--rule");
      ctx.globalAlpha = s === "9500" ? 0.13 : 0.3; path(f.geometry); ctx.fill(); ctx.globalAlpha = 1;
      ctx.strokeStyle = css(SIT[s] || "--rule"); ctx.lineWidth = 1.4;
      path(f.geometry); ctx.stroke();
    });

    // seams: county seams heavy, city seams light
    W.seams.features.forEach(function (f) {
      var cc = f.properties.seam_type === "CROSS_COUNTY";
      ctx.strokeStyle = cc ? css("--ink") : css("--ink-3");
      ctx.lineWidth = cc ? 2.4 : 1.1;
      ctx.setLineDash(cc ? [] : [5, 4]);
      path(f.geometry); ctx.stroke();
    });
    ctx.setLineDash([]);

    // business points
    drawn = [];
    function plot(rows, clear) {
      rows.forEach(function (r) {
        var flag = r[IX.flag] || "CLEAR";
        if (!activeFlags[clear ? "CLEAR" : flag]) return;
        var p = px([r[IX.lon], r[IX.lat]]);
        var rad = clear ? 1.9 : (flag === "CROSS_COUNTY_POSTAL" ? 4.2 : 3.2);
        ctx.beginPath(); ctx.arc(p[0], p[1], rad, 0, 6.2832);
        if (clear) { ctx.fillStyle = css("--ink-3"); ctx.globalAlpha = .3; ctx.fill(); ctx.globalAlpha = 1; }
        else {
          ctx.fillStyle = css(FLAGCOL[flag]); ctx.fill();
          ctx.lineWidth = 1; ctx.strokeStyle = css("--surface"); ctx.stroke();
          drawn.push({ x: p[0], y: p[1], r: rad + 4, row: r });
        }
      });
    }
    plot(W.biz_clear_sample, true);
    plot(W.biz_flagged.filter(function (r) { return r[IX.flag] !== "CROSS_COUNTY_POSTAL"; }), false);
    plot(W.biz_flagged.filter(function (r) { return r[IX.flag] === "CROSS_COUNTY_POSTAL"; }), false);

    [selected, hot].forEach(function (r) {
      if (!r) return;
      var p = px([r[IX.lon], r[IX.lat]]);
      ctx.beginPath(); ctx.arc(p[0], p[1], 10, 0, 6.2832);
      ctx.strokeStyle = css("--ink"); ctx.lineWidth = 2; ctx.stroke();
    });

    /* Label the three municipalities only. The unincorporated polygon is the
       whole county minus the cities, so its bounding-box centre lands nowhere
       meaningful and collides with Lebanon; it is named in the legend instead. */
    ctx.font = "600 13px Archivo, system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    W.wilson_situs.features.forEach(function (f) {
      var s = f.properties.SITUS;
      if (s === "9500") return;
      var cur = [];
      eachCoord(f.geometry, function (c) { cur.push(px(c)); });
      if (!cur.length) return;
      var cx = 0, cy = 0;
      cur.forEach(function (q) { cx += q[0]; cy += q[1]; });
      cx /= cur.length; cy /= cur.length;
      var txt = SITNAME[s] + "  " + s;
      ctx.lineWidth = 4; ctx.strokeStyle = css("--surface"); ctx.strokeText(txt, cx, cy);
      ctx.fillStyle = css("--ink"); ctx.fillText(txt, cx, cy);
    });
    ctx.textBaseline = "alphabetic";
  }

  /* controls */
  var counts = {
    CROSS_COUNTY_POSTAL: B.flags.CROSS_COUNTY_POSTAL || 0,
    BOUNDARY_RISK: B.flags.BOUNDARY_RISK || 0,
    POSTAL_CITY_EXPOSURE: B.flags.POSTAL_CITY_EXPOSURE || 0,
    CLEAR: B.unflagged
  };
  ["CROSS_COUNTY_POSTAL", "BOUNDARY_RISK", "POSTAL_CITY_EXPOSURE", "CLEAR"].forEach(function (fl) {
    var b = document.createElement("button");
    b.className = "chip"; b.type = "button"; b.setAttribute("aria-pressed", "true");
    b.innerHTML = '<span class="dot"></span><span></span><span class="ct"></span>';
    b.querySelector(".dot").style.background = fl === "CLEAR" ? css("--ink-3") : css(FLAGCOL[fl]);
    b.children[1].textContent = fl === "CLEAR" ? "No flag (sample)" : FLAGNAME[fl];
    b.querySelector(".ct").textContent = nf(counts[fl]);
    b.onclick = function () {
      activeFlags[fl] = !activeFlags[fl];
      b.setAttribute("aria-pressed", String(activeFlags[fl]));
      draw();
    };
    document.getElementById("maptools").appendChild(b);
  });
  var lg = document.getElementById("maplegend");
  lg.innerHTML =
    '<span><span class="sw" style="background:var(--ink);border:0;height:3px;width:20px"></span>County seam — both halves at risk</span>' +
    '<span><span class="sw" style="background:var(--ink-3);border:0;height:2px;width:20px"></span>City seam — situs half only</span>' +
    ["9500", "9501", "9502", "9503"].map(function (s) {
      return '<span><span class="sw" style="background:' + css(SIT[s]) + '"></span>' +
             SITNAME[s] + " " + s + "</span>";
    }).join("") +
    '<span>Unflagged points: a 700-point sample of 3,554, drawn for legibility</span>';

  /* hover */
  cv.addEventListener("mousemove", function (e) {
    var r = cv.getBoundingClientRect(), sx = VW / r.width;
    var mx = (e.clientX - r.left) * sx, my = (e.clientY - r.top) * sx, best = null, bd = 1e9;
    for (var i = drawn.length - 1; i >= 0; i--) {
      var d = Math.hypot(drawn[i].x - mx, drawn[i].y - my);
      if (d < drawn[i].r && d < bd) { bd = d; best = drawn[i]; }
    }
    if (!best) { tip.style.opacity = 0; if (hot) { hot = null; draw(); } return; }
    if (hot !== best.row) { hot = best.row; draw(); }
    var q = best.row;
    tip.innerHTML = "<b></b>" +
      (q[IX.house_no] ? q[IX.house_no] + " " : "") + (q[IX.street] || "") +
      "<br>Postal city: " + (q[IX.post_city] || "—") +
      "<br>DOR situs: " + q[IX.situs] + " " + (SITNAME[q[IX.situs]] || "") +
      (q[IX.postal_county] ? "<br>Mail implies: " + q[IX.postal_county] + " County" : "") +
      "<br>Seam distance: " + (q[IX.seam_ft] == null ? "—" : q[IX.seam_ft] + " ft");
    tip.querySelector("b").textContent = q[IX.business] || "(unnamed point)";
    tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 285) + "px";
    tip.style.top = (e.clientY - r.top + 14) + "px";
  });
  cv.addEventListener("mouseleave", function () { tip.style.opacity = 0; hot = null; draw(); });

  /* ---------- 05 queue ---------- */
  var ORDER = { CROSS_COUNTY_POSTAL: 0, BOUNDARY_RISK: 1, POSTAL_CITY_EXPOSURE: 2 };
  var rows = W.biz_flagged.slice().sort(function (a, b) {
    var d = ORDER[a[IX.flag]] - ORDER[b[IX.flag]];
    if (d) return d;
    return (a[IX.seam_ft] == null ? 1e9 : a[IX.seam_ft]) - (b[IX.seam_ft] == null ? 1e9 : b[IX.seam_ft]);
  });
  var qfilter = "ALL";
  ["ALL", "CROSS_COUNTY_POSTAL", "BOUNDARY_RISK", "POSTAL_CITY_EXPOSURE"].forEach(function (fl) {
    var b = document.createElement("button");
    b.className = "chip"; b.type = "button";
    b.setAttribute("aria-pressed", String(fl === "ALL"));
    b.textContent = fl === "ALL" ? "All " + nf(rows.length) : FLAGNAME[fl] + "  " + nf(counts[fl]);
    b.onclick = function () {
      qfilter = fl;
      [].forEach.call(document.getElementById("qtools").children, function (c) {
        c.setAttribute("aria-pressed", String(c === b));
      });
      renderQ();
    };
    document.getElementById("qtools").appendChild(b);
  });
  function situsHTML(s) {
    if (!s) return "—";
    return '<span class="situs"><span class="cy">' + String(s).slice(0, 2) + "</span>" + String(s).slice(2) + "</span>";
  }
  var PILL = { CROSS_COUNTY_POSTAL: "p-cc", BOUNDARY_RISK: "p-br", POSTAL_CITY_EXPOSURE: "p-pc" };
  function renderQ() {
    var list = rows.filter(function (r) { return qfilter === "ALL" || r[IX.flag] === qfilter; });
    var tb = document.getElementById("qbody"); tb.textContent = "";
    document.getElementById("qcount").textContent = nf(list.length) + " candidates";
    list.slice(0, 400).forEach(function (r) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><span class="bizname"></span></td>' +
        '<td class="code"></td><td></td><td class="code">' + situsHTML(r[IX.situs]) +
        ' <span style="color:var(--ink-3)">' + (SITNAME[r[IX.situs]] || "") + "</span></td>" +
        '<td class="num"></td>' +
        '<td><span class="pill ' + (PILL[r[IX.flag]] || "") + '"></span></td>';
      tr.querySelector(".bizname").textContent = r[IX.business] || "(unnamed)";
      tr.children[1].textContent = (r[IX.house_no] ? r[IX.house_no] + " " : "") + (r[IX.street] || "—") +
        (r[IX.zip] ? "  " + r[IX.zip] : "");
      tr.children[2].textContent = (r[IX.post_city] || "—") +
        (r[IX.postal_county] && r[IX.postal_county] !== "WILSON" ? "  → " + r[IX.postal_county] : "");
      tr.children[4].textContent = r[IX.seam_ft] == null ? "—" : nf(r[IX.seam_ft]) + " ft";
      tr.querySelector(".pill").textContent = FLAGNAME[r[IX.flag]] || r[IX.flag];
      tr.onclick = function () {
        [].forEach.call(tb.children, function (c) { c.classList.remove("sel"); });
        tr.classList.add("sel"); selected = r; draw();
        document.getElementById("s3").scrollIntoView({ behavior: "smooth", block: "center" });
      };
      tb.appendChild(tr);
    });
    if (list.length > 400) {
      var tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="6" style="color:var(--ink-3);font-size:.82rem;padding:12px">' +
        "Showing the first 400 of " + nf(list.length) +
        ". The full queue ships as CSV with an evidence packet per row.</td>";
      tb.appendChild(tr);
    }
  }
  renderQ();
  draw();
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  (mq.addEventListener ? mq.addEventListener.bind(mq, "change") : mq.addListener.bind(mq))(draw);
})();
