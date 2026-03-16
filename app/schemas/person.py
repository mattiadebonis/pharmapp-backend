from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class PersonDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    name: str | None = None
    surname: str | None = None
    condition: str | None = None
    codice_fiscale: str | None = None
    is_account: bool
    created_at: datetime
    updated_at: datetime


class PersonCreateRequest(PharmaBaseModel):
    name: str | None = None
    surname: str | None = None
    condition: str | None = None
    codice_fiscale: str | None = None
    is_account: bool = False


class PersonUpdateRequest(PharmaBaseModel):
    name: str | None = None
    surname: str | None = None
    condition: str | None = None
    codice_fiscale: str | None = None
