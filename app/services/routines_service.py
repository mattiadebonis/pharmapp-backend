"""Routine CRUD + step takeover logic.

A routine groups N ordered steps (medication / wait / event / measurement).
When a medication is referenced as a step, its standalone dosing_schedule
is deactivated and `medications.managed_by_routine_id` points at the
routine. This file owns that takeover bookkeeping.
"""

from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.schemas.routine import RoutineCreateRequest, RoutineUpdateRequest
from app.schemas.routine_step import (
    MedicationStepData,
    RoutineStepData,
    RoutineStepDTO,
    step_data_to_columns,
)
from app.services._shared import (
    _conflict,
    _not_found,
    assert_profile_owned,
    assert_routine_owned,
    get_owned_profile_ids,
    log_activity,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_with_steps(routine_row: dict, step_rows: list[dict]) -> dict:
    """Merge a routine row with its steps (sorted by position) into the
    composite shape consumed by `RoutineWithStepsDTO`."""
    sorted_steps = sorted(step_rows, key=lambda s: s["position"])
    return {
        **routine_row,
        "steps": [RoutineStepDTO.from_row(s).model_dump() for s in sorted_steps],
    }


def _medication_ids_in_steps(steps: list[RoutineStepData]) -> list[str]:
    return [
        str(s.medication_id)
        for s in steps
        if isinstance(s, MedicationStepData)
    ]


async def _assert_medications_not_managed_elsewhere(
    supabase: Client,
    medication_ids: list[str],
    exclude_routine_id: str | None = None,
) -> None:
    """Raise 409 if any of the given medications is already managed by an
    active routine other than `exclude_routine_id`."""
    if not medication_ids:
        return
    query = (
        supabase.table("medications")
        .select("id, name, managed_by_routine_id")
        .in_("id", medication_ids)
    )
    res = query.execute()
    for row in res.data:
        managed = row.get("managed_by_routine_id")
        if managed and managed != exclude_routine_id:
            raise _conflict(
                f"Medication '{row.get('name', row['id'])}' is already managed by another routine"
            )


async def _apply_takeover(
    supabase: Client, routine_id: str, medication_ids: list[str]
) -> None:
    """Set medications.managed_by_routine_id = routine_id and deactivate
    their dosing_schedules. Idempotent."""
    if not medication_ids:
        return
    supabase.table("medications").update(
        {"managed_by_routine_id": routine_id}
    ).in_("id", medication_ids).execute()
    supabase.table("dosing_schedules").update(
        {"is_active": False}
    ).in_("medication_id", medication_ids).execute()


async def _release_takeover(
    supabase: Client, routine_id: str, medication_ids: list[str] | None = None
) -> None:
    """Clear managed_by_routine_id for medications that were managed by
    `routine_id`. If `medication_ids` is given, only those are released
    (used when a medication step is removed from an active routine).
    Note: dosing_schedules are NOT auto-reactivated — that's a product
    decision left to the caller."""
    query = (
        supabase.table("medications")
        .update({"managed_by_routine_id": None})
        .eq("managed_by_routine_id", routine_id)
    )
    if medication_ids is not None:
        query = query.in_("id", medication_ids)
    query.execute()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_routines(
    supabase: Client, user_id: UUID, profile_id: UUID | None = None
) -> list[dict]:
    profile_ids = (
        [str(profile_id)]
        if profile_id is not None
        else await get_owned_profile_ids(supabase, user_id)
    )
    if not profile_ids:
        return []
    if profile_id is not None:
        await assert_profile_owned(supabase, user_id, profile_id)

    routines_r = (
        supabase.table("routines")
        .select("*")
        .in_("profile_id", profile_ids)
        .execute()
    )
    routines = routines_r.data
    if not routines:
        return []

    routine_ids = [r["id"] for r in routines]
    steps_r = (
        supabase.table("routine_steps")
        .select("*")
        .in_("routine_id", routine_ids)
        .order("position")
        .execute()
    )
    steps_by_rid: dict[str, list[dict]] = {}
    for s in steps_r.data:
        steps_by_rid.setdefault(s["routine_id"], []).append(s)
    return [_row_with_steps(r, steps_by_rid.get(r["id"], [])) for r in routines]


async def get_routine_with_steps(
    supabase: Client, user_id: UUID, routine_id: UUID
) -> dict:
    row = await assert_routine_owned(supabase, user_id, routine_id)
    steps_r = (
        supabase.table("routine_steps")
        .select("*")
        .eq("routine_id", str(routine_id))
        .order("position")
        .execute()
    )
    return _row_with_steps(row, steps_r.data)


async def create_routine_with_steps(
    supabase: Client, user_id: UUID, data: RoutineCreateRequest
) -> dict:
    await assert_profile_owned(supabase, user_id, data.profile_id)
    medication_ids = _medication_ids_in_steps(data.steps)
    await _assert_medications_not_managed_elsewhere(supabase, medication_ids)

    routine_payload = data.model_dump(
        exclude={"steps"}, exclude_none=True
    )
    routine_payload["profile_id"] = str(data.profile_id)
    routine_row = (
        supabase.table("routines").insert(routine_payload).execute().data[0]
    )
    routine_id = routine_row["id"]

    inserted_steps: list[dict] = []
    if data.steps:
        rows = []
        for idx, step in enumerate(data.steps):
            row = step_data_to_columns(step)
            row["routine_id"] = routine_id
            row["position"] = idx
            rows.append(row)
        try:
            inserted_steps = (
                supabase.table("routine_steps").insert(rows).execute().data
            )
        except Exception:
            # Cleanup: orphan routine rolls back manually since the
            # supabase Python client lacks transactions.
            supabase.table("routines").delete().eq("id", routine_id).execute()
            raise

    if medication_ids:
        await _apply_takeover(supabase, routine_id, medication_ids)

    await log_activity(
        supabase,
        user_id,
        "routine_created",
        profile_id=data.profile_id,
        details={"routine_id": routine_id, "step_count": len(data.steps)},
    )
    return _row_with_steps(routine_row, inserted_steps)


async def update_routine(
    supabase: Client,
    user_id: UUID,
    routine_id: UUID,
    data: RoutineUpdateRequest,
) -> dict:
    await assert_routine_owned(supabase, user_id, routine_id)
    payload = data.model_dump(exclude_none=True, exclude={"steps"})
    raw_steps = data.steps  # None when caller leaves steps untouched

    if payload:
        supabase.table("routines").update(payload).eq(
            "id", str(routine_id)
        ).execute()

    if raw_steps is not None:
        await _replace_steps(supabase, str(routine_id), raw_steps)

    await log_activity(
        supabase,
        user_id,
        "routine_updated",
        details={"routine_id": str(routine_id)},
    )
    return await get_routine_with_steps(supabase, user_id, routine_id)


async def _replace_steps(
    supabase: Client, routine_id: str, steps: list[RoutineStepData]
) -> None:
    """Delete + reinsert the entire step list. Recomputes takeover for
    medication steps."""
    medication_ids = _medication_ids_in_steps(steps)
    await _assert_medications_not_managed_elsewhere(
        supabase, medication_ids, exclude_routine_id=routine_id
    )

    # Snapshot existing medication_ids so we can release takeover for
    # ones that are no longer present in the new step list.
    prev_steps_r = (
        supabase.table("routine_steps")
        .select("medication_id, step_type")
        .eq("routine_id", routine_id)
        .execute()
    )
    prev_med_ids = [
        s["medication_id"]
        for s in prev_steps_r.data
        if s.get("step_type") == "medication" and s.get("medication_id")
    ]

    supabase.table("routine_steps").delete().eq(
        "routine_id", routine_id
    ).execute()
    if steps:
        rows = []
        for idx, step in enumerate(steps):
            row = step_data_to_columns(step)
            row["routine_id"] = routine_id
            row["position"] = idx
            rows.append(row)
        supabase.table("routine_steps").insert(rows).execute()

    released = [m for m in prev_med_ids if m not in medication_ids]
    if released:
        await _release_takeover(supabase, routine_id, released)
    if medication_ids:
        await _apply_takeover(supabase, routine_id, medication_ids)


async def delete_routine(
    supabase: Client, user_id: UUID, routine_id: UUID, hard: bool = False
) -> None:
    """Soft delete by default (`is_active=false`). Pass `hard=true` to
    delete the row outright (cascades through routine_steps via FK).
    Per product spec, the linked medications are also deleted on hard
    delete (caller should warn the user before invoking)."""
    await assert_routine_owned(supabase, user_id, routine_id)

    steps_r = (
        supabase.table("routine_steps")
        .select("medication_id, step_type")
        .eq("routine_id", str(routine_id))
        .execute()
    )
    linked_med_ids = [
        s["medication_id"]
        for s in steps_r.data
        if s.get("step_type") == "medication" and s.get("medication_id")
    ]

    if hard:
        # Releases takeover via ON DELETE SET NULL on the FK, then we
        # explicitly delete the linked medications per product rule.
        res = (
            supabase.table("routines")
            .delete()
            .eq("id", str(routine_id))
            .execute()
        )
        if not res.data:
            raise _not_found("Routine not found")
        if linked_med_ids:
            supabase.table("medications").delete().in_(
                "id", linked_med_ids
            ).execute()
        await log_activity(
            supabase,
            user_id,
            "routine_deleted",
            details={
                "routine_id": str(routine_id),
                "hard": True,
                "deleted_medication_ids": linked_med_ids,
            },
        )
        return

    # Soft delete: deactivate the routine, release takeover so the
    # medications are once again unmanaged. The medications themselves
    # are left intact.
    supabase.table("routines").update({"is_active": False}).eq(
        "id", str(routine_id)
    ).execute()
    if linked_med_ids:
        await _release_takeover(supabase, str(routine_id))
    await log_activity(
        supabase,
        user_id,
        "routine_deleted",
        details={"routine_id": str(routine_id), "hard": False},
    )


async def duplicate_routine(
    supabase: Client, user_id: UUID, routine_id: UUID, new_name: str
) -> dict:
    """Clone a routine + its steps. The duplicate starts inactive (so it
    does not contend for medication takeover) — the user must activate
    it explicitly, at which point validation runs again."""
    src = await assert_routine_owned(supabase, user_id, routine_id)
    src_steps = (
        supabase.table("routine_steps")
        .select("*")
        .eq("routine_id", str(routine_id))
        .order("position")
        .execute()
    ).data

    new_payload = {
        "profile_id": src["profile_id"],
        "name": new_name,
        "rrule": src.get("rrule"),
        "start_time": src.get("start_time"),
        "is_active": False,
    }
    new_routine = (
        supabase.table("routines").insert(new_payload).execute().data[0]
    )
    new_id = new_routine["id"]

    if src_steps:
        rows = []
        for idx, s in enumerate(src_steps):
            row = {
                "routine_id": new_id,
                "position": idx,
                "step_type": s["step_type"],
            }
            for col in (
                "medication_id",
                "dose_amount",
                "duration_minutes",
                "instructions",
                "event_name",
                "parameter_key",
            ):
                if s.get(col) is not None:
                    row[col] = s[col]
            rows.append(row)
        supabase.table("routine_steps").insert(rows).execute()

    await log_activity(
        supabase,
        user_id,
        "routine_duplicated",
        profile_id=src["profile_id"],
        details={"src_routine_id": str(routine_id), "new_routine_id": new_id},
    )
    return await get_routine_with_steps(supabase, user_id, UUID(new_id))
