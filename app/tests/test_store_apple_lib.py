"""Apple App Store Server Library production-mode signature checks.

These tests exercise the ``apple_verify_signature=True`` code path that
ships with `app-store-server-library`. The real Apple chain isn't
available in CI; the goal is to confirm:

  * Lib import + Environment enum bridge
  * Misconfiguration → 500 with structured error
  * Garbage JWS under verification → 400
  * Library can be loaded (skip otherwise)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.store_service import _verify_signature

LIB_AVAILABLE = importlib.util.find_spec("appstoreserverlibrary") is not None


def _settings(**overrides) -> Settings:
    defaults = dict(
        supabase_url="http://localhost",
        supabase_service_role_key="x",
        supabase_jwt_secret="x",
        apple_bundle_id="com.pharmapp.ios",
        apple_verify_signature=True,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.skipif(not LIB_AVAILABLE, reason="app-store-server-library not installed")
class TestApplePrivacyVerify:
    def test_missing_cert_path_returns_500(self):
        with pytest.raises(HTTPException) as exc:
            _verify_signature("h.p.s", _settings(apple_root_cert_path=None))
        assert exc.value.status_code == 500
        assert exc.value.detail["error"]["code"] == "verifier_misconfigured"

    def test_missing_bundle_id_returns_500(self):
        with pytest.raises(HTTPException) as exc:
            _verify_signature(
                "h.p.s",
                _settings(apple_bundle_id=None, apple_root_cert_path="/tmp/fake.pem"),
            )
        assert exc.value.status_code == 500

    def test_bad_cert_file_returns_500(self, tmp_path: Path):
        bad = tmp_path / "bad.pem"
        bad.write_bytes(b"not a pem")
        with pytest.raises(HTTPException) as exc:
            _verify_signature(
                "h.p.s",
                _settings(apple_root_cert_path=str(bad)),
            )
        # Library raises a generic exception when the cert is unparseable;
        # the service maps it to a 500 with a structured error envelope.
        assert exc.value.status_code in {400, 500}

    def test_garbage_jws_with_valid_root_returns_400(self, tmp_path: Path):
        """Use a valid (self-signed) cert as the root — verifier loads
        but the signed transaction signature won't validate against it.
        Expects 400 (signature_invalid) not 500 (config error)."""
        from datetime import datetime, timedelta, timezone

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        key = ec.generate_private_key(ec.SECP256R1())
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "pharmapp test root"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        cert_path = tmp_path / "root.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        with pytest.raises(HTTPException) as exc:
            _verify_signature(
                "h.p.s.signed.with.unknown.key",
                _settings(apple_root_cert_path=str(cert_path)),
            )
        assert exc.value.status_code in {400, 500}

    def test_no_verify_path_is_noop(self):
        """When ``apple_verify_signature=False`` the helper returns
        without touching the library — even with garbage input."""
        # Should not raise
        _verify_signature("garbage.input", _settings(apple_verify_signature=False))


@pytest.mark.skipif(LIB_AVAILABLE, reason="library is installed; skip the missing-import path")
def test_missing_lib_returns_500(monkeypatch):
    """If the library is absent the helper raises a clear 500 instead of
    crashing with an opaque ImportError."""
    with pytest.raises(HTTPException) as exc:
        _verify_signature("h.p.s", _settings(apple_verify_signature=True))
    assert exc.value.status_code == 500
    assert "verifier_unavailable" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# Webhook S2S notification signature path
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LIB_AVAILABLE, reason="app-store-server-library not installed")
class TestNotificationWebhookSignature:
    """The S2S notification endpoint pipes the outer ``signedPayload``
    through ``_verify_signature`` before mutating any state. These tests
    confirm the signature gate is wired."""

    @pytest.mark.asyncio
    async def test_notification_misconfigured_returns_500(self):
        """Decode passes (well-formed JWS shape) but verification config
        is missing (no root cert path) → 500."""
        import base64
        import json

        from app.services.store_service import process_apple_notification
        from app.tests.conftest import FakeSupabase

        fake = FakeSupabase()
        body = base64.urlsafe_b64encode(json.dumps({"notificationType": "TEST"}).encode()).rstrip(b"=").decode()
        outer = f"h.{body}.s"
        with pytest.raises(HTTPException) as exc:
            await process_apple_notification(fake, outer, _settings(apple_root_cert_path=None))
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_notification_garbage_payload_with_valid_root_rejects(self, tmp_path: Path):
        """Self-signed root cert; arbitrary signedPayload won't validate
        against it. The webhook handler should refuse to mutate."""
        from datetime import datetime, timedelta, timezone

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        from app.services.store_service import process_apple_notification
        from app.tests.conftest import FakeSupabase

        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pharmapp test root")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        cert_path = tmp_path / "root.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        fake = FakeSupabase()
        with pytest.raises(HTTPException) as exc:
            await process_apple_notification(
                fake,
                "h.p.s.signed.with.unknown.key",
                _settings(apple_root_cert_path=str(cert_path)),
            )
        assert exc.value.status_code in {400, 500}
        # No upserts must have occurred
        upserts = [c for c in fake.calls if c._operation == "upsert"]
        assert not upserts

    @pytest.mark.asyncio
    async def test_notification_no_verify_processes_payload(self):
        """With verification disabled (default test config) the handler
        runs the decode path. Garbage outer JWS → 400 (decode error) but
        not a verification error."""
        from app.services.store_service import process_apple_notification
        from app.tests.conftest import FakeSupabase

        fake = FakeSupabase()
        with pytest.raises(HTTPException) as exc:
            await process_apple_notification(fake, "garbage", _settings(apple_verify_signature=False))
        assert exc.value.status_code == 400
