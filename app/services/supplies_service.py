from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_medication_ownership(supabase: Client, user_id: UUID, medication_id: UUID) -> None:
    """Verify the medication belongs to the user via the profile chain."""
    med = supabase.table("medications").select("*, profiles!inner(user_id)").eq("id", str(medication_id)).execute()
    if not med.data or med.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )


# ---------------------------------------------------------------------------
# CRUD (upsert pattern — one supply per medication)
# ---------------------------------------------------------------------------


async def get_supply(supabase: Client, user_id: UUID, medication_id: UUID) -> dict | None:
    """Get the supply row for a medication, or None if not yet created."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = supabase.table("supplies").select("*").eq("medication_id", str(medication_id)).execute()
    return result.data[0] if result.data else None


async def upsert_supply(supabase: Client, user_id: UUID, medication_id: UUID, data) -> dict:
    """Create or update the supply for a medication (upsert).

    Because there is a unique index on ``medication_id``, there is at most one
    supply row per medication.  If a row already exists we update it;
    otherwise we insert a new one.
    """
    await _verify_medication_ownership(supabase, user_id, medication_id)
    mid = str(medication_id)
    payload = data.model_dump(exclude_none=True, mode="json")
    # medication_id arriva dal path: scarta eventuali valori nel body per
    # evitare scritture inutili (FK immutabile) e accettare client legacy
    # che ancora lo passano.
    payload.pop("medication_id", None)

    existing = supabase.table("supplies").select("*").eq("medication_id", mid).execute()

    if existing.data:
        existing_row = existing.data[0]
        supabase.table("supplies").update(payload).eq("id", existing_row["id"]).execute()
        # Ricostruiamo la response dalla riga che abbiamo appena letto +
        # i campi aggiornati, invece di affidarci al ``RETURNING`` di
        # Supabase (il client non garantisce ``Prefer: return=representation``
        # in tutte le configurazioni). Il client riavrà ``updated_at``
        # fresh al prossimo bootstrap; per la response immediata non
        # serve.
        return {**existing_row, **payload}

    payload["medication_id"] = mid
    result = supabase.table("supplies").insert(payload).execute()
    if result.data:
        return result.data[0]
    refetch = supabase.table("supplies").select("*").eq("medication_id", mid).execute()
    if refetch.data:
        return refetch.data[0]
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": {"code": "supply_insert_failed", "message": "Supply insert returned no row"}},
    )


async def delete_supply(supabase: Client, user_id: UUID, medication_id: UUID) -> None:
    """Delete the supply for a medication."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = supabase.table("supplies").delete().eq("medication_id", str(medication_id)).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Supply not found"}},
        )
