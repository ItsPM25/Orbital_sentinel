"""The per-channel LSTM predictor chosen in ADR 001: model, training and batch scoring.

Imports torch at module level, so only the detector, training and evaluation
code import this module; the API and its tests run without PyTorch.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from app.pipeline.ingest import HISTORY, Normaliser, sliding_windows

HORIZON = 10
HIDDEN = 80
LAYERS = 2
DROPOUT = 0.3
LEARNING_RATE = 1e-3
BATCH = 64
MAX_EPOCHS = 20
PATIENCE = 3
MIN_DELTA = 3e-4
VALIDATION_SHARE = 0.2

TRAINING_HYPERPARAMS = {
    "history": HISTORY,
    "horizon": HORIZON,
    "hidden": HIDDEN,
    "layers": LAYERS,
    "dropout": DROPOUT,
    "lr": LEARNING_RATE,
    "batch": BATCH,
    "max_epochs": MAX_EPOCHS,
    "patience": PATIENCE,
    "min_delta": MIN_DELTA,
    "validation_share": VALIDATION_SHARE,
}


class LstmPredictor(nn.Module):
    """Predicts the next HORIZON telemetry values from HISTORY steps of every feature."""

    def __init__(self, features: int):
        super().__init__()
        self.lstm = nn.LSTM(features, HIDDEN, num_layers=LAYERS, batch_first=True, dropout=DROPOUT)
        self.head = nn.Linear(HIDDEN, HORIZON)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1])


@dataclass
class TrainedChannel:
    model: LstmPredictor
    stats: dict
    train_seconds: float
    epochs: int


def _training_pairs(data: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
    n_pairs = len(data) - HISTORY - HORIZON + 1
    x = sliding_windows(data, HISTORY)[:n_pairs]
    y = sliding_windows(data[HISTORY:, :1], HORIZON)[:n_pairs, :, 0]
    return torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)), torch.from_numpy(
        np.ascontiguousarray(y, dtype=np.float32)
    )


def prediction_errors(model: LstmPredictor, data: np.ndarray) -> np.ndarray:
    """|actual - first-step prediction| at every index; the first HISTORY indices get 0."""
    errors = np.zeros(len(data), dtype=np.float64)
    n = len(data) - HISTORY
    if n <= 0:
        return errors
    x = torch.from_numpy(np.ascontiguousarray(sliding_windows(data, HISTORY)[:n], dtype=np.float32))
    model.eval()
    with torch.no_grad():
        predicted = torch.cat([model(x[i : i + 512]) for i in range(0, len(x), 512)]).numpy()[:, 0]
    errors[HISTORY:] = np.abs(predicted.astype(np.float64) - data[HISTORY:, 0].astype(np.float64))
    return errors


def train_channel(train: np.ndarray, seed: int = 0) -> TrainedChannel:
    """Adam + MSE with early stopping on the last VALIDATION_SHARE of the training windows."""
    from app.pipeline.detect import EWMA_SPAN, ewma

    torch.manual_seed(seed)
    normaliser = Normaliser.fit(train)
    data = normaliser.transform(train)
    x, y = _training_pairs(data)
    split = int(len(x) * (1 - VALIDATION_SHARE))
    x_train, y_train, x_val, y_val = x[:split], y[:split], x[split:], y[split:]

    model = LstmPredictor(data.shape[1])
    optimiser = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.MSELoss()
    best, best_state, stale, epochs = float("inf"), None, 0, 0
    started = time.perf_counter()
    for epochs in range(1, MAX_EPOCHS + 1):  # noqa: B007 (read after the loop, to report how many ran)
        model.train()
        order = torch.randperm(len(x_train))
        for i in range(0, len(order), BATCH):
            idx = order[i : i + BATCH]
            optimiser.zero_grad()
            loss_fn(model(x_train[idx]), y_train[idx]).backward()
            optimiser.step()
        model.eval()
        with torch.no_grad():
            val = loss_fn(model(x_val), y_val).item()
        if val < best - MIN_DELTA:
            best, stale = val, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    train_seconds = time.perf_counter() - started

    # Statistics the live detector needs: the value range for the negligible-error
    # check, and smoothed training errors to standardise attribution (ADR 002).
    smoothed = ewma(prediction_errors(model, data), EWMA_SPAN)[HISTORY:]
    stats = {
        "features": int(data.shape[1]),
        "normaliser": normaliser.to_dict(),
        "value_range": float(np.ptp(data[:, 0])),
        "train_error_mean": float(smoothed.mean()),
        "train_error_std": float(smoothed.std()) or 1.0,
        "validation_loss": float(best),
        "epochs": epochs,
        "train_seconds": round(train_seconds, 1),
    }
    return TrainedChannel(model=model, stats=stats, train_seconds=train_seconds, epochs=epochs)


def save_channel(artifact_dir: Path, chan_id: str, trained: TrainedChannel) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    torch.save(trained.model.state_dict(), artifact_dir / f"{chan_id}.pt")
    (artifact_dir / f"{chan_id}.stats.json").write_text(json.dumps(trained.stats, indent=1), encoding="utf-8")


def load_channel_model(artifact_dir: Path, chan_id: str) -> tuple[LstmPredictor, dict]:
    stats = json.loads((artifact_dir / f"{chan_id}.stats.json").read_text(encoding="utf-8"))
    model = LstmPredictor(stats["features"])
    model.load_state_dict(torch.load(artifact_dir / f"{chan_id}.pt", map_location="cpu", weights_only=True))
    model.eval()
    return model, stats
