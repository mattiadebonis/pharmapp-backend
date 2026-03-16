import logging
from uuid import UUID

from supabase import Client

from app.schemas.bootstrap import BootstrapResponse, NotificationLockDTO
from app.schemas.cabinet import CabinetDTO, CabinetMembershipDTO
from app.schemas.custom_filter import CustomFilterDTO
from app.schemas.doctor import DoctorDTO
from app.schemas.dose_event import DoseEventDTO
from app.schemas.entry import MedicineEntryDTO
from app.schemas.log import ActivityLogDTO
from app.schemas.medicine import TrackedMedicineDTO, TrackedPackageDTO
from app.schemas.monitoring import MonitoringMeasurementDTO
from app.schemas.person import PersonDTO
from app.schemas.profile import ProfileDTO
from app.schemas.settings import UserSettingsDTO
from app.schemas.stock import StockDTO
from app.schemas.therapy import TherapyWithDosesDTO

logger = logging.getLogger("pharmapp")


async def fetch_bootstrap(supabase: Client, user_id: UUID) -> BootstrapResponse:
    """Fetch all user data for app startup."""
    uid = str(user_id)

    # Fetch all data (sequential for now, can be parallelized later)
    profile_r = supabase.table("profiles").select("*").eq("id", uid).single().execute()
    settings_r = supabase.table("user_settings").select("*").eq("user_id", uid).single().execute()
    people_r = supabase.table("people").select("*").eq("owner_user_id", uid).execute()
    doctors_r = supabase.table("doctors").select("*").eq("owner_user_id", uid).execute()

    # Cabinets: owned + accessible via membership
    cabinets_owned_r = supabase.table("cabinets").select("*").eq("owner_user_id", uid).execute()
    memberships_r = (
        supabase.table("cabinet_memberships")
        .select("*")
        .eq("user_id", uid)
        .eq("status", "active")
        .execute()
    )

    # Get all cabinet IDs the user can access
    owned_cabinet_ids = [c["id"] for c in cabinets_owned_r.data]
    member_cabinet_ids = [m["cabinet_id"] for m in memberships_r.data if m["cabinet_id"] not in owned_cabinet_ids]

    # Fetch shared cabinets the user is a member of (but doesn't own)
    shared_cabinets = []
    if member_cabinet_ids:
        shared_r = supabase.table("cabinets").select("*").in_("id", member_cabinet_ids).execute()
        shared_cabinets = shared_r.data

    all_cabinets = cabinets_owned_r.data + shared_cabinets
    all_cabinet_ids = [c["id"] for c in all_cabinets]

    # Also fetch memberships for owned cabinets (to show who else has access)
    all_memberships = memberships_r.data
    if owned_cabinet_ids:
        owned_memberships_r = (
            supabase.table("cabinet_memberships")
            .select("*")
            .in_("cabinet_id", owned_cabinet_ids)
            .execute()
        )
        # Merge without duplicates
        existing_ids = {m["id"] for m in all_memberships}
        for m in owned_memberships_r.data:
            if m["id"] not in existing_ids:
                all_memberships.append(m)

    # Tracked medicines: owned + in accessible cabinets
    medicines_r = supabase.table("tracked_medicines").select("*").eq("owner_user_id", uid).execute()
    shared_medicines = []
    if member_cabinet_ids:
        shared_med_r = (
            supabase.table("tracked_medicines")
            .select("*")
            .in_("cabinet_id", member_cabinet_ids)
            .execute()
        )
        owned_med_ids = {m["id"] for m in medicines_r.data}
        shared_medicines = [m for m in shared_med_r.data if m["id"] not in owned_med_ids]

    all_medicines = medicines_r.data + shared_medicines
    all_medicine_ids = [m["id"] for m in all_medicines]

    # Fetch related data for all accessible medicines
    empty = type("R", (), {"data": []})()
    if all_medicine_ids:
        packages_r = (
            supabase.table("tracked_packages")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
        entries_r = (
            supabase.table("medicine_entries")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
        therapies_r = (
            supabase.table("therapies")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
        stocks_r = (
            supabase.table("stocks")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
        dose_events_r = (
            supabase.table("dose_events")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
        monitoring_r = (
            supabase.table("monitoring_measurements")
            .select("*")
            .in_("tracked_medicine_id", all_medicine_ids)
            .execute()
        )
    else:
        packages_r = empty
        entries_r = empty
        therapies_r = empty
        stocks_r = empty
        dose_events_r = empty
        monitoring_r = empty

    logs_r = (
        supabase.table("activity_logs")
        .select("*")
        .eq("owner_user_id", uid)
        .order("timestamp", desc=True)
        .limit(500)
        .execute()
    )
    try:
        custom_filters_r = (
            supabase.table("custom_filters")
            .select("*")
            .eq("owner_user_id", uid)
            .is_("deleted_at", "null")
            .order("position")
            .execute()
        )
    except Exception:
        logger.warning("custom_filters table not found, skipping")
        custom_filters_r = empty
    if all_cabinet_ids:
        notification_locks_r = (
            supabase.table("notification_locks")
            .select("*")
            .in_("cabinet_id", all_cabinet_ids)
            .execute()
        )
    else:
        notification_locks_r = empty

    # Fetch therapy doses for all therapies
    therapy_ids = [t["id"] for t in therapies_r.data]
    if therapy_ids:
        doses_r = (
            supabase.table("therapy_doses")
            .select("*")
            .in_("therapy_id", therapy_ids)
            .order("sort_order")
            .execute()
        )
    else:
        doses_r = type("R", (), {"data": []})()

    # Group doses by therapy_id
    doses_by_therapy: dict[str, list] = {}
    for d in doses_r.data:
        doses_by_therapy.setdefault(d["therapy_id"], []).append(d)

    # Build therapies with doses
    therapies_with_doses = []
    for t in therapies_r.data:
        therapy_doses = doses_by_therapy.get(t["id"], [])
        t_dto = {**t, "doses": therapy_doses}
        therapies_with_doses.append(TherapyWithDosesDTO.model_validate(t_dto))

    return BootstrapResponse(
        profile=ProfileDTO.model_validate(profile_r.data),
        settings=UserSettingsDTO.model_validate(settings_r.data),
        people=[PersonDTO.model_validate(p) for p in people_r.data],
        doctors=[DoctorDTO.model_validate(d) for d in doctors_r.data],
        cabinets=[CabinetDTO.model_validate(c) for c in all_cabinets],
        cabinet_memberships=[CabinetMembershipDTO.model_validate(m) for m in all_memberships],
        tracked_medicines=[TrackedMedicineDTO.model_validate(m) for m in all_medicines],
        tracked_packages=[TrackedPackageDTO.model_validate(p) for p in packages_r.data],
        medicine_entries=[MedicineEntryDTO.model_validate(e) for e in entries_r.data],
        therapies=therapies_with_doses,
        stocks=[StockDTO.model_validate(s) for s in stocks_r.data],
        activity_logs=[ActivityLogDTO.model_validate(log) for log in logs_r.data],
        dose_events=[DoseEventDTO.model_validate(de) for de in dose_events_r.data],
        monitoring_measurements=[MonitoringMeasurementDTO.model_validate(m) for m in monitoring_r.data],
        custom_filters=[CustomFilterDTO.model_validate(cf) for cf in custom_filters_r.data],
        notification_locks=[NotificationLockDTO.model_validate(nl) for nl in notification_locks_r.data],
    )
