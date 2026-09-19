# Revenue flows, valuation, scenario — install and run

Files (drop into tn-situs-atlas; build_flows.py, build_cities.py and configs/ also into civvix-wilson-situs, where the county CSVs live):

    build_flows.py                        per-business direction, tier, confidence and VALUE; per-jurisdiction dollar aggregates;
                                          the Revenue flows page with scenario sliders and the statewide Tier A figure
    build_cities.py                       cities index: full-width bulleted "How to read this", Revenue flows tab
    build_index.py                        county atlas: full-width bulleted "How to read this"; pending-county fix
    build_site.py                         ships site/flows/, three-tab nav, non-destructive rebuild
    configs/local_option_sales_tax.json   FY2025 local sales tax by county, all 95, from the DOR June 2025 collections book
                                          (page 13, "Collection Report by Counties - Local Sales"); sums to the report total
    deploy/refresh.sh, .github/workflows/refresh.yml   build_flows.py runs between build_cities and build_site

Valuation: a business is worth its county's FY2025 local sales tax divided by the businesses the run located there;
cross-county flows count the whole average, in-county flows half. Refresh the JSON each July from
https://www.tn.gov/content/dam/tn/revenue/documents/pubs/<yyyy>/Coll<yyyy>06.pdf (page 13) — it is a 95-line table.

Everything on the page says, in its own words, that the priors are assumptions and the average is a skewed upper bound.
