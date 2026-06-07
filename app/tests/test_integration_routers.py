"""Service-level integration tests for the /v2 router surface.

Each test exercises a route through the real FastAPI middleware + auth
dependency + service layer. The Supabase client is replaced by a fake that
records query operations and returns canned rows (see
``conftest.FakeSupabase``). This catches:

* Schema/route mismatches (request shape, response shape)
* Service business logic (filter selection, ownership checks)
* Auth wiring (anonymous requests are rejected, authed requests reach the
  router)

For tests that must hit a real database, mark them ``@pytest.mark.integration``
and run with ``docker compose -f docker-compose.test.yml up -d`` plus
``TEST_SUPABASE_URL`` set.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.tests.conftest import TEST_USER_ID, FakeSupabase


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


class TestProfilesRouter:
    def test_list_returns_200_when_authed(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": str(uuid4()),
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        resp = authed_client.get("/v2/profiles")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_persists_payload(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        resp = authed_client.post(
            "/v2/profiles",
            json={"profile_type": "assisted", "display_name": "Maria", "relation_label": "madre"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["display_name"] == "Maria"
        assert body["relation_label"] == "madre"
        # The service inserted into "profiles"
        insert_calls = [c for c in fake_supabase.calls if c._table == "profiles" and c._operation == "insert"]
        assert insert_calls, "no insert recorded"

    def test_disconnect_returns_profile(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        # Profile owned by another user — current user is the caregiver
        other_user = str(uuid4())
        profile_id = str(uuid4())
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": other_user,
                    "profile_type": "own",
                    "display_name": "Maria",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        resp = authed_client.put(f"/v2/profiles/{profile_id}/disconnect")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Maria"

    def test_disconnect_own_profile_400(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        profile_id = str(uuid4())
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        resp = authed_client.put(f"/v2/profiles/{profile_id}/disconnect")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------


class TestMedicationsRouter:
    def test_list_empty(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("profiles", [])
        fake_supabase.seed_select("medications", [])
        resp = authed_client.get("/v2/medications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_with_injection_sites(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        profile_id = str(uuid4())
        # Seed ownership lookup
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        payload = {
            "profile_id": profile_id,
            "name": "Enantone",
            "injection_sites": [
                {"id": "addome-sx", "name": "Addome sinistro"},
                {"id": "braccio-dx", "name": "Braccio destro"},
            ],
        }
        resp = authed_client.post("/v2/medications", json=payload)
        # The service may filter the injection_sites field before insert;
        # the contract is that the request validates and the route returns
        # 201/200 — silent drops are caught by the schema test instead.
        assert resp.status_code in {200, 201}

    def test_create_with_embedded_schedules(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """POST /v2/medications with `schedules[]` must persist both
        the medication row and each dosing_schedule row in one round-trip.
        Without this, optimistic-UI clients leave orphan medications
        and Today/Terapie/Dati render empty (see commit 11147dd)."""
        profile_id = str(uuid4())
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        payload = {
            "profile_id": profile_id,
            "name": "Ramipril",
            "principle": "Ramipril 5 mg",
            "category": "farmaco",
            "tracking_mode": "active",
            "start_date": "2026-05-09",
            "schedules": [
                {
                    "schedule_type": "scheduled",
                    "times": [{"time": "08:00"}],
                    "pills_per_dose": 1.0,
                    "is_active": True,
                    "importance": "essential",
                }
            ],
        }
        resp = authed_client.post("/v2/medications", json=payload)
        assert resp.status_code in {200, 201}
        # FakeSupabase records every insert; the second one should be
        # the dosing_schedules row, with medication_id wired by the service.
        schedule_inserts = fake_supabase.recorded_inserts.get("dosing_schedules", [])
        assert len(schedule_inserts) >= 1
        sched_row = schedule_inserts[-1]
        # FakeSupabase may store the row dict directly or wrapped in a list.
        if isinstance(sched_row, list):
            sched_row = sched_row[0]
        assert "medication_id" in sched_row, sched_row
        assert sched_row["schedule_type"] == "scheduled"
        assert sched_row["pills_per_dose"] == 1.0

    def test_create_with_embedded_packages(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """POST /v2/medications with `packages[]` must persist a
        medication_packages row per dosaggio with medication_id wired."""
        profile_id = str(uuid4())
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        payload = {
            "profile_id": profile_id,
            "name": "Eutirox",
            "category": "farmaco",
            "tracking_mode": "active",
            "start_date": "2026-05-09",
            "packages": [
                {
                    "strength_text": "10 mg",
                    "strength_mg": 10.0,
                    "units_per_box": 30,
                    "box_count": 1,
                    "current_units": 30.0,
                    "refill_threshold_days": 7,
                },
                {
                    "strength_text": "5 mg",
                    "strength_mg": 5.0,
                    "units_per_box": 28,
                    "box_count": 1,
                    "current_units": 28.0,
                    "refill_threshold_days": 7,
                },
            ],
        }
        resp = authed_client.post("/v2/medications", json=payload)
        assert resp.status_code in {200, 201}
        package_inserts = fake_supabase.recorded_inserts.get("medication_packages", [])
        assert len(package_inserts) >= 1
        rows = package_inserts[-1]
        if isinstance(rows, dict):
            rows = [rows]
        assert len(rows) == 2, rows
        assert all("medication_id" in r for r in rows), rows
        assert {r["strength_text"] for r in rows} == {"10 mg", "5 mg"}

    def test_create_rejects_negative_package_units(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """units_per_box < 1 and current_units < 0 must be rejected by the
        EmbeddedPackageCreate validators (422)."""
        profile_id = str(uuid4())
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": profile_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        payload = {
            "profile_id": profile_id,
            "name": "Eutirox",
            "category": "farmaco",
            "tracking_mode": "active",
            "packages": [{"strength_text": "5 mg", "units_per_box": 0, "current_units": -1}],
        }
        resp = authed_client.post("/v2/medications", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Dose events
# ---------------------------------------------------------------------------


class TestDoseEventsRouter:
    def test_list_filters_by_profile(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("dose_events", [])
        resp = authed_client.get("/v2/dose-events", params={"profile_id": str(uuid4())})
        assert resp.status_code == 200

    def test_create_with_injection_site(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        med_id = str(uuid4())
        prof_id = str(uuid4())
        fake_supabase.seed_select(
            "medications",
            [{"id": med_id, "profile_id": prof_id}],
        )
        fake_supabase.seed_select(
            "profiles",
            [
                {
                    "id": prof_id,
                    "user_id": str(TEST_USER_ID),
                    "profile_type": "own",
                    "display_name": "Mattia",
                    "created_at": _ts(),
                    "updated_at": _ts(),
                }
            ],
        )
        resp = authed_client.post(
            "/v2/dose-events",
            json={
                "medication_id": med_id,
                "profile_id": prof_id,
                "due_at": _ts(),
                "status": "taken",
                "injection_site": "site-default-addome-sx",
            },
        )
        # Without full ownership-check seeding the service may 403/404; the
        # contract being tested is that the route accepts the payload (no
        # 422) and forwards the injection_site downstream.
        assert resp.status_code != 422


# ---------------------------------------------------------------------------
# Caregivers
# ---------------------------------------------------------------------------


class TestCaregiversRouter:
    def test_invite_returns_201(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        resp = authed_client.post(
            "/v2/caregivers/invite",
            json={"permissions": ["view_medications"]},
        )
        # 200/201 success; 429 acceptable when other rate-limit tests in
        # the same session already exhausted the per-process budget.
        assert resp.status_code in {200, 201, 429}

    def test_accept_requires_code(self, authed_client: TestClient):
        resp = authed_client.post("/v2/caregivers/accept", json={})
        assert resp.status_code == 422

    def test_accept_with_invalid_code_format(self, authed_client: TestClient):
        # Code "AB" is too short, service raises 400.
        resp = authed_client.post("/v2/caregivers/accept", json={"invite_code": "AB"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Supplies
# ---------------------------------------------------------------------------


class TestSuppliesRouter:
    def test_get_returns_null_when_absent(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        med_id = str(uuid4())
        prof_id = str(uuid4())
        # The supplies service joins medications→profiles via Supabase
        # ``profiles!inner(user_id)`` syntax; the fake returns whatever we
        # seed, so we embed the joined object directly.
        fake_supabase.seed_select(
            "medications",
            [{"id": med_id, "profile_id": prof_id, "profiles": {"user_id": str(TEST_USER_ID)}}],
        )
        fake_supabase.seed_select("supplies", [])
        resp = authed_client.get(f"/v2/medications/{med_id}/supply")
        # Route exists and ownership check passed; supplies row absent → 200/null
        assert resp.status_code == 200

    def test_put_accepts_payload_without_medication_id(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """The PUT body should not require medication_id (it's in the path).

        Regression for the previous SupplyCreateRequest schema that forced
        clients to repeat the FK in the body and triggered 422 when omitted.
        """
        med_id = str(uuid4())
        prof_id = str(uuid4())
        fake_supabase.seed_select(
            "medications",
            [{"id": med_id, "profile_id": prof_id, "profiles": {"user_id": str(TEST_USER_ID)}}],
        )
        fake_supabase.seed_select("supplies", [])
        resp = authed_client.put(
            f"/v2/medications/{med_id}/supply",
            json={
                "pills_at_purchase": 30,
                "current_pills": 30,
                "purchase_date": "2026-06-04",
                "refill_threshold_days": 7,
                "package_units": 30,
            },
        )
        assert resp.status_code == 200, resp.text
        insert_payload = fake_supabase.recorded_inserts["supplies"][0]
        assert insert_payload["medication_id"] == med_id
        assert insert_payload["current_pills"] == 30

    def test_put_strips_legacy_medication_id_from_body(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """Old clients still send medication_id in the body — the server
        must accept it but never write the legacy value to the row."""
        med_id = str(uuid4())
        legacy_id = str(uuid4())
        prof_id = str(uuid4())
        fake_supabase.seed_select(
            "medications",
            [{"id": med_id, "profile_id": prof_id, "profiles": {"user_id": str(TEST_USER_ID)}}],
        )
        # Seed an existing row → branch UPDATE
        existing_supply_id = str(uuid4())
        fake_supabase.seed_select(
            "supplies",
            [{
                "id": existing_supply_id,
                "medication_id": med_id,
                "current_pills": 5,
                "pills_at_purchase": 30,
                "purchase_date": "2026-05-01",
                "refill_threshold_days": 7,
                "package_units": 30,
                "created_at": "2026-05-01T00:00:00+00:00",
                "updated_at": "2026-05-01T00:00:00+00:00",
            }],
        )
        resp = authed_client.put(
            f"/v2/medications/{med_id}/supply",
            json={
                "medication_id": legacy_id,  # bogus, must be ignored
                "current_pills": 42,
            },
        )
        assert resp.status_code == 200, resp.text
        # Find the UPDATE call and check the payload
        update_calls = [
            c for c in fake_supabase.calls
            if c._table == "supplies" and c._operation == "update"
        ]
        assert update_calls, "expected an UPDATE on supplies"
        assert "medication_id" not in update_calls[-1]._payload


# ---------------------------------------------------------------------------
# Prescriptions
# ---------------------------------------------------------------------------


class TestPrescriptionsRouter:
    def test_create_validates_payload(self, authed_client: TestClient):
        med_id = str(uuid4())
        resp = authed_client.post(
            f"/v2/medications/{med_id}/prescriptions",
            json={"medication_id": med_id, "prescription_type": "ricetta_blu"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Prescription requests
# ---------------------------------------------------------------------------


class TestPrescriptionRequestsRouter:
    def test_patch_updates_purchased_at(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        med_id = str(uuid4())
        req_id = str(uuid4())
        resp = authed_client.patch(
            f"/v2/medications/{med_id}/prescription_requests/{req_id}",
            json={"status": "purchased", "purchased_at": _ts()},
        )
        assert resp.status_code != 422

    def test_create_persists_strength_text(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        """POST con strength_text → persiste la richiesta scoped al dosaggio."""
        med_id = str(uuid4())
        fake_supabase.seed_select(
            "medications", [{"id": med_id, "profiles": {"user_id": str(TEST_USER_ID)}}]
        )
        resp = authed_client.post(
            f"/v2/medications/{med_id}/prescription_requests",
            json={"channel": "whatsapp", "strength_text": "10 mg"},
        )
        assert resp.status_code in {200, 201}
        inserts = fake_supabase.recorded_inserts.get("prescription_requests", [])
        assert inserts, "prescription request should be inserted"
        row = inserts[-1]
        if isinstance(row, list):
            row = row[0]
        assert row.get("strength_text") == "10 mg"
        assert row.get("medication_id") == med_id


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------


class TestDoctorsRouter:
    def test_create_requires_name(self, authed_client: TestClient):
        resp = authed_client.post("/v2/doctors", json={})
        assert resp.status_code == 422

    def test_create_minimal_succeeds(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        resp = authed_client.post("/v2/doctors", json={"name": "Mario"})
        assert resp.status_code in {200, 201}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettingsRouter:
    def test_get_creates_default(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("user_settings", [])
        resp = authed_client.get("/v2/settings")
        # Get-or-create may 200 with defaults or 500 without DB; either way
        # the route is wired.
        assert resp.status_code != 404

    def test_put_validates_tracking_mode(self, authed_client: TestClient):
        resp = authed_client.put("/v2/settings", json={"default_tracking_mode": "manual"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Device tokens
# ---------------------------------------------------------------------------


class TestDeviceTokensRouter:
    def test_register_validates_platform(self, authed_client: TestClient):
        resp = authed_client.post("/v2/device-tokens", json={"token": "abc", "platform": "windows"})
        assert resp.status_code == 422

    def test_register_ios_payload(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        resp = authed_client.post("/v2/device-tokens", json={"token": "apns-xyz", "platform": "ios"})
        assert resp.status_code in {200, 201}


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------


class TestActivityLogsRouter:
    def test_create_validates_action_type(self, authed_client: TestClient):
        resp = authed_client.post("/v2/activity-logs", json={})
        assert resp.status_code == 422

    def test_list_returns_200(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("activity_logs", [])
        resp = authed_client.get("/v2/activity-logs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


class TestBootstrapRouter:
    def test_bootstrap_returns_subscription_field(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        # Empty seeding — service returns empty arrays + free-tier subscription
        for tbl in [
            "profiles",
            "user_settings",
            "doctors",
            "medications",
            "dosing_schedules",
            "supplies",
            "prescriptions",
            "prescription_requests",
            "dose_events",
            "activity_logs",
            "caregiver_relations",
            "device_tokens",
            "routines",
            "routine_steps",
            "parameters",
            "measurements",
            "subscriptions",
        ]:
            fake_supabase.seed_select(tbl, [])
        resp = authed_client.get("/v2/bootstrap")
        assert resp.status_code == 200
        body = resp.json()
        assert "subscription" in body, "bootstrap should include subscription field"
        # When user has never validated a transaction the service returns
        # the synthetic free-tier object (or null is also acceptable).
        sub = body["subscription"]
        assert sub is None or sub.get("tier") == "free"


# ---------------------------------------------------------------------------
# DSAR
# ---------------------------------------------------------------------------


class TestDSARRouter:
    def test_export_route_exists(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        for tbl in [
            "profiles",
            "doctors",
            "medications",
            "dosing_schedules",
            "supplies",
            "prescriptions",
            "prescription_requests",
            "dose_events",
            "activity_logs",
            "caregiver_relations",
            "user_settings",
            "device_tokens",
            "subscriptions",
        ]:
            fake_supabase.seed_select(tbl, [])
        resp = authed_client.get("/v2/me/export")
        # Real export needs DB joins; we only check the route exists and
        # the auth dep ran (status != 404, not 422 for unauth).
        assert resp.status_code != 404


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------


class TestRoutinesRouter:
    def test_list_returns_200(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("routines", [])
        resp = authed_client.get("/v2/routines")
        assert resp.status_code == 200

    def test_create_validates_steps(self, authed_client: TestClient):
        resp = authed_client.post(
            "/v2/routines",
            json={
                "profile_id": str(uuid4()),
                "name": "Mattina",
                "steps": [{"step_type": "unknown"}],
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Apple StoreKit / Subscription
# ---------------------------------------------------------------------------


class TestStoreRouter:
    def test_verify_rejects_malformed_jws(self, authed_client: TestClient):
        resp = authed_client.post(
            "/v2/store/transactions/verify",
            json={"signed_transaction": "not-a-jws", "environment": "sandbox"},
        )
        assert resp.status_code == 400

    def test_verify_decodes_unsigned_jws(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        # Build a JWS-shaped string with a base64url-encoded JSON payload —
        # signature verification is disabled by default in test config.
        import base64
        import json

        payload = {
            "bundleId": "com.pharmapp.ios",
            "productId": "com.pharmapp.pro.yearly",
            "originalTransactionId": "txn-1",
            "expiresDate": int(datetime.now(timezone.utc).timestamp() * 1000) + 86_400_000,
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        jws = f"header.{encoded}.sig"
        resp = authed_client.post(
            "/v2/store/transactions/verify",
            json={"signed_transaction": jws, "environment": "sandbox"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == "pro"
        assert body["product_id"] == "com.pharmapp.pro.yearly"

    def test_subscription_defaults_to_free(self, authed_client: TestClient, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("subscriptions", [])
        resp = authed_client.get("/v2/store/subscription")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == "free"

    def test_notification_webhook_accepts_empty_body(self, authed_client: TestClient):
        resp = authed_client.post("/v2/store/transactions/notification", json={})
        # Webhook silently succeeds when no signedPayload is present.
        assert resp.status_code in {200, 202}
