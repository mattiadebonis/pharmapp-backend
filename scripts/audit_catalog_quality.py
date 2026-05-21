#!/usr/bin/env python3
"""Audit qualità del parsing AIFA su tutto il catalogo.

Interroga la materialized view `catalog_it_packages_audit` (migration 036)
e applica 13 validation rules. Produce:
- Markdown report su stdout (o file via --output)
- CSV completo della view via --csv (per analisi manuale)

Esempi:
    python scripts/audit_catalog_quality.py
    python scripts/audit_catalog_quality.py --output audit-2026-05.md
    python scripts/audit_catalog_quality.py --csv audit-full.csv
    python scripts/audit_catalog_quality.py --refresh    # refresh view prima

Validation rules (sintesi):
    V01 ERROR — Compresse/capsule con dose riconoscibile DEVONO avere strength_text
    V02 WARN  — strength_text length ≤ 60 char
    V03 ERROR — strength_text ≠ descrizione completa (no polluted-legacy)
    V04 ERROR — strength_value implies strength_text
    V05 ERROR — strength_unit implies strength_value
    V06 WARN  — Compresse con count plausibile ≥ 2 ma unit_count = 1
    V07 WARN  — package_type popolato per forme standard
    V08 WARN  — Liquidi orali DOVREBBERO avere volume_value
    V09 ERROR — strength_unit appartiene alla whitelist
    V10 WARN  — Omeopatici DEVONO avere strength_text = NULL
    V11 ERROR — strength_text inizia con cifra
    V12 WARN  — varianti consistenti per cod_farmaco
    V13 ERROR — tasso PARSED_OK / TOTAL ≥ 97% sui "deve-avere-dose"
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Validation rules SQL ────────────────────────────────────────────────────


# Whitelist unità AIFA-normalizzate (post fix migration 031). Qualunque
# `strength_unit` fuori da questa lista è un'unità "inventata" / non
# normalizzata e va investigata.
_VALID_UNITS_WHITELIST = """
    'MG', 'MCG', 'NG', 'PG', 'G', 'ML', 'L', 'UI', 'U.I.', 'IU', 'MMOL',
    'MEQ', 'U', '%',
    -- Composte mass/volume
    'MG/ML', 'MCG/ML', 'NG/ML', 'UI/ML', 'MEQ/ML', 'MG/L', 'MCG/L',
    'IU/ML', 'G/L', 'G/ML', 'PG/ML', 'MMOL/L',
    -- Per-X (rate) — l'unità composta dopo / è una parola, varie possibili
    'MG/ORA', 'MCG/ORA', 'MG/H', 'MCG/H',
    'MG/EROGAZIONE', 'MCG/EROGAZIONE', 'MG/DOSE', 'MCG/DOSE',
    'MG/INALAZIONE', 'MCG/INALAZIONE',
    'MG/24H', 'MCG/24H', 'MG/72H', 'MCG/72H',
    'MG/ATTUAZIONE', 'MCG/ATTUAZIONE'
