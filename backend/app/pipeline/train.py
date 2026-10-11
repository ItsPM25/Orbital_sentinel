"""Offline training CLI: one LSTM predictor per channel → models/<model_id>/ (D3)
plus a DETECTION_MODEL row.

    python -m app.pipeline.train                    # every labelled channel
    python -m app.pipeline.train --channels P-1 S-1

Resumable: channels that already have weights are skipped, so an interrupted
run (for example a laptop that went to sleep) continues where it stopped.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from app.core.db import SessionLocal, utcnow
from app.core.settings import settings
from app.models import DetectionModel
from app.pipeline.dataset import load_channel, load_labels
from app.pipeline.detect import GLOBAL_THRESHOLD, THRESHOLD_HYPERPARAMS
from app.pipeline.lstm import TRAINING_HYPERPARAMS, save_channel, train_channel

DEFAULT_MODEL_ID = "MDL-LSTM-100-80"


def _write_manifest(artifact_dir, model_id: str, channels: list[str]) -> None:
    manifest = {
        "model_id": model_id,
        "model_type": "LSTM predictor + dynamic threshold",
        "threshold": GLOBAL_THRESHOLD,
        "channels": sorted(channels),
        "hyperparams": {**TRAINING_HYPERPARAMS, **THRESHOLD_HYPERPARAMS},
        "updated_at": utcnow().isoformat(),
    }
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def register_model(model_id: str, artifact_dir) -> None:
    with SessionLocal() as db:
        row = db.get(DetectionModel, model_id) or DetectionModel(model_id=model_id)
        row.model_name = "LSTM predictor 100/80"
        row.model_type = "LSTM predictor + dynamic threshold"
        row.threshold = GLOBAL_THRESHOLD
        row.trained_at = utcnow()
        row.artifact_path = str(artifact_dir)
        row.hyperparams = {**TRAINING_HYPERPARAMS, **THRESHOLD_HYPERPARAMS}
        db.add(row)
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--channels", nargs="*", help="dataset channel ids; default: every labelled channel")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-register", action="store_true", help="skip writing the DETECTION_MODEL row")
    args = parser.parse_args()

    artifact_dir = settings.models_dir / args.model_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    channels = args.channels or sorted(load_labels())
    done = sorted(p.stem for p in artifact_dir.glob("*.pt"))

    started = time.perf_counter()
    for i, chan_id in enumerate(channels, 1):
        if chan_id in done:
            print(f"[{i}/{len(channels)}] {chan_id}: already trained, skipping", flush=True)
            continue
        trained = train_channel(load_channel(chan_id, "train").astype(np.float32), seed=args.seed)
        save_channel(artifact_dir, chan_id, trained)
        done.append(chan_id)
        _write_manifest(artifact_dir, args.model_id, done)
        print(
            f"[{i}/{len(channels)}] {chan_id}: {trained.train_seconds:.0f}s, {trained.epochs} epochs, "
            f"val loss {trained.stats['validation_loss']:.4f}",
            flush=True,
        )
    _write_manifest(artifact_dir, args.model_id, done)
    if not args.no_register:
        register_model(args.model_id, artifact_dir)
    print(f"Done: {len(done)} channels in {artifact_dir} ({time.perf_counter() - started:.0f}s this run)")


if __name__ == "__main__":
    main()
