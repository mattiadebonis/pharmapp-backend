-- =============================================================
-- Migration 014 — Functional trigram indexes per ricerca catalogo
-- =============================================================
-- Contesto:
--   La view `catalog_search_v1` espone `display_name = initcap(pkg.denominazione)`
--   e `generic_name = initcap(pkg.pa_associati)`. La query di ricerca
--   fa `ILIKE '%q%'` sulle colonne della view, quindi di fatto su
--   `initcap(pkg.denominazione)` e `initcap(pkg.pa_associati)`.
--
--   Gli indici GIN trigram esistenti (migration 005) sono sulle colonne
--   RAW (`pkg.denominazione`, `pkg.pa_associati`, `pkg.descrizione`).
--   Il planner non può usarli quando il predicato coinvolge `initcap(col)`
--   — funzione opaca — quindi fa sequential scan su ~159K packages.
--   Risultato: ricerca "saridon" impiega 2-3 secondi.
--
--   Creiamo indici GIN trigram FUNZIONALI su `initcap(col)` così il
--   planner può usarli per `initcap(col) ILIKE '%q%'`.
--
--   `descrizione` NON usa initcap nella view (package_label è raw), quindi
--   l'indice esistente (`idx_cat_pkg_descrizione_trgm`) è già sufficiente.
-- =============================================================

-- CREATE INDEX CONCURRENTLY non può stare in una transazione: niente BEGIN/COMMIT.
-- Se l'esecuzione fallisce a metà, droppa l'indice "INVALID" e rilancia.

-- Trigram su initcap(denominazione) per `display_name` della view.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cat_pkg_denominazione_initcap_trgm
    ON public.catalog_it_packages
    USING gin (initcap(denominazione) gin_trgm_ops);

-- Trigram su initcap(pa_associati) per `generic_name` / `principle`.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cat_pkg_pa_initcap_trgm
    ON public.catalog_it_packages
    USING gin (initcap(pa_associati) gin_trgm_ops);

-- Verifica (manuale, dopo apply):
--   EXPLAIN ANALYZE SELECT * FROM catalog_search_v1
--     WHERE country='it' AND display_name ILIKE '%saridon%' LIMIT 60;
--   Dovrebbe usare `Bitmap Index Scan on idx_cat_pkg_denominazione_initcap_trgm`.
