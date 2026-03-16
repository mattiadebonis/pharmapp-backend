from datetime import datetime
from uuid import UUID

from supabase import Client

from app.schemas.log import ActivityLogDTO


async def list_logs(
    supabase: Client,
    user_id: UUID,
    medicine_id: UUID | None,
    since: datetime | None,
    until: datetime | None,
    log_type: str | None,
    limit: int,
    offset: int,
) -> tuple[list[ActivityLogDTO], int]:
    """List activity logs with filters and pagination."""
    query = supabase.table("activity_logs").select("*", count="exact").eq("owner_user_id", str(user_id))
    if medicine_id:
        query = query.eq("tracked_medicine_id", str(medicine_id))
    if since:
        query = query.gte("timestamp", since.isoformat())
    if until:
        query = query.lte("timestamp", until.isoformat())
    if log_type:
        query = query.eq("type", log_type)
    query = query.order("timestamp", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    logs = [ActivityLogDTO.model_validate(row) for row in result.data]
    total = result.count or 0
    return logs, total
