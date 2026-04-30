import logging
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

logger = logging.getLogger("pharmapp")


async def get_bootstrap_data(supabase: Client, user_id: UUID) -> dict:
    """Fetch ALL user data in a single call for app startup / sync.

    Returns a dict with the following keys:
    - profiles
    - medications (with nested dosing_schedules, supply, prescriptions)
    - doctors
    - settings
    - dose_events (recent, last 30 days)
    - activity_logs (recent, last 500)
    - caregiver_relations (active)
    - device_tokens
    """
    uid = str(user_id)

    # ---------------------------------------------------------------
    # 1. Profiles
    # ---------------------------------------------------------------
    profiles_r = (
        supabase.table("profiles")
        .select("*")
        .eq("user_id", uid)
        .execute()
    )
    profiles = profiles_r.data
    profile_ids = [p["id"] for p in profiles]

    # ---------------------------------------------------------------
    # 2. Settings (get or create)
    # ---------------------------------------------------------------
    settings_r = (
        supabase.table("user_settings")
        .select("*")
        .eq("user_id", uid)
        .execute()
    )
    if settings_r.data:
        settings = settings_r.data[0]
    else:
        # Create default settings
        settings = (
            supabase.table("user_settings")
            .insert({
                "user_id": uid,
                "catalog_country": "it",
                "default_refill_threshold": 7,
                "default_tracking_mode": "passive",
                "default_snooze_minutes": 10,
                "grace_minutes": 120,
                "notify_caregivers": True,
                "notifications_enabled": True,
                "refill_alerts_enabled": True,
                "biometrics_enabled": False,
                "face_id_sensitive_actions": False,
                "anonymous_notifications": False,
                "hide_medication_names": False,
            })
            .execute()
        ).data[0]

    # ---------------------------------------------------------------
    # 3. Doctors
    # ---------------------------------------------------------------
    doctors_r = (
        supabase.table("doctors")
        .select("*")
        .eq("user_id", uid)
        .execute()
    )
    doctors = doctors_r.data

    # ---------------------------------------------------------------
    # 4. Medications + related entities
    # ---------------------------------------------------------------
    if profile_ids:
        medications_r = (
            supabase.table("medications")
            .select("*")
            .in_("profile_id", profile_ids)
            .execute()
        )
    else:
        medications_r = type("R", (), {"data": []})()

    medications = medications_r.data
    medication_ids = [m["id"] for m in medications]

    # Fetch related entities for all medications in bulk
    empty = type("R", (), {"data": []})()

    if medication_ids:
        schedules_r = (
            supabase.table("dosing_schedules")
            .select("*")
            .in_("medication_id", medication_ids)
            .execute()
        )
        supplies_r = (
            supabase.table("supplies")
            .select("*")
            .in_("medication_id", medication_ids)
            .execute()
        )
        prescriptions_r = (
            supabase.table("prescriptions")
            .select("*")
            .in_("medication_id", medication_ids)
            .execute()
        )
        prescription_requests_r = (
            supabase.table("prescription_requests")
            .select("*")
            .in_("medication_id", medication_ids)
            .order("sent_at", desc=True)
            .execute()
        )
    else:
        schedules_r = empty
        supplies_r = empty
        prescriptions_r = empty
        prescription_requests_r = empty

    # Group by medication_id
    schedules_by_med: dict[str, list] = {}
    for s in schedules_r.data:
        schedules_by_med.setdefault(s["medication_id"], []).append(s)

    supplies_by_med: dict[str, dict] = {}
    for s in supplies_r.data:
        supplies_by_med[s["medication_id"]] = s

    prescriptions_by_med: dict[str, list] = {}
    for p in prescriptions_r.data:
        prescriptions_by_med.setdefault(p["medication_id"], []).append(p)

    # Enrich medications with nested data
    medications_with_details = []
    for med in medications:
        mid = med["id"]
        medications_with_details.append({
            **med,
            "schedules": schedules_by_med.get(mid, []),
            "supply": supplies_by_med.get(mid),
            "prescriptions": prescriptions_by_med.get(mid, []),
        })

    # ---------------------------------------------------------------
    # 5. Dose events (recent)
    # ---------------------------------------------------------------
    if profile_ids:
        dose_events_r = (
            supabase.table("dose_events")
            .select("*")
            .in_("profile_id", profile_ids)
            .order("due_at", desc=True)
            .limit(500)
            .execute()
        )
    else:
        dose_events_r = empty

    # ---------------------------------------------------------------
    # 6. Activity logs (recent)
    # ---------------------------------------------------------------
    activity_logs_r = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )

    # ---------------------------------------------------------------
    # 7. Caregiver relations (active + pending)
    # ---------------------------------------------------------------
    caregiver_patient_r = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("patient_user_id", uid)
        .neq("status", "revoked")
        .execute()
    )
    caregiver_carer_r = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("caregiver_user_id", uid)
        .neq("status", "revoked")
        .execute()
    )
    # Merge without duplicates
    seen_ids: set[str] = set()
    caregiver_relations: list[dict] = []
    for row in caregiver_patient_r.data + caregiver_carer_r.data:
        if row["id"] not in seen_ids:
            seen_ids.add(row["id"])
            caregiver_relations.append(row)

    # ---------------------------------------------------------------
    # 8. Pending caregiver confirmations/changes for patient
    # ---------------------------------------------------------------
    caregiver_relation_ids_for_patient = [
        row["id"]
        for row in caregiver_relations
        if row.get("patient_user_id") == uid and row.get("status") == "active"
    ]
    if caregiver_relation_ids_for_patient:
        pending_changes_r = (
            supabase.table("pending_changes")
            .select("*")
            .in_("caregiver_relation_id", caregiver_relation_ids_for_patient)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
    else:
        pending_changes_r = empty

    # ---------------------------------------------------------------
    # 9. Device tokens
    # ---------------------------------------------------------------
    device_tokens_r = (
        supabase.table("device_tokens")
        .select("*")
        .eq("user_id", uid)
        .execute()
    )

    # ---------------------------------------------------------------
    # 10. Routines (+ inline steps)
    # ---------------------------------------------------------------
    if profile_ids:
        routines_r = (
            supabase.table("routines")
            .select("*")
            .in_("profile_id", profile_ids)
            .execute()
        )
        routine_ids = [r["id"] for r in routines_r.data]
        if routine_ids:
            routine_steps_r = (
                supabase.table("routine_steps")
                .select("*")
                .in_("routine_id", routine_ids)
                .order("position")
                .execute()
            )
        else:
            routine_steps_r = empty
        steps_by_routine: dict[str, list] = {}
        for s in routine_steps_r.data:
            steps_by_routine.setdefault(s["routine_id"], []).append(s)
        routines_with_steps = [
            {**r, "steps": steps_by_routine.get(r["id"], [])}
            for r in routines_r.data
        ]
    else:
        routines_with_steps = []

    # ---------------------------------------------------------------
    # Assemble response
    # ---------------------------------------------------------------
    return {
        "profiles": profiles,
        "settings": settings,
        "doctors": doctors,
        "medications": medications_with_details,
        "dose_events": dose_events_r.data,
        "activity_logs": activity_logs_r.data,
        "caregiver_relations": caregiver_relations,
        "pending_changes": pending_changes_r.data,
        "device_tokens": device_tokens_r.data,
        "prescription_requests": prescription_requests_r.data,
        "routines": routines_with_steps,
    }
