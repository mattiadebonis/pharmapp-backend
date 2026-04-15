"""Classify FORMA farmaceutica into intake_method for stock tracking.

Each intake_method implies a stock_tracking_mode:
  - 'discrete': count pieces (unit_count)
  - 'continuous': measure volume/weight (volume_value)

The mapping is:
  discrete:   oral_solid, oral_capsule, oral_chew, oral_dissolve,
              oral_dissolve_water, injectable, injectable_prefilled,
              transdermal, rectal, vaginal, implant
  continuous: oral_liquid, topical_skin, auricular
  hybrid:     oral_granules_powder (bustine=discrete, multidose=continuous)
              ophthalmic (monodose=discrete, flacone=continuous)
              inhalation (capsule=discrete, puff=discrete via unit_count)
              nasal (erogazioni=discrete via unit_count, ml=continuous)
"""
from __future__ import annotations


def classify_intake_method(forma: str) -> str:
    """Classify a FORMA farmaceutica string into an intake_method enum value.

    Args:
        forma: The FORMA field from the AIFA CSV (e.g. "Compressa rivestita con film")

    Returns:
        One of: oral_solid, oral_capsule, oral_chew, oral_dissolve, oral_dissolve_water,
        oral_granules_powder, oral_liquid, injectable, injectable_prefilled, transdermal,
        rectal, vaginal, ophthalmic, auricular, inhalation, nasal, topical_skin, gas,
        implant, other, unknown
    """
    if not forma:
        return "unknown"

    fl = forma.lower().strip()

    if not fl or fl == "non nota":
        return "unknown"

    # ── Order matters: check more specific patterns first ──

    # Oral dissolve (orodispersibile, sublinguale, orosolubile)
    if any(x in fl for x in ("orodispers", "sublinguale", "orosolubile", "liofilizzato orale", "film orodispers", "film sublinguale")):
        return "oral_dissolve"

    # Oral chew
    if "masticabil" in fl:
        return "oral_chew"

    # Oral dissolve in water (effervescent, dispersible)
    if "effervescent" in fl or "dispersibil" in fl:
        return "oral_dissolve_water"

    # Oral solid (compresse, confetti, pastiglie, gomme)
    if any(x in fl for x in ("compressa", "confetto", "pastiglia", "gomma da masticare")):
        return "oral_solid"

    # Capsule (before granules because "granuli in capsule" should be capsule)
    if "capsula" in fl or "capsule" in fl:
        return "oral_capsule"

    # Oral granules/powder
    if any(x in fl for x in (
        "granul", "polvere per soluzione orale", "polvere per sospensione orale",
        "granulato per soluzione", "granulato per sospensione",
        "polvere orale",
    )):
        return "oral_granules_powder"

    # Oral liquid (gocce, sciroppo, soluzione orale, sospensione orale)
    if any(x in fl for x in (
        "gocce orali", "soluzione orale", "sospensione orale", "sciroppo",
        "elisir", "emulsione orale", "soluzione per mucosa orale",
        "sospensione orale in bustina", "soluzione orale in bustina",
        "soluzione orale in contenitore",
    )):
        return "oral_liquid"

    # Injectable prefilled (before generic injectable)
    if any(x in fl for x in ("siringa pre", "penna pre")):
        return "injectable_prefilled"

    # Injectable
    if any(x in fl for x in (
        "iniettabile", "infusione", "parenterale", "concentrato per soluzione",
        "polvere e solvente per soluzione iniett", "polvere per soluzione iniett",
        "sospensione iniettabile",
    )):
        return "injectable"

    # Transdermal
    if any(x in fl for x in ("cerotto", "transderm")):
        return "transdermal"

    # Rectal
    if any(x in fl for x in ("supposta", "suppositorio", "soluzione rettale")):
        return "rectal"

    # Vaginal
    if any(x in fl for x in ("ovulo", "vaginale", "lavanda")):
        return "vaginal"

    # Ophthalmic
    if any(x in fl for x in ("collirio", "gel oftalmico", "unguento oftalmico")):
        return "ophthalmic"

    # Auricular
    if any(x in fl for x in ("gocce auricolari", "auricolar")):
        return "auricular"

    # Inhalation
    if any(x in fl for x in (
        "inalazione", "inalatorio", "nebulizzat", "pressurizzat",
        "polvere per inalazione",
    )):
        return "inhalation"

    # Nasal
    if any(x in fl for x in ("spray nasale", "gocce nasali", "polvere nasale")):
        return "nasal"

    # Topical skin
    if any(x in fl for x in (
        "crema", "gel", "unguento", "pomata", "lozione", "soluzione cutanea",
        "schiuma cutanea", "emulsione cutanea", "polvere cutanea",
    )):
        return "topical_skin"

    # Gas
    if any(x in fl for x in ("gas medicinale", "gas per inalazione", "ossigeno")):
        return "gas"

    # Implant
    if any(x in fl for x in ("impianto", "intrauterino", "intravitreal")):
        return "implant"

    return "other"


# Stock tracking mode derived from intake_method
TRACKING_MODE = {
    "oral_solid": "discrete",
    "oral_capsule": "discrete",
    "oral_chew": "discrete",
    "oral_dissolve": "discrete",
    "oral_dissolve_water": "discrete",
    "oral_granules_powder": "discrete",  # bustine=discrete; multidose overridden by app
    "oral_liquid": "continuous",
    "injectable": "discrete",
    "injectable_prefilled": "discrete",
    "transdermal": "discrete",
    "rectal": "discrete",
    "vaginal": "discrete",
    "ophthalmic": "continuous",  # monodose overridden to discrete by app
    "auricular": "continuous",
    "inhalation": "discrete",  # dosi/capsule
    "nasal": "discrete",  # erogazioni
    "topical_skin": "continuous",
    "gas": "continuous",
    "implant": "discrete",
    "other": "discrete",
    "unknown": "discrete",
}


def get_stock_tracking_mode(intake_method: str) -> str:
    """Return 'discrete' or 'continuous' for a given intake_method."""
    return TRACKING_MODE.get(intake_method, "discrete")
