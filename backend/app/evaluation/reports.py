"""REQ-11 / TBD-1: the persistence filter's effect, measured honestly.

Each channel's labelled test split is cut in two by index: a **tuning**
half, used only to sweep persistence_n and pick a value (closes TBD-1), and
a **reporting** half, used only to measure the with/without comparison that
goes in the report. Nothing is tuned on the data it's reported on.

    python -m app.evaluation.reports --model-id MDL-LSTM-100-80 --sweep 1 2 3 5 8 \
        --out docs/results/phase3_persistence_comparison

Writes <out>.json and <out>.md. docs/adr/003-thresholds.md records the
chosen persistence_n and why.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from app.core.settings import settings
from app.evaluation.metrics import aggregate, evaluate_channel
from app.evaluation.persistence import apply_persistence_filter
from app.pipeline.dataset import ChannelLabel, load_channel, load_labels
from app.pipeline.detect import simulate_stream
from app.pipeline.ingest import repair_series
from app.pipeline.lstm import load_channel_model, prediction_errors
from app.pipeline.train import DEFAULT_MODEL_ID

FlagsByChannel = dict[str, tuple[np.ndarray, ChannelLabel]]


def slice_label(label: ChannelLabel, lo: int, hi: int) -> ChannelLabel:
    """Keeps only anomaly sequences that start within [lo, hi), re-indexed to the slice."""
    sequences = []
    classes = []
    for (start, end), cls in zip(label.anomaly_sequences, label.anomaly_classes, strict=True):
        if lo <= start < hi:
            sequences.append((start - lo, min(end, hi - 1) - lo))
            classes.append(cls)
    return replace(label, anomaly_sequences=sequences, anomaly_classes=classes, num_values=hi - lo)


def channel_flags(chan_id: str, model_id: str) -> tuple[np.ndarray, ChannelLabel]:
    """Raw (persistence_n=1) anomaly flags for a channel's whole test split, plus its labels."""
    model, stats = load_channel_model(settings.models_dir / model_id, chan_id)
    test, _, _ = repair_series(load_channel(chan_id, "test").astype(np.float64))
    test = np.asarray(test, dtype=np.float32)
    errors = prediction_errors(model, test)
    flags = simulate_stream(errors, stats["value_range"])
    return flags, load_labels()[chan_id]


def load_all_flags(channels: list[str], model_id: str) -> FlagsByChannel:
    """Runs inference once per channel. LSTM inference over a full test split is the
    expensive step (the rest of this module is cheap array slicing), so the sweep and
    the comparison share this instead of each recomputing it from scratch."""
    return {chan_id: channel_flags(chan_id, model_id) for chan_id in channels}


def sweep_persistence(flags_by_channel: FlagsByChannel, candidates: list[int]) -> dict:
    """Metrics for each candidate persistence_n on each channel's TUNING half (first half)."""
    per_candidate: dict[int, list[dict]] = {n: [] for n in candidates}
    for flags, label in flags_by_channel.values():
        mid = len(flags) // 2
        tuning_flags, tuning_label = flags[:mid], slice_label(label, 0, mid)
        for n in candidates:
            filtered = apply_persistence_filter(tuning_flags, n)
            per_candidate[n].append(evaluate_channel(filtered, tuning_label))
    return {n: aggregate(rows) for n, rows in per_candidate.items()}


def compare_on_reporting_half(flags_by_channel: FlagsByChannel, chosen_n: int) -> dict:
    """With (chosen_n) vs. without (n=1) the filter, on each channel's REPORTING half (second half)."""
    without_rows, with_rows = [], []
    for flags, label in flags_by_channel.values():
        mid = len(flags) // 2
        reporting_flags, reporting_label = flags[mid:], slice_label(label, mid, len(flags))
        without_rows.append(evaluate_channel(reporting_flags, reporting_label))
        filtered = apply_persistence_filter(reporting_flags, chosen_n)
        with_rows.append(evaluate_channel(filtered, reporting_label))
    return {
        "chosen_persistence_n": chosen_n,
        "without_filter": aggregate(without_rows),
        "with_filter": aggregate(with_rows),
    }


def render_markdown(sweep: dict, comparison: dict, channels: list[str]) -> str:
    lines = [
        "# Phase 3 — persistence filter: tuning sweep and REQ-11 comparison",
        "",
        f"Channels: {len(channels)}. Each channel's test split is cut in half by index: "
        "the first half tunes persistence_n (this section), the second half is the held-out "
        "report (the next section). Nothing here is tuned on the data it is reported on.",
        "",
        "## Tuning sweep (first half of each channel)",
        "",
        "| persistence_n | TP | FN | FP | Precision | Recall | F1 | Point FPR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, m in sorted(sweep.items()):
        lines.append(
            f"| {n} | {m['tp']} | {m['fn']} | {m['fp']} | {m['precision']:.3f} | "
            f"{m['recall']:.3f} | {m['f1']:.3f} | {m['point_fpr']:.4f} |"
        )
    w, wo = comparison["with_filter"], comparison["without_filter"]
    lines += [
        "",
        f"**Chosen persistence_n = {comparison['chosen_persistence_n']}** (highest F1 on the tuning half).",
        "",
        "## REQ-11: with vs. without the filter (second half of each channel, held out from tuning)",
        "",
        "| | TP | FN | FP | Precision | Recall | F1 | Point FPR |",
        "|---|---|---|---|---|---|---|---|",
        f"| Without (persistence_n=1) | {wo['tp']} | {wo['fn']} | {wo['fp']} | {wo['precision']:.3f} | "
        f"{wo['recall']:.3f} | {wo['f1']:.3f} | {wo['point_fpr']:.4f} |",
        f"| With (persistence_n={comparison['chosen_persistence_n']}) | {w['tp']} | {w['fn']} | {w['fp']} | "
        f"{w['precision']:.3f} | {w['recall']:.3f} | {w['f1']:.3f} | {w['point_fpr']:.4f} |",
        "",
        f"Point FPR change: {wo['point_fpr']:.4f} -> {w['point_fpr']:.4f} "
        f"({'-' if w['point_fpr'] <= wo['point_fpr'] else '+'}"
        f"{abs(wo['point_fpr'] - w['point_fpr']):.4f}). "
        f"Recall change: {wo['recall']:.3f} -> {w['recall']:.3f} "
        f"({'-' if w['recall'] <= wo['recall'] else '+'}{abs(wo['recall'] - w['recall']):.3f}).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--channels", nargs="*")
    parser.add_argument("--sweep", type=int, nargs="*", default=[1, 2, 3, 5, 8])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    manifest = json.loads((settings.models_dir / args.model_id / "manifest.json").read_text(encoding="utf-8"))
    channels = args.channels or manifest["channels"]

    flags_by_channel = load_all_flags(channels, args.model_id)
    sweep = sweep_persistence(flags_by_channel, args.sweep)
    for n, m in sorted(sweep.items()):
        print(f"persistence_n={n}: {m}")
    chosen_n = max(sweep, key=lambda n: sweep[n]["f1"])
    print(f"Chosen persistence_n = {chosen_n}")

    comparison = compare_on_reporting_half(flags_by_channel, chosen_n)
    print("Reporting-half comparison:", comparison)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(
            json.dumps({"channels": channels, "sweep": sweep, "comparison": comparison}, indent=1),
            encoding="utf-8",
        )
        out.with_suffix(".md").write_text(render_markdown(sweep, comparison, channels), encoding="utf-8")
        print(f"Wrote {out}.json and {out}.md")


if __name__ == "__main__":
    main()
