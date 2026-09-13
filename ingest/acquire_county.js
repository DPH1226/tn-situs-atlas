/*  Civvix situs data acquisition — portable to any Tennessee county.
 *
 *  WHY THIS IS A BROWSER SCRIPT AND NOT A PYTHON SCRIPT
 *  Neither the cloud workspace nor the sandboxed local shell can reach tn.gov,
 *  census.gov or arcgis.com — the egress proxy blocks them. A browser can.
 *  Paste this into the DevTools console on any https://tnmap.tn.gov page and it
 *  downloads the whole county package to your Downloads folder.
 *
 *  Chrome will block everything after the first file until you allow multiple
 *  downloads for the site (address-bar icon, or Settings > Privacy and security
 *  > Site settings > Additional permissions > Automatic downloads).
 *
 *  USAGE:  await civvixAcquire("WILSON")
 *          await civvixAcquire("RUTHERFORD", { statewide: false })
 *
 *  COST: $0. Every endpoint below is public and unauthenticated.
 */
window.civvixAcquire = async function (COUNTY, opts) {
  opts = opts || {};
  COUNTY = String(COUNTY).toUpperCase();
  const R = "https://tnmap.tn.gov/arcgis/rest/services/COMMUNITY/REVENUE_TAX_RATE_BOUNDARIES/MapServer";
  const S = "https://tnmap.tn.gov/arcgis/rest/services/COMMUNITY/SST/MapServer";
  const NG = "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services";
  const log = (...a) => console.log("[civvix]", ...a);

  async function pull(base, where, o) {
    o = o || {};
    const geom = o.geom !== false;
    let all = [], offset = 0;
    for (let guard = 0; guard < 400; guard++) {
      const p = new URLSearchParams({
        where, outFields: o.outFields || "*", returnGeometry: String(geom),
        outSR: "4326", f: geom ? "geojson" : "json",
        resultOffset: String(offset), resultRecordCount: "2000",
      });
      const r = await fetch(base + "/query?" + p);
      if (!r.ok) throw new Error(base + " -> HTTP " + r.status);
      const j = await r.json();
      if (j.error) throw new Error(base + " -> " + JSON.stringify(j.error).slice(0, 200));
      const f = geom ? (j.features || []) : (j.features || []).map((x) => x.attributes);
      all = all.concat(f);
      if (f.length < 2000) break;
      offset += f.length;
    }
    return all;
  }
  function save(name, obj) {
    const b = new Blob([JSON.stringify(obj)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    return b.size;
  }
  const slug = COUNTY.toLowerCase().replace(/[^a-z]/g, "");
  const done = [];
  async function grab(name, base, where, o) {
    const rows = await pull(base, where, o);
    if (!rows.length) { log("EMPTY", name); return; }
    const payload = (o && o.geom === false) ? rows : { type: "FeatureCollection", features: rows };
    done.push([name, rows.length, save(name, payload)]);
    log(name, rows.length, "features");
    await new Promise((s) => setTimeout(s, 400));
  }

  // 1. THE AUTHORITATIVE LAYER. What the Department actually bills against.
  //    Pull statewide once: 473 polygons covering every situs in Tennessee.
  //    This one file is the whole 95-county expansion asset.
  if (opts.statewide !== false)
    await grab("dor_tax_rate_boundaries_TN_statewide.geojson", R + "/0", "1=1");
  await grab(`dor_tax_rate_boundaries_${slug}.geojson`, R + "/0", `COUNTY='${COUNTY}'`);

  // 2. Rate overlays a city-level audit silently misses.
  await grab("dor_cbid_boundaries.geojson", R + "/1", "1=1");
  await grab("dor_tdz_boundaries.geojson", R + "/2", "1=1");

  // 3. Certified municipal boundaries, all 345 TN cities, aggregated monthly by
  //    the Comptroller's Office of Local Government.
  //    NOT ADMINISTRATIVE_BOUNDARIES/0 — that layer's metadata dates it to
  //    June 2017 and would miss every annexation since.
  await grab("tn_sst_city_boundaries.geojson", S + "/2", "1=1");
  await grab("sst_counties.geojson", S + "/3", "1=1");

  // 4. DOR's OWN address-range -> situs table. Comparing this against DOR's own
  //    polygon is the highest-value public-data check available, and it needs
  //    no confidential file.
  //    TRAP: countyno / countyfips in this table are misaligned — filtering on
  //    countyno=95 returns Lake County. Filter on the county NAME.
  await grab(`sst_address_lookup_${slug}.json`, S + "/4", `county='${COUNTY}'`, { geom: false });

  // 5. Rooftop address points. Inc_Muni / Post_City / Census_Plc on one record
  //    is the three-way distinction the whole audit turns on.
  await grab(`${slug}_ng911_address_points.geojson`, NG + "/Tennessee_NG911_Address_Points/FeatureServer/0",
    `County='${COUNTY}'`, {
      outFields: "OBJECTID,Add_Number,AddNo_Full,St_PreDir,St_Name,St_PosTyp,St_PosDir," +
                 "StNam_Full,Unit,County,Inc_Muni,Post_City,Census_Plc,Uninc_Comm,Zip_Code," +
                 "Placement,Parcel_ID,Addr_Type,Lifecycle",
    });
  await grab(`${slug}_ng911_road_centerlines.geojson`,
    NG + "/Tennessee_NG911_Road_Centerlines/FeatureServer/0", `County='${COUNTY}'`);

  // 6. County-specific public sources. These differ per county — find them by
  //    checking the county's 911/ECD district on ArcGIS Online first; it is
  //    routinely more open than the county GIS department.
  if (COUNTY === "WILSON") {
    const W = "https://services1.arcgis.com/ai5RqMP3xEKGv0of/arcgis/rest/services";
    await grab("wilson_business_points.geojson", W + "/Business_Labels/FeatureServer/53", "1=1");
    await grab("wilson_911_address_points.geojson", W + "/911_address_points/FeatureServer/140", "1=1");
    // Mt. Juliet: annexation history. Nothing at state or federal level captures
    // this, and annexation is the commonest cause of a stale situs assignment.
    const A = "https://utility.arcgis.com/usrsvcs/servers/621b088a06a84f16b412e25b8d127804/rest/services/Administration_City/FeatureServer";
    const P = "https://utility.arcgis.com/usrsvcs/servers/5e2f5bfd27984da89b2e45a726d0e37b/rest/services/Planning___Zoning/FeatureServer";
    await grab("mtjuliet_city_limits.geojson", A + "/2", "1=1");
    await grab("mtjuliet_urban_growth_boundary.geojson", A + "/0", "1=1");
    await grab("mtjuliet_annexations.geojson", P + "/0", "1=1");
  }

  console.table(done.map(([n, c, b]) => ({ file: n, features: c, MB: (b / 1e6).toFixed(2) })));
  log("complete —", done.length, "files, $0.00");
  return done;
};
console.log('[civvix] ready. Run:  await civvixAcquire("WILSON")');
