"""Every state and transition in the Exp 5 state diagram (ARCHITECTURE.md 5.4)."""

from app.pipeline.lifecycle import DetectionLifecycle, OutcomeKind, State


def path(result) -> list[tuple[str, str, str]]:
    return [(t.source, t.dest, t.event) for t in result.transitions]


# --- clean-data / normal path (transitions 1, 2, 5, 6, 7) ------------------------------------


def test_normal_window_returns_to_idle():
    lc = DetectionLifecycle()
    result = lc.process_window(malformed=False, score=0.2, threshold=1.0)
    assert result.kind == OutcomeKind.NORMAL
    assert lc.state == State.IDLE
    assert path(result) == [
        (State.IDLE, State.INGESTING, "newWindowArrives"),
        (State.INGESTING, State.SCORING, "validated"),
        (State.SCORING, State.NORMAL, "scored"),
        (State.NORMAL, State.IDLE, "windowComplete"),
    ]


def test_score_at_exactly_threshold_counts_as_normal():
    lc = DetectionLifecycle()
    result = lc.process_window(malformed=False, score=1.0, threshold=1.0)
    assert result.kind == OutcomeKind.NORMAL


# --- malformed-data path (transitions 3, 4) ---------------------------------------------------


def test_malformed_window_goes_to_data_error_and_back():
    lc = DetectionLifecycle()
    result = lc.process_window(malformed=True, score=0.0, threshold=1.0)
    assert result.kind == OutcomeKind.SKIPPED
    assert lc.state == State.IDLE
    assert path(result) == [
        (State.IDLE, State.INGESTING, "newWindowArrives"),
        (State.INGESTING, State.DATA_ERROR, "validated"),
        (State.DATA_ERROR, State.IDLE, "recovered"),
    ]


def test_malformed_does_not_affect_persistence_count():
    lc = DetectionLifecycle(persistence_n=3)
    lc.process_window(malformed=False, score=2.0, threshold=1.0)
    assert lc.consecutive == 1
    lc.process_window(malformed=True, score=0.0, threshold=1.0)
    assert lc.consecutive == 1  # unchanged by the malformed window


# --- anomalous / suppressed path (transitions 8, 9, 10, 12) ---------------------------------


def test_anomalous_window_below_persistence_is_suppressed():
    lc = DetectionLifecycle(persistence_n=3)
    result = lc.process_window(malformed=False, score=2.0, threshold=1.0)
    assert result.kind == OutcomeKind.SUPPRESSED
    assert result.persistence_count == 1
    assert lc.state == State.IDLE
    assert path(result) == [
        (State.IDLE, State.INGESTING, "newWindowArrives"),
        (State.INGESTING, State.SCORING, "validated"),
        (State.SCORING, State.ANOMALOUS, "scored"),
        (State.ANOMALOUS, State.FILTERING, "checkPersistence"),
        (State.FILTERING, State.SUPPRESSED, "evaluated"),
        (State.SUPPRESSED, State.IDLE, "logged"),
    ]


def test_persistence_count_increments_across_consecutive_anomalous_windows():
    lc = DetectionLifecycle(persistence_n=5)
    for expected in (1, 2, 3, 4):
        result = lc.process_window(malformed=False, score=2.0, threshold=1.0)
        assert result.kind == OutcomeKind.SUPPRESSED
        assert result.persistence_count == expected


def test_normal_window_resets_persistence_count():
    lc = DetectionLifecycle(persistence_n=5)
    lc.process_window(malformed=False, score=2.0, threshold=1.0)
    lc.process_window(malformed=False, score=2.0, threshold=1.0)
    assert lc.consecutive == 2
    lc.process_window(malformed=False, score=0.1, threshold=1.0)
    assert lc.consecutive == 0


# --- confirmed / alert path (transitions 11, 13-16, 19) --------------------------------------


