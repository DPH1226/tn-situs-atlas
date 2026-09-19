# Cities layer — install and run

Drop into `~/Downloads/tn-situs-atlas` (the repo that runs refresh.sh). Five files:

    build_cities.py                 new — city pass over out/<county>/, writes artifact/cities/* and artifact/cities.html
    build_site.py                   patched — ships site/cities/, adds the Counties | Cities switch to the atlas
    build_index.py                  patched — one-line fix: pending counties crashed the map-label loop
    deploy/refresh.sh               patched — build_cities.py runs between build_index and build_site
    .github/workflows/refresh.yml   patched — same

Build order is unchanged otherwise: run_all -> build_index -> build_cities -> build_site.

    python3 build_cities.py --city lebanon      # one city, ~30 s; index not rewritten
    python3 build_cities.py                     # every city in every county with out/<slug>/summary.json
    python3 build_site.py

A city page is the county workbench scoped to the city: same wb.js, same evidence packets, same
adjudication store (keyed city-<slug>), with four patches applied to the city copy of wb.js —
the header chip, the home-county check on postal county, the request-pack text, and two
"Wilson" strings. Those last three are also latent bugs in the county workbenches (every county
page currently says "All four Wilson situs codes" on its DOR tab and flags any non-WILSON postal
county as foreign); city_wbjs() in build_cities.py is the fix if you want it applied there too.

Multi-county cities are merged by name: one page, one row, every part.
