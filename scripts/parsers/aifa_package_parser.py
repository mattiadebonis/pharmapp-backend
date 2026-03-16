"""Parser for AIFA denominazionePackage strings.

Extracts structured fields (unit_count, package_type, strength, volume)
from free-text Italian package descriptions like:
  '"24 MG COMPRESSE " 20 COMPRESSE'
  '"2,5 MG/10 ML + 60 MG/10 ML SCIROPPO" FLACONE 100 ML'
  '16 CAPSULE  25 MG'
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

# Volume units: only true volume/weight for containers (not strength units like MG)
_VOLUME_UNITS = {"ML", "L", "G", "KG"}


def _parse_italian_number(s: str) -> float | None:
    """Parse a number using Italian conventions.

    Italian: dot=thousands, comma=decimal.
    '50.000' = 50000, '2,5' = 2.5, '1.33' = 1.33 (ambiguous, treat as decimal).
    Heuristic: if exactly 3 digits after dot, it's a thousands separator.
    """
    s = s.strip()
    if not s:
        return None
    # Check for thousands separator: "50.000", "1.000.000"
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    # Otherwise comma is decimal, dot is also decimal (for ambiguous cases like "1.33")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_container_type(text: str) -> tuple[str, int, int]:
    """Find a known container type in text, return (type, start, end).

    Tries longer multi-word types first. Ensures word boundaries.
    """
    upper = text.upper()
    for ct in sorted(_CONTAINER_TYPES, key=len, reverse=True):
        # Use word boundary matching to avoid partial matches
        pattern = r"\b" + re.escape(ct) + r"\b"
        m = re.search(pattern, upper)
        if m:
            return ct, m.start(), m.end()
    return "", -1, -1


def _extract_count_before(text: str, pos: int) -> int | None:
    """Extract a number immediately before position `pos` in text."""
    before = text[:pos].rstrip()
    m = re.search(r"(\d+)\s*$", before)
    if m:
        return int(m.group(1))
    return None


def _extract_volume_after(text: str, pos: int) -> tuple[float | None, str]:
    """Extract volume (number + volume unit) after position `pos`.

    Only matches true volume/weight units (ML, L, G, KG), not strength units (MG, MCG).
    """
    after = text[pos:].strip()
    # Match patterns like "100 ML", "DA 30 G", "1,33 ML"
    m = re.match(r"(?:DA\s+)?(\d+(?:[.,]\d+)?)\s*(ML|L|G|KG)\b", after, re.IGNORECASE)
    if m:
        val = _parse_italian_number(m.group(1))
        unit = m.group(2).upper()
        return val, unit
    return None, ""


# Strength units (with optional denominator like MG/10ML)
_STRENGTH_UNIT_RE = re.compile(
    r"(%|MG/\d+(?:[.,]\d+)?\s*ML|MCG/\d+(?:[.,]\d+)?\s*ML|G/L|MG|MCG|G|ML|UI|U\.I\.|IU|MMOL)",
    re.IGNORECASE,
)

# Full strength pattern including optional space between number and unit ("200MG" and "200 MG")
_STRENGTH_VALUE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?)"  # number, optionally /number
    r"\s*"  # optional space (handles "200MG" and "200 MG")
    r"(%|MG|MCG|G/L|G|ML|UI|U\.I\.|IU|MMOL)"  # unit
    r"(?:/(\d+(?:[.,]\d+)?)\s*(ML|L|G|MG))?",  # optional denominator
    re.IGNORECASE,
)


# ---------- main parser ----------

def parse_denominazione_package(raw: str | None) -> ParsedPackage:
    """Parse a denominazionePackage string into structured fields."""
    result = ParsedPackage()
    if not raw or not raw.strip():
        return result

    raw = raw.strip()
    result.strength_text = raw  # always store full original

    # ── Split into quoted (dosage) and unquoted (packaging) parts ──
    quoted_part = ""
    packaging_part = raw

    # Handle strings with quoted sections: "..." REST
    quote_match = re.match(r'^["\u201c](.+?)["\u201d]\s*(.*)', raw, re.DOTALL)
    if quote_match:
        quoted_part = quote_match.group(1).strip()
        packaging_part = quote_match.group(2).strip()
    else:
        quoted_part = ""
        packaging_part = raw

    # ── Extract strength from quoted part ──
    if quoted_part:
        strength_match = _STRENGTH_VALUE_RE.match(quoted_part)
        if strength_match:
            result.strength_value = _parse_italian_number(strength_match.group(1))
            unit = strength_match.group(2).upper()
            # Build full unit with denominator if present
            if strength_match.group(3):
                denom_val = strength_match.group(3).strip()
                denom_unit = strength_match.group(4).upper() if strength_match.group(4) else ""
                unit = f"{unit}/{denom_val}{denom_unit}"
            result.strength_unit = unit.replace(" ", "")

    # ── Extract packaging info ──
    if packaging_part:
        # Find container type in packaging part
        container, ct_start, ct_end = _find_container_type(packaging_part)
        if container:
            result.package_type = container.title()

            # Count is the number before the container type
            count = _extract_count_before(packaging_part, ct_start)
            if count is not None and count > 0:
                result.unit_count = count

            # Volume is typically after the container type
            vol_val, vol_unit = _extract_volume_after(packaging_part, ct_end)
            if vol_val is not None:
                result.volume_value = vol_val
                result.volume_unit = vol_unit
        else:
            # No known container type found in packaging part.
            # If no quoted part, try to find container in the full string
            if not quoted_part:
                container, ct_start, ct_end = _find_container_type(raw)
                if container:
                    result.package_type = container.title()
                    count = _extract_count_before(raw, ct_start)
                    if count is not None and count > 0:
                        result.unit_count = count
                    vol_val, vol_unit = _extract_volume_after(raw, ct_end)
                    if vol_val is not None:
                        result.volume_value = vol_val
                        result.volume_unit = vol_unit
                else:
                    # Last resort: first number is count
                    m = re.search(r"(\d+)", packaging_part)
                    if m:
                        result.unit_count = int(m.group(1)) or 1
    elif quoted_part:
        # No packaging part, extract container from quoted part
        container, _, _ = _find_container_type(quoted_part)
        if container:
            result.package_type = container.title()

    # ── Fallback: if no package_type, try from the quoted dosage form ──
    if not result.package_type and quoted_part:
        container, _, _ = _find_container_type(quoted_part)
        if container:
            result.package_type = container.title()

    return result
