"""Tests for measurement validation logic.

The polymorphic value validation lives in
`measurements_service._validate_payload_against_type` — covered here
without needing a DB.
"""

import pytest
from fastapi import HTTPException

from app.services.measurements_service import _validate_payload_against_type


def test_numeric_single_valid():
    _validate_payload_against_type(
        "numericSingle",
        value_single=94,
        value_double_1=None,
        value_double_2=None,
        value_text=None,
    )


def test_numeric_single_missing_value():
    with pytest.raises(HTTPException) as exc:
        _validate_payload_against_type(
            "numericSingle",
            value_single=None,
            value_double_1=None,
            value_double_2=None,
            value_text=None,
        )
    assert exc.value.status_code == 422


def test_numeric_single_rejects_extra_field():
    with pytest.raises(HTTPException):
        _validate_payload_against_type(
            "numericSingle",
            value_single=94,
            value_double_1=None,
            value_double_2=None,
            value_text="extra",
        )


def test_numeric_double_valid():
    _validate_payload_against_type(
        "numericDouble",
        value_single=None,
        value_double_1=128,
        value_double_2=82,
        value_text=None,
    )


def test_numeric_double_partial_rejected():
    with pytest.raises(HTTPException):
        _validate_payload_against_type(
            "numericDouble",
            value_single=None,
            value_double_1=128,
            value_double_2=None,
            value_text=None,
        )


def test_text_valid():
    _validate_payload_against_type(
        "text",
        value_single=None,
        value_double_1=None,
        value_double_2=None,
        value_text="Stanchezza nel pomeriggio",
    )


def test_text_empty_rejected():
    with pytest.raises(HTTPException):
        _validate_payload_against_type(
            "text",
            value_single=None,
            value_double_1=None,
            value_double_2=None,
            value_text="   ",
        )


def test_unknown_value_type_rejected():
    with pytest.raises(HTTPException):
        _validate_payload_against_type(
            "weirdType",
            value_single=1,
            value_double_1=None,
            value_double_2=None,
            value_text=None,
        )