def test_anomalous_window_at_persistence_threshold_is_confirmed_and_raises_alert():
    lc = DetectionLifecycle(persistence_n=1)
    result = lc.process_window(malformed=False, score=2.0, threshold=1.0)
    assert result.kind == OutcomeKind.CONFIRMED
    assert lc.state == State.IDLE  # handed off, transition 19
    assert path(result) == [
        (State.IDLE, State.INGESTING, "newWindowArrives"),
        (State.INGESTING, State.SCORING, "validated"),
        (State.SCORING, State.ANOMALOUS, "scored"),
        (State.ANOMALOUS, State.FILTERING, "checkPersistence"),
        (State.FILTERING, State.CONFIRMED, "evaluated"),
        (State.CONFIRMED, State.ATTRIBUTING, "confirmed"),
        (State.ATTRIBUTING, State.SCORING_SEVERITY, "channelsAttributed"),
        (State.SCORING_SEVERITY, State.ALERT_RAISED, "severityComputed"),
        (State.ALERT_RAISED, State.IDLE, "handedOff"),
    ]


def test_wait_for_ack_stops_at_alert_raised_instead_of_handing_off():
    lc = DetectionLifecycle(persistence_n=1)
    result = lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    assert lc.state == State.ALERT_RAISED
    assert result.kind == OutcomeKind.CONFIRMED


def test_reaching_persistence_threshold_after_several_windows():
    lc = DetectionLifecycle(persistence_n=3)
    first = lc.process_window(malformed=False, score=2.0, threshold=1.0)
    second = lc.process_window(malformed=False, score=2.0, threshold=1.0)
    third = lc.process_window(malformed=False, score=2.0, threshold=1.0)
    assert [first.kind, second.kind, third.kind] == [
        OutcomeKind.SUPPRESSED,
        OutcomeKind.SUPPRESSED,
        OutcomeKind.CONFIRMED,
    ]
    assert third.persistence_count == 3


# --- acknowledge / resolve / stop path (transitions 17, 18) ----------------------------------


def test_user_ack_moves_alert_raised_to_acknowledged():
    lc = DetectionLifecycle(persistence_n=1)
    lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    result = lc.user_ack()
    assert result.kind == OutcomeKind.ACKNOWLEDGED
    assert lc.state == State.ACKNOWLEDGED
    assert path(result) == [(State.ALERT_RAISED, State.ACKNOWLEDGED, "userAck")]


def test_resolve_while_monitoring_active_returns_to_idle():
    lc = DetectionLifecycle(persistence_n=1)
    lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    lc.user_ack()
    result = lc.resolve(monitoring_active=True)
    assert result.kind == OutcomeKind.RESOLVED
    assert lc.state == State.IDLE
    assert path(result) == [
        (State.ACKNOWLEDGED, State.RESOLVED, "logDetection"),
        (State.RESOLVED, State.IDLE, "monitoringActive"),
    ]


def test_resolve_while_monitoring_stopped_reaches_final_state():
    lc = DetectionLifecycle(persistence_n=1)
    lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    lc.user_ack()
    result = lc.resolve(monitoring_active=False)
    assert result.kind == OutcomeKind.STOPPED
    assert lc.state == State.STOPPED
    assert path(result) == [
        (State.ACKNOWLEDGED, State.RESOLVED, "logDetection"),
        (State.RESOLVED, State.STOPPED, "monitoringStopped"),
    ]


# --- guard violations: every public method raises outside its required state -----------------


def test_process_window_requires_idle():
    lc = DetectionLifecycle(persistence_n=1)
    lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    import pytest

    with pytest.raises(RuntimeError):
        lc.process_window(malformed=False, score=0.1, threshold=1.0)


def test_user_ack_requires_alert_raised():
    import pytest

    lc = DetectionLifecycle()
    with pytest.raises(RuntimeError):
        lc.user_ack()


def test_resolve_requires_acknowledged():
    import pytest

    lc = DetectionLifecycle(persistence_n=1)
    lc.process_window(malformed=False, score=2.0, threshold=1.0, wait_for_ack=True)
    with pytest.raises(RuntimeError):
        lc.resolve()
