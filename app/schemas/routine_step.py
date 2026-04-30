"""Polymorphic schema for routine steps.

A routine_step has 4 shapes (medication / wait / event / measurement).
We expose a discriminated `RoutineStepData` union so callers can submit
a single type-safe payload, and the FastAPI/Pydantic v2 validator picks
the right branch from the `step_type` field.
"""

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Step data variants (discriminated by step_type)
# ---------------------------------------------------------------------------


class MedicationStepData(PharmaBaseModel):
    """Medication step. References an existing medication and carries a
    free-text dose label (e.g. "1 compressa", "35 mg")."""

    step_type: Literal["medication"]
    medication_id: UUID
    dose_amount: str | None = Field(None, max_length=80)


class WaitStepData(PharmaBaseModel):
    """Measured wait between two steps. Duration in minutes plus optional
    clinical instruction."""

    step_type: Literal["wait"]
    duration_minutes: int = Field(ge=1, le=24 * 60)
    instructions: str | None = Field(None, max_length=200)


class EventStepData(PharmaBaseModel):
    """Daily-life action the patient confirms (Colazione, Doccia, …)."""

    step_type: Literal["event"]
    event_name: str = Field(min_length=1, max_length=80)


class MeasurementStepData(PharmaBaseModel):
    """Measurement step (glycemia, blood_pressure, weight, …). The
    `parameter_key` is either a predefined string (`'glycemia'`) or a
    custom one in the format `'custom:<uuid>'`."""

    step_type: Literal["measurement"]
    parameter_key: str = Field(min_length=1, max_length=80)


RoutineStepData = Annotated[
    Union[MedicationStepData, WaitStepData, EventStepData, MeasurementStepData],
    Field(discriminator="step_type"),
]


# ---------------------------------------------------------------------------
# Persisted step DTO (returned to the client)
# ---------------------------------------------------------------------------


class RoutineStepDTO(PharmaBaseModel):
    """Step as stored in the DB. The `data` envelope normalizes the four
    legacy column shapes (medication_id / duration_minutes / event_name /
    parameter_key) into a single discriminated union."""

    id: UUID
    routine_id: UUID
    position: int
    data: RoutineStepData
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> "RoutineStepDTO":
        """Build a DTO from a raw `routine_steps` row."""
        return cls(
            id=row["id"],
            routine_id=row["routine_id"],
            position=row["position"],
            data=_step_data_from_row(row),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _step_data_from_row(row: dict) -> RoutineStepData:
    """Translate a flat DB row into the discriminated `RoutineStepData`."""
    step_type = row["step_type"]
    if step_type == "medication":
        return MedicationStepData(
            step_type="medication",
            medication_id=row["medication_id"],
            dose_amount=row.get("dose_amount"),
        )
    if step_type == "wait":
        return WaitStepData(
            step_type="wait",
            duration_minutes=row["duration_minutes"],
            instructions=row.get("instructions"),
        )
    if step_type == "event":
        return EventStepData(
            step_type="event",
            event_name=row["event_name"],
        )
    if step_type == "measurement":
        return MeasurementStepData(
            step_type="measurement",
            parameter_key=row["parameter_key"],
        )
    raise ValueError(f"Unknown step_type: {step_type}")


def step_data_to_columns(data: RoutineStepData) -> dict:
    """Translate a discriminated `RoutineStepData` into the flat column
    dict used by the DB. Strips fields that don't belong to the chosen
    step_type."""
    if isinstance(data, MedicationStepData):
        out: dict = {
            "step_type": "medication",
            "medication_id": str(data.medication_id),
        }
        if data.dose_amount:
            out["dose_amount"] = data.dose_amount
        return out
    if isinstance(data, WaitStepData):
        out = {
            "step_type": "wait",
            "duration_minutes": data.duration_minutes,
        }
        if data.instructions:
            out["instructions"] = data.instructions
        return out
    if isinstance(data, EventStepData):
        return {"step_type": "event", "event_name": data.event_name}
    if isinstance(data, MeasurementStepData):
        return {"step_type": "measurement", "parameter_key": data.parameter_key}
    raise ValueError(f"Unsupported step data: {type(data).__name__}")
