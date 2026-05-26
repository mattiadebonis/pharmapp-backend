from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

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
# Ogni anchor è composto da uno o più `slots`. Ogni slot è
# (id, time, weekdays). Pattern supportati nativamente:
#   * single-slot:  [Tutti i giorni · 06:30]
#   * weekend split: [Lun-Ven · 06:30, Sab-Dom · 08:30]
#   * turni di lavoro: [Lun-Mer · 06:00, Gio-Ven · 14:00, Sab-Dom · 09:00]
#
# Vincolo applicato dal client (UI + AppModel.updateAnchors): all'interno
# di un singolo anchor, ogni giorno della settimana appare in al più uno
# slot. Sovrapposizioni vengono risolte rimuovendo i giorni dagli slot
# esistenti quando lo slot in editing li reclama.
class AnchorSlotDTO(PharmaBaseModel):
    id: UUID
    time: str  # "HH:mm"
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])


class ProfileAnchorDTO(PharmaBaseModel):
    kind: AnchorKind
    slots: list[AnchorSlotDTO]


def _default_anchors() -> list[ProfileAnchorDTO]:
    def _slot(time: str) -> AnchorSlotDTO:
        return AnchorSlotDTO(id=uuid4(), time=time, weekdays=[1, 2, 3, 4, 5, 6, 7])

    return [
        ProfileAnchorDTO(kind="wake", slots=[_slot("06:30")]),
        ProfileAnchorDTO(kind="breakfast", slots=[_slot("07:00")]),
        ProfileAnchorDTO(kind="lunch", slots=[_slot("13:00")]),
        ProfileAnchorDTO(kind="dinner", slots=[_slot("20:00")]),
        ProfileAnchorDTO(kind="night", slots=[_slot("23:00")]),
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
