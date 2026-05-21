#!/usr/bin/env python3
"""Importa l'elenco carenze AIFA → catalog_it_shortages.

AIFA pubblica un CSV ufficiale dei farmaci carenti su:
  https://www.aifa.gov.it/documents/20142/847339/elenco_medicinali_carenti.csv

Il CSV è aggiornato pressoché quotidianamente. Colonne (rilevanti):
  - Codice AIC
  - Principio attivo
  - Forma farmaceutica e dosaggio
  - Data inizio
  - Fine presunta
  - Equivalente (testo libero: AIC alternativi o "Si"/"No")
  - Motivazioni
  - Suggerimenti/Indicazioni AIFA
  - Classe di rimborsabilità (riusabile lato Step 4!)
  - Codice ATC

Strategia di sync:
  1. Scarica il CSV (curl-style fallback per macOS SSL)
  2. Parsa righe → record (key = AIC + start_date)
  3. Carica carenze DB attive (resolved_at IS NULL)
  4. Insert nuove, refresh esistenti, mark resolved le sparite

Usage:
    python scripts/scrape_aifa_carenze.py            # full sync
    python scripts/scrape_aifa_carenze.py --dry-run  # parse only
    python scripts/scrape_aifa_carenze.py --file path.csv  # offline
    python scripts/scrape_aifa_carenze.py --url URL  # custom URL
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_URL = "https://www.aifa.gov.it/documents/20142/847339/elenco_medicinali_carenti.csv"


# ─── Stats ────────────────────────────────────────────────────────────────────


@dataclass
class Stats:
    rows_total: int = 0
    rows_valid: int = 0
    rows_skipped_no_aic: int = 0
    inserted_new: int = 0
    refreshed_existing: int = 0
    marked_resolved: int = 0
    parse_errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"  AIFA Carenze CSV — Riepilogo\n"
            f"{'='*60}\n"
            f"  Righe lette:                  {self.rows_total}\n"
            f"  Record validi:                {self.rows_valid}\n"
            f"  Skippate (no AIC):            {self.rows_skipped_no_aic}\n"
            f"  Nuove carenze inserite:       {self.inserted_new}\n"
            f"  Carenze esistenti aggiornate: {self.refreshed_existing}\n"
            f"  Marcate come risolte:         {self.marked_resolved}\n"
            f"  Errori di parsing:            {len(self.parse_errors)}\n"
            f"{'='*60}"
        )


# ─── Download ─────────────────────────────────────────────────────────────────


def fetch_csv(url: str, timeout: int = 60) -> str:
    """Scarica il CSV. Su macOS dev potrebbe servire certifi.

    Strategia robusta:
      1. Prova httpx con verify=True (cert di sistema)
      2. Se SSL fail: tenta con certifi
      3. Se ancora fail: fallback a urllib con ssl.create_default_context()
    """
    import httpx

    common_headers = {
        "User-Agent": "PharmaApp/1.0 (carenze-sync; mattia.debonis@gmail.com)",
        "Accept": "text/csv,application/csv,text/plain",
        "Accept-Language": "it-IT,it;q=0.9",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=common_headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return _decode_response(resp.content)
    except Exception as e:
        print(f"  httpx fallita: {e!r} — provo certifi/urllib fallback")

    # Fallback 1: certifi se installato
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        from urllib.request import Request, urlopen
        req = Request(url, headers=common_headers)
        with urlopen(req, context=ctx, timeout=timeout) as resp:
            return _decode_response(resp.read())
    except ImportError:
        pass
    except Exception as e:
        print(f"  certifi fallback fallita: {e!r}")

    # Fallback 2: urllib con context default macOS
    from urllib.request import Request, urlopen
    req = Request(url, headers=common_headers)
    with urlopen(req, timeout=timeout) as resp:
        return _decode_response(resp.read())


def _decode_response(content: bytes) -> str:
    """AIFA usa Latin-1 storicamente, a volte UTF-8. Detect."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1", errors="replace")


# ─── Parsing CSV ──────────────────────────────────────────────────────────────


# Mapping CSV AIFA → campi DB. Le intestazioni sono in italiano standard.
CSV_HEADERS = {
    "nome_medicinale": "Nome medicinale",
    "codice_aic": "Codice AIC",
    "principio_attivo": "Principio attivo",
    "forma_dosaggio": "Forma farmaceutica e dosaggio",
    "titolare": "Titolare AIC",
    "data_inizio": "Data inizio",
    "fine_presunta": "Fine presunta",
    "equivalente": "Equivalente",
    "motivazioni": "Motivazioni",
    "suggerimenti": "Suggerimenti/Indicazioni AIFA",
    "nota": "Nota AIFA",
    "classe": "Classe di rimborsabilità",
    "atc": "Codice ATC",
}


