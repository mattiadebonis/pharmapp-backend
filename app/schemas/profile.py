from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
ProfileType = Literal["own", "assisted", "dependent"]
ConnectionStatus = Literal["active", "pending"]
AnchorKind = Literal["wake", "breakfast", "lunch", "dinner", "night"]


# ---------------------------------------------------------------------------
# "La mia giornata" — anchors
# ---------------------------------------------------------------------------
# Ogni profilo ha 5 anchor che descrivono i momenti della giornata
# (Risveglio, Colazione, Pranzo, Cena, Notte). I farmaci possono essere
# "agganciati" a un anchor invece che a un orario fisso, così quando
# l'utente sposta — ad esempio — il risveglio da 06:30 a 07:00, tutte
# le dosi anchored seguono automaticamente.
#
# `time` è l'orario unico in formato "HH:mm". `weekdays` è la lista
# (ISO 8601: 1=Lun … 7=Dom) dei giorni in cui l'anchor è attivo. Per
# default copre tutti e 7 i giorni; l'utente può deselezionarne alcuni
# per coprire pattern come "Pranzo solo Lun-Ven".
class ProfileAnchorDTO(PharmaBaseModel):
    kind: AnchorKind
    time: str  # "HH:mm"
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])


def _default_anchors() -> list[ProfileAnchorDTO]:
    return [
        ProfileAnchorDTO(kind="wake", time="06:30"),
        ProfileAnchorDTO(kind="breakfast", time="07:00"),
        ProfileAnchorDTO(kind="lunch", time="13:00"),
        ProfileAnchorDTO(kind="dinner", time="20:00"),
        ProfileAnchorDTO(kind="night", time="23:00"),
    ]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class ProfileDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    profile_type: ProfileType
    display_name: str
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None
    relation_label: str | None = None
    connection_status: ConnectionStatus | None = None
    # Today v2 — timestamp di pausa terapia globale. Quando != null la
    # Today mostra solo la card muted "In pausa dal X" + CTA "Riprendi".
    therapy_paused_at: datetime | None = None
    # Today v2 — "Modalità ridotta / Giornata difficile": filtra la Today
    # ai soli farmaci con criticality='critical'.
    critical_only_mode: bool = False
    # "La mia giornata" — 5 momenti del giorno (vedi ProfileAnchorDTO).
    # Backfillato dalla migration 038 sui profili esistenti.
    anchors: list[ProfileAnchorDTO] = Field(default_factory=_default_anchors)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request – client-supplied fields only
# ---------------------------------------------------------------------------
class ProfileCreateRequest(PharmaBaseModel):
    id: UUID | None = None
    profile_type: ProfileType
    display_name: str
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None
    relation_label: str | None = None
    connection_status: ConnectionStatus | None = None
    therapy_paused_at: datetime | None = None
    critical_only_mode: bool = False
    anchors: list[ProfileAnchorDTO] | None = None


# ---------------------------------------------------------------------------
# Update request – every field optional
# ---------------------------------------------------------------------------
class ProfileUpdateRequest(PharmaBaseModel):
    profile_type: ProfileType | None = None
    display_name: str | None = None
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None
    relation_label: str | None = None
    connection_status: ConnectionStatus | None = None
    therapy_paused_at: datetime | None = None
    critical_only_mode: bool | None = None
    anchors: list[ProfileAnchorDTO] | None = None
