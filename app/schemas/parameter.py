"""Parameter schema.

A parameter describes WHAT to measure. There are two families:
- Predefined: hard-coded in Python (glycemia, blood_pressure, weight, …)
- Custom: rows in the `parameters` table, identified by
  `parameter_key='custom:<uuid>'`.

Both expose the same DTO shape so callers can render them uniformly.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


ParameterValueType = Literal["numericSingle", "numericDouble", "text"]


class ParameterDTO(PharmaBaseModel):
    """Unified DTO for predefined + custom parameters.

    Predefined parameters have `id=None` (no DB row) and `is_predefined=True`.
    Custom parameters have a UUID and a profile_id.
    """

    id: UUID | None = None
    profile_id: UUID | None = None
    parameter_key: str
    name: str
    unit: str | None = None
    value_type: ParameterValueType
    labels: list[str] | None = None
    decimals: int | None = None
    is_predefined: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ParameterCreateRequest(PharmaBaseModel):
    """Create a CUSTOM parameter. The server allocates the UUID and
    derives `parameter_key='custom:<uuid>'`."""

    profile_id: UUID
    name: str = Field(min_length=1, max_length=40)
    unit: str | None = Field(None, max_length=20)
    value_type: ParameterValueType
    labels: list[str] | None = None
    decimals: int | None = Field(None, ge=0, le=4)


class ParameterUpdateRequest(PharmaBaseModel):
    """Update name/unit/labels/decimals. value_type is immutable so we
    don't need to coerce historical measurements."""

    name: str | None = Field(None, min_length=1, max_length=40)
    unit: str | None = Field(None, max_length=20)
    labels: list[str] | None = None
    decimals: int | None = Field(None, ge=0, le=4)
