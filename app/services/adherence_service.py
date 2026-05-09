"""Adherence aggregation service.

Single entry point: ``build_report``. Combines medications, dosing
schedules, dose events and measurements into a TherapyDataReport.
The same payload drives both the iOS view and the PDF rendering.

Conventions
-----------
* All timestamps are timezone-aware UTC. The DB stores datetimes as
  ISO strings; we normalise into ``datetime`` with ``UTC`` tzinfo on
  read and serialise back as ISO on write (the router does that).
* ``due_at`` of a dose_event is the **scheduled** time. ``taken_at``
  is the **actual** time. Difference > threshold ⇒ "late".
* When there is no row for an expected dose, the day is in the past
  ⇒ "skipped"; if in the future ⇒ "not_due".
* Late and partial both count toward ``rate_pct`` (the spec legend
  considers yellow as "presa", just delayed).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID

from supabase import Client

from app.schemas.adherence import (
    AdherenceReport,
    AdherenceSummary,
    BucketKind,
    DoseDisplayStatus,
    DoseNoteEntry,
    MedicationBar,
    MedicationMonthlyAggregate,
    MedicationSeries,
    MedicationSparklinePoint,
    ParameterPoint,
    ParameterSeries,
    PeriodKind,
    PeriodSpec,
)
from app.schemas.report import TherapyDataReport
from app.services._shared import assert_profile_owned
from app.services.parameters_service import get_predefined

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LATE_THRESHOLD_MIN = 30
"""Default minutes after due_at to consider a taken dose 'late'.

