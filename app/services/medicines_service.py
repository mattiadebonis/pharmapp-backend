from uuid import UUID

from supabase import Client

from app.schemas.medicine import (
    CabinetMoveRequest,
    CreateMedicineFromCatalogRequest,
    LabelsUpdateRequest,
    MedicineUpdateRequest,
    PackageCreateRequest,
    StockThresholdUpdateRequest,
    TrackedMedicineDTO,
    TrackedMedicineWithPackagesDTO,
    TrackedPackageDTO,
)
from app.services.authorization import assert_can_access_tracked_medicine, assert_owner


async def list_medicines(supabase: Client, user_id: UUID) -> list[TrackedMedicineWithPackagesDTO]:
    uid = str(user_id)
    meds_r = supabase.table("tracked_medicines").select("*").eq("owner_user_id", uid).execute()
    if not meds_r.data:
        return []
    med_ids = [m["id"] for m in meds_r.data]
    pkgs_r = supabase.table("tracked_packages").select("*").in_("tracked_medicine_id", med_ids).execute()

    pkgs_by_med: dict[str, list] = {}
    for p in pkgs_r.data:
        pkgs_by_med.setdefault(p["tracked_medicine_id"], []).append(p)

    return [
        TrackedMedicineWithPackagesDTO.model_validate({**m, "packages": pkgs_by_med.get(m["id"], [])})
        for m in meds_r.data
    ]


async def get_medicine_detail(supabase: Client, user_id: UUID, medicine_id: UUID) -> TrackedMedicineWithPackagesDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    mid = str(medicine_id)
    med_r = supabase.table("tracked_medicines").select("*").eq("id", mid).single().execute()
    pkgs_r = supabase.table("tracked_packages").select("*").eq("tracked_medicine_id", mid).execute()
    return TrackedMedicineWithPackagesDTO.model_validate({**med_r.data, "packages": pkgs_r.data})


async def create_medicine(
    supabase: Client, user_id: UUID, data: CreateMedicineFromCatalogRequest
) -> TrackedMedicineWithPackagesDTO:
    uid = str(user_id)
    med_data = {
        "owner_user_id": uid,
        "cabinet_id": str(data.cabinet_id) if data.cabinet_id else None,
        "catalog_country": data.catalog_country,
        "catalog_source": data.catalog_source,
        "catalog_product_key": data.catalog_product_key,
        "catalog_family_key": data.catalog_family_key,
        "name": data.name,
        "principle": data.principle,
        "requires_prescription": data.requires_prescription,
        "labels": data.labels,
        "custom_stock_threshold": data.custom_stock_threshold,
        "manual_intake_registration": data.manual_intake_registration,
        "catalog_snapshot": data.catalog_snapshot,
    }
    med_r = supabase.table("tracked_medicines").insert(med_data).execute()
    medicine_id = med_r.data[0]["id"]

    pkg_data = {
        "tracked_medicine_id": medicine_id,
        "catalog_country": data.catalog_country,
        "catalog_source": data.catalog_source,
        "catalog_package_key": data.catalog_package_key,
        "catalog_code": data.catalog_code,
        "tipologia": data.tipologia,
        "units_per_package": data.units_per_package,
        "unit_value": data.unit_value,
        "unit_name": data.unit_name,
        "volume": data.volume,
        "package_snapshot": data.package_snapshot,
    }
    pkg_r = supabase.table("tracked_packages").insert(pkg_data).execute()
    package_id = pkg_r.data[0]["id"]

    # Create medicine entry
    supabase.table("medicine_entries").insert({
        "tracked_medicine_id": medicine_id,
        "tracked_package_id": package_id,
        "cabinet_id": str(data.cabinet_id) if data.cabinet_id else None,
    }).execute()

    # Create initial stock
    supabase.table("stocks").insert({
        "tracked_medicine_id": medicine_id,
        "tracked_package_id": package_id,
        "context_key": "default",
        "stock_units": 0,
    }).execute()

    return TrackedMedicineWithPackagesDTO.model_validate({**med_r.data[0], "packages": [pkg_r.data[0]]})


async def update_medicine(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: MedicineUpdateRequest
) -> TrackedMedicineDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    update_data = data.model_dump(exclude_unset=True)
    result = (
        supabase.table("tracked_medicines")
        .update(update_data)
        .eq("id", str(medicine_id))
        .execute()
    )
    return TrackedMedicineDTO.model_validate(result.data[0])


async def delete_medicine(supabase: Client, user_id: UUID, medicine_id: UUID) -> None:
    await assert_owner(supabase, user_id, "tracked_medicines", medicine_id)
    supabase.table("tracked_medicines").delete().eq("id", str(medicine_id)).execute()


async def update_labels(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: LabelsUpdateRequest
) -> TrackedMedicineDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    result = (
        supabase.table("tracked_medicines")
        .update({"labels": data.labels})
        .eq("id", str(medicine_id))
        .execute()
    )
    return TrackedMedicineDTO.model_validate(result.data[0])


async def update_stock_threshold(
    supabase: Client,
    user_id: UUID,
    medicine_id: UUID,
    data: StockThresholdUpdateRequest,
) -> TrackedMedicineDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    result = (
        supabase.table("tracked_medicines")
        .update({"custom_stock_threshold": data.custom_stock_threshold})
        .eq("id", str(medicine_id))
        .execute()
    )
    return TrackedMedicineDTO.model_validate(result.data[0])


async def move_to_cabinet(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: CabinetMoveRequest
) -> TrackedMedicineDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    cabinet_id = str(data.cabinet_id) if data.cabinet_id else None
    result = (
        supabase.table("tracked_medicines")
        .update({"cabinet_id": cabinet_id})
        .eq("id", str(medicine_id))
        .execute()
    )
    # Also update entries
    (
        supabase.table("medicine_entries")
        .update({"cabinet_id": cabinet_id})
        .eq("tracked_medicine_id", str(medicine_id))
        .execute()
    )
    return TrackedMedicineDTO.model_validate(result.data[0])


async def create_package(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: PackageCreateRequest
) -> TrackedPackageDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    insert_data = data.model_dump()
    insert_data["tracked_medicine_id"] = str(medicine_id)
    result = supabase.table("tracked_packages").insert(insert_data).execute()
    return TrackedPackageDTO.model_validate(result.data[0])


async def delete_package(
    supabase: Client, user_id: UUID, medicine_id: UUID, package_id: UUID
) -> None:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    supabase.table("tracked_packages").delete().eq("id", str(package_id)).execute()
