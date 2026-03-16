from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class StockDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    tracked_package_id: UUID
    context_key: str
    stock_units: int
    updated_at: datetime


class StockSetRequest(PharmaBaseModel):
    stock_units: int


class StockIncrementRequest(PharmaBaseModel):
    delta: int