Overridable per dosing_schedule via the `late_threshold_minutes` column
(NULL → use this default).
"""

EXPECTED_TO_ACTUAL_TOLERANCE_MIN = 60
"""Tolerance window (± minutes) to match an expected dose with an actual
dose_event row. Doses can drift in the DB if the user retroactively
confirms — we pair to the closest event within this window."""

NOTE_SNIPPET_MAX = 140


IncludeOpt = Literal["adherence", "parameters", "notes"]


# ---------------------------------------------------------------------------
# Period & bucket resolution
# ---------------------------------------------------------------------------
def resolve_period(
    period: PeriodKind,
    *,
    today: date,
    range_from: date | None,
    range_to: date | None,
    history_floor: date | None = None,
) -> PeriodSpec:
    """Convert a period kind + optional custom dates into a concrete window."""
    if period == "7d":
        end = today
        start = end - timedelta(days=6)
    elif period == "28d":
        end = today
        start = end - timedelta(days=27)
    elif period == "12mo":
        end = today
        start = _months_back(end, 12)
    elif period == "all":
        end = today
        start = history_floor or _months_back(end, 36)
    elif period == "custom":
        if range_from is None or range_to is None:
            raise ValueError("custom period requires both `from` and `to`")
        if range_to < range_from:
            raise ValueError("`to` must be ≥ `from`")
        start, end = range_from, range_to
    else:
        raise ValueError(f"unknown period: {period}")
    return PeriodSpec(kind=period, from_=start, to=end)


def select_bucket(period: PeriodKind, *, span_days: int) -> BucketKind:
    """Pick the bucket granularity for a given period kind + span.

    Rules from the spec (refined to match reference PDFs):
        7d, 28d           → per_dose
        12mo, all         → per_month
        custom ≤ 200d     → per_dose  (covers PRO 6-month view)
        custom ≤ 365d     → per_week
        custom > 365d     → per_month
    """
    if period in ("7d", "28d"):
        return "per_dose"
    if period in ("12mo", "all"):
        return "per_month"
    # custom
    if span_days <= 200:
        return "per_dose"
    if span_days <= 365:
        return "per_week"
    return "per_month"


def _months_back(d: date, n: int) -> date:
    """Return ``d`` minus ``n`` whole months, clamped to month length."""
    year = d.year
    month = d.month - n
    while month <= 0:
        month += 12
        year -= 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, 12, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days


# ---------------------------------------------------------------------------
# Expected doses generator
# ---------------------------------------------------------------------------
def expected_doses(
    medication: dict[str, Any],
    schedule: dict[str, Any],
    *,
    range_from: date,
    range_to: date,
) -> list[tuple[datetime, float]]:
    """Generate (due_at, pills_expected) tuples for one med×schedule.

    Returns an empty list if the medication is paused, archived, the
    schedule is inactive, or the schedule type doesn't produce
    deterministic expected doses (`as_needed`).
    """
    if medication.get("is_paused") or medication.get("is_archived"):
        return []
    if not schedule.get("is_active", True):
        return []

    schedule_type = schedule.get("schedule_type", "scheduled")
    if schedule_type == "as_needed":
        return []

    start_date = _parse_date(medication.get("start_date")) or range_from
    window_start = max(range_from, start_date)
    if window_start > range_to:
        return []

    days = _generate_days(schedule, window_start, range_to)
    pills_per_dose = float(schedule.get("pills_per_dose") or 1.0)
    weekly_overrides = schedule.get("weekly_overrides") or {}
    times_list = schedule.get("times") or [{"time": "09:00"}]

    out: list[tuple[datetime, float]] = []
    for d in days:
        weekday_key = _calendar_weekday_key(d)
        if weekly_overrides:
            override = weekly_overrides.get(weekday_key)
            if override is not None:
                pills_today = float(override)
            else:
                pills_today = pills_per_dose
        else:
            pills_today = pills_per_dose
        if pills_today <= 0:
            continue
        for t in times_list:
            time_str = t.get("time") if isinstance(t, dict) else str(t)
            try:
                hh, mm = [int(p) for p in time_str.split(":")[:2]]
            except (ValueError, AttributeError):
                hh, mm = 9, 0
            due = datetime.combine(d, time(hh, mm), tzinfo=UTC)
            out.append((due, pills_today))
    return out


def _generate_days(
    schedule: dict[str, Any], start: date, end: date
) -> list[date]:
    schedule_type = schedule.get("schedule_type", "scheduled")
    if schedule_type == "scheduled":
        return _date_range(start, end)
    if schedule_type == "cycle":
        return _cycle_days(schedule, start, end)
    if schedule_type == "tapering":
        return _tapering_days(schedule, start, end)
    return _date_range(start, end)


def _date_range(start: date, end: date) -> list[date]:
    if start > end:
        return []
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _cycle_days(
    schedule: dict[str, Any], start: date, end: date
) -> list[date]:
    """Cycle pattern: weekly | biweekly | every_n.

    weekly/biweekly use cycle_weekdays (list of ints, 1=Mon..7=Sun
    matching ISO). every_n uses cycle_days as the period and
    cycle_start_date as the anchor (every N days from anchor).
    """
    pattern = schedule.get("cycle_pattern")
    weekdays = schedule.get("cycle_weekdays") or []
    cycle_days_n = schedule.get("cycle_days")
    anchor = _parse_date(schedule.get("cycle_start_date"))
    days = _date_range(start, end)
    if pattern == "weekly" and weekdays:
        return [d for d in days if d.isoweekday() in weekdays]
    if pattern == "biweekly" and weekdays and anchor:
        return [
            d for d in days
            if d.isoweekday() in weekdays
            and (((d - anchor).days // 7) % 2 == 0)
        ]
    if pattern == "every_n" and cycle_days_n and anchor:
        return [
            d for d in days
            if (d - anchor).days >= 0
            and ((d - anchor).days % cycle_days_n) == 0
        ]
    # Unknown pattern → fall back to every day (conservative)
    return days


def _tapering_days(
    schedule: dict[str, Any], start: date, end: date
) -> list[date]:
    """Tapering: produce one expected dose per day across all the steps
    that overlap the window. Step shape:
        {"days": int, "pills_per_dose": float}
    Anchored at cycle_start_date.
    """
    steps = schedule.get("tapering_steps") or []
    anchor = _parse_date(schedule.get("cycle_start_date"))
    if not steps or not anchor:
        return _date_range(start, end)
    out: list[date] = []
    cursor = anchor
    for step in steps:
        n = int(step.get("days") or 0)
        if n <= 0:
            continue
        step_end = cursor + timedelta(days=n - 1)
        for d in _date_range(max(cursor, start), min(step_end, end)):
            out.append(d)
        cursor = step_end + timedelta(days=1)
        if cursor > end:
            break
    return out


def _calendar_weekday_key(d: date) -> str:
    """Convert a Python date to the schedule weekday key.

    The schema docs say "Calendar: 1=Sun…7=Sat". Python's isoweekday()
    is 1=Mon..7=Sun. Convert.
    """
    iso = d.isoweekday()  # 1..7 = Mon..Sun
    cal = (iso % 7) + 1  # 1=Sun..7=Sat
    return str(cal)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            if "T" in value:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify(
    expected_due: datetime,
    pills_expected: float,
    event: dict[str, Any] | None,
    *,
    late_threshold_min: int,
    now: datetime,
) -> tuple[DoseDisplayStatus, datetime | None, int | None, float | None]:
    """Return (status, taken_at, delay_min, pills_taken_effective)."""
    if event is None:
        return ("not_due" if expected_due > now else "skipped", None, None, None)
    status = event.get("status")
    if status in ("missed", "skipped"):
        return ("skipped", None, None, None)
    if status in ("pending", "snoozed"):
        if now > expected_due:
            return ("skipped", None, None, None)
        return ("not_due", None, None, None)
    if status == "taken":
        taken_at = _parse_dt(event.get("taken_at")) or expected_due
        delay = int((taken_at - expected_due).total_seconds() // 60)
        pills_taken = event.get("pills_taken")
        pills_effective = float(pills_taken) if pills_taken is not None else pills_expected
        if pills_taken is not None and pills_taken < pills_expected:
            return ("partial", taken_at, delay, pills_effective)
        if delay > late_threshold_min:
            return ("late", taken_at, delay, pills_effective)
        return ("regular", taken_at, delay, pills_effective)
    return ("not_due", None, None, None)


def _match_event(
    expected_due: datetime,
    candidate_events: list[dict[str, Any]],
    used_ids: set[str],
) -> dict[str, Any] | None:
    """Find the best (closest) unused event within the tolerance window."""
    best: dict[str, Any] | None = None
    best_diff = timedelta(minutes=EXPECTED_TO_ACTUAL_TOLERANCE_MIN + 1)
    for ev in candidate_events:
        if ev["id"] in used_ids:
            continue
        ev_due = _parse_dt(ev.get("due_at"))
        if ev_due is None:
            continue
        diff = abs(ev_due - expected_due)
        if diff <= timedelta(minutes=EXPECTED_TO_ACTUAL_TOLERANCE_MIN) and diff < best_diff:
            best = ev
            best_diff = diff
    if best is not None:
        used_ids.add(best["id"])
    return best


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------
def _month_key(d: datetime | date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _week_key(d: datetime | date) -> str:
    if isinstance(d, datetime):
        d = d.date()
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def _aggregate_buckets(
    bars: list[MedicationBar], bucket: BucketKind
) -> list[MedicationMonthlyAggregate]:
    if bucket == "per_dose":
        return []
    keyfn = _month_key if bucket == "per_month" else _week_key
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"expected": 0, "taken": 0, "late": 0, "partial": 0, "skipped": 0}
    )
    for bar in bars:
        if bar.status == "not_due":
            continue
        key = keyfn(bar.due_at)
        g = grouped[key]
        g["expected"] += 1
        if bar.status == "regular":
            g["taken"] += 1
        elif bar.status == "late":
            g["late"] += 1
        elif bar.status == "partial":
            g["partial"] += 1
        elif bar.status == "skipped":
            g["skipped"] += 1
    out: list[MedicationMonthlyAggregate] = []
    for k in sorted(grouped):
        g = grouped[k]
        rate = (
            (g["taken"] + g["late"] + g["partial"]) / g["expected"] * 100.0
            if g["expected"] > 0 else 0.0
        )
        out.append(
            MedicationMonthlyAggregate(
                bucket=k,
                expected=g["expected"],
                taken=g["taken"],
                late=g["late"],
                partial=g["partial"],
                skipped=g["skipped"],
                rate_pct=round(rate, 1),
            )
        )
    return out


def _sparkline(
    bars: list[MedicationBar], range_from: date, range_to: date
) -> list[MedicationSparklinePoint]:
    """Rolling 7-day adherence rate, one point per day in the range.

    Each point is the rate over the window [d-6, d]. Days with zero
    expected doses get NaN-equivalent (we drop them — chart should
    interpolate)."""
    by_day: dict[date, list[MedicationBar]] = defaultdict(list)
    for bar in bars:
        if bar.status == "not_due":
            continue
        by_day[bar.due_at.date()].append(bar)
    out: list[MedicationSparklinePoint] = []
    cur = range_from
    while cur <= range_to:
        window_start = cur - timedelta(days=6)
        expected = 0
        taken_eq = 0
        d = window_start
        while d <= cur:
            for bar in by_day.get(d, []):
                expected += 1
                if bar.status in ("regular", "late", "partial"):
                    taken_eq += 1
            d += timedelta(days=1)
        if expected > 0:
            out.append(
                MedicationSparklinePoint(
                    date=cur,
                    rate_pct=round(taken_eq / expected * 100.0, 1),
                )
            )
        cur += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# DB fetchers
# ---------------------------------------------------------------------------
async def _fetch_medications(
    supabase: Client,
    profile_id: UUID,
    medication_ids: list[UUID] | None,
) -> list[dict[str, Any]]:
    q = supabase.table("medications").select("*").eq("profile_id", str(profile_id))
    if medication_ids:
        q = q.in_("id", [str(m) for m in medication_ids])
    return q.execute().data or []


async def _fetch_schedules(
    supabase: Client,
    medication_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not medication_ids:
        return {}
    rows = (
        supabase.table("dosing_schedules")
        .select("*")
        .in_("medication_id", medication_ids)
        .execute()
        .data
        or []
    )
    by_med: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_med[r["medication_id"]].append(r)
    return by_med


async def _fetch_dose_events(
    supabase: Client,
    medication_ids: list[str],
    range_from: date,
    range_to: date,
) -> dict[str, list[dict[str, Any]]]:
    if not medication_ids:
        return {}
    range_to_inclusive = range_to + timedelta(days=1)
    rows = (
        supabase.table("dose_events")
        .select("*")
        .in_("medication_id", medication_ids)
        .gte("due_at", range_from.isoformat())
        .lt("due_at", range_to_inclusive.isoformat())
        .execute()
        .data
        or []
    )
    by_med: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_med[r["medication_id"]].append(r)
    return by_med


async def _fetch_measurements(
    supabase: Client,
    profile_id: UUID,
    range_from: date,
    range_to: date,
    parameter_keys: list[str] | None,
) -> list[dict[str, Any]]:
    range_to_inclusive = range_to + timedelta(days=1)
    q = (
        supabase.table("measurements")
        .select("parameter_key, recorded_at, value_single, value_double_1, value_double_2, value_text")
        .eq("profile_id", str(profile_id))
        .gte("recorded_at", range_from.isoformat())
        .lt("recorded_at", range_to_inclusive.isoformat())
        .order("recorded_at")
    )
    if parameter_keys:
        q = q.in_("parameter_key", parameter_keys)
    return q.execute().data or []


async def _fetch_custom_parameter_meta(
    supabase: Client,
    profile_id: UUID,
    parameter_keys: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch metadata for non-predefined parameter_keys (custom: prefix)."""
    custom_keys = [k for k in parameter_keys if k not in {p["parameter_key"] for p in []}]
    custom_keys = [k for k in custom_keys if k.startswith("custom:")]
    if not custom_keys:
        return {}
    rows = (
        supabase.table("parameters")
        .select("parameter_key, name, unit, value_type, labels")
        .eq("profile_id", str(profile_id))
        .in_("parameter_key", custom_keys)
        .execute()
        .data
        or []
    )
    return {r["parameter_key"]: r for r in rows}


