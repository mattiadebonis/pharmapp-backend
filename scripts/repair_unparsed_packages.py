#!/usr/bin/env python3
"""Repair packages 'stale' nel DB con strength_text NULL ma dose parsabile.

Contesto: dopo la migration 036 (cleanup polluted-legacy) e la 038 (regex
POSIX), la view `catalog_it_packages_audit` ha rivelato ~246 packages
classificati `UNPARSED_BUG`: hanno descrizione con dose chiara
(es. "7,5 MG COMPRESSE…") ma strength_text NULL.

Sono confezioni che NON sono più nel CSV `confezioni_fornitura.csv`
corrente (probabilmente cessate o importazione parallela), quindi
il re-import non le aggiorna. Il parser è in grado di estrarre la
dose correttamente — manca solo eseguirlo.

Questo script:
  1. Query `catalog_it_packages_audit` WHERE quality_code='UNPARSED_BUG'
  2. Per ognuno, chiama `parse_denominazione_package(descrizione)`
  3. UPDATE catalog_it_packages SET strength_text=..., strength_value=..., ...
  4. Refresh `catalog_it_packages_audit`
  5. Stampa report before/after

Usage:
    python scripts/repair_unparsed_packages.py            # esecuzione live
    python scripts/repair_unparsed_packages.py --dry-run  # solo report
    python scripts/repair_unparsed_packages.py --limit 50 # primi N record
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from parsers.aifa_package_parser import parse_denominazione_package  # noqa: E402


# ─── Env helpers ─────────────────────────────────────────────────────────────


def _load_env() -> tuple[str, str]:
    env_path = PROJECT_ROOT / ".env"
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
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
        sys.exit(1)
    return url, key


# ─── Stats ───────────────────────────────────────────────────────────────────


@dataclass
class Stats:
    candidates: int = 0
    repaired: int = 0
    skipped_no_strength: int = 0
    skipped_homeopathic: int = 0
    update_errors: int = 0
    examples_skipped: list[str] = field(default_factory=list)
    examples_repaired: list[tuple[str, str]] = field(default_factory=list)


# ─── Main repair ─────────────────────────────────────────────────────────────


def run_repair(dry_run: bool = False, limit: int | None = None) -> Stats:
    url, key = _load_env()
    from supabase import ClientOptions, create_client
    sb = create_client(url, key, options=ClientOptions(postgrest_client_timeout=120))

    print("Fetch candidates UNPARSED_BUG...")
    query = sb.table("catalog_it_packages_audit").select(
        "codice_aic, descrizione, forma, denominazione_prodotto, tipo_procedura"
    ).eq("quality_code", "UNPARSED_BUG")
    if limit:
        query = query.limit(limit)
    candidates = query.execute().data or []
    stats = Stats(candidates=len(candidates))
    print(f"  {len(candidates)} packages da analizzare")

    for row in candidates:
        aic = row["codice_aic"]
        desc = row.get("descrizione") or ""
        tipo = row.get("tipo_procedura")
        nome = row.get("denominazione_prodotto") or ""

        # Sanity: omeopatici devono restare NULL (gestiti da migration 036)
        if tipo == "Omeopatico":
            stats.skipped_homeopathic += 1
            continue

        # Parse
        parsed = parse_denominazione_package(desc)
        if not parsed.strength_text:
            stats.skipped_no_strength += 1
            if len(stats.examples_skipped) < 5:
                stats.examples_skipped.append(f"AIC {aic} ({nome}): {desc[:80]}")
            continue

        if dry_run:
            stats.repaired += 1
            if len(stats.examples_repaired) < 5:
                stats.examples_repaired.append((aic, parsed.strength_text))
            continue

        # UPDATE in DB
        update_payload: dict[str, Any] = {
            "strength_text": parsed.strength_text,
            "strength_value": parsed.strength_value,
            "strength_unit": parsed.strength_unit or None,
        }
        # Aggiorniamo anche unit_count e package_type se erano NULL/zero
        if parsed.unit_count and parsed.unit_count > 0:
            update_payload["unit_count"] = parsed.unit_count
        if parsed.package_type:
            update_payload["package_type"] = parsed.package_type

        try:
            sb.table("catalog_it_packages").update(update_payload).eq("codice_aic", aic).execute()
            stats.repaired += 1
            if len(stats.examples_repaired) < 5:
                stats.examples_repaired.append((aic, parsed.strength_text))
        except Exception as e:
            stats.update_errors += 1
            if stats.update_errors <= 5:
                print(f"  WARN update AIC {aic}: {e!r}")

    # Refresh view audit
    if not dry_run and stats.repaired > 0:
        print("\nRefresh catalog_it_packages_audit...")
        try:
            sb.rpc("refresh_catalog_audit", {}).execute()
            print("  done")
        except Exception as e:
            print(f"  WARN refresh: {e!r}")

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair UNPARSED_BUG packages via parser locale")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="Limita ai primi N candidati")
    args = parser.parse_args()

    stats = run_repair(dry_run=args.dry_run, limit=args.limit)

    print()
    print("=" * 60)
    print("REPAIR REPORT")
    print("=" * 60)
    print(f"  Candidates UNPARSED_BUG:     {stats.candidates}")
    print(f"  Riparati:                    {stats.repaired}")
    print(f"  Skip (parser non estrae):    {stats.skipped_no_strength}")
    print(f"  Skip (omeopatico):           {stats.skipped_homeopathic}")
    print(f"  Update errors:               {stats.update_errors}")

    if stats.examples_repaired:
        print("\nEsempi riparati:")
        for aic, st in stats.examples_repaired[:5]:
            print(f"  AIC {aic} → {st!r}")

    if stats.examples_skipped:
        print("\nEsempi non riparabili (parser non estrae):")
        for ex in stats.examples_skipped[:5]:
            print(f"  {ex}")

    return 1 if stats.update_errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
