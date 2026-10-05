"""Candidate detectors for the Phase 1 spike. Each returns per-point error series
for the train and test splits, aligned to the split's indices."""

import time

import numpy as np
import torch
from sklearn.ensemble import IsolationForest
from torch import nn

from common import Channel

MAX_EPOCHS = 20
PATIENCE = 3
MIN_DELTA = 3e-4
BATCH = 64


def _fit(model: nn.Module, x: torch.Tensor, y: torch.Tensor) -> None:
    """Adam + MSE with early stopping on the last 20% of the training windows."""
    split = int(len(x) * 0.8)
    x_train, y_train, x_val, y_val = x[:split], y[:split], x[split:], y[split:]
    optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    best, best_state, stale = float("inf"), None, 0
    for _ in range(MAX_EPOCHS):
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


def _predict(model: nn.Module, x: torch.Tensor) -> np.ndarray:
    with torch.no_grad():
        return torch.cat([model(x[i : i + 512]) for i in range(0, len(x), 512)]).numpy()


def _windows(data: np.ndarray, length: int, stride: int = 1) -> np.ndarray:
    """(n_windows, length, features) view of every `stride`-th window."""
    view = np.lib.stride_tricks.sliding_window_view(data, length, axis=0)  # (n, features, length)
    return np.ascontiguousarray(view[::stride].transpose(0, 2, 1))


# --- Candidate A: LSTM predictor (the SRS baseline, after Hundman et al. 2018) ---------------


class LstmPredictor(nn.Module):
    def __init__(self, features: int, hidden: int, horizon: int):
        super().__init__()
        self.lstm = nn.LSTM(features, hidden, num_layers=2, batch_first=True, dropout=0.3)
        self.head = nn.Linear(hidden, horizon)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1])


def lstm_predictor_errors(channel: Channel, history: int, hidden: int, horizon: int = 10, seed: int = 0):
    """Predicts the next `horizon` telemetry values from `history` steps of all features.

    The error at index t is |actual - first-step prediction|. The first `history`
    points of each split cannot be scored and get error 0.
    """
    torch.manual_seed(seed)

    def make(data: np.ndarray):
        x = _windows(data, history)[: len(data) - history - horizon + 1]
        y = _windows(data[history:, :1], horizon)[:, :, 0]
        return torch.from_numpy(x), torch.from_numpy(y)

    started = time.perf_counter()
    model = LstmPredictor(channel.train.shape[1], hidden, horizon)
    x_train, y_train = make(channel.train)
    _fit(model, x_train, y_train)
    train_seconds = time.perf_counter() - started

    def errors(data: np.ndarray, x: torch.Tensor, y: torch.Tensor) -> np.ndarray:
        out = np.zeros(len(data), dtype=np.float64)
        out[history : history + len(x)] = np.abs(_predict(model, x)[:, 0] - y[:, 0].numpy())
        return out

    x_test, y_test = make(channel.test)
    return errors(channel.train, x_train, y_train), errors(channel.test, x_test, y_test), train_seconds


# --- Candidate B: LSTM autoencoder ----------------------------------------------------------


class LstmAutoencoder(nn.Module):
    def __init__(self, features: int, hidden: int, length: int):
        super().__init__()
        self.length = length
        self.encoder = nn.LSTM(features, hidden, batch_first=True)
        self.decoder = nn.LSTM(hidden, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        _, (h, _) = self.encoder(x)
        repeated = h[-1].unsqueeze(1).repeat(1, self.length, 1)
        out, _ = self.decoder(repeated)
        return self.head(out).squeeze(-1)


def lstm_autoencoder_errors(channel: Channel, length: int, hidden: int, seed: int = 0):
    """Reconstructs the telemetry of each `length`-step window from all features.

    The error at index t is the reconstruction error of the last point of the
    window ending at t, so scoring only uses data up to t.
    """
    torch.manual_seed(seed)
    started = time.perf_counter()
    model = LstmAutoencoder(channel.train.shape[1], hidden, length)
    train_windows = torch.from_numpy(_windows(channel.train, length, stride=2))
    _fit(model, train_windows, train_windows[:, :, 0])
    train_seconds = time.perf_counter() - started

    def errors(data: np.ndarray) -> np.ndarray:
        windows = torch.from_numpy(_windows(data, length))
        out = np.zeros(len(data), dtype=np.float64)
        out[length - 1 :] = np.abs(_predict(model, windows)[:, -1] - windows[:, -1, 0].numpy())
        return out

    return errors(channel.train), errors(channel.test), train_seconds


# --- Floors: no deep learning ----------------------------------------------------------------


def rolling_zscore(values: np.ndarray, window: int) -> np.ndarray:
    """|x - rolling mean| / rolling std over the previous `window` points."""
    import pandas as pd

    series = pd.Series(values)
    mean = series.rolling(window, min_periods=window).mean().shift(1)
    std = series.rolling(window, min_periods=window).std().shift(1)
    return ((series - mean).abs() / std.replace(0, np.nan)).fillna(0).to_numpy()


def isolation_forest_scores(channel: Channel, length: int = 50, seed: int = 0):
    """Isolation Forest over raw telemetry windows; higher score = more abnormal."""
    started = time.perf_counter()
    forest = IsolationForest(n_estimators=100, random_state=seed)
    forest.fit(_windows(channel.train[:, :1], length, stride=5)[:, :, 0])
    train_seconds = time.perf_counter() - started

    def scores(data: np.ndarray) -> np.ndarray:
        out = np.zeros(len(data), dtype=np.float64)
        out[length - 1 :] = -forest.score_samples(_windows(data[:, :1], length)[:, :, 0])
        return out

    return scores(channel.train), scores(channel.test), train_seconds