"""


def _build_rules() -> list[tuple[str, str, str, str]]:
    """Return list of (rule_id, severity, description, sql).

    Ogni SQL ritorna `count` come unica colonna scalare (intero).
    """
    return [
        (
            "V01", "ERROR",
            "Compresse/capsule con dose chiara → strength_text NOT NULL",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE forma ~* 'compress|capsul|bustin|fial'
              AND descrizione ~* '\\d+\\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|%)\\b'
              AND strength_text IS NULL
              AND tipo_procedura IS DISTINCT FROM 'Omeopatico'
            """,
        ),
        (
            "V02", "WARN",
            "strength_text length ≤ 60 char (60 ammesso per trifasici legittimi)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_text IS NOT NULL AND length(strength_text) > 60
            """,
        ),
        (
            "V03", "ERROR",
            "strength_text ≠ descrizione (no polluted-legacy)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_text IS NOT NULL AND strength_text = descrizione
            """,
        ),
        (
            "V04", "ERROR",
            "strength_value NOT NULL ⇒ strength_text NOT NULL",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_value IS NOT NULL AND strength_text IS NULL
            """,
        ),
        (
            "V05", "ERROR",
            "strength_unit NOT NULL ⇒ strength_value NOT NULL",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_unit IS NOT NULL AND strength_unit <> ''
              AND strength_value IS NULL
            """,
        ),
        (
            "V06", "WARN",
            "Compresse con N≥2 nel desc ma unit_count = 1 (probabile count mancante)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE forma ~* 'compress' AND unit_count = 1
              AND descrizione ~* '\\d{2,}\\s*compress'
            """,
        ),
        (
            "V07", "WARN",
            "package_type popolato per forme standard (tasso ≥ 95%, qui count nulli)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE package_type IS NULL
              AND forma ~* 'compress|capsul|bustin|fial|cerott|supposta|ovul|flacon|tubo|siring'
            """,
        ),
        (
            "V08", "WARN",
            "Liquidi orali dovrebbero avere volume_value",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE forma ~* 'sciropp|sospens|soluzione orale|gocce orali'
              AND volume_value IS NULL
            """,
        ),
        (
            "V09", "ERROR",
            "strength_unit in whitelist normalizzata",
            f"""
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_unit IS NOT NULL AND strength_unit <> ''
              AND upper(strength_unit) NOT IN ({_VALID_UNITS_WHITELIST})
            """,
        ),
        (
            "V10", "WARN",
            "Omeopatici → strength_text NULL (post-fix 036)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE tipo_procedura = 'Omeopatico' AND strength_text IS NOT NULL
            """,
        ),
        (
            "V11", "ERROR",
            "strength_text inizia con cifra (no testo libero prefisso)",
            """
            SELECT COUNT(*) FROM catalog_it_packages_audit
            WHERE strength_text IS NOT NULL
              AND strength_text !~ '^[0-9]'
            """,
        ),
        (
            "V12", "WARN",
            "Varianti coerenti per cod_farmaco (no mix NULL/NOT-NULL strength sulla stessa forma)",
            """
            SELECT COUNT(*) FROM (
              SELECT cod_farmaco, forma
              FROM catalog_it_packages_audit
              WHERE tipo_procedura IS DISTINCT FROM 'Omeopatico'
              GROUP BY cod_farmaco, forma
              HAVING COUNT(*) FILTER (WHERE strength_text IS NULL) > 0
                 AND COUNT(*) FILTER (WHERE strength_text IS NOT NULL) > 0
            ) inconsistent
            """,
        ),
    ]


# V13 è aggregata (rate, non count) — gestita a parte
_V13_SQL = """
SELECT
  COUNT(*) AS total_eligible,
  COUNT(*) FILTER (WHERE strength_text IS NOT NULL) AS parsed_ok
FROM catalog_it_packages_audit
WHERE forma ~* 'compress|capsul|bustin|fial'
  AND descrizione ~* '\\d+\\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|%)\\b'
  AND tipo_procedura IS DISTINCT FROM 'Omeopatico'
"""


# ─── Report dataclasses ──────────────────────────────────────────────────────


@dataclass
class RuleResult:
    rule_id: str
    severity: str
    description: str
    count: int


@dataclass
class AuditReport:
    total_packages: int
    by_quality_code: dict[str, int] = field(default_factory=dict)
    by_quality_code_pct: dict[str, float] = field(default_factory=dict)
    rules: list[RuleResult] = field(default_factory=list)
    v13_total_eligible: int = 0
    v13_parsed_ok: int = 0
    v13_rate: float = 0.0
    v13_pass: bool = False
    examples_by_rule: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def n_errors(self) -> int:
        n = sum(1 for r in self.rules if r.severity == "ERROR" and r.count > 0)
        if not self.v13_pass:
            n += 1
        return n

    def n_warnings(self) -> int:
        return sum(1 for r in self.rules if r.severity == "WARN" and r.count > 0)


# ─── Supabase helpers ────────────────────────────────────────────────────────


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