def _norm_header(h: str) -> str:
    h = h.strip().lower()
    h = re.sub(r"[^a-z0-9]+", "_", h)
    return h.strip("_")


def _detect_columns(headers: list[str]) -> dict[str, int]:
    """Mappa campo → indice colonna. AIFA è coerente, ma per
    robustezza facciamo matching su versione normalizzata."""
    normalized = [_norm_header(h) for h in headers]
    out: dict[str, int] = {}
    for field_name, header_text in CSV_HEADERS.items():
        target = _norm_header(header_text)
        for i, h in enumerate(normalized):
            if h == target:
                out[field_name] = i
                break
    return out


def _parse_date_it(s: str) -> date | None:
    if not s:
        return None
    s = s.strip()
    if not s or s.lower() in {"-", "n.d.", "nd", "non comunicata", "in attesa"}:
        return None

    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            return date(int(y), int(mo), int(d))
        except ValueError:
            return None

    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def parse_carenze_csv(csv_text: str, stats: Stats,
                       source_url: str | None = None) -> list[dict[str, Any]]:
    """Parsa il CSV AIFA. Restituisce lista di record pronti per upsert."""
    # Il CSV AIFA ha alcune righe di intestazione informativa prima del
    # vero header colonne (es. "NB: I medicinali carenti..." e
    # "Elenco aggiornato al..."). Cerchiamo la riga che contiene
    # "Codice AIC" e usiamo quella come header.
    lines = csv_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines[:20]):
        if "Codice AIC" in line and "Principio attivo" in line:
            header_idx = i
            break

    if header_idx is None:
        print("ERROR: header CSV non trovato", file=sys.stderr)
        return []

    csv_body = "\n".join(lines[header_idx:])
    reader = csv.reader(csv_body.splitlines(), delimiter=";", quotechar='"')
    headers = next(reader)
    columns = _detect_columns(headers)

    if "codice_aic" not in columns or "data_inizio" not in columns:
        print(f"ERROR: header CSV non riconosciuto. Trovati: {headers}", file=sys.stderr)
        return []

    out: list[dict[str, Any]] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        stats.rows_total += 1

        raw_aic = row[columns["codice_aic"]] if columns["codice_aic"] < len(row) else ""
        digits = re.sub(r"\D", "", raw_aic)
        if not digits:
            stats.rows_skipped_no_aic += 1
            continue
        if len(digits) < 9:
            digits = digits.zfill(9)
        cod_farmaco = digits[:6]

        # Costruisce la riga
        record: dict[str, Any] = {
            "codice_aic": digits,
            "cod_farmaco": cod_farmaco,
            "source_url": source_url,
        }

        def _cell(field: str) -> str:
            idx = columns.get(field)
            if idx is None or idx >= len(row):
                return ""
            return (row[idx] or "").strip()

        # Reason: combinazione di motivazione + suggerimenti AIFA (se c'è).
        # Spesso "Motivazioni" è il why, "Suggerimenti" è l'azione consigliata.
        motivazioni = _cell("motivazioni")
        suggerimenti = _cell("suggerimenti")
        if motivazioni and suggerimenti:
            record["reason"] = f"{motivazioni} — {suggerimenti}"
        else:
            record["reason"] = motivazioni or suggerimenti or None

        record["start_date"] = _parse_date_it(_cell("data_inizio"))
        record["expected_end_date"] = _parse_date_it(_cell("fine_presunta"))

        # Equivalente / sostitutivi: AIFA spesso scrive "Si"/"No" e
        # in suggerimenti elenca i farmaci alternativi.
        equivalente = _cell("equivalente")
        if equivalente and equivalente.lower() not in {"si", "sì", "no", "-"}:
            record["substitutes"] = equivalente
        elif suggerimenti and motivazioni and motivazioni != suggerimenti:
            # Suggerimenti AIFA spesso contengono nome dei sostitutivi
            record["substitutes"] = suggerimenti

        out.append(record)
        stats.rows_valid += 1

    return out


# ─── Supabase sync ────────────────────────────────────────────────────────────


def _load_env() -> tuple[str, str]:
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
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required in .env", file=sys.stderr)
        sys.exit(1)
    return url, key


