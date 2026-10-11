"""Baseline accuracy report (REQ-5): runs the trained detector over labelled
channels through the same StreamingThreshold the live pipeline uses, and
reports precision/recall/F1/point-FPR per channel and in aggregate.

    python -m app.evaluation.baseline                                # every trained channel
    python -m app.evaluation.baseline --model-id MDL-LSTM-100-80 --out docs/results/phase2_baseline

Writes <out>.json (machine-readable) and <out>.md (report table).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from app.core.settings import settings
from app.evaluation.metrics import aggregate, evaluate_channel
from app.pipeline.dataset import load_channel, load_labels
from app.pipeline.detect import simulate_stream
from app.pipeline.ingest import repair_series
from app.pipeline.lstm import load_channel_model, prediction_errors
from app.pipeline.train import DEFAULT_MODEL_ID


def run_baseline(model_id: str = DEFAULT_MODEL_ID, channels: list[str] | None = None) -> dict:
    artifact_dir = settings.models_dir / model_id
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    labels = load_labels()
    chan_ids = channels or manifest["channels"]
    missing = [c for c in chan_ids if c not in manifest["channels"]]
    if missing:
        raise ValueError(f"not trained in {model_id}: {missing}")

    rows = []
    started = time.perf_counter()
    for chan_id in chan_ids:
        model, stats = load_channel_model(artifact_dir, chan_id)
        test, _, _ = repair_series(load_channel(chan_id, "test").astype(np.float64))
        test = np.asarray(test, dtype=np.float32)
        errors = prediction_errors(model, test)
        flags = simulate_stream(errors, stats["value_range"])
        rows.append(evaluate_channel(flags, labels[chan_id]))
    elapsed = time.perf_counter() - started

    by_spacecraft = {}
    for spacecraft in sorted({r["spacecraft"] for r in rows}):
        by_spacecraft[spacecraft] = aggregate([r for r in rows if r["spacecraft"] == spacecraft])

    return {
        "model_id": model_id,
        "hyperparams": manifest["hyperparams"],
        "channels_evaluated": len(rows),
        "eval_seconds": round(elapsed, 1),
        "overall": aggregate(rows),
        "by_spacecraft": by_spacecraft,
        "per_channel": sorted(rows, key=lambda r: r["chan_id"]),
    }


def render_markdown(report: dict) -> str:
    o = report["overall"]
    lines = [
        "# Phase 2 baseline accuracy report",
        "",
        f"Model `{report['model_id']}` evaluated on **{report['channels_evaluated']}** labelled channels "
        f"in {report['eval_seconds']}s (REQ-5). Detector: {report['hyperparams'].get('history')}-step LSTM "
        "predictor + dynamic threshold (ADR 001), scored through the same streaming code path used live.",
        "",
        "## Overall",
        "",
        "| Channels | TP | FN | FP | Precision | Recall | F1 | Point FPR |",
        "|---|---|---|---|---|---|---|---|",
        f"| {o['channels']} | {o['tp']} | {o['fn']} | {o['fp']} | {o['precision']:.3f} | "
        f"{o['recall']:.3f} | {o['f1']:.3f} | {o['point_fpr']:.4f} |",
        "",
        "## By spacecraft",
        "",
        "| Spacecraft | Channels | TP | FN | FP | Precision | Recall | F1 | Point FPR |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for spacecraft, m in report["by_spacecraft"].items():
        lines.append(
            f"| {spacecraft} | {m['channels']} | {m['tp']} | {m['fn']} | {m['fp']} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['point_fpr']:.4f} |"
        )
    lines += [
        "",
        "## Per channel",
        "",
        "| Channel | Spacecraft | Sequences | TP | FN | FP | Point FPR |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report["per_channel"]:
        n_seq = r["tp"] + r["fn"]
        fpr = r["fp_points"] / r["normal_points"] if r["normal_points"] else 0.0
        lines.append(
            f"| {r['chan_id']} | {r['spacecraft']} | {n_seq} | {r['tp']} | "
            f"{r['fn']} | {r['fp']} | {fpr:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--channels", nargs="*")
    parser.add_argument("--out", default=None, help="output path without extension")
    args = parser.parse_args()

    report = run_baseline(args.model_id, args.channels)
    print(f"Overall: {report['overall']}")
    for spacecraft, m in report["by_spacecraft"].items():
        print(f"  {spacecraft}: {m}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
        print(f"Wrote {out}.json and {out}.md")


if __name__ == "__main__":
    main()
