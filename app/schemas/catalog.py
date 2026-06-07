from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.base import PharmaBaseModel

# I DTO del catalog sono particolarmente esposti a evoluzioni di schema
# (RPC server-side che aggiungono campi via migration). Per evitare che
# un campo nuovo nel JSON DB faccia esplodere l'endpoint con 500 prima
# che il backend sia deployato con il DTO aggiornato, override del
# default `extra="forbid"` di PharmaBaseModel a `extra="ignore"` per il
# modulo catalog. Hostile-extension protection si fa altrove (auth,
# validazione write-side); qui leggiamo da una RPC controllata.
_CATALOG_DTO_CONFIG = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    extra="ignore",
)


class AtcLevelDTO(PharmaBaseModel):
    """Una voce del dizionario ATC con il suo codice e descrizione italiana."""

    model_config = _CATALOG_DTO_CONFIG

    code: str
    description_it: str


class AtcDecodedDTO(PharmaBaseModel):
    """Decodifica gerarchica di un codice ATC.

    Esempio (H03AA01, Eutirox):
        code:        "H03AA01"
        l1:          {code: "H",      description_it: "Preparati ormonali sistemici (esclusi ormoni sessuali e insuline)"}
        l2:          {code: "H03",    description_it: "Terapia tiroidea"}
        l3:          {code: "H03A",   description_it: "Preparati tiroidei"}
        l4:          null   (non popolato per ora)
        summary_it:  "Preparati tiroidei"  (livello più specifico disponibile)

    `summary_it` è il "best label" da mostrare nella UI quando si ha
    poco spazio. La gerarchia completa è disponibile per breadcrumb /
    visualizzazione espansa.
    """

    model_config = _CATALOG_DTO_CONFIG

    code: str
    l1: AtcLevelDTO | None = None
    l2: AtcLevelDTO | None = None
    l3: AtcLevelDTO | None = None
    l4: AtcLevelDTO | None = None
    summary_it: str | None = None


class ShortageInfoDTO(PharmaBaseModel):
    """Una carenza AIFA attiva per una specifica confezione (AIC).

    Popolato da scripts/scrape_aifa_carenze.py + RPC
    fetch_shortages_for_product / fetch_catalog_product_v1.
    Migration 035.
    """

    model_config = _CATALOG_DTO_CONFIG

    codice_aic: str
    reason: str | None = None
    # Date come stringhe ISO (yyyy-mm-dd) o NULL se AIFA non
    # comunica una data certa ("in attesa di comunicazione").
    start_date: str | None = None
    expected_end_date: str | None = None
    # Eventuali farmaci alternativi indicati da AIFA (testo libero).
    substitutes: str | None = None


class CatalogSearchResultDTO(PharmaBaseModel):
    model_config = _CATALOG_DTO_CONFIG

    country: str
    source: str
    product_id: str
    package_id: str
    family_id: str | None = None
    display_name: str
    brand_name: str | None = None
    generic_name: str | None = None
    principle: str | None = None
    manufacturer_name: str | None = None
    requires_prescription: bool
    package_label: str | None = None
    units_per_package: int = Field(validation_alias="units")
    form_type: str | None = Field(default=None, validation_alias="tipologia")
    dosage_value: int = Field(default=0, validation_alias="valore")
    dosage_unit: str = Field(default="", validation_alias="unita")
    strength_text: str | None = None
    volume: str = ""
    availability: str
    catalog_code: str | None = None
    catalog_snapshot: dict[str, Any] = {}
    # New fields from CSV
    link_fi: str | None = None
    link_rcp: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    is_homeopathic: bool | None = None


class CatalogProductSearchResultDTO(PharmaBaseModel):
    """Riga aggregata della ricerca catalogo (1 per cod_farmaco).

    Espone i conteggi (`variant_count`, `package_count`) e, quando applicabile,
    i campi `single_*` per il caso "1-tap final" (1 variante, 1 confezione).
    """

    model_config = _CATALOG_DTO_CONFIG

    country: str
    product_id: str
    display_name: str
    generic_name: str | None = None
    principle: str | None = None
    requires_prescription: bool | None = None
    variant_count: int = 0
    package_count: int = 0
    # Compilati solo se variant_count == 1 / package_count == 1
    single_strength_text: str | None = None
    single_form_type: str | None = None
    single_package_label: str | None = None
    single_units: int | None = None
    single_package_id: str | None = None
    single_catalog_code: str | None = None
    # Meta utili al client
    link_fi: str | None = None
    link_rcp: str | None = None
    codice_atc: str | None = None
    is_homeopathic: bool | None = None


class CatalogProductDTO(PharmaBaseModel):
    model_config = _CATALOG_DTO_CONFIG

    id: str
    country: str
    source: str
    source_product_id: str
    family_id: str | None = None
    display_name: str
    brand_name: str | None = None
    generic_name: str | None = None
    active_ingredients: list[dict[str, Any]] = []
    dosage_form: str | None = None
    routes: list[str] = []
    strength_text: str | None = None
    manufacturer_name: str | None = None
    requires_prescription: bool | None = None
    availability: str
    atc_codes: list[str] = []
    regulatory: dict[str, Any] = {}
    packages: list[dict[str, Any]] = []
    source_meta: dict[str, Any] | None = None
    # New fields from CSV
    link_fi: str | None = None
    link_rcp: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    # Decodifica ATC gerarchica (popolata da decode_atc RPC in
    # fetch_catalog_product_v1). Migration 031-032.
    atc_decoded: AtcDecodedDTO | None = None
    # Classe di rimborsabilità AIFA prevalente per il prodotto.
    # NULL se nessuna confezione ha ancora dati importati dalle
    # liste di trasparenza. Migration 034.
    reimbursement_class: str | None = None
    # Stato carenze AIFA: has_active_shortage indica se almeno
    # una confezione del prodotto è attualmente carente. `shortages`
    # è l'elenco dettagliato per UI. Migration 035.
    has_active_shortage: bool = False
    shortages: list[ShortageInfoDTO] = []
    is_homeopathic: bool | None = None
    forme_distinte: list[str] = []


class CatalogPackageDTO(PharmaBaseModel):
    model_config = _CATALOG_DTO_CONFIG

    id: str
    source_package_id: str
    package_code: str | None = None
    display_name: str | None = None
    unit_count: int | None = None
    package_type: str | None = None
    volume_value: float | None = None
    volume_unit: str | None = None
    strength_text: str | None = None
    marketed: bool | None = None
    marketing_start_date: str | None = None
    marketing_end_date: str | None = None
    is_sample: bool | None = None
    requires_prescription: bool | None = None
    reimbursement_class: str | None = None
    reimbursement_text: str | None = None
    # Prezzo di riferimento AIFA (lista di trasparenza). Migration 034.
    reference_price: float | None = None
    shortage_reason: str | None = None
    shortage_start_date: str | None = None
    shortage_end_date: str | None = None
    availability: str | None = None
    source_meta: dict[str, Any] | None = None
    # New fields from CSV
    fornitura: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    forma: str | None = None
    intake_method: str | None = None