def sync_to_db(records: list[dict[str, Any]], stats: Stats) -> None:
    """Sync DB:
      - INSERT nuove (key = AIC + start_date)
      - UPDATE last_seen_at + fields su quelle ancora presenti
      - resolved_at su quelle sparite
    """
    url, key = _load_env()
    from supabase import ClientOptions, create_client
    supabase = create_client(url, key, options=ClientOptions(postgrest_client_timeout=300))

    now = datetime.now(timezone.utc).isoformat()

    db_rows = supabase.table("catalog_it_shortages") \
        .select("id, codice_aic, start_date") \
        .is_("resolved_at", "null") \
        .execute().data or []

    def _serialize_dates(r: dict[str, Any]) -> dict[str, Any]:
        out = dict(r)
        if isinstance(out.get("start_date"), date):
            out["start_date"] = out["start_date"].isoformat()
        if isinstance(out.get("expected_end_date"), date):
            out["expected_end_date"] = out["expected_end_date"].isoformat()
        return out

    def _key(r: dict[str, Any]) -> tuple[str, str | None]:
        return (r["codice_aic"], r.get("start_date"))

    db_by_key: dict[tuple[str, str | None], str] = {_key(r): r["id"] for r in db_rows}
    scraped_records = [_serialize_dates(r) for r in records]
    scraped_by_key: dict[tuple[str, str | None], dict[str, Any]] = {
        _key(r): r for r in scraped_records
    }

    # Insert nuove
    new_records = [r for k, r in scraped_by_key.items() if k not in db_by_key]
    if new_records:
        try:
            supabase.table("catalog_it_shortages").insert(new_records).execute()
            stats.inserted_new = len(new_records)
        except Exception as e:
            print(f"  WARN: insert batch fallita: {e!r}")
            for r in new_records:
                try:
                    supabase.table("catalog_it_shortages").insert(r).execute()
                    stats.inserted_new += 1
                except Exception as e2:
                    stats.parse_errors.append(f"insert {r.get('codice_aic')}: {e2!r}")

    # Refresh esistenti
    for k in scraped_by_key:
        if k in db_by_key:
            row_id = db_by_key[k]
            update_fields = {
                "last_seen_at": now,
                "reason": scraped_by_key[k].get("reason"),
                "expected_end_date": scraped_by_key[k].get("expected_end_date"),
                "substitutes": scraped_by_key[k].get("substitutes"),
            }
            try:
                supabase.table("catalog_it_shortages").update(update_fields).eq("id", row_id).execute()
                stats.refreshed_existing += 1
            except Exception as e:
                stats.parse_errors.append(f"refresh {k}: {e!r}")

    # Marca resolved
    for k in db_by_key:
        if k not in scraped_by_key:
            row_id = db_by_key[k]
            try:
                supabase.table("catalog_it_shortages").update({"resolved_at": now}).eq("id", row_id).execute()
                stats.marked_resolved += 1
            except Exception as e:
                stats.parse_errors.append(f"resolve {k}: {e!r}")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync AIFA carenze CSV → catalog_it_shortages")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL CSV (default: {DEFAULT_URL})")
    parser.add_argument("--file", type=Path, help="Path locale al CSV (skip download)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"AIFA Carenze Sync — fonte: {args.file or args.url}")
    stats = Stats()
    t0 = time.time()

    if args.file:
        if not args.file.exists():
            print(f"ERROR: file non trovato: {args.file}", file=sys.stderr)
            return 1
        csv_text = _decode_response(args.file.read_bytes())
        source_url = f"file://{args.file.resolve()}"
    else:
        print("Download CSV in corso...")
        try:
            csv_text = fetch_csv(args.url)
        except Exception as e:
            print(f"ERROR: download fallito: {e!r}", file=sys.stderr)
            return 1
        source_url = args.url

    records = parse_carenze_csv(csv_text, stats, source_url=source_url)
    print(f"Parsing in {time.time() - t0:.1f}s — {len(records)} carenze valide")

    if args.dry_run:
        print("\n--dry-run: nessuna scrittura su DB")
        for r in records[:5]:
            sd = r.get("start_date")
            print(f"  AIC={r['codice_aic']}  start={sd}  reason={(r.get('reason') or '')[:80]!r}")
        print(stats.summary())
        return 0

    print(f"\nSync DB...")
    t1 = time.time()
    sync_to_db(records, stats)
    print(f"  Sync completato in {time.time() - t1:.1f}s")
    print(stats.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
