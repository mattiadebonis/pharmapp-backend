"""Schema-level tests for routines (polymorphic discriminator).

DB-bound CRUD tests would require a live Supabase test instance with
seeded auth.users; we skip those here. The discriminator + roundtrip
between rows and DTOs are pure logic and worth covering.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.routine import RoutineCreateRequest
from app.schemas.routine_step import (
    EventStepData,
    MeasurementStepData,
    MedicationStepData,
    RoutineStepDTO,
    WaitStepData,
    step_data_to_columns,
)


def _profile() -> str:
    return str(uuid4())


def test_create_request_parses_all_four_step_types():
    payload = {
        "profile_id": _profile(),
        "name": "Mattina osteoporosi",
        "rrule": "FREQ=WEEKLY;BYDAY=MO",
        "start_time": "07:00",
        "steps": [
            {"step_type": "medication", "medication_id": str(uuid4()), "dose_amount": "1 compressa"},
            {"step_type": "wait", "duration_minutes": 30, "instructions": "stomaco vuoto"},
            {"step_type": "event", "event_name": "Colazione"},
            {"step_type": "measurement", "parameter_key": "glycemia"},
        ],
    }
    req = RoutineCreateRequest(**payload)
    assert [type(s).__name__ for s in req.steps] == [
        "MedicationStepData",
        "WaitStepData",
        "EventStepData",
        "MeasurementStepData",
    ]


def test_invalid_step_type_rejected():
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            steps=[{"step_type": "unknown"}],
        )


def test_missing_required_field_per_step_type():
    # medication requires medication_id
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            steps=[{"step_type": "medication"}],
        )
    # wait requires duration_minutes
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            steps=[{"step_type": "wait"}],
        )
    # event requires event_name
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            steps=[{"step_type": "event"}],
        )
    # measurement requires parameter_key
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            steps=[{"step_type": "measurement"}],
        )


def test_start_time_format_pattern():
    with pytest.raises(ValidationError):
        RoutineCreateRequest(
            profile_id=_profile(),
            name="X",
            start_time="7:00",  # missing leading zero
        )


def test_step_data_to_columns_strips_irrelevant_fields():
    med = MedicationStepData(
        step_type="medication",
        medication_id=uuid4(),
        dose_amount="1 compressa",
    )
    cols = step_data_to_columns(med)
    assert cols["step_type"] == "medication"
    assert "medication_id" in cols
    assert "duration_minutes" not in cols
    assert "event_name" not in cols
    assert "parameter_key" not in cols

    wait = WaitStepData(step_type="wait", duration_minutes=30)
    cols = step_data_to_columns(wait)
    assert cols == {"step_type": "wait", "duration_minutes": 30}


def test_step_dto_from_row_roundtrip():
    rid = uuid4()
    sid = uuid4()
    mid = uuid4()
    row = {
        "id": str(sid),
        "routine_id": str(rid),
        "position": 0,
        "step_type": "medication",
        "medication_id": str(mid),
        "dose_amount": "70 mg",
        "duration_minutes": None,
        "instructions": None,
        "event_name": None,
        "parameter_key": None,
        "created_at": "2026-04-30T07:00:00Z",
        "updated_at": "2026-04-30T07:00:00Z",
    }
    dto = RoutineStepDTO.from_row(row)
    assert isinstance(dto.data, MedicationStepData)
    assert dto.data.dose_amount == "70 mg"
    assert dto.position == 0


def test_event_step_name_length_limits():
    EventStepData(step_type="event", event_name="C")
    with pytest.raises(ValidationError):
        EventStepData(step_type="event", event_name="")
    with pytest.raises(ValidationError):
        EventStepData(step_type="event", event_name="x" * 81)
