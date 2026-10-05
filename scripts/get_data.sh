#!/usr/bin/env bash
# Downloads the NASA SMAP/MSL telemetry dataset (Telemanom release) into data/.
# The original S3 bucket is closed; the Telemanom README now points to this Kaggle copy.
# Usage (from the repo root):  bash scripts/get_data.sh
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
data="$root/data"
zip="$data/smap_msl.zip"
url="https://www.kaggle.com/api/v1/datasets/download/patrickfleith/nasa-anomaly-detection-dataset-smap-msl"

mkdir -p "$data"
if [ ! -f "$zip" ]; then
  echo "Downloading dataset (about 86 MB)..."
  curl -sSL --retry 5 -o "$zip" "$url"
fi

cd "$data"
unzip -q -o "$zip" "data/data/train/*" "data/data/test/*" labeled_anomalies.csv
rm -rf train test
mv data/data/train train
mv data/data/test test
rm -rf data

echo "Done. Check it with:  cd backend && python -m app.pipeline.dataset"
