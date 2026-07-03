from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_profile_ids(supabase: Client, user_id: UUID) -> list[str]:
    """Return all profile IDs that belong to the given user."""
    profiles_result = (
        supabase.table("profiles")
        .select("id")
        .eq("user_id", str(user_id))
        .execute()
    )
    return [p["id"] for p in profiles_result.data]


def _serialize_event_payload(data, user_id: UUID) -> dict:
    """Normalizza un DoseEventCreateRequest in payload Supabase.

    UUID → stringhe lowercase, datetime → ISO, actor_user_id impostato
    server-side. Condiviso tra il POST singolo e il batch del catch-up.
    """
    payload = data.model_dump(exclude_none=True, mode="json")
    for uuid_field in ("id", "profile_id", "medication_id", "dosing_schedule_id"):
        if payload.get(uuid_field):
            payload[uuid_field] = str(payload[uuid_field]).lower()
    for dt_field in ("due_at", "taken_at", "auto_registered_at", "user_corrected_at", "rescheduled_from"):
        if dt_field in payload and hasattr(payload[dt_field], "isoformat"):
            payload[dt_field] = payload[dt_field].isoformat()
    payload["actor_user_id"] = str(user_id)
    return payload


def _raise_conflict_if_foreign_key(exc: Exception) -> None:
    """FK violation = il client referenzia medication/profile che il backend
    non conosce ancora (POST medication non sincronizzato, race, o coda
    offline orfana). 409 con flag chiaro così iOS drena la mutation invece
    di ritentare all'infinito (500)."""
    message = str(exc)
    if "foreign key" in message.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "foreign_key_violation", "message": message}},
        )


# ---------------------------------------------------------------------------
# CRUD + filtered listing
# ---------------------------------------------------------------------------


async def create_dose_event(supabase: Client, user_id: UUID, data) -> dict:
    """Create a dose event.

    The ``profile_id`` in the payload must belong to the user.
    """
    payload = _serialize_event_payload(data, user_id)
    # Verify profile ownership
    profile_id = payload.get("profile_id")
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "profile_id is required"}},
        )
    profile_check = (
        supabase.table("profiles")
        .select("id")
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not profile_check.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Profile does not belong to user"}},
        )
    # Idempotent upsert when client provides id (offline retry, dose confirm
    # replay). Without id, fall back to plain insert.
    try:
        if payload.get("id"):
            result = supabase.table("dose_events").upsert(payload, on_conflict="id").execute()
        else:
            result = supabase.table("dose_events").insert(payload).execute()
    except Exception as exc:
        _raise_conflict_if_foreign_key(exc)
        raise
    return result.data[0]


async def batch_upsert_dose_events(supabase: Client, user_id: UUID, data) -> dict:
    """Upsert idempotente di N dose events in una chiamata.

    Usato dal catch-up iOS: al rientro dopo giorni di app chiusa il client
    registra in blocco le dosi passive arretrate (id deterministici per
    slot → ri-POST e doppio device convergono senza duplicati).

    Ownership: una sola query sui profile_id distinti del batch; se anche
    un solo profilo non appartiene all'utente → 403 e nessun insert
    parziale (l'upsert avviene dopo, in un'unica chiamata).
    """
    requested_profile_ids = {str(event.profile_id).lower() for event in data.events}
    owned_profile_ids = {pid.lower() for pid in await _get_profile_ids(supabase, user_id)}
    if not requested_profile_ids.issubset(owned_profile_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Profile does not belong to user"}},
        )

    payloads = [_serialize_event_payload(event, user_id) for event in data.events]
    try:
        result = supabase.table("dose_events").upsert(payloads, on_conflict="id").execute()
    except Exception as exc:
        _raise_conflict_if_foreign_key(exc)
        raise
    return {"events": result.data, "upserted": len(result.data)}
