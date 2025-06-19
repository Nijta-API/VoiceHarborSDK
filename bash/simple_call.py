#!/usr/bin/env bash
set -euo pipefail

#
# Voice Harbor “curl” client
# Usage: ./voice_harbor.sh \
#          --base-url https://api.example.com \
#          --token YOUR_TOKEN \
#          --inputs-dir ./inputs \
#          --job-yaml ./job_spec.yaml \
#          --output-dir ./results \
#          [--timeout 600] [--interval 10]
#

# defaults
TIMEOUT=600
INTERVAL=10

# parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --base-url)    BASE_URL="$2"; shift 2;;
    --token)       TOKEN="$2";    shift 2;;
    --inputs-dir)  INPUTS_DIR="$2"; shift 2;;
    --job-yaml)    JOB_YAML="$2"; shift 2;;
    --output-dir)  OUTPUT_DIR="$2"; shift 2;;
    --timeout)     TIMEOUT="$2"; shift 2;;
    --interval)    INTERVAL="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

# ensure jq is installed
command -v jq >/dev/null 2>&1 || { echo "jq is required"; exit 1; }

echo "▶ Creating job…"
JOB_ID=$(curl -s -X POST "$BASE_URL/api/jobs" \
  -H "Authorization: $TOKEN" \
  -H "Accept: application/json" \
  | jq -r .job_id)
echo "→ Job ID: $JOB_ID"
echo

# collect filenames for download later
declare -a FILES

echo "▶ Uploading input files from $INPUTS_DIR"
for fp in "$INPUTS_DIR"/*; do
  [ -f "$fp" ] || continue
  ext="${fp##*.}"
  # only supported formats
  case "${ext,,}" in
    wav|mp3|flac|ogg|m4a|yaml) ;;
    *) continue;;
  esac

  fname=$(basename "$fp")
  FILES+=("$fname")
  # detect MIME type
  mime=$(file --mime-type -b "$fp" || echo "application/octet-stream")

  echo "  • Requesting upload URL for $fname"
  UP_URL=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/files/upload-url" \
    -H "Authorization: $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"fileName\":\"$fname\",\"fileType\":\"$mime\"}" \
    | jq -r .signedUrl)

  echo "  • Uploading $fname"
  curl -s -X PUT "$UP_URL" \
    -H "Content-Type: $mime" \
    --data-binary @"$fp"
done
echo

# upload the job-spec YAML
job_yaml_name=$(basename "$JOB_YAML")
echo "▶ Uploading job spec $job_yaml_name"
UP_URL=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/files/upload-url" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"fileName\":\"$job_yaml_name\",\"fileType\":\"application/x-yaml\"}" \
  | jq -r .signedUrl)

curl -s -X PUT "$UP_URL" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @"$JOB_YAML"
echo

# prepare output directory
mkdir -p "$OUTPUT_DIR"

echo "▶ Polling & downloading results to $OUTPUT_DIR"
for fname in "${FILES[@]}"; do
  echo "----"
  echo "Waiting for $fname…"
  start=$(date +%s)
  while true; do
    now=$(date +%s)
    if (( now >= start + TIMEOUT )); then
      echo "‼ Timeout waiting for $fname"; break
    fi

    exists=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/files/finalized" \
      -H "Authorization: $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"fileName\":\"$fname\"}" \
      | jq -r .exists)

    if [[ "$exists" == "true" ]]; then
      echo "✓ $fname is ready"; break
    fi

    sleep "$INTERVAL"
  done

  # download the file
  for target in "$fname" "${fname%.*}.json"; do
    echo "  ↓ Downloading $target"
    DL_URL=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/files/download-url" \
      -H "Authorization: $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"fileName\":\"$target\"}" \
      | jq -r .signedUrl)
    curl -s "$DL_URL" -o "$OUTPUT_DIR/$target"
  done
done

echo
echo "✅ All done."
