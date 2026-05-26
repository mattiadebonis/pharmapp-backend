"""Schema validation coverage for routers without dedicated tests.

Pure-logic pydantic checks — no DB required. Pattern mirrors
``test_routines.py``: build a happy-path payload, then assert the validator
rejects each obvious edge case (missing required, wrong enum, bad shape).

Each grouped class targets one schema family. Add a new class when a new
router lands."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.activity_log import ActivityLogCreateRequest
from app.schemas.caregiver import (
    CaregiverAcceptRequest,
    CaregiverInviteRequest,
    PendingChangeCreateRequest,
)
from app.schemas.device_token import DeviceTokenCreateRequest
from app.schemas.doctor import DoctorCreateRequest, DoctorUpdateRequest
from app.schemas.dose_event import DoseEventCreateRequest, DoseEventUpdateRequest
from app.schemas.dosing_schedule import DosingScheduleCreateRequest
from app.schemas.medication import (
    MedicationCreateRequest,
    MedicationDTO,
    MedicationUpdateRequest,
)
from app.schemas.prescription import (
    PrescriptionCreateRequest,
    PrescriptionUpdateRequest,
)
from app.schemas.prescription_request import (
    PrescriptionRequestCreateRequest,
    PrescriptionRequestUpdateRequest,
)
from app.schemas.profile import (
    AnchorSlotDTO,
    ProfileAnchorDTO,
    ProfileCreateRequest,
    ProfileDTO,
    ProfileUpdateRequest,
)
from app.schemas.settings import UserSettingsUpdateRequest
from app.schemas.subscription import SubscriptionStateDTO, TransactionVerifyRequest
from app.schemas.supply import SupplyCreateRequest, SupplyUpdateRequest

# ---------------------------------------------------------------------------
# Medications + injection_sites
# ---------------------------------------------------------------------------


class TestMedications:
    def test_create_minimal(self):
        req = MedicationCreateRequest(profile_id=uuid4(), name="Tachipirina")
        assert req.tracking_mode == "passive"
        assert req.injection_sites is None

    def test_create_rejects_invalid_tracking_mode(self):
        with pytest.raises(ValidationError):
            MedicationCreateRequest(profile_id=uuid4(), name="X", tracking_mode="manual")

    def test_create_accepts_injection_sites(self):
        req = MedicationCreateRequest(
            profile_id=uuid4(),
            name="Enantone",
            injection_sites=[
                {"id": "addome-sx", "name": "Addome sinistro"},
                {"id": "braccio-dx", "name": "Braccio destro", "zone": "tricipite"},
            ],
        )
        assert len(req.injection_sites) == 2
        assert req.injection_sites[1].zone == "tricipite"

    def test_dto_round_trip(self):
        now = datetime.now(timezone.utc)
        dto = MedicationDTO(
            id=uuid4(),
            profile_id=uuid4(),
            name="Tachipirina",
            created_at=now,
            updated_at=now,
        )
        assert dto.injection_sites == []
        assert dto.tracking_mode == "passive"

    def test_update_partial_only(self):
        req = MedicationUpdateRequest(is_paused=True)
        assert req.is_paused is True
        assert req.name is None


# ---------------------------------------------------------------------------
# Dose events + injection_site
# ---------------------------------------------------------------------------


class TestDoseEvents:
    def _payload(self, **overrides):
        base = {
            "medication_id": uuid4(),
            "profile_id": uuid4(),
            "due_at": datetime.now(timezone.utc),
        }
        base.update(overrides)
        return base

    def test_default_status(self):
        req = DoseEventCreateRequest(**self._payload())
        assert req.status == "pending"
        assert req.snooze_count == 0

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            DoseEventCreateRequest(**self._payload(status="finished"))

    def test_accepts_injection_site(self):
        req = DoseEventCreateRequest(
            **self._payload(status="taken", injection_site="site-default-addome-sx")
        )
        assert req.injection_site == "site-default-addome-sx"

    def test_update_request_can_clear_status(self):
        req = DoseEventUpdateRequest(status="snoozed", snooze_count=3, injection_site="x")
        assert req.status == "snoozed"
        assert req.injection_site == "x"


# ---------------------------------------------------------------------------
# Profiles + connection_status
# ---------------------------------------------------------------------------


class TestProfiles:
    def test_create_minimal(self):
        req = ProfileCreateRequest(profile_type="own", display_name="Mattia")
        assert req.connection_status is None

    def test_rejects_invalid_profile_type(self):
        with pytest.raises(ValidationError):
            ProfileCreateRequest(profile_type="visitor", display_name="X")

    def test_rejects_invalid_connection_status(self):
        with pytest.raises(ValidationError):
            ProfileCreateRequest(
                profile_type="assisted",
                display_name="Maria",
                connection_status="frozen",
            )

    def test_dto_with_managed_fields(self):
        now = datetime.now(timezone.utc)
        dto = ProfileDTO(
            id=uuid4(),
            user_id=uuid4(),
            profile_type="assisted",
            display_name="Maria",
            relation_label="madre",
            connection_status="pending",
            created_at=now,
            updated_at=now,
        )
        assert dto.relation_label == "madre"
        assert dto.connection_status == "pending"

    def test_update_partial(self):
        req = ProfileUpdateRequest(display_name="Mario")
        assert req.display_name == "Mario"
        assert req.profile_type is None

    def test_anchors_default_in_dto(self):
        # I profili senza colonna `anchors` (DB pre-migration oppure
        # bootstrap legacy) devono accettare il default factory: 5 anchor
        # con UN solo slot ciascuno su tutti i 7 giorni.
        now = datetime.now(timezone.utc)
        dto = ProfileDTO(
            id=uuid4(),
            user_id=uuid4(),
            profile_type="own",
            display_name="Mattia",
            created_at=now,
            updated_at=now,
        )
        assert len(dto.anchors) == 5
        assert [a.kind for a in dto.anchors] == [
            "wake",
            "breakfast",
            "lunch",
            "dinner",
            "night",
        ]
        wake = dto.anchors[0]
        assert len(wake.slots) == 1
        assert wake.slots[0].time == "06:30"
        assert wake.slots[0].weekdays == [1, 2, 3, 4, 5, 6, 7]

    def test_anchors_round_trip_with_multi_slot(self):
        # Pattern turni: Lun-Mer 06:00 / Gio-Ven 14:00 / Sab-Dom 09:00.
        req = ProfileUpdateRequest(
            anchors=[
                ProfileAnchorDTO(
                    kind="wake",
                    slots=[
                        AnchorSlotDTO(id=uuid4(), time="06:00", weekdays=[1, 2, 3]),
                        AnchorSlotDTO(id=uuid4(), time="14:00", weekdays=[4, 5]),
                        AnchorSlotDTO(id=uuid4(), time="09:00", weekdays=[6, 7]),
                    ],
                )
            ]
        )
        dumped = req.model_dump(exclude_none=True, mode="json")
        wake = dumped["anchors"][0]
        assert len(wake["slots"]) == 3
        assert wake["slots"][0]["weekdays"] == [1, 2, 3]
        assert wake["slots"][1]["time"] == "14:00"

    def test_anchors_rejects_unknown_kind(self):
        with pytest.raises(ValidationError):
            ProfileAnchorDTO(kind="snack", slots=[])


# ---------------------------------------------------------------------------
# Caregivers
# ---------------------------------------------------------------------------


class TestCaregivers:
    def test_invite_default_permissions(self):
        req = CaregiverInviteRequest()
        assert req.permissions is None

    def test_invite_accepts_permission_list(self):
        req = CaregiverInviteRequest(permissions=["view_medications", "view_adherence_history"])
        assert "view_medications" in req.permissions

    def test_accept_requires_code(self):
        with pytest.raises(ValidationError):
            CaregiverAcceptRequest()

    def test_accept_accepts_dashed_code(self):
        req = CaregiverAcceptRequest(invite_code="ABC-123")
        assert req.invite_code == "ABC-123"

    def test_pending_change_requires_change_type(self):
        with pytest.raises(ValidationError):
            PendingChangeCreateRequest(caregiver_relation_id=uuid4())

    def test_pending_change_with_payload(self):
        req = PendingChangeCreateRequest(
            caregiver_relation_id=uuid4(),
            change_type="routine_create",
            payload={"name": "Mattina"},
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        assert req.change_type == "routine_create"


# ---------------------------------------------------------------------------
# Supplies
# ---------------------------------------------------------------------------


class TestSupplies:
    def test_create_minimal(self):
        req = SupplyCreateRequest(medication_id=uuid4())
        assert req.current_pills is None

    def test_full_payload(self):
        req = SupplyCreateRequest(
            medication_id=uuid4(),
            pills_at_purchase=30,
            current_pills=12,
            purchase_date=date.today(),
            refill_threshold_days=7,
            package_units=30,
        )
        assert req.refill_threshold_days == 7

    def test_update_partial(self):
        req = SupplyUpdateRequest(current_pills=5)
        assert req.current_pills == 5
        assert req.purchase_date is None


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------


class TestPrescriptions:
    def test_create_minimal(self):
        req = PrescriptionCreateRequest(medication_id=uuid4())
        assert req.request_status is None

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            PrescriptionCreateRequest(
                medication_id=uuid4(),
                prescription_type="ricetta_blu",
            )

    def test_full_payload(self):
        req = PrescriptionCreateRequest(
            medication_id=uuid4(),
            doctor_id=uuid4(),
            prescription_type="ricetta_rossa",
            issued_date=date.today(),
            expiry_date=date.today() + timedelta(days=180),
            total_packages=3,
            remaining_packages=2,
        )
        assert req.prescription_type == "ricetta_rossa"

    def test_update_partial(self):
        req = PrescriptionUpdateRequest(remaining_packages=1)
        assert req.remaining_packages == 1


# ---------------------------------------------------------------------------
# Prescription requests
# ---------------------------------------------------------------------------


class TestPrescriptionRequests:
    def test_create_requires_channel(self):
        with pytest.raises(ValidationError):
            PrescriptionRequestCreateRequest()

    def test_create_with_channel(self):
        req = PrescriptionRequestCreateRequest(channel="whatsapp")
        assert req.channel == "whatsapp"
        assert req.status is None

    def test_rejects_invalid_channel(self):
        with pytest.raises(ValidationError):
            PrescriptionRequestCreateRequest(channel="sms")

    def test_update_with_purchased_at(self):
        req = PrescriptionRequestUpdateRequest(purchased_at=datetime.now(timezone.utc))
        assert req.purchased_at is not None


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------


class TestDoctors:
    def test_create_requires_name(self):
        with pytest.raises(ValidationError):
            DoctorCreateRequest()

    def test_full_payload(self):
        req = DoctorCreateRequest(
            name="Mario",
            surname="Rossi",
            specialization="cardiologo",
            phone="+390123456789",
            secretary_name="Giulia",
            profile_ids=[uuid4(), uuid4()],
        )
        assert req.surname == "Rossi"
        assert len(req.profile_ids) == 2

    def test_update_partial(self):
        req = DoctorUpdateRequest(prescription_message_template="Salve dottore...")
        assert req.prescription_message_template.startswith("Salve")


# ---------------------------------------------------------------------------
# Device tokens
# ---------------------------------------------------------------------------


class TestDeviceTokens:
    def test_requires_token_and_platform(self):
        with pytest.raises(ValidationError):
            DeviceTokenCreateRequest()

    def test_rejects_invalid_platform(self):
        with pytest.raises(ValidationError):
            DeviceTokenCreateRequest(token="abc", platform="windows")

    def test_ios_payload(self):
        req = DeviceTokenCreateRequest(token="apns-token", platform="ios")
        assert req.platform == "ios"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    def test_update_all_optional(self):
        req = UserSettingsUpdateRequest()
        assert req.notifications_enabled is None

    def test_rejects_invalid_tracking_mode(self):
        with pytest.raises(ValidationError):
            UserSettingsUpdateRequest(default_tracking_mode="manual")

    def test_partial_update(self):
        req = UserSettingsUpdateRequest(
            notify_caregivers=False,
            grace_minutes=60,
        )
        assert req.notify_caregivers is False


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------


class TestActivityLogs:
    def test_requires_action_type(self):
        with pytest.raises(ValidationError):
            ActivityLogCreateRequest()

    def test_with_optional_fields(self):
        req = ActivityLogCreateRequest(
            action_type="dose_taken",
            details={"medication_name": "Tachipirina"},
            source="ios",
        )
        assert req.action_type == "dose_taken"


# ---------------------------------------------------------------------------
# Dosing schedules
# ---------------------------------------------------------------------------


class TestDosingSchedules:
    def test_create_minimal(self):
        req = DosingScheduleCreateRequest(
            medication_id=uuid4(),
            schedule_type="scheduled",
        )
        assert req.is_active is True

    def test_rejects_invalid_schedule_type(self):
        with pytest.raises(ValidationError):
            DosingScheduleCreateRequest(
                medication_id=uuid4(),
                schedule_type="ondemand",
            )

    def test_with_rrule_and_overrides(self):
        req = DosingScheduleCreateRequest(
            medication_id=uuid4(),
            schedule_type="scheduled",
            rrule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
            weekly_overrides={"1": 0.5, "5": 0},
            importance="vital",
        )
        assert req.weekly_overrides["5"] == 0
        assert req.importance == "vital"

    def test_rejects_invalid_importance(self):
        with pytest.raises(ValidationError):
            DosingScheduleCreateRequest(
                medication_id=uuid4(),
                schedule_type="scheduled",
                importance="critical",
            )


# ---------------------------------------------------------------------------
# Subscription / paywall
# ---------------------------------------------------------------------------


class TestSubscription:
    def test_default_state_is_free(self):
        dto = SubscriptionStateDTO()
        assert dto.tier == "free"
        assert dto.is_trial_active is False
        assert dto.expires_at is None

    def test_rejects_invalid_tier(self):
        with pytest.raises(ValidationError):
            SubscriptionStateDTO(tier="enterprise")

    def test_rejects_invalid_environment(self):
        with pytest.raises(ValidationError):
            SubscriptionStateDTO(tier="pro", environment="test")

    def test_verify_request_defaults_to_production(self):
        req = TransactionVerifyRequest(signed_transaction="header.payload.sig")
        assert req.environment == "production"

    def test_verify_request_accepts_sandbox(self):
        req = TransactionVerifyRequest(
            signed_transaction="h.p.s",
            environment="sandbox",
        )
        assert req.environment == "sandbox"