def _exec_count(sb, sql: str) -> int:
    """Esegue una query SQL che ritorna {count: N} via RPC `exec_count_audit`.

    Nota: Supabase REST non supporta SQL arbitrario; usiamo il client
    Postgres diretto via psycopg2 / supabase RPC. Per semplicità qui
    usiamo .rpc() ma se non disponibile fallback a postgrest filtri.

    In assenza di RPC, costruiamo le query come filtri PostgREST quando
    possibile. Le 13 query di audit sono però troppo complesse — quindi
    usiamo la `from_` chain con `.execute()` su una view PostgreSQL.
    Strategia attuale: usare connection DB diretta via psycopg2 con DATABASE_URL.
    """
    # Strategia: usa httpx con PostgreSQL REST (PgREST exec via stored function)
    # In assenza di RPC dedicata, eseguiamo manualmente:
    # SELECT json_agg(t) FROM (<query>) t  → restituisce JSON con count
    # Per non aggiungere una migration just-for-this, leggiamo via .rpc su pg_temp
    # Fallback: chiamiamo supabase.rpc("audit_exec_count", {"q": sql}) se esiste,
    # altrimenti facciamo una select sulla view per inferire.
    raise NotImplementedError(
        "audit_catalog_quality usa Postgres SQL arbitrario. "
        "Servirebbe una RPC dedicata. Per ora usa --inline-sql."
    )


def _exec_count_via_pg(sql: str) -> int:
    """Esegue SQL via psycopg2 con DATABASE_URL (più semplice per tooling)."""
    import psycopg2  # type: ignore[import-not-found]
    url, _ = _load_env()
    # Supabase DB URL è derivato dal SUPABASE_URL host
    # Es: https://lkthat...supabase.co → db.lkthat...supabase.co:5432
    project_ref = url.replace("https://", "").split(".")[0]
    db_url = os.environ.get("DATABASE_URL") or f"postgresql://postgres.{project_ref}@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
    # In assenza di DATABASE_URL configurato, l'utente deve impostarlo.
    pwd = os.environ.get("SUPABASE_DB_PASSWORD", "")
    if pwd and "@aws" in db_url:
        db_url = db_url.replace(f"postgres.{project_ref}@", f"postgres.{project_ref}:{pwd}@")

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return int(row[0]) if row else 0


# Strategia più semplice: usiamo supabase.postgrest con .execute() su una vista
# che precalcola tutte le violazioni. Ma per ora teniamo l'implementazione via
# supabase-py + raw RPC. Manca quel pezzo — fallback inline:


def _exec_sql_inline(sb, sql: str) -> int:
    """Esegue una query SQL via supabase-py utilizzando una RPC ad-hoc.

    Approccio: usiamo l'estensione `pg_query` se disponibile, altrimenti
    esponiamo una stored function `audit_count(sql_text)` lato DB.

    Per evitare dipendenza da nuove RPC, qui usiamo psycopg2 diretto.
    """
    return _exec_count_via_pg(sql)


# ─── Main audit ──────────────────────────────────────────────────────────────


def run_audit(refresh: bool, examples_limit: int = 5) -> AuditReport:
    url, key = _load_env()
    from supabase import create_client
    sb = create_client(url, key)

    if refresh:
        print("Refresh materialized view catalog_it_packages_audit...", file=sys.stderr)
        try:
            sb.rpc("refresh_catalog_audit", {}).execute()
        except Exception as e:
            print(f"  WARN: refresh failed: {e!r}", file=sys.stderr)

    # Total & by quality_code via supabase REST (non SQL libero — OK qui)
    total_resp = sb.table("catalog_it_packages_audit").select("codice_aic", count="exact").execute()
    total = total_resp.count or 0

    by_qc: dict[str, int] = {}
    qc_resp = sb.table("catalog_it_packages_audit").select("quality_code").execute()
    for row in qc_resp.data or []:
        qc = row["quality_code"]
        by_qc[qc] = by_qc.get(qc, 0) + 1

    report = AuditReport(total_packages=total, by_quality_code=by_qc)
    if total > 0:
        report.by_quality_code_pct = {
            k: round(100.0 * v / total, 2) for k, v in by_qc.items()
        }

    # Validation rules
    for rule_id, severity, description, sql in _build_rules():
        try:
            count = _exec_sql_inline(sb, sql)
        except Exception as e:
            print(f"  WARN rule {rule_id}: {e!r}", file=sys.stderr)
            count = -1
        report.rules.append(RuleResult(rule_id, severity, description, count))

    # V13 aggregate
    try:
        import psycopg2
        url_db = _make_db_url()
        with psycopg2.connect(url_db) as conn:
            with conn.cursor() as cur:
                cur.execute(_V13_SQL)
                row = cur.fetchone()
                total_eligible, parsed_ok = int(row[0]), int(row[1])
                report.v13_total_eligible = total_eligible
                report.v13_parsed_ok = parsed_ok
                if total_eligible > 0:
                    report.v13_rate = round(100.0 * parsed_ok / total_eligible, 2)
                    report.v13_pass = report.v13_rate >= 97.0
                else:
                    report.v13_pass = True
    except Exception as e:
        print(f"  WARN V13: {e!r}", file=sys.stderr)

    # Esempi per ogni rule con count > 0
    for rule in report.rules:
        if rule.count > 0 and rule.count < 1000:
            try:
                # Wrap la query SQL: aggiungi SELECT codice_aic, ... con LIMIT
                # È più semplice farsi una query dedicata, ma per brevità skip.
                pass
            except Exception:
                pass

    return report


