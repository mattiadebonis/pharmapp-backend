#!/usr/bin/env python3
"""Import AIFA aifa_formadosaggio.jsonl into Supabase catalog_it_raw_* tables.

Usage:
    python scripts/import_aifa.py                         # full import
    python scripts/import_aifa.py --dry-run               # parse only, no DB writes
    python scripts/import_aifa.py --batch-size 200        # custom batch size
    python scripts/import_aifa.py --file /path/to/file    # custom input file

Requires .env with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from parsers.aifa_package_parser import parse_denominazione_package


# ─── Configuration ────────────────────────────────────────────────────────────

DEFAULT_AIFA_FILE = Path(__file__).resolve().parent.parent.parent / "aifa-scraper" / "aifa_formadosaggio.jsonl"

PRESCRIPTION_CLASSES = {"RR", "RNR", "RNRL", "RRL", "OSP", "RMR", "USPL"}
NON_PRESCRIPTION_CLASSES = {"OTC", "SOP"}


# ─── Data Containers ─────────────────────────────────────────────────────────

@dataclass
class Stats:
    total_records: int = 0
    skipped_no_data: int = 0
    skipped_http_error: int = 0
    products_ok: int = 0
    packages_ok: int = 0
    ingredients_ok: int = 0
    products_no_confezioni: int = 0
    parse_errors: int = 0

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"  Import AIFA — Riepilogo\n"
            f"{'='*60}\n"
            f"  Record letti:           {self.total_records}\n"
            f"  Skippati (no data):     {self.skipped_no_data}\n"
            f"  Skippati (HTTP error):  {self.skipped_http_error}\n"
            f"  Prodotti importati:     {self.products_ok}\n"
            f"  Confezioni importate:   {self.packages_ok}\n"
            f"  Ingredienti importati:  {self.ingredients_ok}\n"
            f"  Prodotti senza conf.:   {self.products_no_confezioni}\n"
            f"  Errori di parsing:      {self.parse_errors}\n"
            f"{'='*60}"
        )


# ─── Mapping Functions ───────────────────────────────────────────────────────

def _derive_availability(payload: dict[str, Any], medicinale: dict[str, Any]) -> str:
    """Derive availability from AIFA flags and status."""
    if payload.get("revocato") == 1:
        return "revoked"
    if payload.get("sospeso") == 1:
        return "suspended"
    if payload.get("carente") == 1:
        return "shortage"
    stato = medicinale.get("statoAmministrativo", "")
    if stato == "T":
        return "inactive"
    return "active"


def _derive_product_requires_prescription(confezioni: list[dict[str, Any]]) -> bool:
    """Product requires prescription if ANY package does."""
    for conf in confezioni:
        if conf.get("flagPrescrizione") == 1:
            return True
        classe = (conf.get("classeFornitura") or "").split("##")[0].strip().upper()
        if classe in PRESCRIPTION_CLASSES:
            return True
    return False


def _derive_package_requires_prescription(confezione: dict[str, Any]) -> bool:
    """Derive requires_prescription for a single package."""
    if confezione.get("flagPrescrizione") == 1:
        return True
    classe = (confezione.get("classeFornitura") or "").split("##")[0].strip().upper()
    if classe in PRESCRIPTION_CLASSES:
        return True
    if classe in NON_PRESCRIPTION_CLASSES:
        return False
    # Unknown class: default to True (safer for prescription check)
    return confezione.get("flagPrescrizione", 0) == 1


def _derive_package_availability(confezione: dict[str, Any]) -> str:
    """Derive package-level availability."""
    if confezione.get("carente") == 1:
        return "shortage"
    stato = (confezione.get("statoAmministrativo") or "").upper()
    if stato == "S":
        return "suspended"
    if stato == "R":
        return "revoked"
    if stato == "A":
        return "active"
    return "unknown"


def _parse_date(date_str: str | None) -> str | None:
    """Parse AIFA date string to ISO date (YYYY-MM-DD) or None."""
    if not date_str:
        return None
    # AIFA dates: "1995-04-27T22:00:00.000+00:00" → "1995-04-27"
    if "T" in date_str:
        return date_str.split("T")[0]
    return date_str[:10] if len(date_str) >= 10 else None


def map_product(record: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw AIFA JSONL record → catalog_it_raw_products row."""
    data = record.get("data")
    if not isinstance(data, dict):
        return None
    payload = data.get("data")
    if not isinstance(payload, dict):
        payload = data  # fallback

    source_product_id = str(payload.get("id", "")).strip()
    if not source_product_id:
        return None

    medicinale = payload.get("medicinale") or {}
    confezioni = payload.get("confezioni") or []
    principi = payload.get("principiAttiviIt") or []
    vie = payload.get("vieSomministrazione") or []
    atc_codes = payload.get("codiceAtc") or []

    display_name = medicinale.get("denominazioneMedicinale", "").strip()
    if not display_name:
        return None

    generic_name = ", ".join(principi) if principi else None
    family_id = str(medicinale.get("codiceMedicinale", "")).strip() or None

    return {
        "source": "aifa",
        "source_product_id": source_product_id,
        "family_id": family_id,
        "display_name": display_name,
        "brand_name": display_name,
        "generic_name": generic_name,
        "dosage_form": payload.get("formaFarmaceutica"),
        "routes": vie,
        "strength_text": payload.get("descrizioneFormaDosaggio"),
        "manufacturer_name": medicinale.get("aziendaTitolare"),
        "requires_prescription": _derive_product_requires_prescription(confezioni),
        "availability": _derive_availability(payload, medicinale),
        "atc_codes": atc_codes,
        "regulatory": {
            "tipo_autorizzazione": payload.get("tipoAutorizzazione"),
            "categoria_medicinale": medicinale.get("categoriaMedicinale"),
            "piano_terapeutico": payload.get("pianoTerapeutico"),
            "flag_alcol": payload.get("flagAlcol"),
            "flag_potassio": payload.get("flagPotassio"),
            "flag_guida": payload.get("flagGuida"),
            "flag_dopante": payload.get("flagDopante"),
            "livello_guida": payload.get("livelloGuida"),
            "innovativo": payload.get("innovativo"),
            "orfano": payload.get("orfano"),
            "flag_fi": payload.get("flagFI"),
            "flag_rcp": payload.get("flagRCP"),
        },
        "source_meta": payload,
    }


