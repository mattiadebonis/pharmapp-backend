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


# ---------------------------------------------------------------------------
# "La mia giornata" — anchors
# ---------------------------------------------------------------------------
# Ogni profilo ha una lista di "eventi della giornata" completamente
# personalizzabili. I 5 default seedati alla creazione (Risveglio,
# Colazione, Pranzo, Cena, Notte) sono solo punti di partenza:
# l'utente può rinominarli, eliminarli e aggiungerne di nuovi.
#
# Ogni evento è composto da uno o più `slots`. Ogni slot è
# (id, time, weekdays). Pattern supportati nativamente:
#   * single-slot:  [Tutti i giorni · 06:30]
#   * weekend split: [Lun-Ven · 06:30, Sab-Dom · 08:30]
#   * turni di lavoro: [Lun-Mer · 06:00, Gio-Ven · 14:00, Sab-Dom · 09:00]
#
# Vincolo applicato dal client (UI + AppModel.updateAnchors): all'interno
# di un singolo evento, ogni giorno della settimana appare in al più uno
# slot. Sovrapposizioni vengono risolte rimuovendo i giorni dagli slot
# esistenti quando lo slot in editing li reclama.
class AnchorSlotDTO(PharmaBaseModel):
    id: UUID
    time: str  # "HH:mm"
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])


class ProfileAnchorDTO(PharmaBaseModel):
    id: UUID
    name: str
    slots: list[AnchorSlotDTO]


# UUID stabili per i 5 eventi di default — replicati in
# `Models.swift::ProfileAnchor.defaultIDs` per allineare client e backend.
_DEFAULT_ANCHOR_IDS: dict[str, UUID] = {
    "Risveglio": UUID("11111111-1111-1111-1111-111111111111"),
    "Colazione": UUID("22222222-2222-2222-2222-222222222222"),
    "Pranzo":    UUID("33333333-3333-3333-3333-333333333333"),
    "Cena":      UUID("44444444-4444-4444-4444-444444444444"),
    "Notte":     UUID("55555555-5555-5555-5555-555555555555"),
}

_DEFAULT_ANCHOR_SPECS: list[tuple[str, str]] = [
    ("Risveglio", "06:30"),
    ("Colazione", "07:00"),
    ("Pranzo",    "13:00"),
    ("Cena",      "20:00"),
    ("Notte",     "23:00"),
]


def _default_anchors() -> list[ProfileAnchorDTO]:
    return [
        ProfileAnchorDTO(
            id=_DEFAULT_ANCHOR_IDS[name],
            name=name,
            slots=[AnchorSlotDTO(id=uuid4(), time=time, weekdays=[1, 2, 3, 4, 5, 6, 7])],
        )
        for name, time in _DEFAULT_ANCHOR_SPECS
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
