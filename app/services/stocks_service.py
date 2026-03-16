from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.schemas.stock import StockDTO, StockIncrementRequest, StockSetRequest
from app.services.authorization import user_can_access_tracked_medicine


async def _get_package_medicine_id(supabase: Client, tracked_package_id: UUID) -> UUID:
    """Get the tracked_medicine_id for a package."""
    result = (
        supabase.table("tracked_packages")
        .select("tracked_medicine_id")
        .eq("id", str(tracked_package_id))
        .single()
        .execute()
    )
    return UUID(result.data["tracked_medicine_id"])


async def get_stocks(supabase: Client, user_id: UUID) -> list[StockDTO]:
    """Get all stocks for medicines the user can access."""
    uid = str(user_id)
    meds_r = supabase.table("tracked_medicines").select("id").eq("owner_user_id", uid).execute()
    if not meds_r.data:
        return []
    med_ids = [m["id"] for m in meds_r.data]
    stocks_r = supabase.table("stocks").select("*").in_("tracked_medicine_id", med_ids).execute()
    return [StockDTO.model_validate(s) for s in stocks_r.data]


async def set_stock(
    supabase: Client, user_id: UUID, tracked_package_id: UUID, data: StockSetRequest
) -> StockDTO:
    """Set absolute stock units for a package."""
    medicine_id = await _get_package_medicine_id(supabase, tracked_package_id)
    if not await user_can_access_tracked_medicine(supabase, user_id, medicine_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Access denied"}},
        )

    pid = str(tracked_package_id)
    existing = (
        supabase.table("stocks")
        .select("id")
        .eq("tracked_package_id", pid)
        .eq("context_key", "default")
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        result = (
            supabase.table("stocks")
            .update({"stock_units": data.stock_units})
            .eq("id", existing.data["id"])
            .execute()
        )
    else:
        result = supabase.table("stocks").insert({
            "tracked_medicine_id": str(medicine_id),
            "tracked_package_id": pid,
            "context_key": "default",
            "stock_units": data.stock_units,
        }).execute()
    return StockDTO.model_validate(result.data[0])


async def increment_stock(
    supabase: Client, user_id: UUID, tracked_package_id: UUID, data: StockIncrementRequest
) -> StockDTO:
    """Increment/decrement stock by delta."""
    medicine_id = await _get_package_medicine_id(supabase, tracked_package_id)
    if not await user_can_access_tracked_medicine(supabase, user_id, medicine_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Access denied"}},
        )

    pid = str(tracked_package_id)
    existing = (
        supabase.table("stocks")
        .select("id, stock_units")
        .eq("tracked_package_id", pid)
        .eq("context_key", "default")
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        new_units = max(0, existing.data["stock_units"] + data.delta)
        result = (
            supabase.table("stocks")
            .update({"stock_units": new_units})
            .eq("id", existing.data["id"])
            .execute()
        )
    else:
        result = supabase.table("stocks").insert({
            "tracked_medicine_id": str(medicine_id),
            "tracked_package_id": pid,
            "context_key": "default",
            "stock_units": max(0, data.delta),
        }).execute()
    return StockDTO.model_validate(result.data[0])
