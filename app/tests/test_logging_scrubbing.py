"""
Tests for `app.logging_scrubbing.ScrubbingProcessor` and `scrub_value`.

Acts as a regression guard for the privacy invariant: no PHI / PII
ever reaches stdout in plaintext. We test the scrubber both as a unit
(direct calls) and via the structlog processor pipeline.
"""

from __future__ import annotations

import logging

import pytest

from app.logging_config import setup_logging
from app.logging_scrubbing import REDACTED, ScrubbingProcessor, scrub_value


class TestSensitiveKeyRedaction:
    @pytest.mark.parametrize(
        "key",
        [
            "name",
            "first_name",
            "patient_name",
            "medication_name",
            "principio_attivo",
            "dosage",
            "posology",
            "notes",
            "email",
            "phone",
            "fiscal_code",
            "password",
            "access_token",
            "authorization",
        ],
    )
    def test_value_redacted_when_key_is_sensitive(self, key: str) -> None:
        assert scrub_value(key, "Tachipirina 1000") == REDACTED

    def test_nested_dict_is_walked(self) -> None:
        out = scrub_value(
            "context",
            {
                "user_id": "f1e2-...",  # opaque, not redacted
                "medication_name": "Tachipirina",  # redacted by key
                "nested": {"email": "x@y.com", "harmless": "ok"},
            },
        )
        assert out["medication_name"] == REDACTED
        assert out["nested"]["email"] == REDACTED
        assert out["nested"]["harmless"] == "ok"
        assert out["user_id"] == "f1e2-..."  # opaque ids stay


class TestPatternRedaction:
    def test_email_pattern_redacted(self) -> None:
        out = scrub_value("free_text_field", "Contact mario.rossi@example.com today")
        # The key is also matched by SENSITIVE_KEYS → whole-value redaction wins.
        assert out == REDACTED

    def test_email_in_neutral_key(self) -> None:
        out = scrub_value("payload", "Contact mario.rossi@example.com today")
        assert "mario.rossi" not in out
        assert REDACTED in out

    def test_italian_fiscal_code_redacted(self) -> None:
        out = scrub_value("payload", "User CF: RSSMRA80A01H501Z requested export")
        assert "RSSMRA80A01H501Z" not in out
        assert REDACTED in out

    def test_jwt_redacted(self) -> None:
        token = "eyJabc.eyJdef.signature_xyz123"
        out = scrub_value("payload", f"Bearer {token}")
        assert token not in out
        assert REDACTED in out


class TestStructlogIntegration:
    def test_processor_scrubs_event_dict(self) -> None:
        proc = ScrubbingProcessor()
        result = proc(
            None,
            "info",
            {
                "event": "request_completed",
                "user_id": "uuid-1",
                "medication_name": "Tachipirina",
                "email": "x@y.com",
                "duration_ms": 12.3,
            },
        )
        assert result["event"] == "request_completed"
        assert result["user_id"] == "uuid-1"
        assert result["medication_name"] == REDACTED
        assert result["email"] == REDACTED
        assert result["duration_ms"] == 12.3

    def test_end_to_end_setup_logging_no_phi_in_stdout(self, capsys, caplog) -> None:
        # Reconfigure logging to write structlog JSON to stdout.
        setup_logging(level="INFO")
        logger = logging.getLogger("pharmapp")
        logger.info(
            "test_event",
            extra={
                "user_id": "f1e2",
                "medication_name": "Tachipirina 1000",
                "email": "mario.rossi@example.com",
                "fiscal_code": "RSSMRA80A01H501Z",
                "free_text": "Patient ate Tachipirina at 8am",
            },
        )

        out = capsys.readouterr().out
        # Hardline check: nothing identifying should leave the process.
        assert "Tachipirina" not in out, "medication name leaked in log output"
        assert "mario.rossi@example.com" not in out, "email leaked"
        assert "RSSMRA80A01H501Z" not in out, "fiscal code leaked"
        # Sanity check: at least our event marker DID make it to stdout,
        # so the test is exercising the real pipeline.
        assert "test_event" in out
