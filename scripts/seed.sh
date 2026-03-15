#!/usr/bin/env bash
# Seed the backend with sample data for local development.
# Usage: docker compose run --rm seed
# Or:    bash scripts/seed.sh http://localhost:8002

set -euo pipefail

BACKEND_URL="${1:-http://backend:8002}"
TOKEN="${API_TOKEN:-}"

AUTH_HEADER=""
if [ -n "$TOKEN" ]; then
  AUTH_HEADER="Authorization: Bearer $TOKEN"
fi

echo "Seeding backend at $BACKEND_URL..."

# Create a sample source
SRC=$(curl -sf -X POST "$BACKEND_URL/api/v1/sources/" \
  -H "Content-Type: application/json" \
  ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
  -d '{"name": "seed-demo", "format": "json"}' 2>/dev/null || echo '{"id":"skip"}')
SRC_ID=$(echo "$SRC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [ -z "$SRC_ID" ] || [ "$SRC_ID" = "skip" ]; then
  echo "  Source already exists or creation failed, fetching..."
  SRC_ID=$(curl -sf "$BACKEND_URL/api/v1/sources/" | python3 -c "
import sys, json
items = json.load(sys.stdin).get('items', [])
for s in items:
    if s['name'] == 'seed-demo':
        print(s['id'])
        break
" 2>/dev/null || echo "")
fi

if [ -z "$SRC_ID" ]; then
  echo "  Could not create or find source. Exiting."
  exit 1
fi

echo "  Source ID: $SRC_ID"

# Create sample elements
for ELEM in '{"name":"subject_age","data_type":"integer","description":"Age of the participant in years","source_id":"SRC_ID","required":true}' \
            '{"name":"electrode_impedance","data_type":"float","description":"Impedance of the recording electrode in kOhm","source_id":"SRC_ID"}' \
            '{"name":"session_date","data_type":"string","description":"Date of the recording session (ISO 8601)","source_id":"SRC_ID","required":true}' \
            '{"name":"stimulus_type","data_type":"string","description":"Type of stimulus presented","source_id":"SRC_ID","allowed_values":["visual","auditory","tactile"]}' \
            '{"name":"sampling_rate","data_type":"float","description":"Data acquisition sampling rate in Hz","source_id":"SRC_ID","required":true}'; do
  BODY=$(echo "$ELEM" | sed "s/SRC_ID/$SRC_ID/g")
  RESULT=$(curl -sf -X POST "$BACKEND_URL/api/v1/elements/" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$BODY" 2>/dev/null || echo '{"error":"skip"}')
  NAME=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','skipped'))" 2>/dev/null || echo "skipped")
  echo "  Element: $NAME"
done

echo "Seed complete."
