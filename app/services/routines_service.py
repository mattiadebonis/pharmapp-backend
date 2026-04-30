from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_profile_ids(supabase: Client, user_id: UUID) -> list[str]:
    profiles_result = (
        supabase.table("profiles")
        .select("id")
        .eq("user_id", str(user_id))
        .execute()
    )
    return [p["id"] for p in profiles_result.data]


async def _verify_profile_ownership(
    supabase: Client, user_id: UUID, profile_id: UUID
) -> None:
    check = (
        supabase.table("profiles")
        .select("id")
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not check.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Profile does not belong to user"}},
        )


async def _verify_routine_ownership(
    supabase: Client, user_id: UUID, routine_id: UUID
) -> dict:
    res = (
        supabase.table("routines")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(routine_id))
        .execute()
    )
    if not res.data or res.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Routine not found"}},
        )
    row = res.data[0]
    row.pop("profiles", None)
    return row


def _step_payload(routine_id: str, raw: dict) -> dict:
    """Normalize an inline step payload before insert.

    Strips fields irrelevant to the chosen step_type so the DB row only
    carries valid columns. UUIDs are stringified for the supabase client.
    """
    step_type = raw["step_type"]
    payload: dict = {
        "routine_id": routine_id,
        "position": raw["position"],
        "step_type": step_type,
    }
    if step_type == "medication":
        payload["medication_id"] = str(raw["medication_id"])
        if raw.get("dose_amount"):
            payload["dose_amount"] = raw["dose_amount"]
    elif step_type == "wait":
        payload["duration_minutes"] = raw["duration_minutes"]
        if raw.get("instructions"):
            payload["instructions"] = raw["instructions"]
    elif step_type == "event":
        payload["event_name"] = raw["event_name"]
    return payload


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_routines(supabase: Client, user_id: UUID) -> list[dict]:
    profile_ids = await _get_profile_ids(supabase, user_id)
    if not profile_ids:
        return []
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
    steps_by_routine: dict[str, list] = {}
    for s in steps_r.data:
        steps_by_routine.setdefault(s["routine_id"], []).append(s)
    return [
        {**r, "steps": steps_by_routine.get(r["id"], [])}
        for r in routines
    ]


async def get_routine(supabase: Client, user_id: UUID, routine_id: UUID) -> dict:
    row = await _verify_routine_ownership(supabase, user_id, routine_id)
    steps_r = (
        supabase.table("routine_steps")
        .select("*")
        .eq("routine_id", str(routine_id))
        .order("position")
        .execute()
    )
    return {**row, "steps": steps_r.data}


async def create_routine(supabase: Client, user_id: UUID, data) -> dict:
    payload = data.model_dump(exclude_none=True)
    profile_id = payload.get("profile_id")
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "profile_id is required"}},
        )
    await _verify_profile_ownership(supabase, user_id, profile_id)

    raw_steps = payload.pop("steps", []) or []
    payload["profile_id"] = str(profile_id)
    routine_row = supabase.table("routines").insert(payload).execute().data[0]
    routine_id = routine_row["id"]

    inserted_steps: list[dict] = []
    if raw_steps:
        rows = [_step_payload(routine_id, s) for s in raw_steps]
        inserted_steps = (
            supabase.table("routine_steps").insert(rows).execute().data
        )
        inserted_steps.sort(key=lambda s: s["position"])
        await _deactivate_schedules_for_steps(supabase, raw_steps)
    return {**routine_row, "steps": inserted_steps}


async def update_routine(
    supabase: Client, user_id: UUID, routine_id: UUID, data
) -> dict:
    await _verify_routine_ownership(supabase, user_id, routine_id)
    payload = data.model_dump(exclude_none=True)
    raw_steps = payload.pop("steps", None)

    if payload:
        supabase.table("routines").update(payload).eq("id", str(routine_id)).execute()

    if raw_steps is not None:
        # Replace the full step list. Caller sent the desired final state.
        supabase.table("routine_steps").delete().eq(
            "routine_id", str(routine_id)
        ).execute()
        if raw_steps:
            rows = [_step_payload(str(routine_id), s) for s in raw_steps]
            supabase.table("routine_steps").insert(rows).execute()
            await _deactivate_schedules_for_steps(supabase, raw_steps)

    return await get_routine(supabase, user_id, routine_id)


async def delete_routine(
    supabase: Client, user_id: UUID, routine_id: UUID
) -> None:
    """Delete a routine. Per product spec, also deletes every medication
    referenced as a step inside the routine — the user is informed by the
    client UI before this call."""
    await _verify_routine_ownership(supabase, user_id, routine_id)

    # Snapshot linked medication ids before cascade.
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

    res = (
        supabase.table("routines").delete().eq("id", str(routine_id)).execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Routine not found"}},
        )

    if linked_med_ids:
        # Delete the linked medications. Cascades through dosing_schedules,
        # supplies, prescriptions, dose_events via FK ON DELETE CASCADE.
        supabase.table("medications").delete().in_("id", linked_med_ids).execute()


async def _deactivate_schedules_for_steps(supabase: Client, raw_steps: list[dict]) -> None:
    """For every medication step, set every dosing_schedule on that
    medication to is_active=false. The routine becomes the source of truth
    for its timing."""
    med_ids = [
        str(s["medication_id"])
        for s in raw_steps
        if s.get("step_type") == "medication" and s.get("medication_id")
    ]
    if not med_ids:
        return
    supabase.table("dosing_schedules").update({"is_active": False}).in_(
        "medication_id", med_ids
    ).execute()
