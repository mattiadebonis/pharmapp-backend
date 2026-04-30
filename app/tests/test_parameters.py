"""Schema + predefined catalog tests for parameters."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.parameter import ParameterCreateRequest, ParameterUpdateRequest
from app.services.parameters_service import (
    PREDEFINED_KEYS,
    PREDEFINED_PARAMETERS,
    _predefined_dto,
    get_predefined,
)


def test_predefined_catalog_has_seven_entries():
    assert len(PREDEFINED_PARAMETERS) == 7
    expected = {
        "glycemia",
        "blood_pressure",
        "weight",
        "temperature",
        "inr",
        "oxygen_saturation",
        "heart_rate",
    }
    assert PREDEFINED_KEYS == expected


def test_predefined_dto_shape():
    dto = _predefined_dto(get_predefined("glycemia"))
    assert dto["id"] is None
    assert dto["profile_id"] is None
    assert dto["is_predefined"] is True
    assert dto["value_type"] == "numericSingle"
    assert dto["unit"] == "mg/dL"


def test_blood_pressure_has_double_labels():
    bp = get_predefined("blood_pressure")
    assert bp is not None
    assert bp["value_type"] == "numericDouble"
    assert bp["labels"] == ["Sistolica", "Diastolica"]


def test_create_request_value_types():
    ParameterCreateRequest(
        profile_id=uuid4(),
        name="Tacrolimus livello",
        unit="ng/mL",
        value_type="numericSingle",
        decimals=1,
    )
    ParameterCreateRequest(
        profile_id=uuid4(),
        name="Pressione",
        value_type="numericDouble",
        labels=["Sistolica", "Diastolica"],
    )
    ParameterCreateRequest(
        profile_id=uuid4(),
        name="Diario",
        value_type="text",
    )


def test_create_request_rejects_invalid_value_type():
    with pytest.raises(ValidationError):
        ParameterCreateRequest(
            profile_id=uuid4(),
            name="X",
            value_type="bogus",
        )


def test_create_request_decimals_bounds():
    with pytest.raises(ValidationError):
        ParameterCreateRequest(
            profile_id=uuid4(),
            name="X",
            value_type="numericSingle",
            decimals=5,
        )


def test_update_request_omits_value_type():
    update = ParameterUpdateRequest(name="renamed")
    # value_type isn't a field on the update schema — immutable.
    assert "value_type" not in update.model_dump(exclude_none=True)
