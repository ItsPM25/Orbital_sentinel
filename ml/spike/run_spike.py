"""Phase 1 spike runner.

    python run_spike.py tune                      # sweep every candidate on the tuning channels
    python run_spike.py eval --a 250,80 100,80 --b 50,32   # frozen configs on the evaluation channels

Error series are cached in results/errors/, so threshold sweeps and reruns are cheap.
"""

import argparse
import json
import time

import numpy as np

from common import (
    EVAL_CHANNELS,
    RESULTS_DIR,
    TUNING_CHANNELS,
    aggregate,
    dynamic_threshold,
    evaluate,
    ewma,
    load,
    static_threshold,
)
from detectors import (
    isolation_forest_scores,
    lstm_autoencoder_errors,
    lstm_predictor_errors,
    rolling_zscore,
)

SPANS = [30, 105]  # EWMA smoothing of the error series (105 is the paper's default)
STATIC_KS = [3, 5, 8]

A_CONFIGS = [(250, 80), (100, 80), (100, 40)]  # (history, hidden); (250, 80) is the paper's
B_CONFIGS = [(100, 64), (50, 32)]  # (window, hidden)


def cached_errors(family: str, config: tuple, chan_id: str):
    """Returns (train_errors, test_errors, train_seconds, warmup) for one model on one channel."""
    path = RESULTS_DIR / "errors" / f"{family}_{'_'.join(map(str, config))}_{chan_id}.npz"
    if path.exists():
        saved = np.load(path)
        return saved["train"], saved["test"], float(saved["seconds"]), int(saved["warmup"])
    channel = load(chan_id)
    if family == "A":
        train, test, seconds = lstm_predictor_errors(channel, *config)
        warmup = config[0]
    elif family == "B":
        train, test, seconds = lstm_autoencoder_errors(channel, *config)
        warmup = config[0] - 1
    else:  # isolation forest
        train, test, seconds = isolation_forest_scores(channel, *config)
        warmup = config[0] - 1
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, train=train, test=test, seconds=seconds, warmup=warmup)
    return train, test, seconds, warmup


def threshold_variants(train: np.ndarray, test: np.ndarray, warmup: int, value_range: float) -> dict:
    """Every thresholding variant for one error series -> {variant name: boolean mask}."""
    masks = {}
    for span in SPANS:
        smoothed_test = ewma(test, span)
        smoothed_train = ewma(train, span)[warmup:]
        masks[f"dynamic/span{span}"] = dynamic_threshold(smoothed_test, value_range)
        for k in STATIC_KS:
            masks[f"static-k{k}/span{span}"] = static_threshold(smoothed_train, smoothed_test, k)
    return masks


def run(channels: list[str], a_configs, b_configs) -> dict:
    """Returns {variant: {"rows": {chan: counts}, "seconds": [train time per channel]}}."""
    results: dict[str, dict] = {}

    def record(variant: str, chan_id: str, counts: dict, seconds: float):
        entry = results.setdefault(variant, {"rows": {}, "seconds": []})
        entry["rows"][chan_id] = counts
        entry["seconds"].append(seconds)

    for chan_id in channels:
        channel = load(chan_id)
        value_range = float(np.ptp(channel.test[:, 0]))
        families = [("A", c) for c in a_configs] + [("B", c) for c in b_configs] + [("IF", (50,))]
        for family, config in families:
            started = time.perf_counter()
            train, test, seconds, warmup = cached_errors(family, config, chan_id)
            name = f"{family}{list(config)}"
            for variant, mask in threshold_variants(train, test, warmup, value_range).items():
                record(f"{name} {variant}", chan_id, evaluate(mask, channel.label), seconds)
            print(f"  {chan_id:5s} {name:12s} train {seconds:6.1f}s (wall {time.perf_counter() - started:.1f}s)", flush=True)

        # Floor: rolling z-score on the raw telemetry value, no training.
        for window in (100, 250):
            z = rolling_zscore(channel.test[:, 0], window)
            for k in (4, 6, 8):
                record(f"Z[{window}] k{k}", chan_id, evaluate(z > k, channel.label), 0.0)
    return results


def summarise(results: dict) -> list[dict]:
    table = []
    for variant, entry in results.items():
        metrics = aggregate(list(entry["rows"].values()))
        metrics["variant"] = variant
        # Median, because a throttled machine produced a few very slow outliers.
        metrics["train_s_per_channel"] = round(float(np.median(entry["seconds"])), 1)
        table.append(metrics)
    table.sort(key=lambda m: (-m["f1"], m["point_fpr"]))
    return table


def print_table(table: list[dict]) -> None:
    print(f"{'variant':34s} {'P':>6s} {'R':>6s} {'F1':>6s} {'TP':>3s} {'FN':>3s} {'FP':>3s} {'pointFPR':>9s} {'train s/ch':>10s}")
    for m in table:
        print(
            f"{m['variant']:34s} {m['precision']:6.3f} {m['recall']:6.3f} {m['f1']:6.3f} "
            f"{m['tp']:3d} {m['fn']:3d} {m['fp']:3d} {m['point_fpr']:9.4f} {m['train_s_per_channel']:10.1f}"
        )


def parse_config(text: str) -> tuple:
    return tuple(int(part) for part in text.split(","))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["tune", "eval"])
    parser.add_argument("--a", type=parse_config, nargs="*", default=[], help="A configs for eval, e.g. 100,80")
    parser.add_argument("--b", type=parse_config, nargs="*", default=[], help="B configs for eval, e.g. 50,32")
    args = parser.parse_args()

    if args.stage == "tune":
        channels, a_configs, b_configs = TUNING_CHANNELS, A_CONFIGS, B_CONFIGS
    else:
        channels, a_configs, b_configs = EVAL_CHANNELS, args.a, args.b

    results = run(channels, a_configs, b_configs)
    table = summarise(results)
    print_table(table)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"{args.stage}.json").write_text(
        json.dumps({"channels": channels, "table": table, "per_channel": results}, indent=1)
    )
