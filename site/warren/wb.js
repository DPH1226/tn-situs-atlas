/* Situs Workbench — Wilson County. Data: window.WB from wbdata.js. */
(function () {
  "use strict";
  var W = window.WB, F = {}; W.biz_fields.forEach(function (n, i) { F[n] = i; });
  // Thinned rows (unflagged businesses in large counties) arrive compact; expand to full width.
  if (W.biz_min && W.biz_min.length) {
    var MF = {}; W.biz_min_fields.forEach(function (n, i) { MF[n] = i; });
    W.biz_min.forEach(function (m) {
      var r = new Array(W.biz_fields.length).fill(null);
      r[F.id] = m[MF.id]; r[F.business] = m[MF.business]; r[F.kind] = "business"; r[F.source] = m[MF.source];
      r[F.dor_situs] = m[MF.dor_situs]; r[F.lon] = m[MF.lon]; r[F.lat] = m[MF.lat]; W.biz.push(r);
    });
  }
  var $ = function (id) { return document.getElementById(id); };
  var css = function (v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); };
  var nf = function (n) { return n == null ? "—" : Number(n).toLocaleString("en-US"); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var SITNAME = W.situs_names || { "9500": "Unincorporated", "9501": "Lebanon", "9502": "Watertown", "9503": "Mt. Juliet" };
  var SITCODES = Object.keys(SITNAME).sort(), SITVAR = {};
  (function () { var pal = ["--s-9500", "--s-9501", "--s-9503", "--s-9502", "--sev-clear", "--accent", "--sev-high", "--sev-watch", "--sev-crit"];
    SITCODES.forEach(function (c, i) { SITVAR[c] = c.slice(2) === "00" ? "--s-9500" : pal[1 + ((i - 1) % (pal.length - 1))]; }); })();
  var FLAGWHY = {
    CROSS_COUNTY_POSTAL: "Every official layer places this rooftop inside " + (W.county || "the county") + ", but its MAILING address carries another county's postal city. Situs codes are set at registration from whatever address the taxpayer wrote down, so this is where cross-county miscoding happens. Exposure, not proof: the situs report says how it was actually coded.",
    BOUNDARY_RISK: "Within 250 ft of a jurisdictional seam. The geography itself is the question here - geocoder error alone could flip the jurisdiction. Adjudicate against parcel and structure before asserting anything.",
    POSTAL_CITY_EXPOSURE: "The mailing address names a city inside the county, but the rooftop is not in that city's DOR polygon. A mailing-address registration would send the situs half to the wrong jurisdiction. Exposure population, not a finding.",
    CODED_MISMATCH: "A situs-coded roster row matched this rooftop and its coded situs differs from the measured one. This is the audit finding itself.",
    CLEAR: "No exception class applies. The rooftop, its mailing city and every official layer agree."
  };
  var FLAG = {
    CROSS_COUNTY_POSTAL: { name: "Cross-county postal", cls: "p-cc", col: "--sev-crit" },
    BOUNDARY_RISK: { name: "Boundary risk", cls: "p-br", col: "--sev-high" },
    POSTAL_CITY_EXPOSURE: { name: "Postal exposure", cls: "p-pc", col: "--sev-watch" },
    CODED_MISMATCH: { name: "Coded ≠ measured", cls: "p-dor", col: "--ink" },
    CLEAR: { name: "No flag", cls: "p-ok", col: "--ink-3" }
  };
  var STATUS = ["Open", "In review", "Confirmed exception", "Not an exception", "Submitted to DOR", "DOR corrected"];
  var STCOL = { "Open": "--ink-3", "In review": "--sev-high", "Confirmed exception": "--sev-crit", "Not an exception": "--sev-clear", "Submitted to DOR": "--accent", "DOR corrected": "--sev-clear" };

  /* ================= projection: world units are feet ================= */
  var LAT0 = 36.16, LON0 = -86.30, FT_PER_DEG = 364000, K = Math.cos(LAT0 * Math.PI / 180);
  function wx(lon) { return (lon - LON0) * FT_PER_DEG * K; }
  function wy(lat) { return -(lat - LAT0) * FT_PER_DEG; }

  function projRings(g) {
    // -> array of Float64Array rings (flat x,y), for any geometry type
    var out = [];
    function ring(a) { var f = new Float64Array(a.length * 2); for (var i = 0; i < a.length; i++) { f[2 * i] = wx(a[i][0]); f[2 * i + 1] = wy(a[i][1]); } out.push(f); }
    (function walk(gg) {
      if (!gg) return;
      var t = gg.type, c = gg.coordinates, i, j;
      if (t === "GeometryCollection") { (gg.geometries || []).forEach(walk); return; }
      if (t === "Point") { out.push(new Float64Array([wx(c[0]), wy(c[1])])); return; }
      if (t === "MultiPoint" || t === "LineString") { ring(c); return; }
      if (t === "MultiLineString" || t === "Polygon") { for (i = 0; i < c.length; i++) ring(c[i]); return; }
      if (t === "MultiPolygon") for (i = 0; i < c.length; i++) for (j = 0; j < c[i].length; j++) ring(c[i][j]);
    })(g);
    return out;
  }
  function prep(fc) { return fc.features.map(function (f) { return { p: f.properties, r: projRings(f.geometry) }; }); }
  var SITUS = prep(W.wilson_situs), NBR = prep(W.neighbors), SEAMS = prep(W.seams), ANNEX = prep(W.annexations), ROADS = prep(W.roads);
  var BIZ = W.biz.map(function (r) { return { r: r, x: wx(r[F.lon]), y: wy(r[F.lat]), id: String(r[F.id]),
    kind: (F.kind != null ? r[F.kind] : "business") || "business",
    coded: (F.coded_situs != null && r[F.coded_situs] && String(r[F.coded_situs]) !== String(r[F.dor_situs])) ? "CODED_MISMATCH" : null,
    codedSitus: F.coded_situs != null ? r[F.coded_situs] : null }; });
  var BAND = W.band_pts.map(function (p) { return [wx(p[0]), wy(p[1]), p[2]]; });
  var byId = {}; BIZ.forEach(function (b) { byId[b.id] = b; });

  // county bbox for fit
  var bb = [1e12, 1e12, -1e12, -1e12];
  SITUS.forEach(function (f) { f.r.forEach(function (a) { for (var i = 0; i < a.length; i += 2) { if (a[i] < bb[0]) bb[0] = a[i]; if (a[i] > bb[2]) bb[2] = a[i]; if (a[i + 1] < bb[1]) bb[1] = a[i + 1]; if (a[i + 1] > bb[3]) bb[3] = a[i + 1]; } }); });

  /* ================= map engine ================= */
  var cv = $("map"), ctx = cv.getContext("2d"), tip = $("tip");
  var view = { cx: 0, cy: 0, s: 0.001 }; // s = px per foot
  var dpr = Math.min(window.devicePixelRatio || 1, 2), CW = 0, CH = 0;
  var layers = { situs: true, seams: true, annex: false, roads: true, band: false, biz: true, labels: false };
  var showFlag = { CROSS_COUNTY_POSTAL: true, BOUNDARY_RISK: true, POSTAL_CITY_EXPOSURE: true, CODED_MISMATCH: true, CLEAR: true };
  var selected = null, hot = null, hits = [], raf = 0;

  function resize() {
    var r = cv.getBoundingClientRect(); CW = r.width; CH = r.height;
    cv.width = CW * dpr; cv.height = CH * dpr; draw();
  }
  function fit() {
    var pad = 30, sx = (CW - 2 * pad) / (bb[2] - bb[0]), sy = (CH - 2 * pad) / (bb[3] - bb[1]);
    view.s = Math.min(sx, sy); view.cx = (bb[0] + bb[2]) / 2; view.cy = (bb[1] + bb[3]) / 2; draw();
  }
  function sx(x) { return (x - view.cx) * view.s + CW / 2; }
  function sy(y) { return (y - view.cy) * view.s + CH / 2; }
  function inv(px, py) { return [(px - CW / 2) / view.s + view.cx, (py - CH / 2) / view.s + view.cy]; }

  function strokeRings(rings, minLen) {
    ctx.beginPath();
    for (var k = 0; k < rings.length; k++) {
      var a = rings[k]; if (a.length < 4) continue;
      ctx.moveTo(sx(a[0]), sy(a[1]));
      for (var i = 2; i < a.length; i += 2) ctx.lineTo(sx(a[i]), sy(a[i + 1]));
    }
  }
  function fillRings(rings) {
    ctx.beginPath();
    for (var k = 0; k < rings.length; k++) {
      var a = rings[k]; if (a.length < 6) continue;
      ctx.moveTo(sx(a[0]), sy(a[1]));
      for (var i = 2; i < a.length; i += 2) ctx.lineTo(sx(a[i]), sy(a[i + 1]));
      ctx.closePath();
    }
  }
  function visible(rings) {
    // cheap bbox cull
    var x0 = inv(0, 0), x1 = inv(CW, CH);
    for (var k = 0; k < rings.length; k++) { var a = rings[k]; for (var i = 0; i < a.length; i += 2) if (a[i] >= x0[0] && a[i] <= x1[0] && a[i + 1] >= x0[1] && a[i + 1] <= x1[1]) return true; }
    return false;
  }

  function draw() {
    if (raf) return; raf = requestAnimationFrame(function () { raf = 0; paint(); });
  }
  function paint() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = css("--map-bg"); ctx.fillRect(0, 0, CW, CH);
    var ftpx = 1 / view.s; // feet per pixel

    // neighbors
    ctx.fillStyle = css("--surface-2"); ctx.strokeStyle = css("--rule"); ctx.lineWidth = 1;
    NBR.forEach(function (f) { fillRings(f.r); ctx.fill(); ctx.stroke(); });

    // situs fills
    if (layers.situs) SITUS.forEach(function (f) {
      var s = f.p.SITUS; ctx.fillStyle = css(SITVAR[s]); ctx.globalAlpha = s === "9500" ? 0.14 : 0.28;
      fillRings(f.r); ctx.fill(); ctx.globalAlpha = 1;
    });
    // roads (class-gated by zoom)
    if (layers.roads) {
      var showMinor = ftpx < 60, showMid = ftpx < 200;
      ctx.lineCap = "round";
      ROADS.forEach(function (f) {
        var c = f.p.cls;
        if (c === 4 && !showMinor) return; if (c === 3 && !showMid) return;
        if (!visible(f.r)) return;
        ctx.strokeStyle = c <= 2 ? css("--road-major") : css("--road-minor");
        ctx.lineWidth = c === 1 ? 2.2 : c === 2 ? 1.6 : c === 3 ? 1.1 : 0.8;
        strokeRings(f.r); ctx.stroke();
      });
    }
    // situs outlines
    if (layers.situs) SITUS.forEach(function (f) { ctx.strokeStyle = css(SITVAR[f.p.SITUS]); ctx.lineWidth = 1.2; strokeRings(f.r); ctx.stroke(); });
    // annexations
    if (layers.annex) { ctx.strokeStyle = css("--annex"); ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ANNEX.forEach(function (f) { if (!visible(f.r)) return; fillRings(f.r); ctx.fillStyle = css("--annex"); ctx.globalAlpha = .12; ctx.fill(); ctx.globalAlpha = 1; ctx.stroke(); });
      ctx.setLineDash([]); }
    // seams
    if (layers.seams) SEAMS.forEach(function (f) {
      var cc = f.p.seam_type === "CROSS_COUNTY";
      ctx.strokeStyle = cc ? css("--ink") : css("--ink-3"); ctx.lineWidth = cc ? 2.4 : 1.2; ctx.setLineDash(cc ? [] : [5, 4]);
      strokeRings(f.r); ctx.stroke();
    });
    ctx.setLineDash([]);
    // band rooftops
    if (layers.band && ftpx < 120) {
      var x0 = inv(0, 0), x1 = inv(CW, CH);
      BAND.forEach(function (p) {
        if (p[0] < x0[0] || p[0] > x1[0] || p[1] < x0[1] || p[1] > x1[1]) return;
        ctx.fillStyle = p[2] === 0 ? css("--sev-crit") : css("--sev-high"); ctx.globalAlpha = .55;
        ctx.beginPath(); ctx.arc(sx(p[0]), sy(p[1]), 2.2, 0, 6.2832); ctx.fill(); ctx.globalAlpha = 1;
      });
    }
    // selection distance line to nearest seam
    if (selected) drawSeamLine(selected);
    // businesses
    hits = [];
    if (layers.biz) {
      var order = ["CLEAR", "POSTAL_CITY_EXPOSURE", "BOUNDARY_RISK", "CODED_MISMATCH", "CROSS_COUNTY_POSTAL"];
      order.forEach(function (fl) {
        if (!showFlag[fl]) return;
        BIZ.forEach(function (b) {
          if (b.kind !== "business") return;
          if (flagOf(b) !== fl) return;
          var px = sx(b.x), py = sy(b.y); if (px < -8 || py < -8 || px > CW + 8 || py > CH + 8) return;
          var clear = fl === "CLEAR", rad = clear ? (ftpx < 80 ? 3 : 1.8) : (fl === "CROSS_COUNTY_POSTAL" || fl === "CODED_MISMATCH" ? 4.4 : 3.4);
          ctx.beginPath(); ctx.arc(px, py, rad, 0, 6.2832);
          ctx.fillStyle = css(FLAG[fl].col); ctx.globalAlpha = clear ? .45 : 1; ctx.fill(); ctx.globalAlpha = 1;
          if (!clear) { ctx.lineWidth = 1; ctx.strokeStyle = css("--surface"); ctx.stroke(); }
          hits.push({ x: px, y: py, b: b });
        });
      });
    }
    if (layers.labels && ftpx < 120) BIZ.forEach(function (b) {
      if (b.kind === "business") return;
      var px = sx(b.x), py = sy(b.y); if (px < -8 || py < -8 || px > CW + 8 || py > CH + 8) return;
      ctx.beginPath(); ctx.arc(px, py, 3, 0, 6.2832); ctx.strokeStyle = css("--ink-3"); ctx.lineWidth = 1; ctx.stroke();
      hits.push({ x: px, y: py, b: b });
    });
    [hot, selected].forEach(function (b, i) {
      if (!b) return; ctx.beginPath(); ctx.arc(sx(b.x), sy(b.y), i ? 11 : 8, 0, 6.2832);
      ctx.strokeStyle = css("--ink"); ctx.lineWidth = i ? 2 : 1.2; ctx.stroke();
    });
    // city labels
    if (ftpx > 25) { ctx.font = "600 13px Archivo, system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      SITUS.forEach(function (f) { var s = f.p.SITUS; if (s === "9500") return; var n = 0, cx = 0, cy = 0;
        f.r.forEach(function (a) { for (var i = 0; i < a.length; i += 2) { cx += a[i]; cy += a[i + 1]; n++; } });
        var t = SITNAME[s] + "  " + s; ctx.lineWidth = 4; ctx.strokeStyle = css("--surface"); ctx.strokeText(t, sx(cx / n), sy(cy / n)); ctx.fillStyle = css("--ink"); ctx.fillText(t, sx(cx / n), sy(cy / n)); });
      ctx.textBaseline = "alphabetic"; }
    // road labels when close
    if (layers.roads && ftpx < 14) { ctx.font = "500 10px Archivo, system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      var seen = {};
      ROADS.forEach(function (f) { if (!f.p.LABEL || seen[f.p.LABEL] || !visible(f.r)) return; var a = f.r[0]; if (!a || a.length < 4) return;
        var m = (a.length / 2 >> 1) * 2, px = sx(a[m]), py = sy(a[m + 1]); if (px < 40 || py < 20 || px > CW - 40 || py > CH - 20) return;
        seen[f.p.LABEL] = 1; ctx.lineWidth = 3; ctx.strokeStyle = css("--map-bg"); ctx.strokeText(f.p.LABEL, px, py); ctx.fillStyle = css("--ink-2"); ctx.fillText(f.p.LABEL, px, py); });
      ctx.textBaseline = "alphabetic"; }
    scaleBar(ftpx);
  }

  function nearestOnSeams(x, y) {
    var best = null, bd = 1e18;
    SEAMS.forEach(function (f) { f.r.forEach(function (a) {
      for (var i = 0; i + 3 < a.length; i += 2) {
        var ax = a[i], ay = a[i + 1], bx = a[i + 2], by = a[i + 3], dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
        var t = L ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L)) : 0, px = ax + t * dx, py = ay + t * dy;
        var d = (x - px) * (x - px) + (y - py) * (y - py); if (d < bd) { bd = d; best = [px, py, f.p]; }
      } }); });
    return best ? { x: best[0], y: best[1], d: Math.sqrt(bd), seam: best[2] } : null;
  }
  function drawSeamLine(b) {
    var n = nearestOnSeams(b.x, b.y); if (!n) return;
    ctx.setLineDash([4, 3]); ctx.strokeStyle = css("--ink"); ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(sx(b.x), sy(b.y)); ctx.lineTo(sx(n.x), sy(n.y)); ctx.stroke(); ctx.setLineDash([]);
    var ft = b.r[F.seam_ft]; if (ft == null) return;
    var mx = (sx(b.x) + sx(n.x)) / 2, my = (sy(b.y) + sy(n.y)) / 2 - 10, t = nf(Math.round(ft)) + " ft";
    ctx.font = "600 11px IBM Plex Mono, monospace"; ctx.textAlign = "center"; ctx.lineWidth = 4; ctx.strokeStyle = css("--surface"); ctx.strokeText(t, mx, my); ctx.fillStyle = css("--ink"); ctx.fillText(t, mx, my);
  }
  function scaleBar(ftpx) {
    var target = 120, ft = target * ftpx, nice = [50, 100, 250, 500, 1000, 2500, 5280, 10560, 26400, 52800, 105600], pick = nice[0];
    for (var i = 0; i < nice.length; i++) if (nice[i] <= ft) pick = nice[i];
    var w = pick / ftpx, lab = pick >= 5280 ? (pick / 5280) + " mi" : pick + " ft";
    var ticks = ""; if (pick >= 250 && pick <= 1000) { ticks += '<i style="left:' + (50 / ftpx) + 'px"></i>'; if (pick > 250) ticks += '<i style="left:' + (250 / ftpx) + 'px"></i>'; }
    $("scale").innerHTML = lab + (pick >= 250 && pick <= 1000 ? '  <span style="color:var(--ink-3)">· ticks at 50 / 250 ft</span>' : "") + '<div class="bar" style="width:' + w + 'px">' + ticks + "</div>";
  }

  function flagOf(b) { return b.coded || b.r[F.flag] || "CLEAR"; }

  /* interactions */
  var drag = null, moved = false;
  cv.addEventListener("pointerdown", function (e) { drag = { x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy }; moved = false; cv.setPointerCapture(e.pointerId); cv.classList.add("drag"); });
  cv.addEventListener("pointermove", function (e) {
    if (drag) { var dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      view.cx = drag.cx - dx / view.s; view.cy = drag.cy - dy / view.s; draw(); return; }
    var r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, best = null, bd = 12;
    for (var i = hits.length - 1; i >= 0; i--) { var d = Math.hypot(hits[i].x - mx, hits[i].y - my); if (d < bd) { bd = d; best = hits[i].b; } }
    if (best !== hot) { hot = best; draw(); }
    if (!best) { tip.style.opacity = 0; return; }
    var q = best.r; tip.innerHTML = "<b>" + esc(q[F.business] || "(unnamed point)") + "</b>" + esc((q[F.house_no] ? q[F.house_no] + " " : "") + (q[F.street] || "")) +
      "<br>Postal: " + esc(q[F.post_city] || "—") + " · DOR: " + esc(q[F.dor_situs] || "—") + " " + esc(SITNAME[q[F.dor_situs]] || "") +
      (q[F.seam_ft] != null ? "<br>Seam: " + nf(Math.round(q[F.seam_ft])) + " ft · " + esc(q[F.risk_band]) : "");
    tip.style.opacity = 1; tip.style.left = Math.min(mx + 14, CW - 270) + "px"; tip.style.top = (my + 14) + "px";
  });
  cv.addEventListener("pointerup", function (e) {
    cv.classList.remove("drag"); if (!drag) return; drag = null;
    if (moved) return;
    var r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, best = null, bd = 12;
    for (var i = hits.length - 1; i >= 0; i--) { var d = Math.hypot(hits[i].x - mx, hits[i].y - my); if (d < bd) { bd = d; best = hits[i].b; } }
    if (best) select(best, false);
  });
  cv.addEventListener("pointerleave", function () { tip.style.opacity = 0; hot = null; draw(); });
  cv.addEventListener("wheel", function (e) { e.preventDefault(); var r = cv.getBoundingClientRect(); zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * 0.0016)); }, { passive: false });
  function zoomAt(px, py, f) {
    var w = inv(px, py); view.s = Math.max(0.00015, Math.min(3, view.s * f));
    var w2 = inv(px, py); view.cx += w[0] - w2[0]; view.cy += w[1] - w2[1]; draw();
  }
  $("zin").onclick = function () { zoomAt(CW / 2, CH / 2, 1.6); };
  $("zout").onclick = function () { zoomAt(CW / 2, CH / 2, 1 / 1.6); };
  $("zfit").onclick = fit;
  window.addEventListener("resize", resize);
  var mq = window.matchMedia("(prefers-color-scheme: dark)"); (mq.addEventListener ? mq.addEventListener.bind(mq, "change") : mq.addListener.bind(mq))(draw);
  setTimeout(function () { $("hint").style.opacity = 0; }, 6000);

  function flyTo(b) { view.cx = b.x; view.cy = b.y; if (view.s < 0.35) view.s = 0.35; draw(); }

  /* layer controls */
  (function () {
    var L = $("layers"), items = [
      ["hd", "Layers"], ["situs", "DOR situs polygons", "--s-9501"], ["seams", "Jurisdictional seams", "--ink"], ["annex", "Annexations (" + nf(W.annexations.features.length) + ")", "--annex"],
      ["roads", "Roads (NG911)", "--road-major"], ["band", "Boundary-band rooftops (" + nf(W.band_pts.length) + ")", "--sev-high"],
      ["labels", "Non-business labels (" + nf(BIZ.filter(function (b) { return b.kind !== "business"; }).length) + ")", "--ink-3"], ["hd", "Businesses"],
      ["f:CROSS_COUNTY_POSTAL", "Cross-county postal", "--sev-crit"], ["f:BOUNDARY_RISK", "Boundary risk", "--sev-high"], ["f:POSTAL_CITY_EXPOSURE", "Postal exposure", "--sev-watch"], ["f:CODED_MISMATCH", "Coded ≠ measured (DOR file)", "--ink"], ["f:CLEAR", "No flag", "--ink-3"]];
    items.forEach(function (it) {
      if (it[0] === "hd") { var h = document.createElement("div"); h.className = "hd"; h.textContent = it[1]; L.appendChild(h); return; }
      var lab = document.createElement("label"), inp = document.createElement("input"); inp.type = "checkbox"; inp.id = "ly-" + it[0].replace(":", "-");
      var isF = it[0].indexOf("f:") === 0, key = isF ? it[0].slice(2) : it[0];
      inp.checked = isF ? showFlag[key] : layers[key];
      inp.onchange = function () { if (isF) showFlag[key] = inp.checked; else layers[key] = inp.checked; draw(); };
      var sw = document.createElement("span"); sw.className = "sw"; sw.style.background = css(it[2]); if (isF) sw.style.borderRadius = "50%";
      lab.appendChild(inp); lab.appendChild(sw); lab.appendChild(document.createTextNode(it[1])); L.appendChild(lab);
    });
    $("legend").innerHTML = SITCODES.map(function (s) { return '<span><span class="sw" style="width:11px;height:11px;background:' + css(SITVAR[s]) + '"></span>' + SITNAME[s] + ' <span class="mono">' + s + "</span></span>"; }).join("") +
      '<span><span style="width:18px;height:3px;background:var(--ink)"></span>County seam</span><span><span style="width:18px;height:2px;background:var(--ink-3)"></span>City seam</span>';
  })();

  /* ================= adjudication store ================= */
  var ADJ = {}, db = null, dbCol = null, who = "";
  try { who = localStorage.getItem("civvix.who") || ""; } catch (e) {}
  function loadLocal() { try { var s = localStorage.getItem("civvix.adj." + String(W.slug || W.county || "county").toLowerCase()); if (s) ADJ = JSON.parse(s) || {}; } catch (e) {} }
  function saveLocal() { try { localStorage.setItem("civvix.adj." + String(W.slug || W.county || "county").toLowerCase(), JSON.stringify(ADJ)); } catch (e) {} }
  loadLocal();
  window.claude && window.claude.use && window.claude.use("db").then(function (d) {
    if (!d) return;
    db = d; dbCol = db.collection("adjudications");
    dbCol.onSnapshot(function (snap) {
      snap.docs.forEach(function (doc) { if (doc.exists) ADJ[doc.id] = doc.data(); });
      $("dbstat").className = "status on"; $("dbstat").querySelector("span").textContent = "adjudications: shared · " + snap.size + " on file";
      renderQueue(); if (selected) renderEvidence(selected);
    }, function () { $("dbstat").querySelector("span").textContent = "adjudications: shared store unavailable, local only"; });
  }).catch(function () {});
  function setAdj(id, rec) {
    ADJ[id] = rec; saveLocal();
    if (dbCol) return dbCol.doc(id).set(rec).catch(function (e) { $("dbstat").querySelector("span").textContent = "save failed (" + (e && e.code || "error") + ") — kept locally"; });
    return Promise.resolve();
  }

  /* ================= queue ================= */
  var qFlag = "ALL", qStatus = "ALL", qSort = "score", qText = "", qShown = 200;
  var counts = W.flag_counts;
  (function () {
    var t = $("qtools");
    [["ALL", "All"], ["CROSS_COUNTY_POSTAL"], ["BOUNDARY_RISK"], ["POSTAL_CITY_EXPOSURE"], ["CODED_MISMATCH"], ["CLEAR"]].forEach(function (x) {
      var b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.setAttribute("aria-pressed", String(x[0] === "ALL")); b.dataset.flag = x[0];
      b.innerHTML = '<span></span><span class="ct"></span>'; b.children[0].textContent = x[1] || FLAG[x[0]].name;
      b.onclick = function () { qFlag = x[0]; qShown = 200; [].forEach.call(t.querySelectorAll(".chip"), function (c) { c.setAttribute("aria-pressed", String(c === b)); }); renderQueue(); };
      t.appendChild(b);
    });
    var st = document.createElement("select"); st.id = "qstatus"; st.setAttribute("aria-label", "Filter by status");
    st.innerHTML = '<option value="ALL">Any status</option>' + STATUS.map(function (s) { return "<option>" + s + "</option>"; }).join("");
    st.onchange = function () { qStatus = st.value; qShown = 200; renderQueue(); }; t.appendChild(st);
    var so = document.createElement("select"); so.id = "qsort"; so.setAttribute("aria-label", "Sort");
    so.innerHTML = '<option value="score">Score ↓</option><option value="seam">Seam distance ↑</option><option value="name">Name</option>'; so.style.marginLeft = "0";
    so.onchange = function () { qSort = so.value; renderQueue(); }; t.appendChild(so);
    $("qmore").onclick = function () { qShown += 300; renderQueue(); };
    $("q").addEventListener("input", function () { qText = $("q").value.trim().toUpperCase(); qShown = 200; renderQueue(); showPane("queue"); });
  })();
  function updateChipCounts() {
    var c = {}, tot = 0; BIZ.forEach(function (b) { if (b.kind !== "business") return; tot++; var f = flagOf(b); c[f] = (c[f] || 0) + 1; });
    [].forEach.call($("qtools").querySelectorAll(".chip"), function (ch) { var f = ch.dataset.flag; ch.querySelector(".ct").textContent = nf(f === "ALL" ? tot : (c[f] || 0)); });
  }
  function qmatch(b) {
    if (b.kind !== "business") return false;
    var f = flagOf(b), st = (ADJ[b.id] || {}).status || "Open";
    if (qFlag !== "ALL" && f !== qFlag) return false;
    if (qStatus !== "ALL" && st !== qStatus) return false;
    if (qText) { var h = ((b.r[F.business] || "") + " " + (b.r[F.street] || "") + " " + (b.r[F.post_city] || "")).toUpperCase(); if (h.indexOf(qText) < 0) return false; }
    return true;
  }
  var ORD = { CROSS_COUNTY_POSTAL: 0, CODED_MISMATCH: 0, BOUNDARY_RISK: 1, POSTAL_CITY_EXPOSURE: 2, CLEAR: 3 };
  function renderQueue() {
    updateChipCounts();
    var list = BIZ.filter(qmatch);
    list.sort(function (a, b) {
      var d = ORD[flagOf(a)] - ORD[flagOf(b)]; if (d) return d;
      if (qSort === "score") return (b.r[F.score] || 0) - (a.r[F.score] || 0);
      if (qSort === "seam") return (a.r[F.seam_ft] == null ? 1e9 : a.r[F.seam_ft]) - (b.r[F.seam_ft] == null ? 1e9 : b.r[F.seam_ft]);
      return String(a.r[F.business] || "").localeCompare(String(b.r[F.business] || ""));
    });
    var host = $("qlist"); host.textContent = "";
    var frag = document.createDocumentFragment();
    list.slice(0, qShown).forEach(function (b) {
      var q = b.r, f = flagOf(b), st = (ADJ[b.id] || {}).status || "Open", row = document.createElement("div");
      row.className = "qrow" + (selected === b ? " sel" : ""); row.tabIndex = 0; row.setAttribute("role", "button");
      row.innerHTML = '<div class="nm"></div><div class="sc"></div><div class="ad"></div><div class="pl"><span class="pill"></span><span class="st" title=""></span></div>';
      row.children[0].textContent = q[F.business] || "(unnamed point)";
      row.children[1].textContent = q[F.score] == null ? "—" : q[F.score];
      row.children[2].textContent = (q[F.house_no] ? q[F.house_no] + " " : "") + (q[F.street] || "—") + " · " + (q[F.post_city] || "—") + " → " + (q[F.dor_situs] || "—");
      var p = row.querySelector(".pill"); p.className = "pill " + FLAG[f].cls; p.textContent = FLAG[f].name;
      var s = row.querySelector(".st"); s.style.background = css(STCOL[st]); s.title = st;
      row.onclick = function () { select(b, true); }; row.onkeydown = function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(b, true); } };
      frag.appendChild(row);
    });
    host.appendChild(frag);
    $("qcount").textContent = nf(Math.min(qShown, list.length)) + " of " + nf(list.length) + " shown";
    var bn = $("qbanner");
    if (bn) {
      if (dorRows) { bn.className = "notice qbanner ok"; bn.innerHTML = "<b>Situs roster loaded.</b> Rows marked <b>Coded \u2260 measured</b> are registrations whose coded situs differs from the measured location. Everything else is ranked exposure awaiting a coded value."; }
      else { bn.className = "notice qbanner"; bn.innerHTML = "<b>Roster not loaded \u2014 this is ranked exposure, not findings.</b> Nothing here is known to be miscoded yet. Each row is a business whose evidence says it deserves a look first when the Department\u2019s situs report arrives (paste it under the <b>DOR file</b> tab)."; }
    }
    $("qmore").style.visibility = list.length > qShown ? "visible" : "hidden";
  }

  /* ================= evidence ================= */
  function situsHTML(s) { return s ? '<span class="situs"><span class="cy">' + esc(String(s).slice(0, 2)) + "</span>" + esc(String(s).slice(2)) + "</span> " + esc(SITNAME[s] || "") : "—"; }
  function norm(v) { return v == null ? "" : String(v).toUpperCase().replace(/[().]/g, "").replace("MOUNT ", "MT ").trim().replace(/^UNINCORPORATED.*$/, "UNINCORPORATED") || "UNINCORPORATED"; }
  function renderEvidence(b) {
    var q = b.r, f = flagOf(b), a = ADJ[b.id] || {}, st = a.status || "Open", host = $("ev");
    var band = q[F.risk_band] || "NORMAL";
    var dorC = norm(q[F.dor_city]), e911 = norm(q[F.e911_muni]), comp = norm(q[F.comp_city]);
    var sstC = q[F.sst_situs] ? SITNAME[q[F.sst_situs]] : null;
    var agree = function (v) { return v === dorC; };
    var NOTE = { P: "DOR tax polygon", A: "911-authority address point", L: "official layers agree", R: "DOR address-range match",
                 B: "business point within 100 ft", C: "address current", I: "parcel id", s50: "within 50 ft of a seam",
                 s250: "within 250 ft of a seam", X: "conflicting official layers", M: "mailing-only address" };
    var notes = String(q[F.score_notes] || "").split(" ").filter(Boolean).map(function (tok) {
      var m = tok.match(/^([+-]\d+)(.*)$/); return m ? m[1] + " " + (NOTE[m[2]] || m[2]) : tok; });
    var gm = "https://www.google.com/maps?q=" + q[F.lat] + "," + q[F.lon];
    host.innerHTML =
      '<div class="evh"><div><h2>' + esc(q[F.business] || "(unnamed point)") + '</h2><div class="ad">' + esc((q[F.house_no] ? q[F.house_no] + " " : "") + (q[F.street] || "") + (q[F.unit] ? " " + q[F.unit] : "") + (q[F.zip] ? "  " + q[F.zip] : "")) + "</div></div>" +
      '<div class="score"><div class="n">' + (q[F.score] == null ? "—" : esc(q[F.score])) + '</div><div class="l">evidence /100</div></div></div>' +
      '<div class="pills"><span class="pill ' + FLAG[f].cls + '">' + FLAG[f].name + '</span><span class="pill" style="background:var(--surface-2);color:var(--ink-2)">' + esc(q[F.disposition] || "") + '</span>' +
      '<span class="pill" style="background:' + css(STCOL[st]) + ';color:var(--paper)">' + esc(st) + "</span></div>" +
      '<div class="meta" style="margin:-6px 0 12px;font-family:var(--serif);font-size:.84rem;color:var(--ink-2);line-height:1.5">' + esc(FLAGWHY[f] || "") + "</div>" +
      (b.kind !== "business" ? '<div class="notice"><b>Not an audit item.</b> This label is classified as "' + esc(b.kind) + '" (subdivision, lot, utility, institution or unnamed) and is excluded from the queue. Shown for transparency only.</div>' : "") +
      (b.coded ? '<div class="notice"><b>Roster says situs ' + esc(b.codedSitus) + ' (' + esc(SITNAME[b.codedSitus] || "?") + ').</b> Measured rooftop is in ' + esc(q[F.dor_situs]) + " " + esc(SITNAME[q[F.dor_situs]] || "") + ". This is the comparison the whole audit exists to make.</div>" : "") +
      '<div class="sec"><h3>Where it is</h3><dl class="kv">' +
      "<dt>DOR tax polygon</dt><dd>" + situsHTML(q[F.dor_situs]) + "</dd>" +
      "<dt>DOR address file</dt><dd>" + (q[F.sst_situs] ? situsHTML(q[F.sst_situs]) + (String(q[F.sst_situs]) !== String(q[F.dor_situs]) ? ' <span class="bad">≠ polygon</span>' : ' <span class="ok">= polygon</span>') : '<span style="color:var(--ink-3)">no range match</span>') + "</dd>" +
      "<dt>Postal city</dt><dd>" + esc(q[F.post_city] || "—") + (q[F.postal_county] && q[F.postal_county] !== "WILSON" ? ' <span class="bad">→ ' + esc(q[F.postal_county]) + " COUNTY</span>" : "") + "</dd>" +
      "<dt>911 municipality</dt><dd>" + esc(q[F.e911_muni] || "—") + "</dd>" +
      "<dt>Comptroller limit</dt><dd>" + esc(q[F.comp_city] || "—") + "</dd>" +
      "<dt>Census place</dt><dd>" + esc(q[F.census_place] || "—") + "</dd>" +
      "<dt>Mt. Juliet annexation</dt><dd>" + (q[F.in_annexation] ? '<span class="bad">inside an annexation polygon</span>' : "no") + "</dd>" +
      "<dt>Parcel</dt><dd class=\"mono\">" + esc(q[F.parcel_id] || "—") + "</dd>" +
      "<dt>Address match</dt><dd>" + (q[F.addr_match_ft] == null ? '<span style="color:var(--ink-3)">no address point within 500 ft</span>' : nf(Math.round(q[F.addr_match_ft])) + " ft to nearest rooftop") + "</dd></dl></div>" +
      '<div class="sec"><h3>Official layers</h3><table class="lay">' +
      "<tr><td>TN Dept. of Revenue</td><td>" + esc(dorC) + "</td><td>—</td></tr>" +
      "<tr><td>911 addressing authority</td><td>" + esc(e911) + "</td><td class=\"" + (agree(e911) ? "ok" : "bad") + "\">" + (agree(e911) ? "✓" : "✗") + "</td></tr>" +
      "<tr><td>Comptroller OLG</td><td>" + esc(comp) + "</td><td class=\"" + (agree(comp) ? "ok" : "bad") + "\">" + (agree(comp) ? "✓" : "✗") + "</td></tr>" +
      (sstC ? "<tr><td>DOR address file</td><td>" + esc(norm(sstC)) + "</td><td class=\"" + (norm(sstC) === dorC ? "ok" : "bad") + "\">" + (norm(sstC) === dorC ? "✓" : "✗") + "</td></tr>" : "") +
      "</table>" + (q[F.layers_agree] === false ? '<div class="meta" style="margin-top:6px;color:var(--sev-crit)">Rule 5: official layers disagree — no automated submission.</div>' : "") + "</div>" +
      '<div class="sec"><h3>Boundary</h3><dl class="kv"><dt>Nearest seam</dt><dd>' + (q[F.seam_ft] == null ? "—" : '<span class="mono">' + nf(Math.round(q[F.seam_ft])) + " ft</span>") + "</dd>" +
      "<dt>Seam divides</dt><dd>" + (q[F.seam_a] ? situsHTML(q[F.seam_a]) + " | " + situsHTML(q[F.seam_b]) : "—") + "</dd>" +
      '<dt>Band</dt><dd><span class="band b-' + esc(band) + '">' + esc(band) + "</span></dd></dl></div>" +
      '<div class="sec"><h3>Score</h3><div class="brk">' + notes.map(function (n) { var m = n.match(/^([+-]\d+)\s*(.*)$/); return m ? '<div><span>' + esc(m[2]) + '</span><span class="' + (m[1][0] === "-" ? "neg" : "pos") + '">' + esc(m[1]) + "</span></div>" : "<div><span>" + esc(n) + "</span></div>"; }).join("") + "</div></div>" +
      '<div class="sec"><h3>Adjudication</h3><div class="adj">' +
      '<div class="row"><input id="adj-who" placeholder="Your initials" value="' + esc(who) + '" aria-label="Analyst initials" style="max-width:120px"><select id="adj-status" aria-label="Status">' + STATUS.map(function (s) { return '<option' + (s === st ? " selected" : "") + ">" + s + "</option>"; }).join("") + "</select></div>" +
      '<textarea id="adj-note" placeholder="What was checked, what was found, what to send DOR…" aria-label="Note">' + esc(a.note || "") + "</textarea>" +
      '<div class="row"><button class="btn" id="adj-save" type="button">Save adjudication</button><button class="btn sec2" id="adj-copy" type="button">Copy packet</button></div>' +
      '<div class="meta" id="adj-meta">' + (a.updatedAt ? "Last saved " + esc(new Date(a.updatedAt).toLocaleString()) + (a.by ? " by " + esc(a.by) : "") : "Not yet adjudicated") + "</div></div></div>" +
      '<div class="sec"><h3>Verify</h3><div class="links"><a href="' + gm + '" target="_blank" rel="noopener">Google Maps / Street View ↗</a><a href="https://tnmap.tn.gov/sst/sst.html" target="_blank" rel="noopener">TN SST address lookup ↗</a></div></div>';
    $("adj-save").onclick = function () {
      var w = $("adj-who").value.trim().slice(0, 12); who = w; try { localStorage.setItem("civvix.who", w); } catch (e) {}
      var rec = { status: $("adj-status").value, note: $("adj-note").value.slice(0, 4000), by: w, updatedAt: new Date().toISOString(), business: q[F.business] || null, flag: f, dor_situs: q[F.dor_situs] || null };
      $("adj-save").disabled = true;
      setAdj(b.id, rec).then(function () { $("adj-save").disabled = false; $("adj-meta").textContent = "Saved " + new Date().toLocaleTimeString() + (w ? " by " + w : ""); renderQueue(); renderEvidence(b); });
    };
    $("adj-copy").onclick = function () {
      var lines = ["CIVVIX SITUS EVIDENCE PACKET", "Business: " + (q[F.business] || ""), "Address: " + (q[F.house_no] || "") + " " + (q[F.street] || "") + " " + (q[F.zip] || ""), "Coordinates: " + q[F.lat] + ", " + q[F.lon],
        "DOR tax polygon: " + q[F.dor_situs] + " " + (SITNAME[q[F.dor_situs]] || ""), "DOR address file: " + (q[F.sst_situs] || "no match"), "Postal city: " + (q[F.post_city] || "") + (q[F.postal_county] ? " (" + q[F.postal_county] + " County)" : ""),
        "911 municipality: " + (q[F.e911_muni] || ""), "Comptroller limit: " + (q[F.comp_city] || ""), "Nearest seam: " + (q[F.seam_ft] == null ? "" : Math.round(q[F.seam_ft]) + " ft, " + q[F.seam_a] + "|" + q[F.seam_b]), "Band: " + band,
        "Evidence score: " + q[F.score] + " — " + (q[F.score_notes] || ""), "Disposition: " + (q[F.disposition] || ""), "Class: " + FLAG[f].name, "Status: " + st + (a.note ? "\nNote: " + a.note : ""), "Generated: " + new Date().toISOString()];
      if (navigator.clipboard) navigator.clipboard.writeText(lines.join("\n")).then(function () { $("adj-copy").textContent = "Copied"; setTimeout(function () { $("adj-copy").textContent = "Copy packet"; }, 1500); });
    };
  }
  function select(b, fly) {
    selected = b; renderEvidence(b); showPane("ev"); if (fly) flyTo(b); else draw();
    [].forEach.call($("qlist").children, function (r) { r.classList.remove("sel"); });
  }
  function showPane(name) {
    ["queue", "ev", "dor"].forEach(function (p) { $("pane-" + p).classList.toggle("on", p === name); $("tab-" + p).setAttribute("aria-selected", String(p === name)); });
  }
  [].forEach.call(document.querySelectorAll(".tabs button"), function (b) { b.onclick = function () { showPane(b.dataset.pane); }; });

  /* ================= DOR file pane ================= */
  var dorRows = null, dorMap = { name: null, addr: null, situs: null };
  function renderDor() {
    var host = $("dor");
    host.innerHTML =
      '<div class="notice"><b>Confidential — stays in this browser tab.</b> Nothing pasted here is uploaded, stored, or shared. Close the tab and it is gone. ' +
      "Under T.C.A. § 67-1-1704(e) the only fields a contractor may hold are <b>name, address and situs</b> — paste nothing else.</div>" +
      "<p>When the situs report arrives from the Department, paste it as CSV. The workbench matches each row to a rooftop-placed business, compares the <b>coded</b> situs with the <b>measured</b> one, and adds a “Coded ≠ measured” class to the queue.</p>" +
      '<textarea id="dor-csv" placeholder="business_name,location_address,situs&#10;ADAMS AUTO SHOP,15115 LEBANON RD OLD HICKORY TN 37138,1900&#10;…" aria-label="Paste situs report CSV"></textarea>' +
      '<div class="map" id="dor-map" hidden></div>' +
      '<div style="display:flex;gap:8px;margin-top:8px"><button class="btn" id="dor-parse" type="button">Read columns</button><button class="btn" id="dor-join" type="button" disabled>Match &amp; compare</button><button class="btn sec2" id="dor-clear" type="button">Clear</button></div>' +
      '<div id="dor-out"></div>' +
      '<div class="sec"><h3>What the request asks for</h3><ul><li>All four Wilson situs codes: <span class="mono">9500 9501 9502 9503</span></li><li>35 ZIP codes — 14 in-county, 21 in the surrounding ring</li><li>Name · DBA · account id · physical address · mailing address · ZIP · situs · status · registration date · location id · as-of date</li><li>Situs-code table, correction procedure, lookback authority, REP access, contractor requirements</li></ul>' +
      '<div class="zips"><b>Tier 1</b> 37012 37016 37071 37085 37087 37088 37090 37095 37118 37121 37122 37136 37138 37184<br><b>Tier 2</b> 37030 37031 37057 37059 37066 37074 37075 37076 37086 37115 37129 37130 37149 37151 37166 37167 37190 38547 38563 38567 38569</div></div>';
    $("dor-parse").onclick = parseDor; $("dor-join").onclick = joinDor;
    $("dor-clear").onclick = function () { dorRows = null; BIZ.forEach(function (b) { b.coded = null; b.codedSitus = null; }); renderDor(); renderQueue(); draw(); };
  }
  function parseCSV(text) {
    var rows = [], row = [], cur = "", inq = false;
    for (var i = 0; i < text.length; i++) { var c = text[i];
      if (inq) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else inq = false; } else cur += c; }
      else if (c === '"') inq = true; else if (c === ",") { row.push(cur); cur = ""; } else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cur); rows.push(row); row = []; cur = ""; } else cur += c; }
    if (cur.length || row.length) { row.push(cur); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (x) { return x.trim(); }); });
  }
  function guess(headers, pats) { for (var i = 0; i < headers.length; i++) for (var j = 0; j < pats.length; j++) if (pats[j].test(headers[i])) return i; return -1; }
  function parseDor() {
    var rows = parseCSV($("dor-csv").value); if (rows.length < 2) { $("dor-out").innerHTML = '<p style="color:var(--sev-crit)">Need a header row and at least one data row.</p>'; return; }
    var H = rows[0].map(function (h) { return h.trim(); }); dorRows = rows.slice(1);
    dorMap = { name: guess(H, [/name/i]), addr: guess(H, [/location|physical|street|address/i]), situs: guess(H, [/situs|juris/i]) };
    var m = $("dor-map"); m.hidden = false;
    m.innerHTML = ["name", "addr", "situs"].map(function (k) { return "<label>" + { name: "Business name", addr: "Physical address", situs: "Situs code" }[k] + '</label><select id="map-' + k + '">' + H.map(function (h, i) { return '<option value="' + i + '"' + (i === dorMap[k] ? " selected" : "") + ">" + esc(h) + "</option>"; }).join("") + "</select>"; }).join("");
    $("dor-join").disabled = false; $("dor-out").innerHTML = '<p>' + nf(dorRows.length) + " rows read, " + H.length + " columns. Check the mapping, then match.</p>";
  }
  function nname(s) { return String(s || "").toUpperCase().replace(/['\u2019]/g, "").replace(/[^A-Z0-9 ]/g, " ").replace(/\b(LLC|INC|CORP|CO|LTD|LP|PLLC|THE|OF|AND|DBA)\b/g, " ").replace(/\s+/g, " ").trim(); }
  function joinDor() {
    ["name", "addr", "situs"].forEach(function (k) { dorMap[k] = +$("map-" + k).value; });
    var idx = {}; BIZ.forEach(function (b) { b.coded = null; b.codedSitus = null; var k = nname(b.r[F.business]); if (k) (idx[k] = idx[k] || []).push(b); });
    var matched = 0, mism = 0, unmatched = [], results = [];
    dorRows.forEach(function (r) {
      var nm = nname(r[dorMap.name]), addr = String(r[dorMap.addr] || "").toUpperCase(), situs = String(r[dorMap.situs] || "").trim().slice(0, 4);
      var cands = idx[nm] || [], hit = null;
      if (cands.length === 1) hit = cands[0];
      else if (cands.length > 1) { var hn = (addr.match(/^\s*(\d+)/) || [])[1]; hit = cands.filter(function (b) { return String(b.r[F.house_no]) === hn; })[0] || null; }
      if (!hit) { unmatched.push([r[dorMap.name], addr, situs]); return; }
      matched++; hit.codedSitus = situs;
      if (situs && situs !== String(hit.r[F.dor_situs])) { mism++; hit.coded = "CODED_MISMATCH"; results.push(hit); }
    });
    renderQueue(); draw();
    $("dor-out").innerHTML = '<div class="stat"><div><div class="v">' + nf(dorRows.length) + '</div><div class="k">DOR rows</div></div><div><div class="v">' + nf(matched) + '</div><div class="k">matched to a rooftop</div></div><div><div class="v" style="color:var(--sev-crit)">' + nf(mism) + '</div><div class="k">coded ≠ measured</div></div></div>' +
      (mism ? "<p>Mismatches are now in the queue under <b>Coded ≠ measured</b>. Each carries the coded situs beside the measured one in its evidence packet.</p>" : "") +
      (unmatched.length ? "<p><b>" + nf(unmatched.length) + " rows did not match</b> a rooftop-placed business by name. These are either outside the public business layer, registered under a different name, or not physically in Wilson County — every one is worth a look, because a Wilson-coded business with no Wilson rooftop is the reverse error.</p><div class=\"zips\" style=\"max-height:180px;overflow:auto\">" + unmatched.slice(0, 200).map(function (u) { return esc(u[0]) + " · " + esc(u[1]) + " · " + esc(u[2]); }).join("<br>") + "</div>" : "");
    if (mism) { qFlag = "CODED_MISMATCH"; [].forEach.call($("qtools").querySelectorAll(".chip"), function (c) { c.setAttribute("aria-pressed", String(c.dataset.flag === "CODED_MISMATCH")); }); renderQueue(); showPane("queue"); }
  }
  renderDor();

  if (W.county) { var cc = document.querySelector(".top .county"); if (cc) cc.textContent = W.county + " · TN · " + SITCODES[0] + "–" + SITCODES[SITCODES.length - 1]; }
  /* ================= boot ================= */
  resize(); fit(); renderQueue();
})();
