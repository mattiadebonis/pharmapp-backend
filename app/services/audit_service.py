"""
Audit service — write rows to `audit.access_log` (migration 024).

Used by the FastAPI service layer whenever a user touches PHI through
a path that is NOT covered by the trivial RLS audit (i.e. anything
that runs through the backend with service_role rather than reaching
PostgREST directly).

Design notes:
- We log via `service_role` because the backend's Supabase client is
  always created with the service-role key. This bypasses RLS, but the
  caller is expected to pass an `actor_user_id` extracted from the
  verified JWT — never from request body/query.
- Failures here are logged but never propagated. Audit must never block
  the user-facing operation; the trade-off is that a flaky DB connection
  could silently drop audit rows. We accept that and rely on application
  metrics to catch sustained losses.
- The schema is INSERT-only (per migration 024); UPDATE/DELETE are
  rejected by trigger. This file deliberately exposes no `update`/
  `delete` helper.
"""

import logging
from typing import Literal
from uuid import UUID

from supabase import Client

logger = logging.getLogger("pharmapp")

Action = Literal["select", "insert", "update", "delete"]
Via = Literal["owner", "caregiver", "admin"]


async def log_access(
    supabase: Client,
    *,
    actor_user_id: UUID,
    target_user_id: UUID,
    resource_table: str,
    action: Action,
    via: Via,
    resource_id: UUID | None = None,
    request_id: str | None = None,
) -> None:
    """Best-effort INSERT into `audit.access_log`.

    Never raises: a failure to record audit must not abort the user
    operation. We log the exception so monitoring can pick it up.
    """
    try:
        # We have to use the schema-qualified name. The supabase-py
        # client default schema is `public`; explicit schema selection
        # is supported via `.schema('audit').table('access_log')`.
        supabase.schema("audit").table("access_log").insert(
            {
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(target_user_id),
                "resource_table": resource_table,
                "resource_id": str(resource_id) if resource_id else None,
                "action": action,
                "via": via,
                "request_id": request_id,
            }
        ).execute()
    except Exception:  # noqa: BLE001 — explicitly swallow, see docstring
        logger.exception(
            "audit_log_write_failed actor=%s target=%s table=%s action=%s",
            actor_user_id,
            target_user_id,
            resource_table,
            action,
        )
