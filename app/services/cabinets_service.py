from uuid import UUID

from supabase import Client

from app.schemas.cabinet import (
    CabinetCreateRequest,
    CabinetDTO,
    CabinetMembershipCreateRequest,
    CabinetMembershipDTO,
    CabinetMembershipUpdateRequest,
    CabinetUpdateRequest,
    CabinetWithMembershipsDTO,
)
from app.services.authorization import assert_owner


async def list_cabinets(
    supabase: Client, user_id: UUID
) -> list[CabinetWithMembershipsDTO]:
    uid = str(user_id)
    # Owned cabinets
    owned_r = (
        supabase.table("cabinets")
        .select("*")
        .eq("owner_user_id", uid)
        .execute()
    )
    # Cabinets via membership
    memberships_r = (
        supabase.table("cabinet_memberships")
        .select("*")
        .eq("user_id", uid)
        .eq("status", "active")
        .execute()
    )
    member_cabinet_ids = [m["cabinet_id"] for m in memberships_r.data]
    owned_ids = {c["id"] for c in owned_r.data}
    extra_ids = [
        cid for cid in member_cabinet_ids if cid not in owned_ids
    ]

    shared = []
    if extra_ids:
        shared_r = (
            supabase.table("cabinets")
            .select("*")
            .in_("id", extra_ids)
            .execute()
        )
        shared = shared_r.data

    all_cabinets = owned_r.data + shared
    all_cabinet_ids = [c["id"] for c in all_cabinets]

    # Fetch all memberships for these cabinets
    all_memberships = []
    if all_cabinet_ids:
        all_memberships_r = (
            supabase.table("cabinet_memberships")
            .select("*")
            .in_("cabinet_id", all_cabinet_ids)
            .execute()
        )
        all_memberships = all_memberships_r.data

    # Group memberships by cabinet_id
    memberships_map: dict[str, list] = {}
    for m in all_memberships:
        memberships_map.setdefault(m["cabinet_id"], []).append(m)

    result = []
    for c in all_cabinets:
        cms = memberships_map.get(c["id"], [])
        result.append(
            CabinetWithMembershipsDTO.model_validate(
                {**c, "memberships": cms}
            )
        )
    return result


async def create_cabinet(supabase: Client, user_id: UUID, data: CabinetCreateRequest) -> CabinetDTO:
    insert_data = data.model_dump()
    insert_data["owner_user_id"] = str(user_id)
    result = supabase.table("cabinets").insert(insert_data).execute()
    cabinet_id = result.data[0]["id"]
    # Create owner membership
    supabase.table("cabinet_memberships").insert({
        "cabinet_id": cabinet_id,
        "user_id": str(user_id),
        "role": "owner",
        "status": "active",
    }).execute()
    return CabinetDTO.model_validate(result.data[0])


async def update_cabinet(
    supabase: Client, user_id: UUID, cabinet_id: UUID, data: CabinetUpdateRequest
) -> CabinetDTO:
    await assert_owner(supabase, user_id, "cabinets", cabinet_id)
    update_data = data.model_dump(exclude_unset=True)
    result = (
        supabase.table("cabinets")
        .update(update_data)
        .eq("id", str(cabinet_id))
        .execute()
    )
    return CabinetDTO.model_validate(result.data[0])


async def delete_cabinet(
    supabase: Client, user_id: UUID, cabinet_id: UUID, move_to: UUID | None = None
) -> None:
    await assert_owner(supabase, user_id, "cabinets", cabinet_id)
    cid = str(cabinet_id)
    if move_to:
        # Move medicines to another cabinet
        (
            supabase.table("tracked_medicines")
            .update({"cabinet_id": str(move_to)})
            .eq("cabinet_id", cid)
            .execute()
        )
        (
            supabase.table("medicine_entries")
            .update({"cabinet_id": str(move_to)})
            .eq("cabinet_id", cid)
            .execute()
        )
    supabase.table("cabinets").delete().eq("id", cid).execute()


async def create_membership(
    supabase: Client, user_id: UUID, cabinet_id: UUID, data: CabinetMembershipCreateRequest
) -> CabinetMembershipDTO:
    await assert_owner(supabase, user_id, "cabinets", cabinet_id)
    insert_data = data.model_dump()
    insert_data["cabinet_id"] = str(cabinet_id)
    insert_data["user_id"] = str(data.user_id)
    insert_data["status"] = "invited"
    result = supabase.table("cabinet_memberships").insert(insert_data).execute()
    return CabinetMembershipDTO.model_validate(result.data[0])


async def update_membership(
    supabase: Client,
    user_id: UUID,
    cabinet_id: UUID,
    membership_id: UUID,
    data: CabinetMembershipUpdateRequest,
) -> CabinetMembershipDTO:
    await assert_owner(supabase, user_id, "cabinets", cabinet_id)
    update_data = data.model_dump(exclude_unset=True)
    result = (
        supabase.table("cabinet_memberships")
        .update(update_data)
        .eq("id", str(membership_id))
        .execute()
    )
    return CabinetMembershipDTO.model_validate(result.data[0])


async def delete_membership(
    supabase: Client, user_id: UUID, cabinet_id: UUID, membership_id: UUID
) -> None:
    await assert_owner(supabase, user_id, "cabinets", cabinet_id)
    (
        supabase.table("cabinet_memberships")
        .delete()
        .eq("id", str(membership_id))
        .execute()
    )
