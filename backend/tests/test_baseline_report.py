"""render_markdown() formatting (the CLI that fits a trained model is exercised
for real in docs/results/phase2_baseline.md, not here)."""

from app.evaluation.baseline import render_markdown


def sample_report() -> dict:
    return {
        "model_id": "MDL-TEST",
        "hyperparams": {"history": 100},
        "channels_evaluated": 2,
        "eval_seconds": 1.2,
        "overall": {
            "channels": 2, "tp": 2, "fn": 1, "fp": 0,
            "precision": 1.0, "recall": 0.667, "f1": 0.8, "point_fpr": 0.01,
        },
        "by_spacecraft": {
            "SMAP": {
                "channels": 1, "tp": 1, "fn": 0, "fp": 0,
                "precision": 1.0, "recall": 1.0, "f1": 1.0, "point_fpr": 0.0,
            },
            "MSL": {
                "channels": 1, "tp": 1, "fn": 1, "fp": 0,
                "precision": 1.0, "recall": 0.5, "f1": 0.667, "point_fpr": 0.02,
            },
        },
        "per_channel": [
            {
                "chan_id": "A-1", "spacecraft": "SMAP",
                "tp": 1, "fn": 0, "fp": 0, "fp_points": 0, "normal_points": 100,
            },
            {
                "chan_id": "M-1", "spacecraft": "MSL",
                "tp": 1, "fn": 1, "fp": 0, "fp_points": 2, "normal_points": 100,
            },
        ],
    }


def test_render_markdown_includes_model_id_and_overall_metrics():
    md = render_markdown(sample_report())
    assert "MDL-TEST" in md
    assert "channels_evaluated" not in md  # rendered as prose/table, not the raw key
    assert "2 |" in md  # channel count appears in the overall table
    assert "0.800" in md  # overall F1


def test_render_markdown_lists_each_spacecraft_and_channel():
    md = render_markdown(sample_report())
    assert "SMAP" in md and "MSL" in md
    assert "A-1" in md and "M-1" in md


def test_render_markdown_is_valid_enough_markdown_tables():
    md = render_markdown(sample_report())
    table_lines = [line for line in md.splitlines() if line.startswith("|")]
    assert len(table_lines) >= 6  # header+sep+row for 3 tables minimum
    for line in table_lines:
        assert line.endswith("|")
