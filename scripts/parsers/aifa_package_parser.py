"""Parser for AIFA denominazionePackage (DESCRIZIONE) strings.

Extracts structured fields (unit_count, package_type, strength, volume)
from free-text Italian package descriptions. AIFA format is typically:

    DOSAGE FORM - COUNT CONTAINER [MATERIAL]

Examples:
    '1000 MG COMPRESSE - 16 COMPRESSE'
    '10 MG/ML SOLUZIONE PER INFUSIONE- 12 SACCHE DA 100 ML'
    '250 MG GRANULATO- 10 BUSTINE IN AL'
    '100 MG/ML GOCCE ORALI, SOLUZIONE-FLACONE 30 ML'
    '"24 MG COMPRESSE" 20 COMPRESSE'
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedPackage:
    unit_count: int = 1
    package_type: str = ""
    strength_value: float | None = None
    strength_unit: str = ""
    strength_text: str = ""
    volume_value: float | None = None
    volume_unit: str = ""


# ---------- helpers ----------

_CONTAINER_TYPES = {
    "COMPRESSE", "COMPRESSA", "CAPSULE", "CAPSULA", "CAPSULE MOLLI", "CAPSULE RIGIDE",
    "FIALE", "FIALA", "FLACONE", "FLACONI", "FLACONCINI", "FLACONCINO",
    "SIRINGHE", "SIRINGA", "SIRINGHE PRERIEMPITE", "SIRINGA PRERIEMPITA",
    "TUBO", "TUBI", "BUSTINE", "BUSTINA", "BUSTE", "BUSTA",
    "SACCHE", "SACCA", "SUPPOSTE", "SUPPOSTA",
    "CEROTTI", "CEROTTO", "OVULI", "OVULO",
    "BLISTER", "STICK", "CARTUCCE", "CARTUCCIA",
    "FIALE MONODOSE", "CONTENITORI MONODOSE", "CONTENITORE MONODOSE",
    "FLACONE CONTAGOCCE", "NEBULIZZATORE", "INALATORE",
    "DISPOSITIVO", "PENNA", "PENNE", "PENNE PRERIEMPITE", "PENNA PRERIEMPITA",
    "SCIROPPO",
    # Unità di dose discrete dispensate da un singolo contenitore fisico.
    # Per inalatori, spray nasali, pompette il "count" clinicamente
    # rilevante è il numero di erogazioni/dosi/puff, non il numero di
    # flaconi/inalatori (sempre 1). Es: "FLACONE 140 EROGAZIONI" →
    # unit_count=140 anziché 1 (più informativo per l'utente).
    "EROGAZIONI", "EROGAZIONE", "INALAZIONI", "INALAZIONE",
    "DOSI", "DOSE", "PUFF", "ATTUAZIONI", "ATTUAZIONE",
}

_VOLUME_UNITS = {"ML", "L", "G", "KG"}

# Separator between dosage/form and packaging count info.
# AIFA uses "- ", "– ", "-", or ">" as separators.
_SEPARATOR_RE = re.compile(r"\s*[-–>]\s*")


# ─── Normalizzazione unità "per esteso" ──────────────────────────────────────
#
# AIFA scrive a volte le unità per esteso ("25 MICROGRAMMI COMPRESSE", "15
# MILLIGRAMMI COMPRESSE RIVESTITE..."). Senza normalizzazione, la regex di
# strength sotto — che riconosce solo le forme abbreviate (MCG/MG/UI...) —
# fallisce e tutto il prodotto perde lo strength_text. Per Eutirox & le
# levotiroxine questo significa che tutti i dosaggi della famiglia
# collassano in una sola variante "vuota" nella UI di setup.
#
# Importante: l'ordine conta. "MICROGRAMMI" contiene "GRAMMI", quindi le
# alternative col prefisso (MICRO/MILLI/NANO/PICO) devono essere applicate
# PRIMA di "GRAMMI" semplice, altrimenti "GRAMMI" matcha al suo interno
# e produce risultati corrotti.
#
# Nota sui boundary: usiamo `(?<![A-Za-z])` invece di `\b` come
# left-boundary perché AIFA a volte scrive "25MICROGRAMMI" senza spazio
# (es. "SALMETEROLO E FLUTICASONE 25MICROGRAMMI/125MICROGRAMMI..."). Con
# `\b` la transizione digit→letter NON è un boundary (entrambi `\w`),
# quindi non scatta. Il lookbehind `(?<![A-Za-z])` invece accetta sia
# stringa-vuota che digit che separatore, ma esclude letter — così non
# tocchiamo parole come "ANTIGRAMM" o simili.
_UNIT_WORD_NORMALIZATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<![A-Za-z])MICROGRAMM(?:O|I)\b", re.IGNORECASE), "MCG"),
    (re.compile(r"(?<![A-Za-z])MILLIGRAMM(?:O|I)\b", re.IGNORECASE), "MG"),
    (re.compile(r"(?<![A-Za-z])NANOGRAMM(?:O|I)\b", re.IGNORECASE), "NG"),
    (re.compile(r"(?<![A-Za-z])PICOGRAMM(?:O|I)\b", re.IGNORECASE), "PG"),
    (re.compile(r"(?<![A-Za-z])MILLILITR(?:O|I)\b", re.IGNORECASE), "ML"),
    (re.compile(r"(?<![A-Za-z])MILLIEQUIVALENT(?:E|I)\b", re.IGNORECASE), "MEQ"),
    # "UNITA INTERNAZIONALI" / "UNITÀ INTERNAZIONALI" (con o senza apostrofo,
    # con o senza accento) → UI. Il backslash su ` ` accetta unicode " ".
    (re.compile(r"\bUNIT[AÀ]['’]?\s+INTERNAZIONAL(?:E|I)\b", re.IGNORECASE), "UI"),
    # "GRAMMI"/"GRAMMO" puri — solo DOPO aver consumato i prefissi sopra.
    (re.compile(r"(?<![A-Za-z])GRAMM(?:O|I)\b", re.IGNORECASE), "G"),
)


def _normalize_unit_words(text: str) -> str:
    """Sostituisce le unità AIFA scritte per esteso con la forma abbreviata."""
    for pattern, repl in _UNIT_WORD_NORMALIZATIONS:
        text = pattern.sub(repl, text)
    return text


# Denominatori "per X" (rate / dose discreta) usati nei farmaci ad
# erogazione (spray, inalatori, cerotti). Vanno parsati come parte
# integrante dell'unità — `5 MCG/ORA` è clinicamente diverso da `5 MCG`.
_PER_X_DENOMINATOR = (
    r"EROGAZION[EI]|INALAZION[EI]|DOS[EI]|ATTUAZION[EI]|"
    r"APPLICAZION[EI]|OR[AE]|MINUT[OI]|SETTIMAN[AE]|"
    r"24H|48H|72H|H|MIN"
)


# Strength pattern: number + unit (con varianti composte e per-X)
#
# Gruppi:
#   1: numero principale
#   2: unità primaria (può essere composta tipo MG/ML)
#   3,4: denominatore numerico opzionale (X MG / 5 ML)
#   5: denominatore "per X" opzionale (X MCG / EROGAZIONE)
_STRENGTH_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)"
    r"\s*"
    r"("
    # Unità COMPOSTE prima (longest-match: MG/ML deve essere tentato prima di MG)
    r"%|"
    r"MG/ML|MCG/ML|NG/ML|UI/ML|MEQ/ML|MG/L|MCG/L|"
    # Unità singole
    r"MG|MCG|NG|PG|MEQ|G|ML|UI|U\.I\.|IU|MMOL|U"
    r")"
    # Denominatore numerico: /5 ML, /2 ML
    r"(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*(ML|L|G|MG|H|MIN))?"
    # Denominatore "per X" (mutualmente esclusivo col numerico)
    r"(?:\s*/\s*(" + _PER_X_DENOMINATOR + r"))?",
    re.IGNORECASE,
)


# Continuation pattern per combinazioni (paracetamolo+codeina, trifasici, ecc.).
# Cattura "+ X UNIT" o "/ X UNIT" *dopo* una strength già matchata.
# Usato per costruire `strength_text` con tutte le dosi visibili.
#
# Gruppi:
#   1: separatore (`+` o `/`)
#   2: numero
#   3: unità primaria
#   4,5: denominatore numerico opzionale (es. "/0,035 MG" nei trifasici
#        contraccettivi tipo Briladona, "/0,5 ML" in Vicks Medinait, ecc.)
#   6: denominatore "per X" opzionale (es. "/EROGAZIONE")
_STRENGTH_CONTINUATION_RE = re.compile(
    r"\s*([+/])\s*"
    r"(\d+(?:[.,]\d+)?)"
    r"\s*"
    r"("
    r"%|"
    r"MG/ML|MCG/ML|NG/ML|UI/ML|MEQ/ML|MG/L|MCG/L|"
    r"MG|MCG|NG|PG|MEQ|G|ML|UI|U\.I\.|IU|MMOL|U"
    r")"
    # Denominatore numerico (es. "/0,035 MG") — necessario per i
    # contraccettivi trifasici (Briladona TRIFASE: "+ 0,215 MG/0,035 MG"),
    # nebulizzatori multidose (NAOS: "+ 0,375 MG/0,5 ML") ecc.
    r"(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*(ML|L|G|MG|H|MIN|MCG))?"
    r"(?:\s*/\s*(" + _PER_X_DENOMINATOR + r"))?",
    re.IGNORECASE,
)


# Container boundary: usato in _extract_strength per troncare lo
# strength_text al primo container token. Protegge da dosage_part
# che inglobano "COMPRESSE", "CAPSULE" o altre parole-contenitore
# tipiche dei kit di inizio trattamento (es. Brilique-like:
# "10 MG + 20 MG + 30 MG COMPRESSE - 4 COMPRESSE DA…").
_CONTAINER_BOUNDARY_RE = re.compile(
    r"\s+(?:COMPRESS|CAPSUL|BUSTIN|FIAL|GRANULAT|POLVER|SOLUZ|SOSPENS|"
    r"SCIROPP|UNGUENT|CREMA|GEL|SPRAY|CEROTT|FLACONI?|SIRING|OVUL|SUPPOSTA|"
    r"COLLIRIO|CONTENITOR|STICK|BLISTER)\w*\b",
    re.IGNORECASE,
)


def _parse_italian_number(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_container_type(text: str) -> tuple[str, int, int]:
    """Find a known container type in text, return (type, start, end)."""
    upper = text.upper()
    for ct in sorted(_CONTAINER_TYPES, key=len, reverse=True):
        pattern = r"\b" + re.escape(ct) + r"\b"
        m = re.search(pattern, upper)
        if m:
            return ct, m.start(), m.end()
    return "", -1, -1


def _find_all_containers(text: str) -> list[tuple[str, int, int]]:
    """Find ALL container type occurrences in text (for disambiguation)."""
    upper = text.upper()
    results = []
    for ct in sorted(_CONTAINER_TYPES, key=len, reverse=True):
        pattern = r"\b" + re.escape(ct) + r"\b"
        for m in re.finditer(pattern, upper):
            # Check it's not overlapping with an already-found match
            overlaps = any(m.start() < e and m.end() > s for _, s, e in results)
            if not overlaps:
                results.append((ct, m.start(), m.end()))
    results.sort(key=lambda x: x[1])
    return results


def _extract_count_before(text: str, pos: int) -> int | None:
    """Extract a number immediately before position `pos` in text.

    Handles patterns like "16 COMPRESSE", "DA 30 COMPRESSE", "D100 ML",
    "10x1 COMPRESSE" (= 10).
    """
    before = text[:pos].rstrip()
    # NxN pattern: "10x1 COMPRESSE" → 10*1=10, "3x10 CAPSULE" → 30
    m = re.search(r"(\d+)\s*[xX]\s*(\d+)\s*$", before)
    if m:
        return int(m.group(1)) * int(m.group(2))
    # Direct: "16 COMPRESSE"
    m = re.search(r"(\d+)\s*$", before)
    if m:
        return int(m.group(1))
    # "DA 30 COMPRESSE" or "D100 ML" (contracted form)
    m = re.search(r"(?:DA?\s+)(\d+)\s*$", before, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_volume_after(text: str, pos: int) -> tuple[float | None, str]:
    """Extract volume (number + volume unit) after position.

    AIFA scrive il volume del contenitore con due varianti principali:
      a) subito dopo il container: "FLACONE 30 ML"
      b) con "DA <num> UNIT" intermedi: "TUBO IN ALLUMINIO DA 50 G"
      c) sintetico: "FLAC.115 G"

    Usiamo `re.match` per (a) e fallback a `re.search` con prefisso "DA"
    per (b/c) — il prefisso "DA" disambigua e ci protegge dal catturare
    numeri estranei (es. "10 BUSTINE FILTRO G 2" non deve produrre
    volume 2 G).
    """
    after = text[pos:].strip()

    # (a) Volume immediatamente dopo il container, con o senza "DA"
    m = re.match(r"(?:DA?\.?\s*)?(\d+(?:[.,]\d+)?)\s*(ML|L|G|KG)\b", after, re.IGNORECASE)
    if m:
        val = _parse_italian_number(m.group(1))
        unit = m.group(2).upper()
        return val, unit

    # (b) "DA <num> UNIT" più avanti nella stringa (preceduto da spazio o inizio)
    m = re.search(r"(?:^|\s)DA\s+(\d+(?:[.,]\d+)?)\s*(ML|L|G|KG)\b", after, re.IGNORECASE)
    if m:
        val = _parse_italian_number(m.group(1))
        unit = m.group(2).upper()
        return val, unit

    return None, ""


def _format_strength_fragment(num_str: str, unit: str,
                              denom_val: str | None = None,
                              denom_unit: str | None = None,
                              per_x: str | None = None) -> str:
    """Formatta un frammento di strength canonicalizzato.

    Esempi:
      ("25", "MCG") → "25 MCG"
      ("120", "MG", "5", "ML") → "120 MG/5 ML"
      ("5", "MCG", per_x="ORA") → "5 MCG/ORA"
    """
    base = f"{num_str} {unit.upper()}"
    if denom_val:
        base = f"{base}/{denom_val} {(denom_unit or '').upper()}".rstrip()
    elif per_x:
        base = f"{base}/{per_x.upper()}"
    return base


def _extract_strength(dosage_part: str) -> tuple[str, float | None, str]:
    """Estrae strength dalla porzione "dosage" del nome confezione.

    Restituisce (canonical_text, primary_value, primary_unit_compound).
    Gestisce:
      - Unità composte (MG/ML, UI/ML, MCG/EROGAZIONE)
      - Denominatori numerici (120 MG/5 ML)
      - Denominatori "per X" (5 MCG/ORA, 50 MCG/EROGAZIONE)
      - Combinazioni (500 MG + 30 MG, 875 MG/125 MG)
    """
    primary = _STRENGTH_RE.search(dosage_part)
    if not primary:
        return "", None, ""

    num_str = primary.group(1)
    unit = primary.group(2).upper()
    denom_val = primary.group(3)
    denom_unit = primary.group(4)
    per_x = primary.group(5)

    primary_value = _parse_italian_number(num_str)
    if denom_val:
        compound_unit = f"{unit}/{denom_val}{(denom_unit or '').upper()}"
    elif per_x:
        compound_unit = f"{unit}/{per_x.upper()}"
    else:
        compound_unit = unit
    compound_unit = compound_unit.replace(" ", "")

    primary_text = _format_strength_fragment(
        num_str, unit,
        denom_val=denom_val,
        denom_unit=denom_unit,
        per_x=per_x,
    )

    # Continuazioni per combinazioni: "+ 30 MG", "/ 125 MG", o trifasici
    # come Briladona "+ 0,215 MG/0,035 MG". Ne accettiamo fino a 4 per
    # coprire combo 4-in-1 (Stribild: 150/150/200/245).
    text_parts: list[str] = [primary_text]
    rest = dosage_part[primary.end():]
    for _ in range(4):
        cont = _STRENGTH_CONTINUATION_RE.match(rest)
        if not cont:
            break
        sep = cont.group(1)
        cont_num = cont.group(2)
        cont_unit = cont.group(3).upper()
        # Nuovi gruppi (post-fix Briladona): denom numerico nella continuation
        cont_denom_val = cont.group(4)
        cont_denom_unit = cont.group(5)
        cont_per_x = cont.group(6)
        cont_frag = _format_strength_fragment(
            cont_num, cont_unit,
            denom_val=cont_denom_val,
            denom_unit=cont_denom_unit,
            per_x=cont_per_x,
        )
        text_parts.append(f"{sep} {cont_frag}")
        rest = rest[cont.end():]

    canonical_text = " ".join(text_parts)
    # Boundary cut: tronca prima del primo container token per proteggere
    # da kit di inizio trattamento (Brilique-like) dove il dosage_part
    # ingloba "COMPRESSE…" o simili. Lascia intatti i casi normali in cui
    # il primary regex si è fermato ben prima del container.
    canonical_text = _CONTAINER_BOUNDARY_RE.split(canonical_text, maxsplit=1)[0].rstrip(" ,")
    return canonical_text, primary_value, compound_unit


# ---------- main parser ----------

def parse_denominazione_package(raw: str | None) -> ParsedPackage:
    """Parse a DESCRIZIONE string into structured fields."""
    result = ParsedPackage()
    if not raw or not raw.strip():
        return result

    raw = raw.strip()
    # Clean leading ? characters (AIFA artifact)
    cleaned = re.sub(r"^\?+", "", raw).strip()
    # Also handle mid-string ? (like "?BAMBINI 500 MG SUPPOSTE? 20 SUPPOSTE...")
    cleaned = cleaned.replace("?", " ").strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    # Normalizza le unità AIFA scritte per esteso → forma abbreviata.
    # Va fatto PRIMA di tutto il parsing successivo (split separatore,
    # strength regex, container detection) per garantire uniformità.
    cleaned = _normalize_unit_words(cleaned)

    # ── Handle quoted strings: "DOSAGE FORM" COUNT CONTAINER ──
    quote_match = re.match(r'^["\u201c](.+?)["\u201d]\s*(.*)', cleaned, re.DOTALL)
    if quote_match:
        dosage_part = quote_match.group(1).strip()
        packaging_part = quote_match.group(2).strip()
    else:
        # Split on separator (dash): DOSAGE FORM - COUNT CONTAINER
        # Find the LAST separator that has a number after it (the packaging part)
        parts = _SEPARATOR_RE.split(cleaned, maxsplit=1)
        if len(parts) == 2:
            dosage_part = parts[0].strip()
            packaging_part = parts[1].strip()
        else:
            # No separator found — whole string is both dosage and packaging
            dosage_part = cleaned
            packaging_part = cleaned

    # ── Extract strength from dosage part ──
    strength_text, strength_value, strength_unit = _extract_strength(dosage_part)
    # Fallback: alcune confezioni AIFA mettono il brand prima del trattino
    # e la dose dopo (es. "DISKUS -50 MICROGRAMMI/500 MICROGRAMMI/DOSE...").
    # Se il primo tentativo non ha trovato nulla, riproviamo sull'intera
    # stringa pulita — ma scartiamo match con sola unità "volumetrica"
    # (ML/L/G/KG) perché in packaging_part queste sono SEMPRE il volume del
    # contenitore (es. "TUBO ... DA 50 G", "SIRINGA DA 0,5 ML"), non la
    # dose. Le dosi accettate via fallback devono avere unità di "massa
    # farmacologica" (MG/MCG/UI/...) o composte (MG/ML).
    if not strength_text and packaging_part and packaging_part != dosage_part:
        fb_text, fb_value, fb_unit = _extract_strength(cleaned)
        if fb_unit and fb_unit.upper() not in {"ML", "L", "G", "KG"}:
            strength_text, strength_value, strength_unit = fb_text, fb_value, fb_unit
    result.strength_text = strength_text
    result.strength_value = strength_value
    result.strength_unit = strength_unit

    # ── Extract packaging info (count + container) ──
    # First try from the packaging_part (after separator)
    if packaging_part:
        containers = _find_all_containers(packaging_part)
        if containers:
            # Find the best container: the one with the highest numeric count.
            # This handles "BLISTER 50 COMPRESSE" → prefer COMPRESSE(50) over BLISTER(none).
            # Also handles "1 BLISTER DA 30 COMPRESSE" → prefer COMPRESSE(30) over BLISTER(1).
            best_ct = None
            best_count = 0
            best_end = 0
            for ct_name, ct_start, ct_end in containers:
                count = _extract_count_before(packaging_part, ct_start)
                if count is not None and count > best_count:
                    best_ct = ct_name
                    best_count = count
                    best_end = ct_end
            if best_ct and best_count > 0:
                result.package_type = best_ct.title()
                result.unit_count = best_count
                vol_val, vol_unit = _extract_volume_after(packaging_part, best_end)
                if vol_val is not None:
                    result.volume_value = vol_val
                    result.volume_unit = vol_unit
            else:
                # No container has a count — use the first one
                ct_name, ct_start, ct_end = containers[0]
                result.package_type = ct_name.title()
                vol_val, vol_unit = _extract_volume_after(packaging_part, ct_end)
                if vol_val is not None:
                    result.volume_value = vol_val
                    result.volume_unit = vol_unit
        else:
            # No container in packaging part — try to get a count from first number
            m = re.match(r"(\d+)\b", packaging_part.strip())
            if m:
                result.unit_count = int(m.group(1)) or 1

    # ── If packaging_part == dosage_part (no separator), use smarter logic ──
    if packaging_part == dosage_part and not quote_match:
        containers = _find_all_containers(cleaned)
        if len(containers) >= 2:
            # Multiple container mentions. Walk backwards to find the best one:
            # prefer a container with a valid numeric count that isn't the strength value.
            best = None
            for ct_name, ct_start, ct_end in reversed(containers):
                count = _extract_count_before(cleaned, ct_start)
                if count is not None and count > 0:
                    # Skip if the count is actually the strength value
                    if result.strength_value is not None and count == int(result.strength_value):
                        continue
                    best = (ct_name, ct_start, ct_end, count)
                    break
            if best:
                ct_name, ct_start, ct_end, count = best
                result.package_type = ct_name.title()
                result.unit_count = count
                vol_val, vol_unit = _extract_volume_after(cleaned, ct_end)
                if vol_val is not None:
                    result.volume_value = vol_val
                    result.volume_unit = vol_unit
            # else: keep what we found in the first pass
        elif len(containers) == 1:
            ct_name, ct_start, ct_end = containers[0]
            result.package_type = ct_name.title()
            count = _extract_count_before(cleaned, ct_start)
            if count is not None and count > 0:
                # Only use this count if it's not the strength value
                if result.strength_value is None or count != int(result.strength_value):
                    result.unit_count = count
            vol_val, vol_unit = _extract_volume_after(cleaned, ct_end)
            if vol_val is not None:
                result.volume_value = vol_val
                result.volume_unit = vol_unit

    # ── Fallback: get package_type from dosage part if still missing ──
    if not result.package_type:
        container, _, _ = _find_container_type(dosage_part)
        if container:
            result.package_type = container.title()

    return result
