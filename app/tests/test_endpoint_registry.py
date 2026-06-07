"""Endpoint registry smoke test.

Every (method, template) tuple below must be served by the FastAPI app. The
test materializes the template (substitutes `{country}` with `it` and any
other path parameter with a UUID), sends a request without authentication,
and asserts the response is anything but 404. Authentication errors (401)
and validation errors (422) confirm the route is reachable.

The list mirrors what the iOS client actually calls (search the Swift
sources for ``/v2/``). Add an entry whenever a new endpoint ships, remove
one when the iOS surface drops a feature; the test fails fast either way.
"""

import re
from uuid import uuid4

from fastapi.testclient import TestClient

_UID = str(uuid4())


def _materialize(template: str) -> str:
    """Substitute path templates with concrete values for the test request.
    `{country}` → ``it`` (the only fixture country), every other `{...}`
    placeholder → a static test UUID.
    """
    out = template.replace("{country}", "it")
    return re.sub(r"\{[^}]+\}", _UID, out)


def _normalize(path: str) -> str:
    """Canonicalize a path for set comparison: every `{...}` placeholder
    becomes the literal token ``{}`` so two templates with different
    parameter names line up."""
    return re.sub(r"\{[^}]+\}", "{}", path)


EXPECTED_ENDPOINTS: list[tuple[str, str]] = [
    # Health (unauthenticated)
    ("GET", "/health"),
    # Bootstrap
    ("GET", "/v2/bootstrap"),
    # Catalog (unauthenticated)
    ("GET", "/v2/catalog/search?country=it&q=tachi"),
    ("GET", "/v2/catalog/products/search?country=it&q=tachi"),
    ("GET", "/v2/catalog/products/{country}/{product_id}"),
    ("GET", "/v2/catalog/packages/{country}/{package_id}"),
    # Profiles
    ("GET", "/v2/profiles"),
    ("POST", "/v2/profiles"),
    ("POST", "/v2/profiles/init"),
    ("GET", "/v2/profiles/{profile_id}"),
    ("PUT", "/v2/profiles/{profile_id}"),
    ("DELETE", "/v2/profiles/{profile_id}"),
    ("PUT", "/v2/profiles/{profile_id}/disconnect"),
    ("POST", "/v2/profiles/{profile_id}/resend-invite"),
    ("DELETE", "/v2/profiles/{profile_id}/cancel"),
    # Debug / diagnostics
    ("GET", "/v2/debug/whoami"),
    # Therapy data
    ("GET", "/v2/profiles/{profile_id}/therapy-data"),
    ("GET", "/v2/profiles/{profile_id}/therapy-data/report.pdf"),
    # Doctors
    ("GET", "/v2/doctors"),
    ("POST", "/v2/doctors"),
    ("GET", "/v2/doctors/{doctor_id}"),
    ("PUT", "/v2/doctors/{doctor_id}"),
    ("DELETE", "/v2/doctors/{doctor_id}"),
    # Medications
    ("GET", "/v2/medications"),
    ("POST", "/v2/medications"),
    ("GET", "/v2/medications/{medication_id}"),
    ("PUT", "/v2/medications/{medication_id}"),
    ("DELETE", "/v2/medications/{medication_id}"),
    # Dosing schedules
    ("GET", "/v2/medications/{medication_id}/schedules"),
    ("POST", "/v2/medications/{medication_id}/schedules"),
    ("GET", "/v2/medications/{medication_id}/schedules/{schedule_id}"),
    ("PUT", "/v2/medications/{medication_id}/schedules/{schedule_id}"),
    ("DELETE", "/v2/medications/{medication_id}/schedules/{schedule_id}"),
    # Supplies
    ("GET", "/v2/medications/{medication_id}/supply"),
    ("PUT", "/v2/medications/{medication_id}/supply"),
    ("DELETE", "/v2/medications/{medication_id}/supply"),
    # Packages (scorte per dosaggio)
    ("GET", "/v2/medications/{medication_id}/packages"),
    ("PUT", "/v2/medications/{medication_id}/packages"),
    # Prescriptions
    ("GET", "/v2/medications/{medication_id}/prescriptions"),
    ("POST", "/v2/medications/{medication_id}/prescriptions"),
    ("GET", "/v2/medications/{medication_id}/prescriptions/{prescription_id}"),
    ("PUT", "/v2/medications/{medication_id}/prescriptions/{prescription_id}"),
    ("DELETE", "/v2/medications/{medication_id}/prescriptions/{prescription_id}"),
    # Prescription requests
    ("GET", "/v2/medications/{medication_id}/prescription_requests"),
    ("POST", "/v2/medications/{medication_id}/prescription_requests"),
    ("GET", "/v2/medications/{medication_id}/prescription_requests/{request_id}"),
    ("PATCH", "/v2/medications/{medication_id}/prescription_requests/{request_id}"),
    # Dose events
    ("GET", "/v2/dose-events"),
    ("POST", "/v2/dose-events"),
    ("GET", "/v2/dose-events/{event_id}"),
    ("PUT", "/v2/dose-events/{event_id}"),
    ("DELETE", "/v2/dose-events/{event_id}"),
    # Routines
    ("GET", "/v2/routines"),
    ("POST", "/v2/routines"),
    ("GET", "/v2/routines/{routine_id}"),
    ("PUT", "/v2/routines/{routine_id}"),
    ("DELETE", "/v2/routines/{routine_id}"),
    ("POST", "/v2/routines/{routine_id}/duplicate"),
    # Routine steps
    ("POST", "/v2/routines/{routine_id}/steps"),
    ("PUT", "/v2/routines/{routine_id}/steps/{step_id}"),
    ("DELETE", "/v2/routines/{routine_id}/steps/{step_id}"),
    ("PATCH", "/v2/routines/{routine_id}/steps/reorder"),
    # Parameters
    ("GET", "/v2/parameters?profile_id=" + _UID),
    ("POST", "/v2/parameters"),
    ("GET", "/v2/parameters/{parameter_id}"),
    ("PATCH", "/v2/parameters/{parameter_id}"),
    ("DELETE", "/v2/parameters/{parameter_id}"),
    # Measurements
    ("GET", "/v2/measurements"),
    ("POST", "/v2/measurements"),
    ("GET", "/v2/measurements/{measurement_id}"),
    ("PATCH", "/v2/measurements/{measurement_id}"),
    ("DELETE", "/v2/measurements/{measurement_id}"),
    # Settings
    ("GET", "/v2/settings"),
    ("PUT", "/v2/settings"),
    # Caregivers
    ("GET", "/v2/caregivers/relations"),
    ("POST", "/v2/caregivers/invite"),
    ("POST", "/v2/caregivers/accept"),
    ("GET", "/v2/caregivers/confirmations"),
    ("PUT", "/v2/caregivers/relations/{relation_id}/confirm"),
    ("PUT", "/v2/caregivers/relations/{relation_id}/reject"),
    ("PUT", "/v2/caregivers/relations/{relation_id}/revoke"),
    ("GET", "/v2/caregivers/pending-changes"),
    ("POST", "/v2/caregivers/relations/{relation_id}/changes"),
    ("PUT", "/v2/caregivers/pending-changes/{change_id}/approve"),
    ("PUT", "/v2/caregivers/pending-changes/{change_id}/reject"),
    # Activity logs
    ("GET", "/v2/activity-logs"),
    ("POST", "/v2/activity-logs"),
    # Device tokens
    ("GET", "/v2/device-tokens"),
    ("POST", "/v2/device-tokens"),
    ("DELETE", "/v2/device-tokens"),
    # DSAR
    ("GET", "/v2/me/export"),
    ("DELETE", "/v2/me"),
    ("GET", "/v2/me/access-log"),
    # Apple StoreKit
    ("POST", "/v2/store/transactions/verify"),
    ("POST", "/v2/store/transactions/notification"),
    ("GET", "/v2/store/subscription"),
]


