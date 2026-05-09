"""Deterministic personas for adherence tests.

Anchor date: 2026-04-20 — matches the mockup screenshots in the spec.
Each persona returns a dict shaped like a Supabase seed::

    {"profiles": [...], "medications": [...], "dosing_schedules": [...],
     "dose_events": [...], "measurements": [...], "parameters": [...]}

The User UUID owning everything is `USER_ID`. All entities for the
persona reference that user via the profile chain.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

ANCHOR_DATE = date(2026, 4, 20)
USER_ID = UUID("00000000-0000-0000-0000-000000000001")
ANOTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000099")  # for ownership tests

# Stable persona profile UUIDs (used by tests & shim — must match the
# string `id` of each profile row). Picked to be obvious under a
# debugger; not random.
MATTIA_PROFILE_ID = "11111111-1111-1111-1111-111111111111"
MARCO_PROFILE_ID = "22222222-2222-2222-2222-222222222222"
ROBERTO_PROFILE_ID = "33333333-3333-3333-3333-333333333333"


def _med_uuid(slug: str) -> str:
    """Deterministic UUID-shaped id for a medication (so the FastAPI
    UUID path validator accepts it). Encodes the slug into the hex
    body so debugging tells you which med it is."""
    body = slug.encode("utf-8").hex().ljust(32, "0")[:32]
    return f"{body[:8]}-{body[8:12]}-{body[12:16]}-{body[16:20]}-{body[20:32]}"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _at(d: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(d, time(hh, mm), tzinfo=UTC).isoformat()


def _generate_events(
    *,
    medication_id: str,
    schedule_id: str,
    profile_id: str,
    times: list[tuple[int, int]],
    days_back: int,
    skip_dates: set[date] | None = None,
    late_dates: dict[date, int] | None = None,
    note_dates: dict[date, str] | None = None,
    weekdays_only: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Generate dose_events for each (day × time) pair going back N days."""
    skip_dates = skip_dates or set()
    late_dates = late_dates or {}
    note_dates = note_dates or {}
    out: list[dict[str, Any]] = []
    counter = 0
    for offset in range(days_back):
        day = ANCHOR_DATE - timedelta(days=days_back - 1 - offset)
        if weekdays_only and day.isoweekday() not in weekdays_only:
            continue
        for hh, mm in times:
            counter += 1
            due_iso = _at(day, hh, mm)
            ev_id = f"{medication_id}-ev-{counter}"
            event: dict[str, Any] = {
                "id": ev_id,
                "medication_id": medication_id,
                "dosing_schedule_id": schedule_id,
                "profile_id": profile_id,
                "due_at": due_iso,
                "status": "taken",
                "taken_at": due_iso,
                "snooze_count": 0,
                "actor_user_id": str(USER_ID),
                "note": note_dates.get(day),
                "pills_taken": None,
                "auto_registered_at": None,
                "user_corrected_at": None,
                "actor_device_id": None,
                "created_at": due_iso,
                "updated_at": due_iso,
            }
            if day in skip_dates:
                event["status"] = "skipped"
                event["taken_at"] = None
            elif day in late_dates:
                delay_min = late_dates[day]
                taken_dt = datetime.combine(day, time(hh, mm), tzinfo=UTC) + timedelta(
                    minutes=delay_min
                )
                event["taken_at"] = taken_dt.isoformat()
            out.append(event)
    return out


