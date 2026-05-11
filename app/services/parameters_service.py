"""Parameters service.

Predefined parameters live in this file as a Python constant. Custom
parameters are persisted in the `parameters` table per profile.

The list_parameters endpoint returns BOTH families (predefined first,
then the user's customs sorted by created_at).
"""

import uuid as _uuid
from typing import Any
from uuid import UUID

from supabase import Client

from app.schemas.parameter import ParameterCreateRequest, ParameterUpdateRequest
from app.services._shared import (
    _conflict,
    _not_found,
    assert_profile_owned,
    log_activity,
)


# ---------------------------------------------------------------------------
# Predefined catalog
# ---------------------------------------------------------------------------
# These are exposed as DTOs alongside the user's custom parameters in
# every list_parameters response. They have `id=None` and
# `is_predefined=True`.

PREDEFINED_PARAMETERS: list[dict[str, Any]] = [
    {
        "parameter_key": "glycemia",
        "name": "Glicemia",
        "unit": "mg/dL",
        "value_type": "numericSingle",
        "decimals": 0,
        "labels": None,
        # Target plasma glucose: 70–130 mg/dL (post-prandial 2h ≤180).
        "target_low": 70,
        "target_high": 130,
        "target_label": "70–130",
    },
    {
        "parameter_key": "blood_pressure",
        "name": "Pressione arteriosa",
        "unit": "mmHg",
        "value_type": "numericDouble",
        "decimals": 0,
        "labels": ["Sistolica", "Diastolica"],
        # Hypertension target: SBP <140, DBP <90 (general); <130/80 for
        # diabetic / nephropathic patients. Use general target.
        "target_low_v1": None,
        "target_high_v1": 140,
        "target_low_v2": None,
        "target_high_v2": 90,
        "target_label": "<140/90",
    },
    {
        "parameter_key": "weight",
        "name": "Peso corporeo",
        "unit": "kg",
        "value_type": "numericSingle",
        "decimals": 1,
        "labels": None,
        # No fixed target — patient-specific.
    },
    {
        "parameter_key": "temperature",
        "name": "Temperatura",
        "unit": "°C",
        "value_type": "numericSingle",
        "decimals": 1,
        "labels": None,
        "target_low": 36.0,
        "target_high": 37.5,
        "target_label": "36–37,5",
    },
    {
        "parameter_key": "inr",
        "name": "INR",
        "unit": None,
        "value_type": "numericSingle",
        "decimals": 2,
        "labels": None,
        # Therapeutic range varies (2.0–3.0 typical, 2.5–3.5 mechanical
        # valve). Default to general range; clinicians override.
        "target_low": 2.0,
        "target_high": 3.0,
        "target_label": "2,0–3,0",
    },
    {
        "parameter_key": "oxygen_saturation",
        "name": "Saturazione O₂",
        "unit": "%",
        "value_type": "numericSingle",
        "decimals": 0,
        "labels": None,
        "target_low": 95,
        "target_high": None,
        "target_label": "≥95",
    },
    {
        "parameter_key": "heart_rate",
        "name": "Frequenza cardiaca",
        "unit": "bpm",
        "value_type": "numericSingle",
        "decimals": 0,
        "labels": None,
        "target_low": 60,
        "target_high": 100,
        "target_label": "60–100",
    },
]

PREDEFINED_KEYS: set[str] = {p["parameter_key"] for p in PREDEFINED_PARAMETERS}


def _predefined_dto(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": None,
        "profile_id": None,
        "parameter_key": p["parameter_key"],
        "name": p["name"],
        "unit": p.get("unit"),
        "value_type": p["value_type"],
        "labels": p.get("labels"),
        "decimals": p.get("decimals"),
        "is_predefined": True,
        "created_at": None,
        "updated_at": None,
    }


def get_predefined(parameter_key: str) -> dict[str, Any] | None:
    for p in PREDEFINED_PARAMETERS:
        if p["parameter_key"] == parameter_key:
            return p
    return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_parameters(
    supabase: Client, user_id: UUID, profile_id: UUID
) -> list[dict[str, Any]]:
    await assert_profile_owned(supabase, user_id, profile_id)
    custom_r = (
        supabase.table("parameters")
        .select("*")
        .eq("profile_id", str(profile_id))
        .order("created_at")
        .execute()
    )
    custom_dtos = [{**row, "is_predefined": False} for row in custom_r.data]
    return [_predefined_dto(p) for p in PREDEFINED_PARAMETERS] + custom_dtos


async def create_custom_parameter(
    supabase: Client, user_id: UUID, data: ParameterCreateRequest
) -> dict[str, Any]:
    await assert_profile_owned(supabase, user_id, data.profile_id)
    param_id = str(data.id).lower() if data.id else str(_uuid.uuid4())
    parameter_key = f"custom:{param_id}"
    payload = {
        "id": param_id,
        "profile_id": str(data.profile_id),
        "parameter_key": parameter_key,
        "name": data.name,
        "unit": data.unit,
        "value_type": data.value_type,
        "labels": data.labels,
        "decimals": data.decimals,
    }
    if data.id:
        res = supabase.table("parameters").upsert(payload, on_conflict="id").execute()
    else:
        res = supabase.table("parameters").insert(payload).execute()
    await log_activity(
        supabase,
        user_id,
        "parameter_custom_created",
        profile_id=data.profile_id,
        details={"parameter_id": res.data[0]["id"], "name": data.name},
    )
    return {**res.data[0], "is_predefined": False}


async def get_custom_parameter(
    supabase: Client, user_id: UUID, parameter_id: UUID
) -> dict[str, Any]:
    res = (
        supabase.table("parameters")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(parameter_id))
        .execute()
    )
    if not res.data or res.data[0]["profiles"]["user_id"] != str(user_id):
        raise _not_found("Parameter not found")
    row = res.data[0]
    row.pop("profiles", None)
    return {**row, "is_predefined": False}


async def update_custom_parameter(
    supabase: Client,
    user_id: UUID,
    parameter_id: UUID,
    data: ParameterUpdateRequest,
) -> dict[str, Any]:
    await get_custom_parameter(supabase, user_id, parameter_id)
    payload = data.model_dump(exclude_none=True, mode="json")
    if not payload:
        return await get_custom_parameter(supabase, user_id, parameter_id)
    res = (
        supabase.table("parameters")
        .update(payload)
        .eq("id", str(parameter_id))
        .execute()
    )
    return {**res.data[0], "is_predefined": False}


async def delete_custom_parameter(
    supabase: Client, user_id: UUID, parameter_id: UUID
) -> None:
    """Block deletion if the parameter is referenced by routine_steps or
    measurements. Application-level FK enforcement (the column is TEXT,
    not a true FK)."""
    row = await get_custom_parameter(supabase, user_id, parameter_id)
    parameter_key = row["parameter_key"]

    used_in_steps = (
        supabase.table("routine_steps")
        .select("id")
        .eq("parameter_key", parameter_key)
        .limit(1)
        .execute()
    )
    if used_in_steps.data:
        raise _conflict("Parameter is used by one or more routines")

    used_in_measurements = (
        supabase.table("measurements")
        .select("id")
        .eq("parameter_key", parameter_key)
        .limit(1)
        .execute()
    )
    if used_in_measurements.data:
        raise _conflict("Parameter has recorded measurements")

    supabase.table("parameters").delete().eq(
        "id", str(parameter_id)
    ).execute()
    await log_activity(
        supabase,
        user_id,
        "parameter_custom_deleted",
        details={"parameter_id": str(parameter_id)},
    )
