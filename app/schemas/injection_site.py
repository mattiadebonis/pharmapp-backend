from app.schemas.base import PharmaBaseModel


class InjectionSiteDTO(PharmaBaseModel):
    """Single rotation site for injectable medications. The ordered list on
    Medication.injection_sites defines the rotation cycle."""

    id: str
    name: str
    zone: str | None = None
