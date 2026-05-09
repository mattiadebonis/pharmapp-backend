"""Unit tests for `classify()` — turns one (expected_due, event) into a
DoseDisplayStatus, with late threshold + partial dose handling."""

from datetime import UTC, datetime, timedelta

from app.services.adherence_service import (
    DEFAULT_LATE_THRESHOLD_MIN,
    classify,
)

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
DUE_PAST = datetime(2026, 4, 19, 8, 0, tzinfo=UTC)
DUE_FUTURE = datetime(2026, 4, 21, 8, 0, tzinfo=UTC)


def test_no_event_in_past_is_skipped():
    status, *_ = classify(DUE_PAST, 1.0, None, late_threshold_min=30, now=NOW)
    assert status == "skipped"


def test_no_event_in_future_is_not_due():
    status, *_ = classify(DUE_FUTURE, 1.0, None, late_threshold_min=30, now=NOW)
    assert status == "not_due"


def test_pending_event_in_past_is_skipped():
    ev = {"status": "pending"}
    status, *_ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "skipped"


def test_explicit_skipped_status():
    ev = {"status": "skipped"}
    status, *_ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "skipped"


def test_explicit_missed_status():
    ev = {"status": "missed"}
    status, *_ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "skipped"


def test_taken_within_threshold_is_regular():
    ev = {"status": "taken", "taken_at": (DUE_PAST + timedelta(minutes=10)).isoformat()}
    status, _, delay, _ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "regular"
    assert delay == 10


def test_taken_after_threshold_is_late():
    ev = {"status": "taken", "taken_at": (DUE_PAST + timedelta(minutes=45)).isoformat()}
    status, _, delay, _ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "late"
    assert delay == 45


def test_taken_partial_pills_marked_partial_even_if_on_time():
    ev = {
        "status": "taken",
        "taken_at": DUE_PAST.isoformat(),
        "pills_taken": 0.5,
    }
    status, _, _, pills = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "partial"
    assert pills == 0.5


def test_full_pills_explicit_is_regular():
    ev = {
        "status": "taken",
        "taken_at": DUE_PAST.isoformat(),
        "pills_taken": 1.0,
    }
    status, *_ = classify(DUE_PAST, 1.0, ev, late_threshold_min=30, now=NOW)
    assert status == "regular"


def test_default_threshold_constant_is_30_min():
    assert DEFAULT_LATE_THRESHOLD_MIN == 30


def test_per_schedule_threshold_overrides_default():
    # 20 min is over the 5-min insulin threshold → late
    ev = {"status": "taken", "taken_at": (DUE_PAST + timedelta(minutes=20)).isoformat()}
    status, *_ = classify(DUE_PAST, 1.0, ev, late_threshold_min=5, now=NOW)
    assert status == "late"