def map_packages(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Map confezioni from an AIFA record → list of catalog_it_raw_packages rows."""
    data = record.get("data")
    if not isinstance(data, dict):
        return []
    payload = data.get("data")
    if not isinstance(payload, dict):
        payload = data

    source_product_id = str(payload.get("id", "")).strip()
    if not source_product_id:
        return []

    confezioni = payload.get("confezioni") or []
    rows = []

    for conf in confezioni:
        pkg_id = str(conf.get("idPackage", "")).strip()
        if not pkg_id:
            continue

        denom = (conf.get("denominazionePackage") or "").strip()
        parsed = parse_denominazione_package(denom)

        rows.append({
            "source_package_id": pkg_id,
            "source_product_id": source_product_id,
            "package_code": conf.get("aic"),
            "display_name": denom or f"Confezione {pkg_id}",
            "unit_count": parsed.unit_count,
            "package_type": parsed.package_type or None,
            "strength_value": parsed.strength_value,
            "strength_unit": parsed.strength_unit or None,
            "strength_text": parsed.strength_text or None,
            "volume_value": parsed.volume_value,
            "volume_unit": parsed.volume_unit or None,
            "marketed": conf.get("flagCommercio") == 1 if conf.get("flagCommercio") is not None else None,
            "marketing_start_date": _parse_date(conf.get("dataAutorizzazione")),
            "marketing_end_date": None,
            "is_sample": None,
            "requires_prescription": _derive_package_requires_prescription(conf),
            "reimbursement_class": conf.get("classeRimborsabilita"),
            "reimbursement_text": conf.get("descrizioneRimborsabilita"),
            "shortage_reason": conf.get("carenzaMotivazione"),
            "shortage_start_date": _parse_date(conf.get("carenzaInizio")),
            "shortage_end_date": _parse_date(conf.get("carenzaFinePresunta")),
            "availability": _derive_package_availability(conf),
            "source_meta": conf,
        })

    return rows


def map_ingredients(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Map principiAttiviIt from an AIFA record → list of catalog_it_raw_ingredients rows."""
    data = record.get("data")
    if not isinstance(data, dict):
        return []
    payload = data.get("data")
    if not isinstance(payload, dict):
        payload = data

    source_product_id = str(payload.get("id", "")).strip()
    if not source_product_id:
        return []

    principi = payload.get("principiAttiviIt") or []
    rows = []

    for i, name in enumerate(principi):
        name = str(name).strip()
        if not name:
            continue
        rows.append({
            "source_product_id": source_product_id,
            "name": name,
            "strength_value": None,
            "strength_unit": None,
            "strength_text": None,
            "sort_order": i,
        })

    # Try to enrich strength from principioAttivoForma
    forme = payload.get("principioAttivoForma") or []
    for forma in forme:
        if not isinstance(forma, dict):
            continue
        # principioAttivoForma contains the active ingredients per dosage form
        # but doesn't have individual strengths per ingredient in a structured way

    return rows


# ─── Supabase Upload ─────────────────────────────────────────────────────────

def _load_env() -> tuple[str, str]:
    """Load Supabase credentials from .env file."""
    env_path = PROJECT_ROOT / ".env"
    env_vars: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")

    url = os.environ.get("SUPABASE_URL") or env_vars.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or env_vars.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env or environment")
        sys.exit(1)
    return url, key


def upsert_batch(supabase, table: str, rows: list[dict[str, Any]], key_column: str) -> int:
    """Upsert a batch of rows into a Supabase table. Returns count of rows upserted."""
    if not rows:
        return 0
    result = supabase.table(table).upsert(rows, on_conflict=key_column).execute()
    return len(result.data) if result.data else 0


# ─── Main Import ─────────────────────────────────────────────────────────────

def run_import(file_path: Path, dry_run: bool = False, batch_size: int = 500) -> Stats:
    """Run the full AIFA import."""
    stats = Stats()

    # Accumulate rows for batching
    product_rows: list[dict[str, Any]] = []
    package_rows: list[dict[str, Any]] = []
    ingredient_rows: list[dict[str, Any]] = []

    print(f"Reading {file_path}...")
    t0 = time.time()

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            stats.total_records += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                stats.parse_errors += 1
                print(f"  WARN: line {line_num}: JSON decode error: {e}")
                continue

            # Skip HTTP errors
            http_status = record.get("status")
            if http_status and http_status != 200:
                stats.skipped_http_error += 1
                continue

            # Map product
            product = map_product(record)
            if not product:
                stats.skipped_no_data += 1
                continue

            product_rows.append(product)
            stats.products_ok += 1

            # Map packages
            packages = map_packages(record)
            if not packages:
                stats.products_no_confezioni += 1
            for pkg in packages:
                package_rows.append(pkg)
                stats.packages_ok += 1

            # Map ingredients
            ingredients = map_ingredients(record)
            for ing in ingredients:
                ingredient_rows.append(ing)
                stats.ingredients_ok += 1

            # Progress
            if stats.total_records % 1000 == 0:
                print(f"  Parsed {stats.total_records} records...")

    elapsed_parse = time.time() - t0
    print(f"Parsing completato in {elapsed_parse:.1f}s")
    print(f"  {len(product_rows)} prodotti, {len(package_rows)} confezioni, {len(ingredient_rows)} ingredienti")

    if dry_run:
        print("\n--dry-run: nessuna scrittura su DB")
        print(stats.summary())
        return stats

    # ── Upload to Supabase ──
    print("\nConnessione a Supabase...")
    url, key = _load_env()

    from supabase import create_client
    supabase = create_client(url, key)

    # 1. Products (must go first due to FK)
    print(f"\nUpserting {len(product_rows)} prodotti (batch={batch_size})...")
    t1 = time.time()
    for i in range(0, len(product_rows), batch_size):
        batch = product_rows[i : i + batch_size]
        upsert_batch(supabase, "catalog_it_raw_products", batch, "source_product_id")
        done = min(i + batch_size, len(product_rows))
        print(f"  prodotti: {done}/{len(product_rows)}")
    print(f"  Prodotti completati in {time.time() - t1:.1f}s")

    # 2. Packages
    print(f"\nUpserting {len(package_rows)} confezioni (batch={batch_size})...")
    t2 = time.time()
    for i in range(0, len(package_rows), batch_size):
        batch = package_rows[i : i + batch_size]
        upsert_batch(supabase, "catalog_it_raw_packages", batch, "source_package_id")
        done = min(i + batch_size, len(package_rows))
        print(f"  confezioni: {done}/{len(package_rows)}")
    print(f"  Confezioni completate in {time.time() - t2:.1f}s")

    # 3. Ingredients (no natural PK, delete + insert)
    print(f"\nInserting {len(ingredient_rows)} ingredienti (batch={batch_size})...")
    t3 = time.time()
    # Get unique product IDs to delete old ingredients
    product_ids = list({r["source_product_id"] for r in ingredient_rows})
    # Delete in batches
    for i in range(0, len(product_ids), batch_size):
        batch_ids = product_ids[i : i + batch_size]
        supabase.table("catalog_it_raw_ingredients").delete().in_("source_product_id", batch_ids).execute()

    # Insert in batches
    for i in range(0, len(ingredient_rows), batch_size):
        batch = ingredient_rows[i : i + batch_size]
        supabase.table("catalog_it_raw_ingredients").insert(batch).execute()
        done = min(i + batch_size, len(ingredient_rows))
        print(f"  ingredienti: {done}/{len(ingredient_rows)}")
    print(f"  Ingredienti completati in {time.time() - t3:.1f}s")

    total_elapsed = time.time() - t0
    print(f"\nImport totale completato in {total_elapsed:.1f}s")
    print(stats.summary())
    return stats


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Import AIFA catalog into Supabase")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_AIFA_FILE,
        help=f"Path to aifa_formadosaggio.jsonl (default: {DEFAULT_AIFA_FILE})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    parser.add_argument("--batch-size", type=int, default=500, help="Upsert batch size (default: 500)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"ERROR: File not found: {args.file}")
        return 1

    print(f"AIFA Import — file: {args.file}")
    print(f"  dry_run={args.dry_run}, batch_size={args.batch_size}")
    print()

    run_import(args.file, dry_run=args.dry_run, batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
