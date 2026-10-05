"""Read access to the NASA SMAP/MSL telemetry dataset (Telemanom release).

Layout expected under the data directory:
    train/<chan_id>.npy   test/<chan_id>.npy   labeled_anomalies.csv

Each .npy is shaped (timesteps, features). Column 0 is the telemetry value;
the remaining columns are one-hot command flags.

Run `python -m app.pipeline.dataset` for a summary and sanity check.
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.settings import settings


@dataclass(frozen=True)
class ChannelLabel:
    chan_id: str
    spacecraft: str  # "SMAP" or "MSL"
    anomaly_sequences: list[tuple[int, int]]  # inclusive [start, end] indices into the test split
    anomaly_classes: list[str]  # "point" or "contextual", one per sequence
    num_values: int


def _merge_overlapping(
    sequences: list[tuple[int, int]], classes: list[str]
) -> tuple[list[tuple[int, int]], list[str]]:
    merged: list[tuple[int, int]] = []
    merged_classes: list[str] = []
    for (start, end), cls in sorted(zip(sequences, classes, strict=True)):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
            merged_classes.append(cls)
    return merged, merged_classes


def load_labels(data_dir: Path | None = None) -> dict[str, ChannelLabel]:
    """Labels keyed by channel id.

    Known quirks of the release: P-2 is listed twice with overlapping ranges (merged
    here into one sequence), and T-10 has data files but no labels (so it is absent).
    """
    data_dir = data_dir or settings.data_dir
    labels: dict[str, ChannelLabel] = {}
    with open(data_dir / "labeled_anomalies.csv", newline="") as f:
        for row in csv.DictReader(f):
            sequences = [tuple(pair) for pair in json.loads(row["anomaly_sequences"])]
            classes = [c.strip() for c in row["class"].strip("[]").split(",")]
            previous = labels.get(row["chan_id"])
            if previous is not None:
                sequences = previous.anomaly_sequences + sequences
                classes = previous.anomaly_classes + classes
            sequences, classes = _merge_overlapping(sequences, classes)
            labels[row["chan_id"]] = ChannelLabel(
                chan_id=row["chan_id"],
                spacecraft=row["spacecraft"],
                anomaly_sequences=sequences,
                anomaly_classes=classes,
                num_values=int(row["num_values"]),
            )
    return labels


def load_channel(chan_id: str, split: str, data_dir: Path | None = None) -> np.ndarray:
    """Returns the (timesteps, features) array for one channel and split ("train" or "test")."""
    data_dir = data_dir or settings.data_dir
    return np.load(data_dir / split / f"{chan_id}.npy")


def anomaly_mask(label: ChannelLabel, length: int) -> np.ndarray:
    """Boolean ground-truth mask over the test split."""
    mask = np.zeros(length, dtype=bool)
    for start, end in label.anomaly_sequences:
        mask[start : end + 1] = True
    return mask


def summarise(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or settings.data_dir
    labels = load_labels(data_dir)
    train_files = {p.stem for p in (data_dir / "train").glob("*.npy")}
    test_files = {p.stem for p in (data_dir / "test").glob("*.npy")}
    per_spacecraft: dict[str, dict] = {}
    length_mismatches = []
    for chan_id, label in labels.items():
        if chan_id not in test_files:
            continue
        test = load_channel(chan_id, "test", data_dir)
        train = load_channel(chan_id, "train", data_dir)
        stats = per_spacecraft.setdefault(
            label.spacecraft,
            {"channels": 0, "sequences": 0, "train_points": 0, "test_points": 0, "features": set()},
        )
        stats["channels"] += 1
        stats["sequences"] += len(label.anomaly_sequences)
        stats["train_points"] += len(train)
        stats["test_points"] += len(test)
        stats["features"].add(test.shape[1])
        if len(test) != label.num_values:
            length_mismatches.append((chan_id, len(test), label.num_values))
    return {
        "labelled_channels": len(labels),
        "train_files": len(train_files),
        "test_files": len(test_files),
        "labelled_without_data": sorted(set(labels) - test_files),
        "data_without_labels": sorted(test_files - set(labels)),
        "per_spacecraft": per_spacecraft,
        "length_mismatches": length_mismatches,
    }


if __name__ == "__main__":
    summary = summarise()
    print(f"Labelled channels: {summary['labelled_channels']}")
    print(f"Train files: {summary['train_files']}  Test files: {summary['test_files']}")
    for spacecraft, stats in sorted(summary["per_spacecraft"].items()):
        print(
            f"  {spacecraft}: {stats['channels']} channels, {stats['sequences']} anomaly sequences, "
            f"{stats['train_points']:,} train points, {stats['test_points']:,} test points, "
            f"features per timestep {sorted(stats['features'])}"
        )
    total = sum(s["sequences"] for s in summary["per_spacecraft"].values())
    print(f"Total anomaly sequences: {total}")
    print(f"Labelled channels with no data file: {summary['labelled_without_data'] or 'none'}")
    print(f"Data files with no labels: {summary['data_without_labels'] or 'none'}")
    print(f"Test length != num_values: {summary['length_mismatches'] or 'none'}")