async def _fetch_dose_notes(
    supabase: Client,
    medication_ids: list[str],
    range_from: date,
    range_to: date,
) -> list[dict[str, Any]]:
    """Fetch dose_events with non-null notes + medication name."""
    if not medication_ids:
        return []
    range_to_inclusive = range_to + timedelta(days=1)
    rows = (
        supabase.table("dose_events")
        .select("medication_id, due_at, note, medications(name)")
        .in_("medication_id", medication_ids)
        .gte("due_at", range_from.isoformat())
        .lt("due_at", range_to_inclusive.isoformat())
        .not_.is_("note", "null")
        .order("due_at", desc=True)
        .execute()
        .data
        or []
    )
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def build_report(
    supabase: Client,
    user_id: UUID,
    profile_id: UUID,
    *,
    period: PeriodKind,
    range_from: date | None = None,
    range_to: date | None = None,
    medication_ids: list[UUID] | None = None,
    parameter_keys: list[str] | None = None,
    include: set[IncludeOpt] | None = None,
    now: datetime | None = None,
) -> TherapyDataReport:
    """Build the therapy-data report for the given profile."""
    await assert_profile_owned(supabase, user_id, profile_id)

    now = now or datetime.now(UTC)
    today = now.date()
    include = include or {"adherence", "parameters", "notes"}

    period_spec = resolve_period(
        period, today=today, range_from=range_from, range_to=range_to
    )
    span_days = (period_spec.to - period_spec.from_).days + 1
    bucket = select_bucket(period, span_days=span_days)

    meds = await _fetch_medications(supabase, profile_id, medication_ids)
    med_ids_str = [m["id"] for m in meds]
    schedules_by_med = await _fetch_schedules(supabase, med_ids_str)
    events_by_med = (
        await _fetch_dose_events(supabase, med_ids_str, period_spec.from_, period_spec.to)
        if "adherence" in include else {}
    )

    adherence: AdherenceReport | None = None
    if "adherence" in include:
        adherence = _build_adherence(
            meds=meds,
            schedules_by_med=schedules_by_med,
            events_by_med=events_by_med,
            period=period,
            bucket=bucket,
            range_from=period_spec.from_,
            range_to=period_spec.to,
            now=now,
        )

    parameters_payload: list[ParameterSeries] | None = None
    if "parameters" in include:
        parameters_payload = await _build_parameters(
            supabase=supabase,
            profile_id=profile_id,
            range_from=period_spec.from_,
            range_to=period_spec.to,
            parameter_keys=parameter_keys,
        )

    notes_payload: list[DoseNoteEntry] | None = None
    if "notes" in include:
        notes_rows = await _fetch_dose_notes(supabase, med_ids_str, period_spec.from_, period_spec.to)
        notes_payload = _build_notes(notes_rows, meds)

    return TherapyDataReport(
        profile_id=profile_id,
        period=period_spec,
        bucket=bucket,
        generated_at=now,
        adherence=adherence,
        parameters=parameters_payload,
        notes=notes_payload,
    )