# ---------------------------------------------------------------------------
# Mattia · 2 farmaci (Eutirox, Vitamina D), no measurements
# ---------------------------------------------------------------------------
def mattia_persona() -> dict[str, list[dict[str, Any]]]:
    profile_id = MATTIA_PROFILE_ID
    profile = {
        "id": profile_id,
        "user_id": str(USER_ID),
        "display_name": "Mattia Calcagni",
        "profile_type": "own",
        "birth_date": "1988-03-12",
    }

    eutirox_id = _med_uuid("med-eutirox")
    vitd_id = _med_uuid("med-vitd")
    sched_eutirox_id = _med_uuid("sched-eutirox")
    sched_vitd_id = _med_uuid("sched-vitd")

    eutirox = {
        "id": eutirox_id,
        "profile_id": profile_id,
        "name": "Eutirox",
        "principle": "Levotiroxina 50 mcg",
        "color": "#9DBFE8",
        "category": "farmaco",
        "is_paused": False,
        "is_archived": False,
        "start_date": "2025-12-01",
    }
    vitd = {
        "id": vitd_id,
        "profile_id": profile_id,
        "name": "Vitamina D",
        "principle": "Colecalciferolo 1000 UI",
        "color": "#F0CB6C",
        "category": "integratore",
        "is_paused": False,
        "is_archived": False,
        "start_date": "2025-12-01",
    }

    sched_eutirox = {
        "id": sched_eutirox_id,
        "medication_id": eutirox_id,
        "schedule_type": "scheduled",
        "times": [{"time": "06:30"}],
        "pills_per_dose": 1,
        "is_active": True,
        "late_threshold_minutes": None,
    }
    sched_vitd = {
        "id": sched_vitd_id,
        "medication_id": vitd_id,
        "schedule_type": "scheduled",
        "times": [{"time": "12:00"}],
        "pills_per_dose": 1,
        "is_active": True,
        "late_threshold_minutes": None,
    }

    eutirox_events = _generate_events(
        medication_id=eutirox_id,
        schedule_id=sched_eutirox_id,
        profile_id=profile_id,
        times=[(6, 30)],
        days_back=28,
        skip_dates={ANCHOR_DATE - timedelta(days=19)},  # 1 saltata
    )
    vitd_events = _generate_events(
        medication_id=vitd_id,
        schedule_id=sched_vitd_id,
        profile_id=profile_id,
        times=[(12, 0)],
        days_back=28,
        skip_dates={
            ANCHOR_DATE - timedelta(days=20),
            ANCHOR_DATE - timedelta(days=8),
        },  # 2 saltate
        note_dates={
            ANCHOR_DATE - timedelta(days=8): "Forte mal di stomaco la sera, saltato",
        },
    )

    return {
        "profiles": [profile],
        "medications": [eutirox, vitd],
        "dosing_schedules": [sched_eutirox, sched_vitd],
        "dose_events": eutirox_events + vitd_events,
        "measurements": [],
        "parameters": [],
    }


