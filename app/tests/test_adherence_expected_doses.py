"""Unit tests for `expected_doses()` — the deterministic generator that
turns medication × dosing_schedule × range into a list of (due_at, pills)."""

from datetime import UTC, date, datetime

from app.services.adherence_service import expected_doses


def _med(start: str | None = "2024-01-01", paused: bool = False) -> dict:
    return {
        "id": "m1",
        "profile_id": "p1",
        "name": "Test",
        "is_paused": paused,
        "is_archived": False,
        "start_date": start,
    }


def _sched_scheduled(times=None, weekly_overrides=None, pills=1.0) -> dict:
    return {
        "id": "s1",
        "medication_id": "m1",
        "schedule_type": "scheduled",
        "times": times or [{"time": "09:00"}],
        "pills_per_dose": pills,
        "is_active": True,
        "weekly_overrides": weekly_overrides,
    }


def test_scheduled_daily_one_dose_per_day():
    out = expected_doses(
        _med(),
        _sched_scheduled(),
        range_from=date(2026, 4, 1),
        range_to=date(2026, 4, 7),
    )
    assert len(out) == 7
    assert all(p == 1.0 for _, p in out)
    assert out[0][0] == datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def test_scheduled_two_times_per_day():
    out = expected_doses(
        _med(),
        _sched_scheduled(times=[{"time": "08:00"}, {"time": "20:00"}]),
        range_from=date(2026, 4, 1),
        range_to=date(2026, 4, 3),
    )
    assert len(out) == 6
    hours = sorted({d.hour for d, _ in out})
    assert hours == [8, 20]


def test_paused_medication_returns_no_doses():
    out = expected_doses(
        _med(paused=True),
        _sched_scheduled(),
        range_from=date(2026, 4, 1),
        range_to=date(2026, 4, 7),
    )
    assert out == []


def test_inactive_schedule_returns_no_doses():
    sched = _sched_scheduled()
    sched["is_active"] = False
    out = expected_doses(
        _med(), sched,
        range_from=date(2026, 4, 1), range_to=date(2026, 4, 7),
    )
    assert out == []


def test_as_needed_returns_no_doses():
    sched = _sched_scheduled()
    sched["schedule_type"] = "as_needed"
    out = expected_doses(
        _med(), sched,
        range_from=date(2026, 4, 1), range_to=date(2026, 4, 7),
    )
    assert out == []


def test_start_date_clips_window():
    out = expected_doses(
        _med(start="2026-04-05"),
        _sched_scheduled(),
        range_from=date(2026, 4, 1),
        range_to=date(2026, 4, 7),
    )
    assert len(out) == 3
    assert out[0][0].date() == date(2026, 4, 5)


def test_weekly_overrides_zero_skips_day():
    # Calendar weekday key: 1=Sun..7=Sat. 2026-04-06 is Mon → ISO 1 → key "2".
    out = expected_doses(
        _med(),
        _sched_scheduled(weekly_overrides={"2": 0}),
        range_from=date(2026, 4, 6),
        range_to=date(2026, 4, 12),
    )
    # Mon (4/6) is skipped → 6 doses for the other 6 days.
    assert len(out) == 6


def test_weekly_overrides_custom_dose():
    # 2026-04-06 Mon → key "2". Override pills to 2.
    out = expected_doses(
        _med(),
        _sched_scheduled(weekly_overrides={"2": 2}),
        range_from=date(2026, 4, 6),
        range_to=date(2026, 4, 6),
    )
    assert len(out) == 1
    assert out[0][1] == 2.0


def test_cycle_weekly_specific_weekdays():
    # Bactrim-like: lun/mer/ven only (ISO 1, 3, 5)
    sched = {
        "id": "s2",
        "medication_id": "m1",
        "schedule_type": "cycle",
        "cycle_pattern": "weekly",
        "cycle_weekdays": [1, 3, 5],
        "cycle_start_date": "2026-04-01",
        "times": [{"time": "08:00"}],
        "pills_per_dose": 1,
        "is_active": True,
    }
    out = expected_doses(
        _med(), sched,
        range_from=date(2026, 4, 6),
        range_to=date(2026, 4, 12),
    )
    # Mon, Wed, Fri in the week 4/6 - 4/12 → 3 doses
    weekdays = sorted({d.isoweekday() for d, _ in out})
    assert weekdays == [1, 3, 5]
    assert len(out) == 3


def test_cycle_every_n():
    sched = {
        "id": "s3",
        "medication_id": "m1",
        "schedule_type": "cycle",
        "cycle_pattern": "every_n",
        "cycle_days": 3,
        "cycle_start_date": "2026-04-01",
        "times": [{"time": "10:00"}],
        "pills_per_dose": 1,
        "is_active": True,
    }
    out = expected_doses(
        _med(), sched,
        range_from=date(2026, 4, 1),
        range_to=date(2026, 4, 10),
    )
    # 4/1, 4/4, 4/7, 4/10 → 4 doses
    assert len(out) == 4
    days = sorted({d.day for d, _ in out})
    assert days == [1, 4, 7, 10]
