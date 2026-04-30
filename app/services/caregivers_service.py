import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INVITE_CODE_LENGTH = 6
INVITE_CODE_GROUP = 3
INVITE_EXPIRY_HOURS = 24
INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_PERMISSIONS = [
    "view_medications",
    "view_adherence_history",
    "receive_low_stock_notifications",
]


def _normalize_permissions(permissions: list[str] | dict[str, Any] | None) -> list[str]:
    if permissions is None:
        return DEFAULT_PERMISSIONS
    if isinstance(permissions, list):
        cleaned = [str(item).strip() for item in permissions if str(item).strip()]
        return sorted(set(cleaned)) if cleaned else DEFAULT_PERMISSIONS
    if isinstance(permissions, dict):
        enabled = [key for key, value in permissions.items() if bool(value)]
        cleaned = [item.strip() for item in enabled if item.strip()]
        return sorted(set(cleaned)) if cleaned else DEFAULT_PERMISSIONS
    return DEFAULT_PERMISSIONS


def _format_invite_code(raw_code: str) -> str:
    return f"{raw_code[:INVITE_CODE_GROUP]}-{raw_code[INVITE_CODE_GROUP:]}"


def _generate_invite_code() -> str:
    raw = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))
    return _format_invite_code(raw)


def _normalize_invite_code(input_code: str) -> str:
    raw = "".join(char for char in input_code.upper() if char.isalnum())
    if len(raw) != INVITE_CODE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "Invite code must be 6 alphanumeric characters"}},
        )
    return _format_invite_code(raw)


def _is_relation_visible(status_value: str) -> bool:
    return status_value not in {"revoked", "rejected"}


# ---------------------------------------------------------------------------
# Invite flow
# ---------------------------------------------------------------------------


