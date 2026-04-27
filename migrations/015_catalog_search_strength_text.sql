-- =============================================================
-- Migration 015 — catalog_search_v1 espone `strength_text`
-- =============================================================
-- Contesto:
--   Il filtro lato iOS per mostrare le confezioni coerenti con la
--   variante clinica selezionata confronta `strengthText` del search
--   result con `strengthText` del package. Senza un `strength_text`
--   esposto dalla view, il client deriva la stringa da
--   dosage_value+dosage_unit+volume ("60 MG/ML · 30 ml"), mentre il
--   package espone la stringa raw AIFA ("60 MG/ML"). Mismatch →
--   filtro svuota risultato → fallback mostra lista pool mista.
--
--   Esponiamo `pkg.strength_text` verbatim sulla view così ricerca
--   e packages condividono la stessa fonte e il filtro fa equality
--   diretta.
-- =============================================================

BEGIN;

DROP VIEW IF EXISTS public.catalog_search_v1 CASCADE;

CREATE VIEW public.catalog_search_v1
WITH (security_invoker = true) AS
SELECT
    'it'::text AS country,
    'aifa'::text AS source,
    p.cod_farmaco AS product_id,
    pkg.codice_aic AS package_id,
    p.cod_farmaco AS family_id,
    initcap(pkg.denominazione) AS display_name,
    initcap(pkg.denominazione) AS brand_name,
    initcap(pkg.pa_associati)  AS generic_name,
    initcap(pkg.pa_associati)  AS principle,
    pkg.requires_prescription,
    pkg.descrizione AS package_label,
    COALESCE(pkg.unit_count, 1) AS units_per_package,
    pkg.forma AS form_type,
    COALESCE(pkg.strength_value, 0)::int AS dosage_value,
    COALESCE(pkg.strength_unit, '') AS dosage_unit,
    pkg.strength_text AS strength_text,   -- NUOVO: canonical strength verbatim
    COALESCE(
        CASE WHEN pkg.volume_value IS NOT NULL
             THEN pkg.volume_value::text || ' ' || COALESCE(pkg.volume_unit, '')
             ELSE '' END,
        ''
    ) AS volume,
    CASE WHEN pkg.stato_amministrativo = 'Sospesa' THEN 'suspended' ELSE 'active' END AS availability,
    pkg.codice_aic AS catalog_code,
    '{}'::jsonb AS catalog_snapshot,
    p.link_fi,
    p.link_rcp,
    pkg.fornitura_code,
    pkg.codice_atc,
    p.is_homeopathic
FROM public.catalog_it_packages pkg
JOIN public.catalog_it_products p ON p.cod_farmaco = pkg.cod_farmaco
WHERE pkg.stato_amministrativo = 'Autorizzata'
  AND pkg.fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR');

REVOKE ALL ON public.catalog_search_v1 FROM PUBLIC, anon;
GRANT SELECT ON public.catalog_search_v1 TO authenticated;

COMMIT;
