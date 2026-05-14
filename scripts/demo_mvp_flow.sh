#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
DEMO_EMAIL="${DEMO_EMAIL:-canopy-demo-$(date +%s)@example.org}"
DEMO_PASSWORD="${DEMO_PASSWORD:-correct-horse-battery}"
DEMO_ORG="${DEMO_ORG:-Canopy Demo Org}"
OUTPUT_DIR="${OUTPUT_DIR:-demo-output}"
CSV_PATH="$OUTPUT_DIR/canopy-alerts-with-fusion.csv"
NDVI_SAMPLE_CSV="${NDVI_SAMPLE_CSV:-docs/sample-data/ndvi_sample.csv}"

mkdir -p "$OUTPUT_DIR"

json_get() {
  python -c 'import json,sys; data=json.load(sys.stdin); print(eval(sys.argv[1], {}, {"data": data}))' "$1"
}

api_json() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -fsS -X "$method" "$API_BASE_URL$path" \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer ${TOKEN:-}" \
      -d "$body"
  else
    curl -fsS -X "$method" "$API_BASE_URL$path" \
      -H "Authorization: Bearer ${TOKEN:-}"
  fi
}

echo "Checking API health at $API_BASE_URL..."
api_json GET /api/health | python -m json.tool >/dev/null

SIGNUP_RESPONSE=$(curl -fsS -X POST "$API_BASE_URL/api/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Demo Ranger\",\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\",\"organization_name\":\"$DEMO_ORG\"}")
TOKEN=$(printf '%s' "$SIGNUP_RESPONSE" | json_get 'data["access_token"]')

LOGIN_RESPONSE=$(curl -fsS -X POST "$API_BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\"}")
TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | json_get 'data["access_token"]')

ME_RESPONSE=$(api_json GET /api/auth/me)
ORG_ID=$(printf '%s' "$ME_RESPONSE" | json_get 'data["org_id"]')

REGION_RESPONSE=$(api_json POST /api/regions '{"name":"Demo Sector","description":"Automated MVP demo region"}')
REGION_ID=$(printf '%s' "$REGION_RESPONSE" | json_get 'data["id"]')

SENSOR_RESPONSE=$(api_json POST /api/sensors "{\"name\":\"FLU-Demo\",\"device_type\":\"forest-listening-unit\",\"region_id\":$REGION_ID,\"location\":{\"lat\":-3.4653,\"lon\":-62.2159}}")
SENSOR_ID=$(printf '%s' "$SENSOR_RESPONSE" | json_get 'data["id"]')

AUDIO_FILE=$(mktemp /tmp/canopy-chainsaw-demo.XXXXXX.wav)
printf 'RIFF....WAVE' > "$AUDIO_FILE"
CLIP_RESPONSE=$(curl -fsS -X POST "$API_BASE_URL/api/clips/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "sensor_id=$SENSOR_ID" \
  -F "file=@$AUDIO_FILE;type=audio/wav")
rm -f "$AUDIO_FILE"
ACOUSTIC_ALERT_ID=$(printf '%s' "$CLIP_RESPONSE" | json_get 'data["generated_alert"]["id"]')

if [[ ! -f "$NDVI_SAMPLE_CSV" ]]; then
  echo "NDVI sample CSV not found: $NDVI_SAMPLE_CSV" >&2
  exit 1
fi
NDVI_RESPONSE=$(curl -fsS -X POST "$API_BASE_URL/api/ndvi/upload-csv" \
  -H "Authorization: Bearer $TOKEN" \
  -F "region_id=$REGION_ID" \
  -F 'loss_threshold=-0.15' \
  -F 'default_confidence=0.75' \
  -F "file=@$NDVI_SAMPLE_CSV;type=text/csv")
NDVI_BATCH_ID=$(printf '%s' "$NDVI_RESPONSE" | json_get 'data["batch_id"]')
SATELLITE_CHANGE_IDS=$(printf '%s' "$NDVI_RESPONSE" | python -c 'import json,sys; print(",".join(str(x) for x in json.load(sys.stdin)["created_satellite_change_ids"]))')
SATELLITE_CHANGE_ID=$(printf '%s' "$NDVI_RESPONSE" | json_get 'data["created_satellite_change_ids"][0]')

FUSION_RESPONSE=$(api_json POST /api/fusion/run '{"time_window_days":14,"distance_meters":500,"min_acoustic_confidence":0.65,"min_satellite_severity":0.3}')
FUSED_ALERT_ID=$(printf '%s' "$FUSION_RESPONSE" | json_get 'data["alerts"][0]["id"]')

ALERTS_RESPONSE=$(api_json GET '/api/alerts?type=fusion')
printf '%s' "$ALERTS_RESPONSE" | python -c 'import json,sys; data=json.load(sys.stdin); assert data and data[0]["type"] == "fusion"'

api_json PATCH "/api/alerts/$FUSED_ALERT_ID/status" '{"status":"investigating","note":"Automated demo smoke test"}' | python -m json.tool >/dev/null

curl -fsS -L -H "Authorization: Bearer $TOKEN" \
  "$API_BASE_URL/api/alerts/export?format=csv" -o "$CSV_PATH"

echo "Canopy MVP demo flow completed successfully."
echo "org_id=$ORG_ID"
echo "region_id=$REGION_ID"
echo "sensor_id=$SENSOR_ID"
echo "acoustic_alert_id=$ACOUSTIC_ALERT_ID"
echo "ndvi_batch_id=$NDVI_BATCH_ID"
echo "created_satellite_change_ids=$SATELLITE_CHANGE_IDS"
echo "satellite_change_id=$SATELLITE_CHANGE_ID"
echo "fused_alert_id=$FUSED_ALERT_ID"
echo "csv_path=$CSV_PATH"
