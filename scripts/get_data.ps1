# Downloads the NASA SMAP/MSL telemetry dataset (Telemanom release) into data/.
# The original S3 bucket is closed; the Telemanom README now points to this Kaggle copy.
# Usage (from the repo root):  powershell -File scripts/get_data.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$data = Join-Path $root "data"
$zip = Join-Path $data "smap_msl.zip"
$url = "https://www.kaggle.com/api/v1/datasets/download/patrickfleith/nasa-anomaly-detection-dataset-smap-msl"

New-Item -ItemType Directory -Force $data | Out-Null
if (-not (Test-Path $zip)) {
    Write-Host "Downloading dataset (about 86 MB)..."
    curl.exe -sSL --retry 5 -o $zip $url
}

$tmp = Join-Path $data "_extract"
Expand-Archive -Path $zip -DestinationPath $tmp -Force
foreach ($split in "train", "test") {
    $target = Join-Path $data $split
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Move-Item (Join-Path $tmp "data/data/$split") $target
}
Move-Item -Force (Join-Path $tmp "labeled_anomalies.csv") (Join-Path $data "labeled_anomalies.csv")
Remove-Item -Recurse -Force $tmp

Write-Host "Done. Check it with:  cd backend; .venv\Scripts\python -m app.pipeline.dataset"