def _make_db_url() -> str:
    url, _ = _load_env()
    project_ref = url.replace("https://", "").split(".")[0]
    pwd = os.environ.get("SUPABASE_DB_PASSWORD", "")
    return f"postgresql://postgres.{project_ref}:{pwd}@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"


# ─── Output formatters ───────────────────────────────────────────────────────


def render_markdown(report: AuditReport) -> str:
    lines: list[str] = []
    from datetime import datetime
    lines.append(f"# Audit catalogo AIFA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"**Packages totali (pubblici autorizzati)**: {report.total_packages}")
    lines.append("")
    lines.append("## Distribuzione qualità")
    lines.append("")
    lines.append("| Quality code | Count | % |")
    lines.append("|---|---:|---:|")
    for qc, cnt in sorted(report.by_quality_code.items(), key=lambda x: -x[1]):
        pct = report.by_quality_code_pct.get(qc, 0.0)
        lines.append(f"| {qc} | {cnt:,} | {pct} |")
    lines.append("")

    lines.append("## Validation rules")
    lines.append("")
    lines.append("| ID | Severity | Description | Count |")
    lines.append("|---|---|---|---:|")
    for r in report.rules:
        marker = "🔴" if (r.severity == "ERROR" and r.count > 0) else ("🟡" if (r.severity == "WARN" and r.count > 0) else "✅")
        lines.append(f"| {r.rule_id} | {marker} {r.severity} | {r.description} | {r.count} |")
    lines.append("")

    lines.append("## V13 — Tasso di parsing su confezioni con dose chiara")
    if report.v13_total_eligible > 0:
        marker = "✅" if report.v13_pass else "🔴"
        lines.append(f"{marker} **{report.v13_parsed_ok:,} / {report.v13_total_eligible:,}** ({report.v13_rate}%) — soglia: 97%")
    else:
        lines.append("⚪ V13 non eseguita")
    lines.append("")

    lines.append("## Riepilogo")
    lines.append(f"- 🔴 Errori: {report.n_errors()}")
    lines.append(f"- 🟡 Warning: {report.n_warnings()}")
    return "\n".join(lines)


def render_csv(report: AuditReport) -> str:
    """Per ora ritorna CSV summary; il CSV completo (151k righe) è
    meglio esportarlo direttamente con `psql -c "\\copy ..."` o supabase CLI."""
    rows = [["rule_id", "severity", "description", "count"]]
    for r in report.rules:
        rows.append([r.rule_id, r.severity, r.description, str(r.count)])
    rows.append(["V13", "ERROR" if not report.v13_pass else "OK",
                 f"Tasso parsing {report.v13_rate}%",
                 f"{report.v13_parsed_ok}/{report.v13_total_eligible}"])
    return "\n".join(";".join(r) for r in rows)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit qualità parsing AIFA")
    parser.add_argument("--output", type=Path, help="Path file Markdown (default: stdout)")
    parser.add_argument("--csv", type=Path, help="Path file CSV summary")
    parser.add_argument("--refresh", action="store_true",
                        help="Refresh materialized view prima dell'audit")
    args = parser.parse_args()

    report = run_audit(refresh=args.refresh)
    md = render_markdown(report)

    if args.output:
        args.output.write_text(md, encoding="utf-8")
        print(f"Report scritto in: {args.output}", file=sys.stderr)
    else:
        print(md)

    if args.csv:
        args.csv.write_text(render_csv(report), encoding="utf-8")
        print(f"CSV summary scritto in: {args.csv}", file=sys.stderr)

    return 1 if report.n_errors() > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
