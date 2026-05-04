"""
PII / PHI scrubbing for log records.

Hooked into structlog as a processor (see `app/logging_config.py`).
Runs over every log event right before rendering, recursively walking
the event dict and:

  1. Replacing values whose key matches a sensitive-key pattern with
     `***`.
  2. Replacing PII patterns (email, Italian fiscal code, JWT, phone)
     inside string values with `***`.

False positives are tolerated. False negatives are not: when in doubt
the redaction wins. The scrubber is the last line of defence; the
first is "don't pass PHI to the logger in the first place".
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***"

# Keys whose VALUES we redact regardless of content. Match is case-
# insensitive `in` check, so `medication_name`, `patientName`, and
# `notes_field` all hit. Be liberal: better to over-redact than leak.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "first_name",
        "last_name",
        "full_name",
        "patient_name",
        "display_name",
        "email",
        "phone",
        "phone_number",
        "fiscal_code",
        "cf",
        "tax_id",
        "address",
        "date_of_birth",
        "dob",
        "medication_name",
        "drug_name",
        "active_ingredient",
        "principio_attivo",
        "principle",
        "dosage",
        "posology",
        "diagnosis",
        "condition",
        "notes",
        "free_text",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "authorization",
        "cookie",
        "set-cookie",
    }
)

# Patterns matched inside string values.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Italian fiscal code: 16 alphanumeric, fixed pattern.
CF_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
# Phone numbers: optional + and country code, then 6+ digits with
# optional spaces/dashes. Lower bound on length to avoid stripping
# 4-digit OTPs. Capped at 20 chars to avoid eating long ids.
PHONE_RE = re.compile(r"\b\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{6,10}\b")


def _scrub_string(value: str) -> str:
    s = EMAIL_RE.sub(REDACTED, value)
    s = CF_RE.sub(REDACTED, s)
    s = JWT_RE.sub(REDACTED, s)
    if len(value) < 50:
        # Phone heuristic is noisier on long strings; avoid matching
        # within unrelated free text.
        s = PHONE_RE.sub(REDACTED, s)
    return s


def _key_is_sensitive(key: str) -> bool:
    lower = key.lower()
    return any(s in lower for s in SENSITIVE_KEYS)


def scrub_value(key: str, value: Any) -> Any:
    """Recursively scrub `value`. Public for tests."""
    if _key_is_sensitive(key):
        return REDACTED
    if isinstance(value, str):
        return _scrub_string(value)
    if isinstance(value, dict):
        return {k: scrub_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(scrub_value(key, v) for v in value)
    return value


class ScrubbingProcessor:
    """structlog-compatible processor.

    structlog calls processors with `(logger, method_name, event_dict)`
    and expects the (possibly mutated) event_dict back. We replace each
    value through `scrub_value`.
    """

    def __call__(self, logger, method_name, event_dict):  # noqa: ARG002
        return {k: scrub_value(k, v) for k, v in event_dict.items()}
