"""
DSAR (Data Subject Access Request) schemas.

Endpoints implementing GDPR articles 15 (access), 17 (erasure), and the
audit trail expected for art. 9 health data processing.

These schemas explicitly use `extra="forbid"` via PharmaBaseModel so
clients cannot smuggle extra fields, and `response_model` is enforced on
every router endpoint.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class ExportResponse(PharmaBaseModel):
    """Full data export for the authenticated user.

    Contains a JSON dump of every row owned by the user across all PHI
    tables. Generated on demand from the live database (no eventual
    consistency lag). Sized to fit in a single HTTP response; if the
    user has > 50k rows in any single table, a future iteration will
    return a Storage signed URL instead.
    """

    user_id: UUID
    generated_at: datetime
    schema_version: str  # bump on breaking changes to export shape

    # All user-owned data, grouped by table.
    profiles: list[dict[str, Any]]
    settings: dict[str, Any] | None
    doctors: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    dosing_schedules: list[dict[str, Any]]
    supplies: list[dict[str, Any]]
    prescriptions: list[dict[str, Any]]
    prescription_requests: list[dict[str, Any]]
    dose_events: list[dict[str, Any]]
    routines: list[dict[str, Any]]
    routine_steps: list[dict[str, Any]]
    parameters: list[dict[str, Any]]
    measurements: list[dict[str, Any]]
    caregiver_relations: list[dict[str, Any]]
    pending_changes: list[dict[str, Any]]
    activity_logs: list[dict[str, Any]]
    device_tokens: list[dict[str, Any]]


class DeleteAccountResponse(PharmaBaseModel):
    """Acknowledgement of an account deletion request.

    The deletion is asynchronous: the call returns 202 immediately and
    the back-end completes the cascade in the background. Clients are
    expected to invalidate their local session and clear caches as soon
    as they receive this response.
    """

    user_id: UUID
    deleted_at: datetime
    status: str  # always "queued"


class AccessLogEntry(PharmaBaseModel):
    """A single audit-log row.

    Currently sourced from the `activity_logs` table. Once migration 024
    introduces the dedicated `audit.access_log` schema, the service layer
    will switch over and the DTO shape stays stable.
    """

    id: UUID
    actor_user_id: UUID
    target_user_id: UUID | None
    action: str
    resource_table: str | None
    resource_id: UUID | None
    via: str | None  # owner | caregiver | admin
    created_at: datetime