# ---------------------------------------------------------------------------
# Marco · 5 farmaci, pressione 3×/sett
# ---------------------------------------------------------------------------
def marco_persona() -> dict[str, list[dict[str, Any]]]:
    profile_id = MARCO_PROFILE_ID
    profile = {
        "id": profile_id,
        "user_id": str(USER_ID),
        "display_name": "Marco Rossi",
        "profile_type": "own",
        "birth_date": "1962-07-21",
    }

    meds_data = [
        ("med-ramipril", "Ramipril", "Ramipril 5 mg", [(8, 0)], 0),
        ("med-atorva", "Atorvastatina", "Atorvastatina 20 mg", [(22, 0)], 1),
        ("med-metformina", "Metformina", "Metformina 850 mg", [(8, 0), (20, 0)], 2),
        ("med-bisoprololo", "Bisoprololo", "Bisoprololo 2,5 mg", [(8, 0)], 0),
        ("med-omeprazolo", "Omeprazolo", "Omeprazolo 20 mg", [(7, 30)], 1),
    ]
    medications = []
    schedules = []
    events: list[dict[str, Any]] = []
    for slug, name, principle, times_list, n_skips in meds_data:
        med_id = _med_uuid(slug)
        sched_id = _med_uuid(f"sched-{slug}")
        medications.append({
            "id": med_id, "profile_id": profile_id, "name": name,
            "principle": principle, "color": "#9DBFE8",
            "category": "farmaco", "is_paused": False, "is_archived": False,
            "start_date": "2025-09-01",
        })
        schedules.append({
            "id": sched_id, "medication_id": med_id,
            "schedule_type": "scheduled", "times": [{"time": f"{h:02d}:{m:02d}"} for h, m in times_list],
            "pills_per_dose": 1, "is_active": True, "late_threshold_minutes": None,
        })
        skip_set = {ANCHOR_DATE - timedelta(days=14 + i * 5) for i in range(n_skips)}
        notes = {}
        if slug == "med-atorva":
            notes[ANCHOR_DATE - timedelta(days=15)] = "Mal di stomaco, salto"
            notes[ANCHOR_DATE - timedelta(days=1)] = "Cena fuori, presa alle 22"
        events.extend(_generate_events(
            medication_id=med_id, schedule_id=sched_id, profile_id=profile_id,
            times=times_list, days_back=28,
            skip_dates=skip_set, note_dates=notes,
        ))

    measurements = []
    # blood_pressure 3×/sett (Mon, Wed, Fri) for last 12 weeks
    for off in range(0, 28):
        d = ANCHOR_DATE - timedelta(days=off)
        if d.isoweekday() in (1, 3, 5):
            v1 = 130 + (off % 5) * 2
            v2 = 80 + (off % 4)
            measurements.append({
                "id": f"meas-bp-{off}",
                "profile_id": profile_id,
                "parameter_key": "blood_pressure",
                "value_single": None,
                "value_double_1": v1,
                "value_double_2": v2,
                "value_text": None,
                "recorded_at": _at(d, 7, 0),
                "note": None,
                "routine_id": None,
                "routine_step_id": None,
                "created_at": _at(d, 7, 0),
            })

    return {
        "profiles": [profile],
        "medications": medications,
        "dosing_schedules": schedules,
        "dose_events": events,
        "measurements": measurements,
        "parameters": [],
    }


