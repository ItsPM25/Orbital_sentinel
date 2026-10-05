"""TBD-3: which channel-attribution method to use.

Builds virtual satellites (groups of 4 channels replayed side by side) and asks:
while exactly one channel has a labelled anomaly, does the method rank that
channel first?

Methods compared
  error-rank   per-channel LSTM predictors (the architecture's default); rank channels
               by smoothed prediction error, standardised by each channel's training errors
  joint-recon  one multivariate LSTM autoencoder over the group; rank channels by their
               share of the reconstruction error
  joint-shap   the same joint model; exact Shapley values over channels, where an
               "absent" channel is replaced by its training mean (SHAP-style)

    python attribution.py --a 100,80
"""

import argparse
import itertools
import json
import math
import time

import numpy as np
import torch
from torch import nn

from common import RESULTS_DIR, ewma, load
from detectors import _fit, _predict, _windows
from run_spike import cached_errors, parse_config

GROUPS = {
    "SMAP-1": ["S-1", "E-1", "A-2", "F-1"],
    "SMAP-2": ["G-7", "T-1", "P-4", "P-1"],
    "MSL-1": ["F-7", "P-10", "D-14", "T-13"],
}
WINDOW = 100
SPAN = 30
SAMPLE_EVERY = 5


class JointAutoencoder(nn.Module):
    """Reconstructs every channel of the window's last point from the whole window."""

    def __init__(self, channels: int, hidden: int = 64):
        super().__init__()
        self.encoder = nn.LSTM(channels, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, channels))

    def forward(self, x):
        _, (h, _) = self.encoder(x)
        return self.head(h[-1])


def joint_errors(model: nn.Module, windows: torch.Tensor) -> np.ndarray:
    """(n_windows, channels) absolute reconstruction error of each window's last point."""
    return np.abs(_predict(model, windows) - windows[:, -1, :].numpy())


def shapley(model: nn.Module, windows: torch.Tensor, baseline: torch.Tensor) -> np.ndarray:
    """Exact Shapley value of each channel for the total reconstruction error.

    v(S) = total error when the channels outside S are replaced by their baseline.
    """
    n_channels = windows.shape[2]
    players = range(n_channels)
    value = {}
    for size in range(n_channels + 1):
        for subset in itertools.combinations(players, size):
            masked = baseline.expand_as(windows).clone()
            masked[:, :, list(subset)] = windows[:, :, list(subset)]
            value[subset] = joint_errors(model, masked).sum(axis=1)
    phi = np.zeros((len(windows), n_channels))
    for c in players:
        others = [p for p in players if p != c]
        for size in range(n_channels):
            weight = math.factorial(size) * math.factorial(n_channels - size - 1) / math.factorial(n_channels)
            for subset in itertools.combinations(others, size):
                with_c = tuple(sorted(subset + (c,)))
                phi[:, c] += weight * (value[with_c] - value[subset])
    return phi


def run_group(name: str, chan_ids: list[str], a_config: tuple) -> dict:
    channels = [load(c) for c in chan_ids]
    n_test = min(len(c.test) for c in channels)
    n_train = min(len(c.train) for c in channels)

    # Ground truth per timestep: which channels are inside a labelled anomaly.
    truth = np.zeros((n_test, len(channels)), dtype=bool)
    events = []  # (channel index, start, end)
    for i, channel in enumerate(channels):
        for start, end in channel.label.anomaly_sequences:
            if start < n_test:
                truth[start : min(end, n_test - 1) + 1, i] = True
                events.append((i, start, min(end, n_test - 1)))
    single = truth.sum(axis=1) == 1
    warmup = max(a_config[0], WINDOW)
    points = np.array([t for t in range(warmup, n_test, SAMPLE_EVERY) if single[t]])
    target = truth[points].argmax(axis=1)

    # error-rank: per-channel predictors, errors standardised by training errors.
    started = time.perf_counter()
    scores = np.zeros((n_test, len(channels)))
    for i, chan_id in enumerate(chan_ids):
        train, test, _, w = cached_errors("A", a_config, chan_id)
        train_s = ewma(train, SPAN)[w:]
        scores[:, i] = (ewma(test, SPAN)[:n_test] - train_s.mean()) / train_s.std()
    rank_seconds = time.perf_counter() - started

    # Joint model over the telemetry column of every channel.
    torch.manual_seed(0)
    train = np.stack([c.train[:n_train, 0] for c in channels], axis=1)
    test = np.stack([c.test[:n_test, 0] for c in channels], axis=1)
    model = JointAutoencoder(len(channels))
    train_windows = torch.from_numpy(_windows(train, WINDOW, stride=2))
    started = time.perf_counter()
    _fit(model, train_windows, train_windows[:, -1, :])
    joint_train_seconds = time.perf_counter() - started

    windows = torch.from_numpy(np.stack([test[t - WINDOW + 1 : t + 1] for t in points]))
    train_err = joint_errors(model, torch.from_numpy(_windows(train, WINDOW)))
    started = time.perf_counter()
    recon = (joint_errors(model, windows) - train_err.mean(axis=0)) / train_err.std(axis=0)
    recon_ms = (time.perf_counter() - started) / len(points) * 1000
    baseline = torch.from_numpy(train.mean(axis=0)).reshape(1, 1, -1)
    started = time.perf_counter()
    shap = shapley(model, windows, baseline)
    shap_ms = (time.perf_counter() - started) / len(points) * 1000

    methods = {"error-rank": scores[points], "joint-recon": recon, "joint-shap": shap}
    result = {"group": name, "channels": chan_ids, "points": int(len(points)), "events": len(events)}
    for method, values in methods.items():
        point_hits = float((values.argmax(axis=1) == target).mean())
        # Event level: at the labelled sequence's strongest sampled point, is the top channel right?
        event_hits = []
        for chan_index, start, end in events:
            inside = np.flatnonzero((points >= start) & (points <= end))
            if len(inside) == 0:
                continue
            peak = inside[values[inside].max(axis=1).argmax()]
            event_hits.append(values[peak].argmax() == chan_index)
        result[method] = {
            "point_hit_rate": round(point_hits, 3),
            "event_hit_rate": round(float(np.mean(event_hits)), 3),
            "events_scored": len(event_hits),
        }
    result["cost"] = {
        "error-rank_extra_ms_per_window": 0.0,  # reuses the detector's own errors
        "error-rank_setup_s": round(rank_seconds, 2),
        "joint_model_train_s": round(joint_train_seconds, 1),
        "joint-recon_ms_per_window": round(recon_ms, 3),
        "joint-shap_ms_per_window": round(shap_ms, 3),
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", type=parse_config, required=True, help="A config, e.g. 100,80")
    args = parser.parse_args()

    results = [run_group(name, chans, args.a) for name, chans in GROUPS.items()]
    for r in results:
        print(f"\n{r['group']} {r['channels']}  ({r['points']} sampled points, {r['events']} labelled events)")
        for method in ("error-rank", "joint-recon", "joint-shap"):
            m = r[method]
            print(f"  {method:12s} point hit rate {m['point_hit_rate']:.3f}   event hit rate {m['event_hit_rate']:.3f} ({m['events_scored']} events)")
        print(f"  cost: {r['cost']}")
    print("\n(random guess = 0.25 with 4 channels)")
    (RESULTS_DIR / "attribution.json").write_text(json.dumps(results, indent=1))
