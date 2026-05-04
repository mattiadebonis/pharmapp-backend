"""
DSAR (Data Subject Access Request) service.

Implements:
- export_full_state(user_id): GDPR art. 15 — right to access.
- delete_account(user_id): GDPR art. 17 — right to erasure.
- list_access_log(user_id, since): art. 9 audit-trail readback.

All three are gated behind `request.state.user_id` extracted from the
verified JWT in the router; this layer trusts that the user_id is the
authenticated principal and does NOT re-read it from any client input.

Hard-delete model:
- We CASCADE on auth.users(id) for every PHI table. Calling
  `auth.admin.delete_user()` is therefore the single source of
  destruction; the row in `auth.users` going away takes everything else
  with it.
- Storage cleanup (medication photos, etc.) is handled separately
  because storage.objects do not cascade. Currently the app does not
  upload to storage so this is a TODO for Fase 4 if photos are added.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from supabase import Client

from app.services.bootstrap_service import get_bootstrap_data

logger = logging.getLogger("pharmapp")

EXPORT_SCHEMA_VERSION = "1.0"


async def export_full_state(supabase: Client, user_id: UUID) -> dict:
    """Return every row the user owns across all PHI tables.

    Reuses `get_bootstrap_data()` for the bulk of the dump, then extends
    with the long-tail data that the bootstrap endpoint truncates for
    performance reasons (full dose_events / measurements / activity_logs
    history rather than the last 500).
    """
    uid = str(user_id)
    bootstrap = await get_bootstrap_data(supabase, user_id)

    # Owned profile ids — used to fan out to nested tables.
    profile_ids = [p["id"] for p in bootstrap.get("profiles", [])]

    # Full history (no `.limit`) for tables that bootstrap truncates.
    if profile_ids:
        full_dose_events = (
            supabase.table("dose_events")
            .select("*")
            .in_("profile_id", profile_ids)
            .order("due_at", desc=True)
            .execute()
            .data
        )
        full_measurements = (
            supabase.table("measurements")
            .select("*")
            .in_("profile_id", profile_ids)
            .order("recorded_at", desc=True)
            .execute()
            .data
        )
    else:
        full_dose_events = []
        full_measurements = []

    full_activity_logs = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .execute()
        .data
    )

    # Flatten the nested medication payload from bootstrap into per-table
    # lists so the export is one-row-per-row of the source DB. This makes
    # the dump easier to re-import or analyse externally.
    medications: list[dict] = []
    dosing_schedules: list[dict] = []
    supplies: list[dict] = []
    prescriptions: list[dict] = []
    for med in bootstrap.get("medications", []):
        med_copy = {k: v for k, v in med.items() if k not in {"schedules", "supply", "prescriptions"}}
        medications.append(med_copy)
        dosing_schedules.extend(med.get("schedules", []) or [])
        if med.get("supply"):
            supplies.append(med["supply"])
        prescriptions.extend(med.get("prescriptions", []) or [])

    routine_steps: list[dict] = []
    routines_flat: list[dict] = []
    for r in bootstrap.get("routines", []):
        r_copy = {k: v for k, v in r.items() if k != "steps"}
        routines_flat.append(r_copy)
        routine_steps.extend(r.get("steps", []) or [])

    return {
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc),
        "schema_version": EXPORT_SCHEMA_VERSION,
        "profiles": bootstrap.get("profiles", []),
        "settings": bootstrap.get("settings"),
        "doctors": bootstrap.get("doctors", []),
        "medications": medications,
        "dosing_schedules": dosing_schedules,
        "supplies": supplies,
        "prescriptions": prescriptions,
        "prescription_requests": bootstrap.get("prescription_requests", []),
        "dose_events": full_dose_events,
        "routines": routines_flat,
        "routine_steps": routine_steps,
        "parameters": bootstrap.get("parameters", []),
        "measurements": full_measurements,
        "caregiver_relations": bootstrap.get("caregiver_relations", []),
        "pending_changes": bootstrap.get("pending_changes", []),
        "activity_logs": full_activity_logs,
        "device_tokens": bootstrap.get("device_tokens", []),
    }


async def delete_account(supabase: Client, user_id: UUID) -> dict:
    """Hard-delete the user. Cascades to every PHI table via FK.

    Steps:
      1. Best-effort cleanup of `device_tokens` so any pending APNs push
         is dropped immediately, before the auth row goes away. (FK
         cascade would handle this, but doing it eagerly closes the
         push channel sooner.)
      2. Call Supabase Auth admin API to remove the row in `auth.users`,
         which CASCADEs to every PHI table referencing it.

    We log only the user_id (UUID, opaque) — no PII fields.
    """
    uid = str(user_id)

    # Defensive: nuke device tokens up-front. RLS does not apply because
    # we use the service-role client. Errors are logged but never block
    # the deletion — the FK cascade will sweep them anyway.
    try:
        supabase.table("device_tokens").delete().eq("user_id", uid).execute()
    except Exception:  # noqa: BLE001 — see comment above
        logger.exception("dsar_device_token_cleanup_failed user_id=%s", uid)

    # auth.admin.delete_user requires service-role privileges. The
    # `supabase` client passed in here is already the service-role one
    # (see app/dependencies.py::get_supabase).
    try:
        supabase.auth.admin.delete_user(uid)
    except Exception:
        # Re-raise so the router returns 500 and the iOS client can
        # surface a "retry later" UX rather than silently leaving the
        # account half-deleted.
        logger.exception("dsar_auth_delete_failed user_id=%s", uid)
        raise

    logger.info("dsar_account_deleted user_id=%s", uid)

    return {
        "user_id": user_id,
        "deleted_at": datetime.now(timezone.utc),
        "status": "queued",
    }


async def list_access_log(
    supabase: Client,
    user_id: UUID,
    since: datetime | None = None,
) -> list[dict]:
    """Return audit-log rows where the user is the actor or target.

    Reads from `activity_logs` today; once migration 024 lands the
    dedicated `audit.access_log` schema, swap the source here without
    changing the DTO contract in app/schemas/dsar.py.
    """
    uid = str(user_id)

    query = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(2000)
    )
    if since is not None:
        query = query.gte("created_at", since.isoformat())

    rows = query.execute().data

    # Map activity_logs → AccessLogEntry shape. activity_logs has a
    # different column layout: it stores `action_type` rather than
    # `action`. We normalise here so the iOS client sees the same shape
    # before and after migration 024.
    return [
        {
            "id": row["id"],
            "actor_user_id": row.get("user_id") or user_id,
            "target_user_id": row.get("user_id") or user_id,
            "action": row.get("action_type") or "unknown",
            "resource_table": _resource_table_from_log(row),
            "resource_id": row.get("medication_id") or row.get("profile_id"),
            "via": "owner",
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _resource_table_from_log(row: dict) -> str | None:
    """Best-effort extraction of which table the log row touched."""
    if row.get("medication_id"):
        return "medications"
    if row.get("profile_id"):
        return "profiles"
    return None