# ---------------------------------------------------------------------------
# Internals — adherence
# ---------------------------------------------------------------------------
def _build_adherence(
    *,
    meds: list[dict[str, Any]],
    schedules_by_med: dict[str, list[dict[str, Any]]],
    events_by_med: dict[str, list[dict[str, Any]]],
    period: PeriodKind,
    bucket: BucketKind,
    range_from: date,
    range_to: date,
    now: datetime,
) -> AdherenceReport:
    series_list: list[MedicationSeries] = []
    sum_e = sum_t = sum_l = sum_p = sum_s = 0
    span_days = (range_to - range_from).days + 1
    want_sparkline = period == "all" and span_days > 365 // 2

    for med in meds:
        med_id = med["id"]
        schedules = schedules_by_med.get(med_id, [])
        events = events_by_med.get(med_id, [])
        # Generate all expected doses across all schedules
        expected_pairs: list[tuple[datetime, float, dict[str, Any]]] = []
        for sched in schedules:
            for due, pills in expected_doses(med, sched, range_from=range_from, range_to=range_to):
                expected_pairs.append((due, pills, sched))
        expected_pairs.sort(key=lambda x: x[0])

        used_ids: set[str] = set()
        bars: list[MedicationBar] = []
        e = t = l = p = sk = 0
        for due, pills, sched in expected_pairs:
            ev = _match_event(due, events, used_ids)
            late_threshold = sched.get("late_threshold_minutes") or DEFAULT_LATE_THRESHOLD_MIN
            status, taken_at, delay, pills_eff = classify(
                due, pills, ev, late_threshold_min=late_threshold, now=now
            )
            bars.append(
                MedicationBar(
                    due_at=due,
                    status=status,
                    taken_at=taken_at,
                    delay_min=delay,
                    pills_expected=pills,
                    pills_taken=pills_eff if status in ("regular", "late", "partial") else None,
                )
            )
            if status == "not_due":
                continue
            e += 1
            if status == "regular":
                t += 1
            elif status == "late":
                l += 1
            elif status == "partial":
                p += 1
            elif status == "skipped":
                sk += 1
        rate = ((t + l + p) / e * 100.0) if e > 0 else 0.0
        series = MedicationSeries(
            medication_id=UUID(med_id),
            name=med.get("name", ""),
            color=med.get("color"),
            principle=med.get("principle"),
            expected=e,
            taken=t,
            late=l,
            partial=p,
            skipped=sk,
            rate_pct=round(rate, 1),
            bars=bars if bucket == "per_dose" else None,
            monthly=_aggregate_buckets(bars, bucket) if bucket != "per_dose" else None,
            sparkline=_sparkline(bars, range_from, range_to) if want_sparkline else None,
            schedule_label=_schedule_label(schedules),
        )
        series_list.append(series)
        sum_e += e
        sum_t += t
        sum_l += l
        sum_p += p
        sum_s += sk

    overall_rate = ((sum_t + sum_l + sum_p) / sum_e * 100.0) if sum_e > 0 else 0.0
    summary = AdherenceSummary(
        expected=sum_e, taken=sum_t, late=sum_l, partial=sum_p, skipped=sum_s,
        rate_pct=round(overall_rate, 1),
    )
    return AdherenceReport(summary=summary, medications=series_list)


