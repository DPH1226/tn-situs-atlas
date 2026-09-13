#!/usr/bin/env bash
# Full statewide refresh. Same steps as .github/workflows/refresh.yml, for a Railway cron service.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 fetch/fetch_county.py --statewide --live
for c in $(ls configs/*.yaml | xargs -n1 basename | sed 's/\.yaml//' | grep -v -e statewide -e schema); do
  python3 fetch/fetch_county.py --county "$c" --live || echo "fetch failed: $c"
done
python3 fetch/postal_map.py
python3 run_all.py --skip-ingest --workers "${WORKERS:-4}"
python3 build_index.py
python3 build_site.py --domain "${SITE_DOMAIN:-navigationholdings.com}"
if [ -n "${GIT_PUSH:-}" ]; then
  git config user.name civvix-bot && git config user.email bot@civvix.ai
  git add out/*/summary.json out/*/bulletins out/statewide_index.json configs/postal_home_county.json site
  git diff --cached --quiet || (git commit -m "refresh: $(date -u +%F)" && git push)
fi
