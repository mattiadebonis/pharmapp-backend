from datetime import datetime, timezone
from uuid import UUID

from supabase import Client

from app.schemas.operation import OperationRequest, OperationResultDTO, UndoOperationRequest
from app.services.authorization import assert_can_access_tracked_medicine


async def _check_idempotency(supabase: Client, operation_id: UUID) -> OperationResultDTO | None:
    """Check if an operation already exists. Returns result if duplicate."""
    existing = (
        supabase.table("activity_logs")
        .select("id")
        .eq("operation_id", str(operation_id))
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return OperationResultDTO(
            operation_id=operation_id,
            was_duplicate=True,
            activity_log_id=UUID(existing.data["id"]),
        )
    return None


async def _insert_log(supabase: Client, log_data: dict) -> dict:
    """Insert activity log, handling unique violation gracefully."""
    try:
        result = supabase.table("activity_logs").insert(log_data).execute()
        return result.data[0]
    except Exception as e:
        if "23505" in str(e):
            existing = (
                supabase.table("activity_logs")
                .select("id")
                .eq("operation_id", log_data["operation_id"])
                .single()
                .execute()
            )
            return {"id": existing.data["id"], "_duplicate": True}
        raise


async def _adjust_stock(supabase: Client, medicine_id: UUID, package_id: UUID, delta: int) -> None:
    """Adjust stock for a package. Creates stock row if none exists."""
    mid = str(medicine_id)
    pid = str(package_id)
    existing = (
        supabase.table("stocks")
        .select("id, stock_units")
        .eq("tracked_package_id", pid)
        .eq("context_key", "default")
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        new_units = max(0, existing.data["stock_units"] + delta)
        supabase.table("stocks").update({"stock_units": new_units}).eq("id", existing.data["id"]).execute()
    else:
        supabase.table("stocks").insert({
            "tracked_medicine_id": mid,
            "tracked_package_id": pid,
            "context_key": "default",
            "stock_units": max(0, delta),
        }).execute()


async def _upsert_dose_event(
    supabase: Client, therapy_id: UUID, medicine_id: UUID, due_at: datetime, event_status: str, user_id: UUID
) -> None:
    """Create or update a dose event."""
    existing = (
        supabase.table("dose_events")
        .select("id")
        .eq("therapy_id", str(therapy_id))
        .eq("due_at", due_at.isoformat())
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        supabase.table("dose_events").update({
            "status": event_status,
            "actor_user_id": str(user_id),
        }).eq("id", existing.data["id"]).execute()
    else:
        supabase.table("dose_events").insert({
            "therapy_id": str(therapy_id),
            "tracked_medicine_id": str(medicine_id),
            "due_at": due_at.isoformat(),
            "status": event_status,
            "actor_user_id": str(user_id),
        }).execute()


async def _record_operation(
    supabase: Client, user_id: UUID, req: OperationRequest, op_type: str, stock_delta: int | None = None
) -> OperationResultDTO:
    """Common logic for recording an operation."""
    await assert_can_access_tracked_medicine(supabase, user_id, req.tracked_medicine_id)

    dup = await _check_idempotency(supabase, req.operation_id)
    if dup:
        return dup

    log_data = {
        "owner_user_id": str(user_id),
        "tracked_medicine_id": str(req.tracked_medicine_id),
        "tracked_package_id": str(req.tracked_package_id) if req.tracked_package_id else None,
        "therapy_id": str(req.therapy_id) if req.therapy_id else None,
        "operation_id": str(req.operation_id),
        "type": op_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduled_due_at": req.scheduled_due_at.isoformat() if req.scheduled_due_at else None,
        "actor_user_id": str(user_id),
        "actor_device_id": req.actor_device_id,
        "source": req.source,
    }

    result = await _insert_log(supabase, log_data)
    if result.get("_duplicate"):
        return OperationResultDTO(operation_id=req.operation_id, was_duplicate=True, activity_log_id=UUID(result["id"]))

    # Adjust stock if applicable
    if stock_delta is not None and req.tracked_package_id:
        await _adjust_stock(supabase, req.tracked_medicine_id, req.tracked_package_id, stock_delta)

    return OperationResultDTO(
        operation_id=req.operation_id,
        was_duplicate=False,
        activity_log_id=UUID(result["id"]),
    )


async def record_intake(supabase: Client, user_id: UUID, req: OperationRequest) -> OperationResultDTO:
    result = await _record_operation(supabase, user_id, req, "intake", stock_delta=-1)
    if not result.was_duplicate and req.therapy_id and req.scheduled_due_at:
        await _upsert_dose_event(
            supabase, req.therapy_id, req.tracked_medicine_id,
            req.scheduled_due_at, "taken", user_id,
        )
    return result


async def record_purchase(supabase: Client, user_id: UUID, req: OperationRequest) -> OperationResultDTO:
    # Get units_per_package for stock increment
    units = 1
    if req.tracked_package_id:
        pkg = (
            supabase.table("tracked_packages")
            .select("units_per_package")
            .eq("id", str(req.tracked_package_id))
            .maybe_single()
            .execute()
        )
        if pkg and pkg.data:
            units = pkg.data.get("units_per_package", 1)
    return await _record_operation(
        supabase, user_id, req, "purchase", stock_delta=units,
    )


async def record_prescription_request(supabase: Client, user_id: UUID, req: OperationRequest) -> OperationResultDTO:
    return await _record_operation(supabase, user_id, req, "new_prescription_request")


async def record_prescription_received(supabase: Client, user_id: UUID, req: OperationRequest) -> OperationResultDTO:
    return await _record_operation(supabase, user_id, req, "new_prescription")


async def undo_operation(supabase: Client, user_id: UUID, req: UndoOperationRequest) -> OperationResultDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, req.tracked_medicine_id)

    dup = await _check_idempotency(supabase, req.operation_id)
    if dup:
        return dup

    # Find the original operation to determine undo type and reverse stock
    original = (
        supabase.table("activity_logs")
        .select("type, tracked_package_id")
        .eq("operation_id", str(req.reversal_of_operation_id))
        .maybe_single()
        .execute()
    )

    undo_type_map = {
        "intake": "intake_undo",
        "purchase": "purchase_undo",
        "new_prescription_request": "prescription_request_undo",
        "new_prescription": "prescription_received_undo",
    }
    undo_type = undo_type_map.get(original.data["type"], "intake_undo") if original and original.data else "intake_undo"

    log_data = {
        "owner_user_id": str(user_id),
        "tracked_medicine_id": str(req.tracked_medicine_id),
        "tracked_package_id": str(req.tracked_package_id) if req.tracked_package_id else None,
        "therapy_id": str(req.therapy_id) if req.therapy_id else None,
        "operation_id": str(req.operation_id),
        "reversal_of_operation_id": str(req.reversal_of_operation_id),
        "type": undo_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_user_id": str(user_id),
        "actor_device_id": req.actor_device_id,
        "source": req.source,
    }

    result = await _insert_log(supabase, log_data)
    if result.get("_duplicate"):
        return OperationResultDTO(operation_id=req.operation_id, was_duplicate=True, activity_log_id=UUID(result["id"]))

    # Reverse stock change
    if original and original.data and req.tracked_package_id:
        if original.data["type"] == "intake":
            await _adjust_stock(supabase, req.tracked_medicine_id, req.tracked_package_id, +1)
        elif original.data["type"] == "purchase":
            pkg = (
                supabase.table("tracked_packages")
                .select("units_per_package")
                .eq("id", str(req.tracked_package_id))
                .maybe_single()
                .execute()
            )
            units = pkg.data.get("units_per_package", 1) if pkg and pkg.data else 1
            await _adjust_stock(supabase, req.tracked_medicine_id, req.tracked_package_id, -units)

    return OperationResultDTO(
        operation_id=req.operation_id,
        was_duplicate=False,
        activity_log_id=UUID(result["id"]),
    )
