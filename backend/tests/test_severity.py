"""REQ-9: severity_index = norm(score) x g(persistence) -> band + risk_level."""

import pytest

from app.models import SeverityLevel
from app.pipeline.explain.severity import compute_severity, risk_label


@pytest.mark.parametrize(
    "risk_level,expected",
    [(1, SeverityLevel.LOW), (3, SeverityLevel.LOW), (4, SeverityLevel.MEDIUM), (5, SeverityLevel.MEDIUM),
     (6, SeverityLevel.HIGH), (8, SeverityLevel.HIGH),
     (9, SeverityLevel.CRITICAL), (10, SeverityLevel.CRITICAL)],
)
def test_risk_label_bands(risk_level, expected):
    assert risk_label(risk_level) == expected


def test_compute_severity_risk_level_is_always_in_range():
    for score in [0.5, 1.0, 1.5, 3.0, 100.0]:
        for persistence in [0, 1, 5, 50]:
            _, risk_level = compute_severity(score, persistence, severity_threshold=0.5)
            assert 1 <= risk_level <= 10


def test_compute_severity_increases_with_score():
    _, low = compute_severity(score=1.1, persistence_count=5, severity_threshold=0.5)
    _, high = compute_severity(score=3.0, persistence_count=5, severity_threshold=0.5)
    assert high > low


def test_compute_severity_increases_with_persistence():
    _, low = compute_severity(score=2.0, persistence_count=1, severity_threshold=0.5)
    _, high = compute_severity(score=2.0, persistence_count=10, severity_threshold=0.5)
    assert high >= low


def test_compute_severity_fresh_detection_at_threshold_score_is_low():
    """A detection that just crossed the threshold (score ~= 1) and has not
    persisted should not already read as severe."""
    severity_level, risk_level = compute_severity(score=1.01, persistence_count=1, severity_threshold=0.5)
    assert severity_level == SeverityLevel.LOW
    assert risk_level <= 3


def test_compute_severity_sustained_strong_anomaly_is_critical():
    severity_level, risk_level = compute_severity(score=5.0, persistence_count=10, severity_threshold=0.5)
    assert severity_level == SeverityLevel.CRITICAL
    assert risk_level == 10


def test_compute_severity_lower_threshold_is_more_sensitive():
    """A lower severity_threshold (more sensitive satellite) reaches the same
    band sooner for the same raw score/persistence."""
    _, sensitive = compute_severity(score=1.5, persistence_count=3, severity_threshold=0.2)
    _, lenient = compute_severity(score=1.5, persistence_count=3, severity_threshold=0.9)
    assert sensitive >= lenient


def test_compute_severity_never_raises_on_extreme_inputs():
    compute_severity(score=0.0, persistence_count=0, severity_threshold=0.0)
    compute_severity(score=1e6, persistence_count=1_000_000, severity_threshold=1e6)