# ---------------------------------------------------------------------------
# Roberto · 6 farmaci immunosuppressed, pressione/peso/creatinina
# ---------------------------------------------------------------------------
def roberto_persona(*, days_back: int = 28) -> dict[str, list[dict[str, Any]]]:
    profile_id = ROBERTO_PROFILE_ID
    profile = {
        "id": profile_id,
        "user_id": str(USER_ID),
        "display_name": "Roberto Conti",
        "profile_type": "own",
        "birth_date": "1971-11-03",
    }

    meds_data = [
        ("med-tacro", "Tacrolimus", "Tacrolimus 2 mg", [(8, 0), (20, 0)], None),
        ("med-mico", "Micofenolato", "Micofenolato 1000 mg", [(8, 0), (20, 0)], None),
        ("med-pred", "Prednisone", "Prednisone 5 mg", [(8, 0)], None),
        ("med-ramipril2", "Ramipril", "Ramipril 5 mg", [(8, 0)], None),
        ("med-atorva2", "Atorvastatina", "Atorvastatina 10 mg", [(22, 0)], None),
        ("med-bactrim", "Bactrim", "Sulfametoxazolo+Trimetoprim 480 mg", [(8, 0)], [1, 3, 5]),
    ]
    medications = []
    schedules = []
    events: list[dict[str, Any]] = []
    skip_seed = {
        "med-tacro": [-12, -7],
        "med-mico": [-15],
        "med-pred": [-9],
        "med-ramipril2": [-3],
        "med-atorva2": [-18],
        "med-bactrim": [],
    }
    for slug, name, principle, times_list, weekdays in meds_data:
        med_id = _med_uuid(slug)
        sched_id = _med_uuid(f"sched-{slug}")
        medications.append({
            "id": med_id, "profile_id": profile_id, "name": name,
            "principle": principle, "color": "#A8D9C4",
            "category": "farmaco", "is_paused": False, "is_archived": False,
            "start_date": "2025-08-01",
        })
        if weekdays:
            schedules.append({
                "id": sched_id, "medication_id": med_id,
                "schedule_type": "cycle",
                "cycle_pattern": "weekly",
                "cycle_weekdays": weekdays,
                "cycle_start_date": "2025-08-01",
                "times": [{"time": f"{h:02d}:{m:02d}"} for h, m in times_list],
                "pills_per_dose": 1, "is_active": True,
                "late_threshold_minutes": None,
            })
        else:
            schedules.append({
                "id": sched_id, "medication_id": med_id,
                "schedule_type": "scheduled",
                "times": [{"time": f"{h:02d}:{m:02d}"} for h, m in times_list],
                "pills_per_dose": 1, "is_active": True,
                "late_threshold_minutes": None,
            })
        skip_offsets = skip_seed.get(slug, [])
        skip_set = {ANCHOR_DATE + timedelta(days=o) for o in skip_offsets}
        events.extend(_generate_events(
            medication_id=med_id, schedule_id=sched_id, profile_id=profile_id,
            times=times_list, days_back=days_back,
            skip_dates=skip_set,
            weekdays_only=weekdays,
        ))

    measurements = []
    # pressure 1×/day
    for off in range(0, days_back):
        d = ANCHOR_DATE - timedelta(days=off)
        v1 = 128 + (off % 4)
        v2 = 78 + (off % 3)
        measurements.append({
            "id": f"meas-bp2-{off}",
            "profile_id": profile_id,
            "parameter_key": "blood_pressure",
            "value_single": None,
            "value_double_1": v1, "value_double_2": v2,
            "value_text": None,
            "recorded_at": _at(d, 7, 0),
            "note": None, "routine_id": None, "routine_step_id": None,
            "created_at": _at(d, 7, 0),
        })
    # weight 1×/sett (Mon)
    counter = 0
    for off in range(0, days_back):
        d = ANCHOR_DATE - timedelta(days=off)
        if d.isoweekday() == 1:
            counter += 1
            measurements.append({
                "id": f"meas-w-{counter}",
                "profile_id": profile_id,
                "parameter_key": "weight",
                "value_single": 76.2 + counter * 0.1,
                "value_double_1": None, "value_double_2": None,
                "value_text": None,
                "recorded_at": _at(d, 7, 30),
                "note": None, "routine_id": None, "routine_step_id": None,
                "created_at": _at(d, 7, 30),
            })

    # creatinine 1×/sett (Wed)
    counter = 0
    for off in range(0, days_back):
        d = ANCHOR_DATE - timedelta(days=off)
        if d.isoweekday() == 3:
            counter += 1
            measurements.append({
                "id": f"meas-cr-{counter}",
                "profile_id": profile_id,
                "parameter_key": "custom:creatinine",
                "value_single": 1.3,
                "value_double_1": None, "value_double_2": None,
                "value_text": None,
                "recorded_at": _at(d, 8, 0),
                "note": None, "routine_id": None, "routine_step_id": None,
                "created_at": _at(d, 8, 0),
            })

    parameters = [
        {
            "id": "param-creatinine",
            "profile_id": profile_id,
            "parameter_key": "custom:creatinine",
            "name": "Creatininemia",
            "unit": "mg/dL",
            "value_type": "numericSingle",
            "labels": None,
            "decimals": 2,
        },
    ]

    return {
        "profiles": [profile],
        "medications": medications,
        "dosing_schedules": schedules,
        "dose_events": events,
        "measurements": measurements,
        "parameters": parameters,
    }


def roberto_pro_persona() -> dict[str, list[dict[str, Any]]]:
    """Roberto with 6 mesi (180 giorni) of history — long view test."""
    return roberto_persona(days_back=180)


# ---------------------------------------------------------------------------
# Aggregate a multi-persona seed for the FakeSupabase shim
# ---------------------------------------------------------------------------
def merge_seeds(*seeds: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for seed in seeds:
        for table, rows in seed.items():
            out.setdefault(table, []).extend(rows)
    return out


def all_personas_seed() -> dict[str, list[dict[str, Any]]]:
    return merge_seeds(
        mattia_persona(),
        marco_persona(),
        roberto_persona(),
    )
