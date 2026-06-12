from typing import Literal

from pydantic import BaseModel, ConfigDict

# Shared enum used by both medication and settings schemas.
TrackingMode = Literal["passive", "active"]


class PharmaBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")
