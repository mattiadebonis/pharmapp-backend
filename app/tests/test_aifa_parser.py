"""Tests per il parser AIFA `parse_denominazione_package`.

Copre i casi reali presi dal CSV `confezioni_fornitura.csv`. La regressione
principale che ha motivato l'audit del catalogo: il parser perdeva il
dosaggio quando AIFA scriveva l'unità per esteso ("MICROGRAMMI" anziché
"MCG") — 1.653 confezioni AIFA su 392 prodotti, inclusi Eutirox, Tirosint,
Ventolin, Symbicort, Cerazette, le levotiroxine generiche.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ non è una package; aggiungiamo il path come fa import_aifa_csv.py.
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from parsers.aifa_package_parser import parse_denominazione_package  # noqa: E402


# ─── Eutirox e altre tiroidi: parola "MICROGRAMMI" ───────────────────────────

class TestMicrogrammiWord:
    """Eutirox & co. usano "MICROGRAMMI" per esteso. Il parser deve
    riconoscerlo come equivalente a "MCG" e popolare strength_text/value/unit.
    """

    def test_eutirox_25mcg(self):
        p = parse_denominazione_package("25 MICROGRAMMI COMPRESSE- 50 COMPRESSE IN BLISTER PVC/AL")
        assert p.strength_value == 25.0
        assert p.strength_unit == "MCG"
        assert p.strength_text.upper().startswith("25 MCG")
        assert p.unit_count == 50
        assert p.package_type == "Compresse"

    def test_eutirox_175mcg_with_leading_space(self):
        # AIFA a volte mette uno spazio iniziale nella descrizione
        p = parse_denominazione_package(" 175 MICROGRAMMI COMPRESSE - 50 COMPRESSE IN BLISTER PVC/AL")
        assert p.strength_value == 175.0
        assert p.strength_unit == "MCG"

    def test_levotiroxina_doc_25mcg(self):
        p = parse_denominazione_package("25 MICROGRAMMI COMPRESSE- 15 COMPRESSE IN BLISTER PVC/PVDC/AL")
        assert p.strength_value == 25.0
        assert p.strength_unit == "MCG"
        assert p.unit_count == 15

    def test_tirosint_gocce_microgrammi_per_ml(self):
        p = parse_denominazione_package("100 MICROGRAMMI/ML GOCCE ORALI, SOLUZIONE - FLACONE 20 ML")
        assert p.strength_value == 100.0
        assert "MCG" in p.strength_unit.upper()
        assert "ML" in p.strength_unit.upper()
        # volume del flacone deve essere catturato a parte
        assert p.volume_value == 20.0
        assert p.volume_unit == "ML"

    def test_dobetin_b12_microgrammi(self):
        p = parse_denominazione_package("1000 MICROGRAMMI/ML SOLUZIONE INIETTABILE- 5 FIALE DA  1 ML")
        assert p.strength_value == 1000.0
        assert "MCG" in p.strength_unit.upper()
        assert "ML" in p.strength_unit.upper()


# ─── MILLIGRAMMI per esteso (raro ma esiste in AIFA) ─────────────────────────

class TestMilligrammiWord:
    def test_unoxir_milligrammi(self):
        p = parse_denominazione_package(
            "15 MILLIGRAMMI COMPRESSE RIVESTITE CON FILM- 28 COMPRESSE IN BLISTER PVC/PVDC/AL"
        )
        assert p.strength_value == 15.0
        assert p.strength_unit == "MG"
        assert p.strength_text.upper().startswith("15 MG")
        assert p.unit_count == 28


# ─── Denominatori "/EROGAZIONE", "/INALAZIONE", "/ORA" (cerotti, spray) ──────

class TestPerXDenominators:
    """Spray nasali, inalatori, cerotti trasdermici usano denominatori come
    "/EROGAZIONE", "/INALAZIONE", "/ORA". Vanno parsati come parte dell'unità,
    non scartati.
    """

    def test_nasonex_per_erogazione(self):
        p = parse_denominazione_package(
            "50 MICROGRAMMI/EROGAZIONE SPRAY NASALE, SOSPENSIONE- 1 FLACONE 140 EROGAZIONI"
        )
        assert p.strength_value == 50.0
        assert "MCG" in p.strength_unit.upper()
        assert "EROGAZ" in p.strength_unit.upper()

    def test_busette_cerotto_per_ora(self):
        p = parse_denominazione_package(
            "5 MICROGRAMMI/ORA, CEROTTO TRASDERMICO - 2 CEROTTI"
        )
        assert p.strength_value == 5.0
        assert "MCG" in p.strength_unit.upper()
        assert "ORA" in p.strength_unit.upper()

    def test_ventolin_inalatore(self):
        p = parse_denominazione_package(
            "100 MICROGRAMMI SOSPENSIONE PRESSURIZZATA PER INALAZIONE-1 CONTENITORE SOTTO PRESSIONE 200 EROGAZIONI"
        )
        # qui non c'è "/EROGAZIONE" né "/INALAZIONE" come denominatore,
        # ma "200 EROGAZIONI" è il count del package
        assert p.strength_value == 100.0
        assert p.strength_unit == "MCG"
        # 200 erogazioni = unit_count (è il count del package, non la strength)
        assert p.unit_count == 200


# ─── Concentrazioni X UI/ML — denominatore senza numero ──────────────────────

class TestUIperML:
    """40 UI/ML è una concentrazione di insulina. Va parsata come unità
    composta, non spezzata in "40 UI" + denominatore mancante.
    """

    def test_insulina_40_ui_ml(self):
        p = parse_denominazione_package(
            "40 UI/ML SOLUZIONE INIETTABILE-PENNA 3 ML"
        )
        assert p.strength_value == 40.0
        assert "UI" in p.strength_unit.upper()
        assert "ML" in p.strength_unit.upper()
        # volume della penna deve essere a parte
        assert p.volume_value == 3.0

    def test_insulina_300_ui_su_0_3_ml(self):
        # Caso con denominatore numerico esplicito
        p = parse_denominazione_package(
            "300 UI/0,3 ML SOLUZIONE INIETTABILE - 1 SIRINGA PRERIEMPITA DA 0,3 ML"
        )
        assert p.strength_value == 300.0
        # Deve mantenere il /0,3 ML nel formato (sia denominator numerico)
        assert "UI" in p.strength_unit.upper()


# ─── Casi che già funzionavano: regression guard ─────────────────────────────

class TestExistingBehavior:
    """Verifica che il fix non rompa casi che già funzionavano."""

    def test_compresse_mg(self):
        p = parse_denominazione_package("1000 MG COMPRESSE - 16 COMPRESSE")
        assert p.strength_value == 1000.0
        assert p.strength_unit == "MG"
        assert p.unit_count == 16

    def test_effervescenti_mg(self):
        p = parse_denominazione_package("500 MG COMPRESSE EFFERVESCENTI-20 CPR EFF.")
        assert p.strength_value == 500.0
        assert p.strength_unit == "MG"
        assert p.unit_count == 20

    def test_sciroppo_mg_per_ml(self):
        p = parse_denominazione_package("120 MG/5 ML SCIROPPO- FLACONE 100 ML")
        assert p.strength_value == 120.0
        assert "MG" in p.strength_unit.upper()
        assert "ML" in p.strength_unit.upper()
        assert p.volume_value == 100.0
        assert p.volume_unit == "ML"

    def test_crema_percentuale(self):
        p = parse_denominazione_package("5% CREMA-TUBO DA 30 G")
        assert p.strength_value == 5.0
        assert p.strength_unit == "%"
        assert p.volume_value == 30.0
        assert p.volume_unit == "G"

    def test_amoxi_clavulanico_combo_slash(self):
        # Combo con / come separatore (già funzionava parzialmente)
        p = parse_denominazione_package("875 MG/125 MG COMPRESSE RIVESTITE-12 COMPRESSE")
        assert p.strength_value == 875.0
        assert p.strength_unit.upper().startswith("MG")
        # Il testo deve riflettere entrambe le dosi
        assert "125" in p.strength_text
        assert p.unit_count == 12

    def test_tisana_grammi_per_bustina(self):
        p = parse_denominazione_package("1,3 G TISANA-20 BUSTINE")
        assert p.strength_value == 1.3
        assert p.strength_unit == "G"
        assert p.unit_count == 20
        assert p.package_type == "Bustine"


# ─── Combinazioni con "+" (paracetamolo+codeina ecc.) ────────────────────────

class TestCombinations:
    """Combinazioni di principi attivi con separatore +. Oggi il parser
    cattura solo la prima dose; dopo il fix vogliamo entrambe nel
    strength_text per disambiguare visivamente.
    """

    def test_paracetamolo_codeina(self):
        p = parse_denominazione_package(
            "500 MG + 30 MG COMPRESSE EFFERVESCENTI- 20 COMPRESSE"
        )
        # Almeno la dose primaria deve essere catturata
        assert p.strength_value == 500.0
        # strength_text deve contenere entrambe le dosi per disambiguazione
        assert "500" in p.strength_text
        assert "30" in p.strength_text
        assert p.unit_count == 20

    def test_symbicort_combo_per_inalazione(self):
        p = parse_denominazione_package(
            "TURBOHALER 160 MICROGRAMMI/4,5 MICROGRAMMI/INALAZIONE POLVERE PER INALAZIONE- 1 INALATORE 120 DOSI"
        )
        # Entrambe le dosi devono essere riconosciute
        assert "160" in p.strength_text
        assert "4,5" in p.strength_text or "4.5" in p.strength_text


# ─── Casi limite e robustezza ────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_input(self):
        p = parse_denominazione_package(None)
        assert p.strength_value is None
        assert p.strength_text == ""

    def test_empty_string(self):
        p = parse_denominazione_package("")
        assert p.strength_value is None

    def test_no_strength_just_form(self):
        # Vaccini, balsami: nessuna dose esplicita
        p = parse_denominazione_package("<UNGUENTO> TUBO IN ALLUMINIO DA 50 G")
        # Il "50 G" qui è VOLUME del tubo, non strength. Non deve essere
        # catturato come strength.
        assert p.strength_text in ("", None) or "50" not in (p.strength_text or "")
        assert p.volume_value == 50.0
        assert p.volume_unit == "G"

    def test_volume_only_no_strength(self):
        # Vaccino siringa preriempita
        p = parse_denominazione_package(
            "SOSPENSIONE INIETTABILE IN SIRINGA PRERIEMPITA- 1 SIRINGA DA 0,5 ML SENZA AGO"
        )
        # Niente strength, ma volume sì
        assert p.strength_text in ("", None) or not p.strength_text
        assert p.volume_value == 0.5
        assert p.volume_unit == "ML"

    def test_microgrammi_then_other_words(self):
        # Verifica che "MICROGRAMMI" venga normalizzato anche con suffissi
        p = parse_denominazione_package("38 MICROGRAMMI COMPRESSE- 50 COMPRESSE IN BLISTER PVC/AL")
        assert p.strength_value == 38.0
        assert p.strength_unit == "MCG"

    def test_eutirox_full_dosage_range(self):
        """Verifica TUTTI i 13 dosaggi reali di Eutirox dal CSV."""
        eutirox_dosages = [25, 38, 50, 63, 75, 88, 100, 112, 125, 137, 150, 175, 200]
        for mcg in eutirox_dosages:
            desc = f"{mcg} MICROGRAMMI COMPRESSE- 50 COMPRESSE IN BLISTER PVC/AL"
            p = parse_denominazione_package(desc)
            assert p.strength_value == float(mcg), f"Failed for {mcg} mcg: got {p.strength_value}"
            assert p.strength_unit == "MCG", f"Failed unit for {mcg} mcg: got {p.strength_unit!r}"
            assert p.unit_count == 50