def test_every_ios_endpoint_is_routable(client: TestClient):
    """Every iOS endpoint must be reachable. Status 404 with Starlette's
    default ``{"detail":"Not Found"}`` body means a route disappeared from
    the backend while the iOS client still calls it. Status 404 with our
    structured ``{"error":{"code":"not_found",...}}`` body is a legitimate
    business-logic response (the test UUID does not exist) and confirms the
    route is wired."""
    missing: list[tuple[str, str, int]] = []
    for method, template in EXPECTED_ENDPOINTS:
        url = _materialize(template)
        resp = client.request(method, url)
        if resp.status_code != 404:
            continue
        body = resp.json() if resp.content else {}
        # Business 404 has the structured error envelope; route-not-found
        # has Starlette's default `detail` field.
        is_route_missing = body.get("detail") == "Not Found" and "error" not in body
        if is_route_missing:
            missing.append((method, template, resp.status_code))
    assert not missing, (
        "The following iOS endpoints are missing on the backend (returned 404):\n"
        + "\n".join(f"  {m} {p} -> {s}" for m, p, s in missing)
    )


def test_no_orphan_routes_in_app(client: TestClient):
    """Mirror check: every authenticated /v2 route on the FastAPI app
    should appear in EXPECTED_ENDPOINTS. Catches the case where a backend
    endpoint exists but no iOS code calls it — surfaces dead code or
    missing client integration. OpenAPI / docs / health are exempt."""
    declared = {(m.upper(), _normalize(_strip_query(p))) for m, p in EXPECTED_ENDPOINTS}
    orphans: list[tuple[str, str]] = []
    for route in client.app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or not path.startswith("/v2"):
            continue
        for method in methods:
            if method == "OPTIONS":
                continue
            normalized = (method, _normalize(path))
            if normalized not in declared:
                orphans.append((method, path))
    assert not orphans, (
        "Backend exposes routes the iOS client does not call:\n"
        + "\n".join(f"  {m} {p}" for m, p in orphans)
    )


def _strip_query(path: str) -> str:
    return path.split("?", 1)[0]
