"""Granular CRUD for individual `routine_steps`.

Used by the editor UI for incremental edits without re-uploading the
full routine. The full-replace path lives in `routines_service.update_routine`
when the caller passes `steps`."""

from uuid import UUID

from supabase import Client

from app.schemas.routine_step import (
    MedicationStepData,
    RoutineStepData,
    RoutineStepDTO,
    step_data_to_columns,
)
from app.services._shared import (
    _conflict,
    _not_found,
    assert_routine_owned,
    log_activity,
)
from app.services.routines_service import (
    _apply_takeover,
    _assert_medications_not_managed_elsewhere,
    _release_takeover,
)


async def _get_step(
    supabase: Client, routine_id: UUID, step_id: UUID
) -> dict:
    res = (
        supabase.table("routine_steps")
        .select("*")
        .eq("id", str(step_id))
        .eq("routine_id", str(routine_id))
        .execute()
    )
    if not res.data:
        raise _not_found("Step not found")
    return res.data[0]


async def add_step(
    supabase: Client,
    user_id: UUID,
    routine_id: UUID,
    step_data: RoutineStepData,
    position: int | None = None,
) -> RoutineStepDTO:
    await assert_routine_owned(supabase, user_id, routine_id)

    if isinstance(step_data, MedicationStepData):
        await _assert_medications_not_managed_elsewhere(
            supabase, [str(step_data.medication_id)],
            exclude_routine_id=str(routine_id),
        )

    if position is None:
        # Append: position = max(position) + 1
        existing = (
            supabase.table("routine_steps")
            .select("position")
            .eq("routine_id", str(routine_id))
            .order("position", desc=True)
            .limit(1)
            .execute()
        )
        position = (existing.data[0]["position"] + 1) if existing.data else 0
    else:
        # Make room: shift later steps down by 1.
        await _shift_positions(supabase, str(routine_id), from_position=position)

    payload = step_data_to_columns(step_data)
    payload["routine_id"] = str(routine_id)
    payload["position"] = position

    inserted = (
        supabase.table("routine_steps").insert(payload).execute().data[0]
    )

    if isinstance(step_data, MedicationStepData):
        await _apply_takeover(
            supabase, str(routine_id), [str(step_data.medication_id)]
        )

    await log_activity(
        supabase,
        user_id,
        "routine_step_added",
        details={
            "routine_id": str(routine_id),
            "step_id": inserted["id"],
            "step_type": inserted["step_type"],
        },
    )
    return RoutineStepDTO.from_row(inserted)


async def update_step(
    supabase: Client,
    user_id: UUID,
    routine_id: UUID,
    step_id: UUID,
    step_data: RoutineStepData,
) -> RoutineStepDTO:
    await assert_routine_owned(supabase, user_id, routine_id)
    prev = await _get_step(supabase, routine_id, step_id)

    if isinstance(step_data, MedicationStepData):
        await _assert_medications_not_managed_elsewhere(
            supabase, [str(step_data.medication_id)],
            exclude_routine_id=str(routine_id),
        )

    payload = step_data_to_columns(step_data)
    # Wipe legacy columns from the previous shape — Supabase doesn't have
    # a "set null" alias, we send explicit None for the columns that the
    # new shape doesn't use.
    for col in (
        "medication_id",
        "dose_amount",
        "duration_minutes",
        "instructions",
        "event_name",
        "parameter_key",
    ):
        if col not in payload:
            payload[col] = None

    updated = (
        supabase.table("routine_steps")
        .update(payload)
        .eq("id", str(step_id))
        .execute()
        .data[0]
    )

    # Takeover bookkeeping if medication changed.
    prev_med = (
        prev.get("medication_id") if prev.get("step_type") == "medication" else None
    )
    new_med = (
        str(step_data.medication_id)
        if isinstance(step_data, MedicationStepData)
        else None
    )
    if prev_med and prev_med != new_med:
        await _release_takeover(supabase, str(routine_id), [prev_med])
    if new_med and new_med != prev_med:
        await _apply_takeover(supabase, str(routine_id), [new_med])

    await log_activity(
        supabase,
        user_id,
        "routine_step_updated",
        details={
            "routine_id": str(routine_id),
            "step_id": str(step_id),
            "step_type": updated["step_type"],
        },
    )
    return RoutineStepDTO.from_row(updated)


async def delete_step(
    supabase: Client, user_id: UUID, routine_id: UUID, step_id: UUID
) -> None:
    await assert_routine_owned(supabase, user_id, routine_id)
    prev = await _get_step(supabase, routine_id, step_id)
    deleted_position = prev["position"]

    supabase.table("routine_steps").delete().eq(
        "id", str(step_id)
    ).execute()

    if prev.get("step_type") == "medication" and prev.get("medication_id"):
        await _release_takeover(
            supabase, str(routine_id), [prev["medication_id"]]
        )

    await log_activity(
        supabase,
        user_id,
        "routine_step_removed",
        details={
            "routine_id": str(routine_id),
            "step_id": str(step_id),
            "step_type": prev["step_type"],
        },
    )

    # Backfill positions: every step with position > deleted_position
    # shifts up by 1.
    later = (
        supabase.table("routine_steps")
        .select("id, position")
        .eq("routine_id", str(routine_id))
        .gt("position", deleted_position)
        .execute()
    )
    for row in later.data:
        supabase.table("routine_steps").update(
            {"position": row["position"] - 1}
        ).eq("id", row["id"]).execute()


async def reorder_steps(
    supabase: Client,
    user_id: UUID,
    routine_id: UUID,
    ordering: list[dict],
) -> list[RoutineStepDTO]:
    """Apply a batch position rewrite. `ordering` is a list of
    `{step_id, position}`; missing ids leave their position untouched
    (caller must send the full list to be safe)."""
    await assert_routine_owned(supabase, user_id, routine_id)
    seen = {item["step_id"] for item in ordering}
    if len(seen) != len(ordering):
        raise _conflict("Duplicate step_id in reorder payload")

    # Two-phase write to avoid transient unique-constraint violations
    # on (routine_id, position): bump each step to a temporary
    # large position, then write the final values.
    for idx, item in enumerate(ordering):
        supabase.table("routine_steps").update(
            {"position": 1_000_000 + idx}
        ).eq("id", item["step_id"]).eq(
            "routine_id", str(routine_id)
        ).execute()

    for item in ordering:
        supabase.table("routine_steps").update(
            {"position": item["position"]}
        ).eq("id", item["step_id"]).eq(
            "routine_id", str(routine_id)
        ).execute()

    res = (
        supabase.table("routine_steps")
        .select("*")
        .eq("routine_id", str(routine_id))
        .order("position")
        .execute()
    )
    await log_activity(
        supabase,
        user_id,
        "routine_step_reordered",
        details={"routine_id": str(routine_id), "step_count": len(ordering)},
    )
    return [RoutineStepDTO.from_row(r) for r in res.data]


async def _shift_positions(
    supabase: Client, routine_id: str, from_position: int
) -> None:
    """Shift every step with position >= from_position one slot down."""
    later = (
        supabase.table("routine_steps")
        .select("id, position")
        .eq("routine_id", routine_id)
        .gte("position", from_position)
        .order("position", desc=True)  # work top-down to avoid clashes
        .execute()
    )
    for row in later.data:
        supabase.table("routine_steps").update(
            {"position": row["position"] + 1}
        ).eq("id", row["id"]).execute()