async def create_invite(
    supabase: Client,
    patient_user_id: UUID,
    permissions: list[str] | dict[str, Any] | None = None,
) -> dict:
    """Create an invite code that a caregiver can accept.

    Returns the new ``caregiver_relations`` row (status='pending') with the
    invite code and expiry.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)
    normalized_permissions = _normalize_permissions(permissions)

    for _ in range(6):
        payload = {
            "patient_user_id": str(patient_user_id),
            "invite_code": _generate_invite_code(),
            "invite_expires_at": expires_at.isoformat(),
            "status": "pending",
            "permissions": normalized_permissions,
        }
        try:
            result = supabase.table("caregiver_relations").insert(payload).execute()
            return result.data[0]
        except Exception:
            # Retry with a new code in case of rare collision.
            continue

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": {"code": "internal_error", "message": "Unable to generate invite code"}},
    )


async def accept_invite(
    supabase: Client,
    caregiver_user_id: UUID,
    invite_code: str,
) -> dict:
    """Redeem an invite code as caregiver.

    - The invite must exist and be in ``pending`` status.
    - The invite must not have expired.
    - Sets ``caregiver_user_id`` and moves status to ``patient_confirmation``.
    - The patient must explicitly confirm before status becomes ``active``.
    """
    normalized_code = _normalize_invite_code(invite_code)
    row = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("invite_code", normalized_code)
        .eq("status", "pending")
        .execute()
    )
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Invite not found or already used"}},
        )
    relation = row.data[0]

    raw_expires = relation.get("invite_expires_at")
    try:
        expires_at = datetime.fromisoformat(str(raw_expires).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "invalid_invite", "message": "Invite metadata corrupt"}},
        ) from exc
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": "expired", "message": "Invite has expired"}},
        )

    if relation["patient_user_id"] == str(caregiver_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "Cannot be your own caregiver"}},
        )

    result = (
        supabase.table("caregiver_relations")
        .update(
            {
                "caregiver_user_id": str(caregiver_user_id),
                "status": "patient_confirmation",
            }
        )
        .eq("id", relation["id"])
        .execute()
    )
    return result.data[0]


async def confirm_invite(
    supabase: Client,
    patient_user_id: UUID,
    relation_id: UUID,
) -> dict:
    """Patient explicitly confirms a caregiver after code redemption."""
    uid = str(patient_user_id)
    row = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("id", str(relation_id))
        .eq("patient_user_id", uid)
        .eq("status", "patient_confirmation")
        .execute()
    )
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Relation not awaiting patient confirmation"}},
        )

    result = supabase.table("caregiver_relations").update({"status": "active"}).eq("id", str(relation_id)).execute()
    return result.data[0]


async def reject_invite(
    supabase: Client,
    patient_user_id: UUID,
    relation_id: UUID,
) -> dict:
    """Patient rejects a caregiver request before activation."""
    uid = str(patient_user_id)
    row = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("id", str(relation_id))
        .eq("patient_user_id", uid)
        .in_("status", ["pending", "patient_confirmation"])
        .execute()
    )
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Relation not pending"}},
        )

    result = supabase.table("caregiver_relations").update({"status": "rejected"}).eq("id", str(relation_id)).execute()
    return result.data[0]


async def revoke_relation(
    supabase: Client,
    user_id: UUID,
    relation_id: UUID,
) -> dict:
    """Revoke a caregiver relation.

    Either the patient or the caregiver can revoke.
    """
    uid = str(user_id)
    row = supabase.table("caregiver_relations").select("*").eq("id", str(relation_id)).execute()
    if not row.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Relation not found"}},
        )
    relation = row.data[0]
    if relation["patient_user_id"] != uid and relation.get("caregiver_user_id") != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Access denied"}},
        )
    result = supabase.table("caregiver_relations").update({"status": "revoked"}).eq("id", str(relation_id)).execute()
    return result.data[0]


# ---------------------------------------------------------------------------
# Listing relations
# ---------------------------------------------------------------------------


async def list_relations(
    supabase: Client,
    user_id: UUID,
    role: str | None = None,
) -> list[dict]:
    """List caregiver relations for the user.

    ``role`` can be ``"patient"`` (I am patient, listing my caregivers) or
    ``"caregiver"`` (I am caregiver, listing my patients). If omitted, returns
    both.
    """
    uid = str(user_id)
    if role == "patient":
        result = supabase.table("caregiver_relations").select("*").eq("patient_user_id", uid).execute()
        return [row for row in result.data if _is_relation_visible(row["status"])]
    if role == "caregiver":
        result = supabase.table("caregiver_relations").select("*").eq("caregiver_user_id", uid).execute()
        return [row for row in result.data if _is_relation_visible(row["status"])]

    patient_r = supabase.table("caregiver_relations").select("*").eq("patient_user_id", uid).execute()
    caregiver_r = supabase.table("caregiver_relations").select("*").eq("caregiver_user_id", uid).execute()
    seen_ids = set()
    combined: list[dict] = []
    for row in patient_r.data + caregiver_r.data:
        if row["id"] not in seen_ids and _is_relation_visible(row["status"]):
            seen_ids.add(row["id"])
            combined.append(row)
    return combined


async def list_patient_confirmations(
    supabase: Client,
    patient_user_id: UUID,
) -> list[dict]:
    """List caregiver links waiting for explicit patient consent."""
    uid = str(patient_user_id)
    result = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("patient_user_id", uid)
        .eq("status", "patient_confirmation")
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


# ---------------------------------------------------------------------------
# Pending changes (approval flow)
# ---------------------------------------------------------------------------


async def list_pending_changes(
    supabase: Client,
    user_id: UUID,
) -> list[dict]:
    """List all pending changes for relations where the user is the patient.

    Only the patient approves/rejects changes proposed by the caregiver.
    """
    uid = str(user_id)
    relations = (
        supabase.table("caregiver_relations").select("id").eq("patient_user_id", uid).eq("status", "active").execute()
    )
    if not relations.data:
        return []
    relation_ids = [r["id"] for r in relations.data]
    result = (
        supabase.table("pending_changes")
        .select("*")
        .in_("caregiver_relation_id", relation_ids)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


async def create_pending_change(
    supabase: Client,
    caregiver_user_id: UUID,
    relation_id: UUID,
    data,
) -> dict:
    """Create a pending change (proposed by a caregiver).

    The caregiver must belong to the relation and the relation must be active.
    """
    uid = str(caregiver_user_id)
    relation = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("id", str(relation_id))
        .eq("caregiver_user_id", uid)
        .eq("status", "active")
        .execute()
    )
    if not relation.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Not an active caregiver for this relation"}},
        )
    payload = data.model_dump(exclude_none=True)
    payload["caregiver_relation_id"] = str(relation_id)
    if "expires_at" not in payload:
        payload["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    elif hasattr(payload["expires_at"], "isoformat"):
        payload["expires_at"] = payload["expires_at"].isoformat()
    if payload.get("medication_id"):
        payload["medication_id"] = str(payload["medication_id"])
    result = supabase.table("pending_changes").insert(payload).execute()
    return result.data[0]


async def approve_change(
    supabase: Client,
    patient_user_id: UUID,
    change_id: UUID,
) -> dict:
    """Approve a pending change (patient only)."""
    return await _resolve_change(supabase, patient_user_id, change_id, "approved")


async def reject_change(
    supabase: Client,
    patient_user_id: UUID,
    change_id: UUID,
) -> dict:
    """Reject a pending change (patient only)."""
    return await _resolve_change(supabase, patient_user_id, change_id, "rejected")


async def _resolve_change(
    supabase: Client,
    patient_user_id: UUID,
    change_id: UUID,
    new_status: str,
) -> dict:
    """Approve or reject a pending change.

    Verifies the change belongs to a relation where the user is the patient.
    On approval, applies the change to the target tables via the
    appropriate service.
    """
    uid = str(patient_user_id)
    change = (
        supabase.table("pending_changes")
        .select("*, caregiver_relations!inner(patient_user_id)")
        .eq("id", str(change_id))
        .eq("status", "pending")
        .execute()
    )
    if not change.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Pending change not found"}},
        )
    if change.data[0]["caregiver_relations"]["patient_user_id"] != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Only the patient can approve/reject changes"}},
        )

    change_row = change.data[0]
    if new_status == "approved":
        await _apply_pending_change(supabase, patient_user_id, change_row)

    result = supabase.table("pending_changes").update({"status": new_status}).eq("id", str(change_id)).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Pending change not found"}},
        )
    return result.data[0]


async def _apply_pending_change(
    supabase: Client,
    patient_user_id: UUID,
    change_row: dict,
) -> None:
    """Apply the approved pending change to the target tables.

    Dispatches by `change_type`. For routine_*/parameter_*/measurement_*
    we delegate to the existing service layer using the patient's user_id
    so ownership checks pass.
    """
    change_type = change_row.get("change_type") or ""
    payload = change_row.get("payload") or {}

    # Routines
    if change_type == "routine_create":
        from app.schemas.routine import RoutineCreateRequest
        from app.services.routines_service import create_routine_with_steps

        await create_routine_with_steps(supabase, patient_user_id, RoutineCreateRequest(**payload))
        return

    if change_type == "routine_update":
        from app.schemas.routine import RoutineUpdateRequest
        from app.services.routines_service import update_routine

        rid = UUID(payload["routine_id"])
        body = {k: v for k, v in payload.items() if k != "routine_id"}
        await update_routine(supabase, patient_user_id, rid, RoutineUpdateRequest(**body))
        return

    if change_type == "routine_delete":
        from app.services.routines_service import delete_routine

        await delete_routine(
            supabase,
            patient_user_id,
            UUID(payload["routine_id"]),
            hard=bool(payload.get("hard", False)),
        )
        return

    # Routine steps
    if change_type == "routine_step_add":
        from app.schemas.routine_step import (
            EventStepData,
            MeasurementStepData,
            MedicationStepData,
            WaitStepData,
        )
        from app.services.routine_steps_service import add_step

        rid = UUID(payload["routine_id"])
        step_payload = payload["step_data"]
        step = _parse_step_data(
            step_payload,
            MedicationStepData,
            WaitStepData,
            EventStepData,
            MeasurementStepData,
        )
        await add_step(supabase, patient_user_id, rid, step, payload.get("position"))
        return

    if change_type == "routine_step_update":
        from app.schemas.routine_step import (
            EventStepData,
            MeasurementStepData,
            MedicationStepData,
            WaitStepData,
        )
        from app.services.routine_steps_service import update_step

        rid = UUID(payload["routine_id"])
        sid = UUID(payload["step_id"])
        step = _parse_step_data(
            payload["step_data"],
            MedicationStepData,
            WaitStepData,
            EventStepData,
            MeasurementStepData,
        )
        await update_step(supabase, patient_user_id, rid, sid, step)
        return

    if change_type == "routine_step_remove":
        from app.services.routine_steps_service import delete_step

        rid = UUID(payload["routine_id"])
        sid = UUID(payload["step_id"])
        await delete_step(supabase, patient_user_id, rid, sid)
        return

    if change_type == "routine_step_reorder":
        from app.services.routine_steps_service import reorder_steps

        rid = UUID(payload["routine_id"])
        await reorder_steps(supabase, patient_user_id, rid, payload["ordering"])
        return

    # Parameters
    if change_type == "parameter_create":
        from app.schemas.parameter import ParameterCreateRequest
        from app.services.parameters_service import create_custom_parameter

        await create_custom_parameter(supabase, patient_user_id, ParameterCreateRequest(**payload))
        return

    if change_type == "parameter_delete":
        from app.services.parameters_service import delete_custom_parameter

        await delete_custom_parameter(supabase, patient_user_id, UUID(payload["parameter_id"]))
        return

    # Measurements
    if change_type == "measurement_create":
        from app.schemas.measurement import MeasurementCreateRequest
        from app.services.measurements_service import create_measurement

        await create_measurement(supabase, patient_user_id, MeasurementCreateRequest(**payload))
        return

    # Unknown change_type: no-op (legacy / forward-compat).
    return


def _parse_step_data(payload: dict, *variants):
    """Parse the discriminated step payload by trying each variant — the
    discriminator is `step_type`."""
    step_type = payload.get("step_type")
    for v in variants:
        if v.model_fields["step_type"].default == step_type or (
            hasattr(v.model_fields["step_type"], "annotation")
            and step_type in (getattr(v.model_fields["step_type"].annotation, "__args__", [step_type]))
        ):
            return v(**payload)
    # Fallback: try each variant directly until one validates.
    last_err: Exception | None = None
    for v in variants:
        try:
            return v(**payload)
        except Exception as exc:
            last_err = exc
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": {
                "code": "validation_error",
                "message": f"Invalid step_data payload: {last_err}",
            }
        },
    )
