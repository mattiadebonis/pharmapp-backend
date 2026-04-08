#!/usr/bin/env python3
"""Import AIFA confezioni_fornitura CSV into Supabase catalog_it_* tables.

Usage:
    python scripts/import_aifa_csv.py                         # full import
    python scripts/import_aifa_csv.py --dry-run               # parse only, no DB writes
    python scripts/import_aifa_csv.py --batch-size 200        # custom batch size
    python scripts/import_aifa_csv.py --file /path/to/file    # custom input file

Requires .env with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from parsers.aifa_package_parser import parse_denominazione_package


# ─── Fornitura Classification ────────────────────────────────────────────────

FORNITURA_MAP: dict[str, tuple[str, bool]] = {
    # (fornitura_code, requires_prescription)
    "Medicinali non soggetti a prescrizione medica, da banco.": ("OTC", False),
    "Medicinali non soggetti a prescrizione medica ma non da banco": ("SOP", False),
    "Medicinali soggetti a prescrizione medica": ("RR", True),
    "Medicinali soggetti a prescrizione medica da rinnovare volta per volta": ("RNR", True),
    "Medicinali soggetti a prescrizione medica limitativa, da rinnovare volta per volta, vendibili al pubblico su prescrizione di centri ospedalieri o di specialisti": ("RNRL", True),
    "Medicinali soggetti a prescrizione medica limitativa, utilizzabili esclusivamente dallo specialista": ("USPL", True),
    "Medicinali soggetti a prescrizione medica limitativa, utilizzabili esclusivamente in ambiente ospedaliero o in una struttura ad esso assimilabile": ("OSP", True),
    "Medicinali soggetti a prescrizione medica limitativa, vendibili al pubblico su prescrizione di centri ospedalieri o di specialisti": ("RRL", True),
    "Medicinali soggetti a prescrizione medica speciale con Ricetta Ministeriale a Ricalco": ("RMR", True),
    "N.D.": ("ND", False),
}


def classify_fornitura(fornitura_text: str) -> tuple[str, bool]:
    """Return (fornitura_code, requires_prescription) from the full FORNITURA text."""
    text = fornitura_text.strip()
    if text in FORNITURA_MAP:
        return FORNITURA_MAP[text]
    # Fallback: try partial matching
    lower = text.lower()
    if "non soggetti" in lower and "da banco" in lower:
        return ("OTC", False)
    if "non soggetti" in lower:
        return ("SOP", False)
    if "soggetti" in lower:
        return ("RR", True)
    return ("ND", False)


# ─── Stats ───────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    total_rows: int = 0
    skipped_empty: int = 0
    packages_ok: int = 0
    products_ok: int = 0
    ingredients_ok: int = 0
    parse_errors: int = 0
    fornitura_codes: dict[str, int] = field(default_factory=lambda: Counter())

    def summary(self) -> str:
        forn_lines = "\n".join(f"    {k}: {v}" for k, v in sorted(self.fornitura_codes.items()))
        return (
            f"\n{'='*60}\n"
            f"  Import AIFA CSV — Riepilogo\n"
            f"{'='*60}\n"
            f"  Righe CSV lette:        {self.total_rows}\n"
            f"  Skippate (vuote):       {self.skipped_empty}\n"
            f"  Confezioni importate:   {self.packages_ok}\n"
            f"  Prodotti aggregati:     {self.products_ok}\n"
            f"  Ingredienti estratti:   {self.ingredients_ok}\n"
            f"  Errori parsing:         {self.parse_errors}\n"
            f"  Distribuzione fornitura:\n{forn_lines}\n"
            f"{'='*60}"
        )


# ─── CSV Parsing ─────────────────────────────────────────────────────────────

def _strip_quotes(val: str) -> str:
    """Strip surrounding double quotes from a CSV value."""
    val = val.strip()
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1].strip()
    return val


def parse_csv(file_path: Path, stats: Stats) -> tuple[list[dict], dict[str, dict], list[dict]]:
    """Parse the CSV and return (package_rows, products_dict, ingredient_rows)."""
    package_rows: list[dict[str, Any]] = []
    # Aggregate product data from packages
    products: dict[str, dict[str, Any]] = {}  # keyed by cod_farmaco
    # Track per-product aggregates
    product_forms: dict[str, list[str]] = defaultdict(list)
    product_pa: dict[str, list[str]] = defaultdict(list)
    product_atc: dict[str, list[str]] = defaultdict(list)
    product_fornitura: dict[str, list[str]] = defaultdict(list)
    product_prescription: dict[str, list[bool]] = defaultdict(list)
    # Ingredients (deduplicated per product)
    ingredient_set: dict[str, dict[str, int]] = defaultdict(dict)  # cod_farmaco -> {name: sort_order}

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        header = next(reader)  # skip header

        for row_num, row in enumerate(reader, start=2):
            stats.total_rows += 1

            if len(row) < 15:
                stats.skipped_empty += 1
                continue

            codice_aic = _strip_quotes(row[0])
            cod_farmaco = _strip_quotes(row[1])
            cod_confezione = _strip_quotes(row[2])
            denominazione = _strip_quotes(row[3])
            descrizione = _strip_quotes(row[4])
            codice_ditta_str = _strip_quotes(row[5])
            ragione_sociale = _strip_quotes(row[6])
            stato_amministrativo = _strip_quotes(row[7])
            tipo_procedura = _strip_quotes(row[8])
            forma = _strip_quotes(row[9])
            codice_atc = _strip_quotes(row[10])
            pa_associati = _strip_quotes(row[11])
            fornitura_text = _strip_quotes(row[12])
            link_fi = _strip_quotes(row[13])
            link_rcp = _strip_quotes(row[14])

            if not codice_aic or not cod_farmaco:
                stats.skipped_empty += 1
                continue

            # Parse CODICE_DITTA as integer
            try:
                codice_ditta = int(codice_ditta_str) if codice_ditta_str else None
            except ValueError:
                codice_ditta = None

            # Classify fornitura
            fornitura_code, requires_prescription = classify_fornitura(fornitura_text)
            stats.fornitura_codes[fornitura_code] += 1

            # Parse DESCRIZIONE for structured fields
            try:
                parsed = parse_denominazione_package(descrizione)
            except Exception as e:
                stats.parse_errors += 1
                if stats.parse_errors <= 10:
                    print(f"  WARN: row {row_num}: parse error for '{descrizione}': {e}")
                parsed = parse_denominazione_package(None)

            # Build package row
            pkg = {
                "codice_aic": codice_aic,
                "cod_farmaco": cod_farmaco,
                "cod_confezione": cod_confezione,
                "denominazione": denominazione,
                "descrizione": descrizione,
                "forma": forma,
                "codice_atc": codice_atc,
                "pa_associati": pa_associati,
                "stato_amministrativo": stato_amministrativo,
                "tipo_procedura": tipo_procedura,
                "fornitura": fornitura_text,
                "fornitura_code": fornitura_code,
                "requires_prescription": requires_prescription,
                "unit_count": parsed.unit_count,
                "package_type": parsed.package_type or None,
                "strength_value": parsed.strength_value,
                "strength_unit": parsed.strength_unit or None,
                "strength_text": parsed.strength_text or None,
                "volume_value": parsed.volume_value,
                "volume_unit": parsed.volume_unit or None,
            }
            package_rows.append(pkg)
            stats.packages_ok += 1

            # Aggregate product-level data
            if cod_farmaco not in products:
                products[cod_farmaco] = {
                    "cod_farmaco": cod_farmaco,
                    "denominazione": denominazione,
                    "codice_ditta": codice_ditta,
                    "ragione_sociale": ragione_sociale,
                    "link_fi": link_fi,
                    "link_rcp": link_rcp,
                    "stato_amministrativo": stato_amministrativo,
                    "tipo_procedura": tipo_procedura,
                }

            # Track per-package varying fields for aggregation
            if forma:
                product_forms[cod_farmaco].append(forma)
            if pa_associati:
                product_pa[cod_farmaco].append(pa_associati)
            if codice_atc:
                product_atc[cod_farmaco].append(codice_atc)
            product_fornitura[cod_farmaco].append(fornitura_code)
            product_prescription[cod_farmaco].append(requires_prescription)

            # Extract ingredients from PA_ASSOCIATI
            if pa_associati:
                for i, name in enumerate(pa_associati.split("/")):
                    name = name.strip()
                    if name and name not in ingredient_set[cod_farmaco]:
                        ingredient_set[cod_farmaco][name] = len(ingredient_set[cod_farmaco])

            # Progress
            if stats.total_rows % 20000 == 0:
                print(f"  Parsed {stats.total_rows} rows...")

    # Finalize product aggregates
    product_rows: list[dict[str, Any]] = []
    for cod_farmaco, prod in products.items():
        forms = product_forms.get(cod_farmaco, [])
        pa_list = product_pa.get(cod_farmaco, [])
        atc_list = product_atc.get(cod_farmaco, [])
        forn_list = product_fornitura.get(cod_farmaco, [])
        presc_list = product_prescription.get(cod_farmaco, [])

        # Most common value
        forma_counter = Counter(forms)
        pa_counter = Counter(pa_list)
        atc_counter = Counter(atc_list)
        forn_counter = Counter(forn_list)

        prod["forma_prevalente"] = forma_counter.most_common(1)[0][0] if forma_counter else None
        prod["forme_distinte"] = sorted(set(forms)) if forms else []
        prod["pa_prevalente"] = pa_counter.most_common(1)[0][0] if pa_counter else None
        prod["codice_atc"] = atc_counter.most_common(1)[0][0] if atc_counter else None
        prod["codice_atc_all"] = sorted(set(atc_list)) if atc_list else []
        prod["fornitura_code"] = forn_counter.most_common(1)[0][0] if forn_counter else None
        prod["is_homeopathic"] = prod.get("tipo_procedura") == "Omeopatico"
        prod["requires_prescription"] = any(presc_list)

        product_rows.append(prod)

    stats.products_ok = len(product_rows)

    # Build ingredient rows
    ingredient_rows: list[dict[str, Any]] = []
    for cod_farmaco, names in ingredient_set.items():
        for name, sort_order in names.items():
            ingredient_rows.append({
                "cod_farmaco": cod_farmaco,
                "name": name,
                "sort_order": sort_order,
            })
    stats.ingredients_ok = len(ingredient_rows)

    return package_rows, product_rows, ingredient_rows


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
    """Run the full AIFA CSV import."""
    stats = Stats()

    print(f"Reading {file_path}...")
    t0 = time.time()

    package_rows, product_rows, ingredient_rows = parse_csv(file_path, stats)

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
        upsert_batch(supabase, "catalog_it_products", batch, "cod_farmaco")
        done = min(i + batch_size, len(product_rows))
        print(f"  prodotti: {done}/{len(product_rows)}")
    print(f"  Prodotti completati in {time.time() - t1:.1f}s")

    # 2. Packages
    print(f"\nUpserting {len(package_rows)} confezioni (batch={batch_size})...")
    t2 = time.time()
    for i in range(0, len(package_rows), batch_size):
        batch = package_rows[i : i + batch_size]
        upsert_batch(supabase, "catalog_it_packages", batch, "codice_aic")
        done = min(i + batch_size, len(package_rows))
        print(f"  confezioni: {done}/{len(package_rows)}")
    print(f"  Confezioni completate in {time.time() - t2:.1f}s")

    # 3. Ingredients (delete + insert by product)
    print(f"\nInserting {len(ingredient_rows)} ingredienti (batch={batch_size})...")
    t3 = time.time()
    # Get unique product IDs to delete old ingredients
    product_ids = list({r["cod_farmaco"] for r in ingredient_rows})
    for i in range(0, len(product_ids), batch_size):
        batch_ids = product_ids[i : i + batch_size]
        supabase.table("catalog_it_ingredients").delete().in_("cod_farmaco", batch_ids).execute()

    # Insert in batches
    for i in range(0, len(ingredient_rows), batch_size):
        batch = ingredient_rows[i : i + batch_size]
        supabase.table("catalog_it_ingredients").insert(batch).execute()
        done = min(i + batch_size, len(ingredient_rows))
        print(f"  ingredienti: {done}/{len(ingredient_rows)}")
    print(f"  Ingredienti completati in {time.time() - t3:.1f}s")

    total_elapsed = time.time() - t0
    print(f"\nImport totale completato in {total_elapsed:.1f}s")
    print(stats.summary())
    return stats


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Import AIFA CSV catalog into Supabase")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "confezioni_fornitura.csv",
        help="Path to confezioni_fornitura CSV file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    parser.add_argument("--batch-size", type=int, default=500, help="Upsert batch size (default: 500)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"ERROR: File not found: {args.file}")
        return 1

    print(f"AIFA CSV Import — file: {args.file}")
    print(f"  dry_run={args.dry_run}, batch_size={args.batch_size}")
    print()

    run_import(args.file, dry_run=args.dry_run, batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
