"""Golden set di regression sui farmaci più prescritti in Italia.

Questi test sono "live": interrogano Supabase tramite supabase-py e
verificano che lo `strength_text`, `strength_value`, `strength_unit` e
`unit_count` in DB siano quelli attesi. Marcati `@pytest.mark.golden`
così si possono escludere in CI senza credenziali DB.

Eseguibili con:
    pytest app/tests/test_aifa_parser_golden.py -v
    pytest -m golden -v
    pytest -m "golden and not slow" -v  (sottoset rapido)

Aggiornamento del set: i valori attesi sono stati estratti dal DB live
post-fix migration 036 (cleanup omeopatici/legacy) + parser v2.6 (fix
trifasici + boundary cut). Se in futuro AIFA cambia la `DESCRIZIONE`
di una confezione, il test segnalerà la divergenza e va valutato se
- aggiornare il valore atteso (la nuova interpretazione AIFA è giusta)
- aggiungere/fixare il parser (la descrizione è cambiata in un nuovo formato)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ─── Golden set ──────────────────────────────────────────────────────────────
# Tuple: (codice_aic, denominazione, expected_strength_text, expected_value, expected_unit, expected_unit_count)
GOLDEN_SET: list[tuple[str, str, str, float, str, int]] = [
    # Analgesici / FANS / antipiretici
    ("004763037", "ASPIRINA", "500 MG", 500.0, "MG", 20),
    ("024840074", "CARDIOASPIRIN", "100 MG", 100.0, "MG", 30),
    ("025940026", "AULIN", "100 MG", 100.0, "MG", 30),
    ("022593115", "BRUFEN", "800 MG", 800.0, "MG", 20),
    ("029396013", "BUSCOFEN", "200 MG", 200.0, "MG", 20),
    ("025669019", "MOMENT", "200 MG", 200.0, "MG", 12),
    ("028511057", "OKI", "160 MG", 160.0, "MG", 10),
    ("012745028", "TACHIPIRINA", "500 MG", 500.0, "MG", 10),
    ("026608036", "EFFERALGAN", "500 MG", 500.0, "MG", 16),
    ("023181011", "VOLTAREN", "50 MG", 50.0, "MG", 30),
    ("031825045", "TACHIDOL", "500 MG/30 MG", 500.0, "MG/30MG", 10),

    # Antibiotici
    ("026089019", "AUGMENTIN", "875 MG/125 MG", 875.0, "MG/125MG", 12),
    ("027370055", "KLACID", "250 MG", 250.0, "MG", 12),
    ("027530056", "MACLADIN", "250 MG", 250.0, "MG", 12),
    ("026664019", "CIPROXIN", "250 MG", 250.0, "MG", 10),
    ("025202019", "ROCEFIN", "250 MG/2 ML", 250.0, "MG/2ML", 1),

    # Cardiovascolari
    ("016366027", "COUMADIN", "5 MG", 5.0, "MG", 30),
    ("041225018", "ELIQUIS", "2,5 MG", 2.5, "MG", 10),
    ("038744025", "XARELTO", "10 MG", 10.0, "MG", 10),
    ("038451011", "PRADAXA", "75 MG", 75.0, "MG", 10),
    ("027161052", "TRIATEC", "2,5 MG", 2.5, "MG", 28),
    ("027428010", "NORVASC", "5 MG", 5.0, "MG", 28),
    ("032210015", "LOBIVON", "5 MG", 5.0, "MG", 28),
    ("026573016", "CONCOR", "10 MG", 10.0, "MG", 28),
    ("034954014", "CARDICOR", "1.25 MG", 1.25, "MG", 28),
    ("023993013", "LASIX", "25 MG", 25.0, "MG", 30),
    ("026966097", "CLEXANE", "2.000 UI", 2000.0, "UI", 10),
    ("034128013", "PLAVIX", "75 MG", 75.0, "MG", 28),

    # PPI / gastro
    ("028245090", "ANTRA", "20 MG", 20.0, "MG", 14),
    ("028600017", "LANSOX", "30 MG", 30.0, "MG", 14),
    ("034216022", "PARIET", "10 MG", 10.0, "MG", 14),
    ("031835022", "PANTOPAN", "20 MG", 20.0, "MG", 14),
    ("035367046", "LUCEN", "20 MG", 20.0, "MG", 14),

    # Statine / diabete
    ("035885021", "CRESTOR", "10 MG", 10.0, "MG", 14),
    ("017758018", "GLUCOPHAGE", "500 MG", 500.0, "MG", 30),
    ("043443023", "JARDIANCE", "25 MG", 25.0, "MG", 10),
    ("035724044", "LANTUS", "100 IU", 100.0, "IU", 10),
    ("043783012", "TRULICITY", "0,75 MG", 0.75, "MG", 2),
    ("046128017", "OZEMPIC", "1,34 MG/ML", 1.34, "MG/ML", 1),

    # Tiroide
    ("024402048", "EUTIROX", "25 MCG", 25.0, "MCG", 50),
    ("034368074", "TIROSINT", "25 MCG/1 ML", 25.0, "MCG/1ML", 30),

    # Psico / neuro
    ("025980057", "XANAX", "0,25 MG", 0.25, "MG", 20),
    ("022531053", "TAVOR", "1 MG", 1.0, "MG", 20),
    ("023593015", "EN", "0,5 MG", 0.5, "MG", 20),
    ("022905121", "LEXOTAN", "3 MG", 3.0, "MG", 20),
    ("022323036", "TRITTICO", "50 MG", 50.0, "MG", 30),
    ("027753019", "ZOLOFT", "50 MG", 50.0, "MG", 15),
    ("035767019", "CIPRALEX", "5 MG", 5.0, "MG", 14),
    ("036476012", "LYRICA", "25 MG", 25.0, "MG", 14),
    ("022483109", "DEPAKIN", "300 MG", 300.0, "MG", 30),
    ("035039015", "KEPPRA", "250 MG", 250.0, "MG", 20),
    ("036582017", "ABILIFY", "5 MG", 5.0, "MG", 1),
    ("032944023", "SEROQUEL", "100 MG", 100.0, "MG", 30),
    ("028752018", "RISPERDAL", "1 MG", 1.0, "MG", 20),
    ("043187018", "BRINTELLIX", "5 MG", 5.0, "MG", 14),

    # Asma / COPD
    ("022984052", "VENTOLIN", "100 MCG", 100.0, "MCG", 200),
    ("023103132", "CLENIL", "800 MCG", 800.0, "MCG", 20),
    ("035668019", "SPIRIVA", "18 MCG", 18.0, "MCG", 30),

    # Inquadrare il combo "per inalazione" — strength_text deve includere entrambi le dosi
    # Symbicort 160/4,5/INALAZIONE: forma "Polvere per inalazione"
    # (test diretto su strength_text richiede match parziale)
]


# Combo "complete dose info" — verificano che TUTTE le dosi siano presenti
# anche quando il chip è lungo. Più sciolto: assert su substring.
GOLDEN_SET_COMBO: list[tuple[str, str, list[str]]] = [
    # (codice_aic, denominazione, lista_substring_attese)
    ("035194012", "SYMBICORT",   ["160", "4,5"]),
    ("049585019", "SERETIDE",    ["50", "500"]),
    ("021978046", "BACTRIM",     ["160", "800"]),
    ("049473010", "BRILADONA TRIFASE", ["0,180", "0,215", "0,250", "0,035"]),
]


# ─── Test helpers ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def supabase_client():
    """Crea il client Supabase una volta sola per session."""
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    env_vars: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")
    url = os.environ.get("SUPABASE_URL") or env_vars.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or env_vars.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY non impostati (CI senza credenziali)")
    from supabase import create_client  # type: ignore[import-not-found]
    return create_client(url, key)


def _fetch_pkg(supabase, codice_aic: str) -> dict | None:
    result = supabase.table("catalog_it_packages") \
        .select("strength_text, strength_value, strength_unit, unit_count, descrizione") \
        .eq("codice_aic", codice_aic).execute()
    return result.data[0] if result.data else None


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("aic,nome,expected_text,expected_value,expected_unit,expected_count", GOLDEN_SET)
def test_golden_brand_exact(supabase_client, aic, nome, expected_text, expected_value, expected_unit, expected_count):
    """Verifica che lo strength parsato in DB sia EXACT per i farmaci top."""
    pkg = _fetch_pkg(supabase_client, aic)
    assert pkg is not None, f"AIC {aic} ({nome}) non trovato in catalog_it_packages"
    assert pkg["strength_text"] == expected_text, (
        f"[{nome} AIC={aic}] strength_text mismatch: "
        f"atteso {expected_text!r}, ottenuto {pkg['strength_text']!r}. "
        f"DESCRIZIONE: {pkg['descrizione']!r}"
    )
    assert pkg["strength_value"] == expected_value, (
        f"[{nome}] strength_value: atteso {expected_value}, ottenuto {pkg['strength_value']}"
    )
    assert pkg["strength_unit"] == expected_unit, (
        f"[{nome}] strength_unit: atteso {expected_unit!r}, ottenuto {pkg['strength_unit']!r}"
    )
    assert pkg["unit_count"] == expected_count, (
        f"[{nome}] unit_count: atteso {expected_count}, ottenuto {pkg['unit_count']}"
    )


@pytest.mark.golden
@pytest.mark.parametrize("aic,nome,expected_substrings", GOLDEN_SET_COMBO)
def test_golden_combo_substrings(supabase_client, aic, nome, expected_substrings):
    """Per le combo a 2+ dosi, verifica che TUTTE le dosi appaiano in strength_text."""
    pkg = _fetch_pkg(supabase_client, aic)
    assert pkg is not None, f"AIC {aic} ({nome}) non trovato"
    st = pkg["strength_text"] or ""
    for substr in expected_substrings:
        assert substr in st, (
            f"[{nome} AIC={aic}] manca substring {substr!r} in strength_text {st!r}. "
            f"DESCRIZIONE: {pkg['descrizione']!r}"
        )


@pytest.mark.golden
def test_golden_set_coverage(supabase_client):
    """Sanity: il golden set copre almeno 55 AIC distinti (mono+combo)."""
    total = len(GOLDEN_SET) + len(GOLDEN_SET_COMBO)
    assert total >= 55, f"Golden set troppo piccolo: {total} voci"
    all_aic = [row[0] for row in GOLDEN_SET] + [row[0] for row in GOLDEN_SET_COMBO]
    assert len(set(all_aic)) == len(all_aic), "AIC duplicati nel golden set"
