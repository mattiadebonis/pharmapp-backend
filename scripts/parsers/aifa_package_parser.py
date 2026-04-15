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
}

_VOLUME_UNITS = {"ML", "L", "G", "KG"}

# Separator between dosage/form and packaging count info.
# AIFA uses "- ", "– ", "-", or ">" as separators.
_SEPARATOR_RE = re.compile(r"\s*[-–>]\s*")

# Strength pattern: number (optionally /number) + unit
_STRENGTH_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)"  # main number
    r"\s*"
    r"(%|MG/ML|MCG/ML|MG|MCG|G/L|G|ML|UI|U\.I\.|IU|MMOL)"  # unit (compound units first)
    r"(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*(ML|L|G|MG))?"  # optional denominator e.g. /5 ML
    ,
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
    """Extract volume (number + volume unit) after position."""
    after = text[pos:].strip()
    m = re.match(r"(?:DA?\s+)?(\d+(?:[.,]\d+)?)\s*(ML|L|G|KG)\b", after, re.IGNORECASE)
    if m:
        val = _parse_italian_number(m.group(1))
        unit = m.group(2).upper()
        return val, unit
    return None, ""


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
    strength_match = _STRENGTH_RE.search(dosage_part)
    if strength_match:
        result.strength_value = _parse_italian_number(strength_match.group(1))
        unit = strength_match.group(2).upper()
        if strength_match.group(3):
            denom_val = strength_match.group(3).strip()
            denom_unit = strength_match.group(4).upper() if strength_match.group(4) else ""
            unit = f"{unit}/{denom_val}{denom_unit}"
        result.strength_unit = unit.replace(" ", "")

        # Build a clean strength_text: "1000 MG" or "120 MG/5 ML"
        num_str = strength_match.group(1)
        if strength_match.group(3):
            result.strength_text = f"{num_str} {strength_match.group(2).upper()}/{strength_match.group(3)} {strength_match.group(4).upper() if strength_match.group(4) else ''}".strip()
        else:
            result.strength_text = f"{num_str} {strength_match.group(2).upper()}"
    else:
        result.strength_text = ""

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