# ---------------------------------------------------------------------------
# Internals — parameters
# ---------------------------------------------------------------------------
async def _build_parameters(
    *,
    supabase: Client,
    profile_id: UUID,
    range_from: date,
    range_to: date,
    parameter_keys: list[str] | None,
) -> list[ParameterSeries]:
    rows = await _fetch_measurements(supabase, profile_id, range_from, range_to, parameter_keys)
    if not rows:
        return []
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_key[r["parameter_key"]].append(r)

    custom_keys = [k for k in by_key.keys() if k.startswith("custom:")]
    custom_meta = (
        await _fetch_custom_parameter_meta(supabase, profile_id, custom_keys)
        if custom_keys else {}
    )

    out: list[ParameterSeries] = []
    for key, items in by_key.items():
        meta = get_predefined(key) or custom_meta.get(key) or {
            "name": key, "unit": None, "value_type": "numericSingle", "labels": None,
        }
        value_type = meta.get("value_type", "numericSingle")
        if value_type == "text":
            continue  # not chartable
        points: list[ParameterPoint] = []
        for item in sorted(items, key=lambda r: r.get("recorded_at") or ""):
            recorded_at = _parse_dt(item.get("recorded_at"))
            if recorded_at is None:
                continue
            if value_type == "numericDouble":
                v1 = _to_float(item.get("value_double_1"))
                v2 = _to_float(item.get("value_double_2"))
            else:  # numericSingle
                v1 = _to_float(item.get("value_single"))
                v2 = None
            points.append(ParameterPoint(recorded_at=recorded_at, v1=v1, v2=v2))
        out.append(
            ParameterSeries(
                parameter_key=key,
                name=meta.get("name", key),
                unit=meta.get("unit"),
                value_type=value_type,
                labels=meta.get("labels"),
                points=points,
            )
        )
    return out


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Internals — notes
# ---------------------------------------------------------------------------
def _schedule_label(schedules: list[dict[str, Any]]) -> str | None:
    """Compose a short human-readable summary of the active schedules
    for one medication. Examples::

        "08:00"
        "08:00 · 20:00"
        "lun · mer · ven · 08:00"
        "ogni 3 giorni · 10:00"
        "al bisogno"
    """
    if not schedules:
        return None
    active = [s for s in schedules if s.get("is_active", True)]
    if not active:
        return None
    fragments: list[str] = []
    weekday_names = {
        1: "lun", 2: "mar", 3: "mer", 4: "gio",
        5: "ven", 6: "sab", 7: "dom",
    }
    for sched in active:
        stype = sched.get("schedule_type", "scheduled")
        if stype == "as_needed":
            fragments.append("al bisogno")
            continue
        # Cycle pattern → weekdays / every N
        if stype == "cycle":
            pattern = sched.get("cycle_pattern")
            if pattern in ("weekly", "biweekly"):
                wd = sched.get("cycle_weekdays") or []
                if wd:
                    fragments.append(" · ".join(weekday_names.get(d, "") for d in wd if d in weekday_names))
            elif pattern == "every_n":
                n = sched.get("cycle_days")
                if n:
                    fragments.append(f"ogni {n} giorni")
        # Times-of-day for any schedule_type that has them
        times = sched.get("times") or []
        time_strs: list[str] = []
        for t in times:
            if isinstance(t, dict) and t.get("time"):
                time_strs.append(str(t["time"]))
            elif isinstance(t, str):
                time_strs.append(t)
        if time_strs:
            fragments.append(" · ".join(time_strs))
    return " · ".join(f for f in fragments if f) or None


def _build_notes(
    rows: list[dict[str, Any]], meds: list[dict[str, Any]]
) -> list[DoseNoteEntry]:
    name_by_id = {m["id"]: m.get("name", "") for m in meds}
    out: list[DoseNoteEntry] = []
    for r in rows:
        med_id = r.get("medication_id")
        note = (r.get("note") or "").strip()
        if not note:
            continue
        snippet = note if len(note) <= NOTE_SNIPPET_MAX else note[: NOTE_SNIPPET_MAX - 1] + "…"
        med_name = (
            (r.get("medications") or {}).get("name")
            if isinstance(r.get("medications"), dict)
            else name_by_id.get(med_id, "")
        )
        due_at = _parse_dt(r.get("due_at"))
        if due_at is None:
            continue
        out.append(
            DoseNoteEntry(
                medication_id=UUID(med_id),
                medication_name=med_name or name_by_id.get(med_id, ""),
                due_at=due_at,
                snippet=snippet,
            )
        )
    return out
