"""Measurements service.

Validates the polymorphic value payload against the parameter's value_type
(predefined or custom). Owns retrieval/filter/CRUD.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.schemas.measurement import (
    MeasurementCreateRequest,
    MeasurementUpdateRequest,
)
from app.services._shared import (
    _not_found,
    assert_profile_owned,
    log_activity,
)
from app.services.parameters_service import (
    PREDEFINED_KEYS,
    get_predefined,
)


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": {"code": "validation_error", "message": message}},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_parameter(
    supabase: Client, profile_id: UUID, parameter_key: str
) -> dict[str, Any]:
    """Return parameter metadata for the given key, predefined or custom.
    Raises 404 if not found / not owned."""
    if parameter_key in PREDEFINED_KEYS:
        meta = get_predefined(parameter_key)
        if meta is None:
            raise _not_found("Parameter not found")
        return meta
    res = (
        supabase.table("parameters")
        .select("*")
        .eq("profile_id", str(profile_id))
        .eq("parameter_key", parameter_key)
        .execute()
    )
    if not res.data:
        raise _not_found("Parameter not found")
    return res.data[0]


def _validate_payload_against_type(
    value_type: str,
    *,
    value_single: float | None,
    value_double_1: float | None,
    value_double_2: float | None,
    value_text: str | None,
) -> None:
    if value_type == "numericSingle":
        if value_single is None:
            raise _validation_error("value_single is required for numericSingle")
        if (
            value_double_1 is not None
            or value_double_2 is not None
            or value_text is not None
        ):
            raise _validation_error(
                "Only value_single is allowed for numericSingle"
            )
        return
    if value_type == "numericDouble":
        if value_double_1 is None or value_double_2 is None:
            raise _validation_error(
                "value_double_1 and value_double_2 are required for numericDouble"
            )
        if value_single is not None or value_text is not None:
            raise _validation_error(
                "Only value_double_1 + value_double_2 are allowed for numericDouble"
            )
        return
    if value_type == "text":
        if value_text is None or not value_text.strip():
            raise _validation_error("value_text is required for text")
        if (
            value_single is not None
            or value_double_1 is not None
            or value_double_2 is not None
        ):
            raise _validation_error("Only value_text is allowed for text")
        return
    raise _validation_error(f"Unknown value_type: {value_type}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_measurements(
    supabase: Client,
    user_id: UUID,
    profile_id: UUID,
    parameter_key: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 500,
) -> list[dict]:
    await assert_profile_owned(supabase, user_id, profile_id)
    query = (
        supabase.table("measurements")
        .select("*")
        .eq("profile_id", str(profile_id))
        .order("recorded_at", desc=True)
        .limit(min(max(limit, 1), 2000))
    )
    if parameter_key:
        query = query.eq("parameter_key", parameter_key)
    if from_dt:
        query = query.gte("recorded_at", from_dt.isoformat())
    if to_dt:
        query = query.lte("recorded_at", to_dt.isoformat())
    res = query.execute()
    return res.data


async def create_measurement(
    supabase: Client, user_id: UUID, data: MeasurementCreateRequest
) -> dict:
    await assert_profile_owned(supabase, user_id, data.profile_id)
    meta = await _resolve_parameter(supabase, data.profile_id, data.parameter_key)
    _validate_payload_against_type(
        meta["value_type"],
        value_single=data.value_single,
        value_double_1=data.value_double_1,
        value_double_2=data.value_double_2,
        value_text=data.value_text,
    )

    payload: dict[str, Any] = {
        "profile_id": str(data.profile_id),
        "parameter_key": data.parameter_key,
        "actor_user_id": str(user_id),
    }
    for field in (
        "value_single",
        "value_double_1",
        "value_double_2",
        "value_text",
        "note",
    ):
        v = getattr(data, field)
        if v is not None:
            payload[field] = v
    if data.recorded_at is not None:
        payload["recorded_at"] = data.recorded_at.isoformat()
    if data.routine_id is not None:
        payload["routine_id"] = str(data.routine_id)
    if data.routine_step_id is not None:
        payload["routine_step_id"] = str(data.routine_step_id)

    res = supabase.table("measurements").insert(payload).execute()
    await log_activity(
        supabase,
        user_id,
        "measurement_recorded",
        profile_id=data.profile_id,
        details={
            "measurement_id": res.data[0]["id"],
            "parameter_key": data.parameter_key,
        },
    )
    return res.data[0]


async def get_measurement(
    supabase: Client, user_id: UUID, measurement_id: UUID
) -> dict:
    res = (
        supabase.table("measurements")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(measurement_id))
        .execute()
    )
    if not res.data or res.data[0]["profiles"]["user_id"] != str(user_id):
        raise _not_found("Measurement not found")
    row = res.data[0]
    row.pop("profiles", None)
    return row


async def update_measurement(
    supabase: Client,
    user_id: UUID,
    measurement_id: UUID,
    data: MeasurementUpdateRequest,
) -> dict:
    existing = await get_measurement(supabase, user_id, measurement_id)
    parameter_key = existing["parameter_key"]
    profile_id = UUID(existing["profile_id"])
    meta = await _resolve_parameter(supabase, profile_id, parameter_key)

    payload = data.model_dump(exclude_none=True)
    # If any value field is in the patch, re-validate against the type.
    if any(
        f in payload
        for f in ("value_single", "value_double_1", "value_double_2", "value_text")
    ):
        merged = {
            "value_single": payload.get(
                "value_single", existing.get("value_single")
            ),
            "value_double_1": payload.get(
                "value_double_1", existing.get("value_double_1")
            ),
            "value_double_2": payload.get(
                "value_double_2", existing.get("value_double_2")
            ),
            "value_text": payload.get("value_text", existing.get("value_text")),
        }
        _validate_payload_against_type(meta["value_type"], **merged)

    if "recorded_at" in payload and isinstance(
        payload["recorded_at"], datetime
    ):
        payload["recorded_at"] = payload["recorded_at"].isoformat()

    res = (
        supabase.table("measurements")
        .update(payload)
        .eq("id", str(measurement_id))
        .execute()
    )
    await log_activity(
        supabase,
        user_id,
        "measurement_updated",
        details={"measurement_id": str(measurement_id)},
    )
    return res.data[0]


async def delete_measurement(
    supabase: Client, user_id: UUID, measurement_id: UUID
) -> None:
    await get_measurement(supabase, user_id, measurement_id)
    supabase.table("measurements").delete().eq(
        "id", str(measurement_id)
    ).execute()
    await log_activity(
        supabase,
        user_id,
        "measurement_deleted",
        details={"measurement_id": str(measurement_id)},
    )
