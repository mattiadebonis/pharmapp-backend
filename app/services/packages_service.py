from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

# ---------------------------------------------------------------------------
# Scorte per dosaggio (medication_packages). Più confezioni per medication,
# una per dosaggio. Fonte di verità delle scorte; `supplies` resta come
# aggregato legacy.
# ---------------------------------------------------------------------------


async def _verify_medication_ownership(supabase: Client, user_id: UUID, medication_id: UUID) -> None:
    """Verify the medication belongs to the user via the profile chain."""
    med = supabase.table("medications").select("*, profiles!inner(user_id)").eq("id", str(medication_id)).execute()
    if not med.data or med.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )


async def replace_packages(supabase: Client, user_id: UUID, medication_id: UUID, data) -> list[dict]:
    """Replace the full set of packages for a medication.

    The iOS client always sends the complete current set, so we delete the
    existing rows and insert the provided ones. Each package keeps its client
    ``id`` (offline replay idempotency); rows are upserted on ``id`` and any
    stale rows not in the payload are removed.
    """
    await _verify_medication_ownership(supabase, user_id, medication_id)
    mid = str(medication_id)

    rows = []
    for pkg in data.packages:
        row = pkg.model_dump(exclude_none=True, mode="json")
        row["medication_id"] = mid
        if row.get("id"):
            row["id"] = str(row["id"]).lower()
        rows.append(row)

    kept_ids = [r["id"] for r in rows if r.get("id")]

    # Rimuovi le confezioni non più presenti nel set inviato.
    stale = supabase.table("medication_packages").select("id").eq("medication_id", mid).execute()
    stale_ids = [r["id"] for r in (stale.data or []) if r["id"] not in kept_ids]
    for sid in stale_ids:
        supabase.table("medication_packages").delete().eq("id", sid).execute()

    if not rows:
        return []

    if any(r.get("id") for r in rows):
        supabase.table("medication_packages").upsert(rows, on_conflict="id").execute()
    else:
        supabase.table("medication_packages").insert(rows).execute()

    refetch = supabase.table("medication_packages").select("*").eq("medication_id", mid).execute()
    return refetch.data or []
