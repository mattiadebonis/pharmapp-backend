-- =============================================================
-- Migration 016 — RPC search_catalog_products_v1
-- =============================================================
-- Contesto:
--   La ricerca attuale (`/v2/catalog/search`) ritorna 1 riga per
--   *package* (codice_aic). UI ridisegnata con espansione nested
--   "farmaco → dosaggio → confezione" richiede 1 riga per
--   *prodotto* (cod_farmaco) con aggregati:
--     - variant_count = distinct (strength_text, forma) per prodotto
--     - package_count = totale packages per prodotto
--     - single_strength_text / single_forma / single_package_label /
--       single_units / single_package_id se variant_count = 1 e/o
--       package_count = 1 (per "1-tap final" UX).
--
--   Aggregazione in SQL (server-side) per evitare di fetchare
--   tutti i packages e raggruppare lato client (latenza + limit
--   problematico su brand grandi tipo Aulin/Tachipirina).
-- =============================================================

CREATE OR REPLACE FUNCTION public.search_catalog_products_v1(
    p_country text,
    p_query text,
    p_limit integer DEFAULT 30,
    p_include_homeopathic boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    pattern text := '%' || p_query || '%';
    qlower text := lower(p_query);
    result jsonb;
BEGIN
    IF p_country <> 'it' THEN
        RETURN '[]'::jsonb;
    END IF;

    WITH matched AS (
        SELECT *
        FROM public.catalog_search_v1
        WHERE country = p_country
          AND fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR')
          AND (p_include_homeopathic OR is_homeopathic = false)
          AND (
              display_name ILIKE pattern
              OR generic_name ILIKE pattern
              OR principle ILIKE pattern
              OR package_label ILIKE pattern
          )
    ),
    aggregated AS (
        SELECT
            product_id,
            MAX(display_name)   AS display_name,
            MAX(generic_name)   AS generic_name,
            MAX(principle)      AS principle,
            BOOL_OR(requires_prescription) AS requires_prescription,
            -- conteggi
            COUNT(DISTINCT (strength_text, form_type)) AS variant_count,
            COUNT(*) AS package_count,
            -- single_* compilati solo se variant_count/package_count = 1
            CASE WHEN COUNT(DISTINCT (strength_text, form_type)) = 1
                 THEN MAX(strength_text) END AS single_strength_text,
            CASE WHEN COUNT(DISTINCT (strength_text, form_type)) = 1
                 THEN MAX(form_type) END AS single_form_type,
            CASE WHEN COUNT(*) = 1 THEN MAX(package_label) END AS single_package_label,
            CASE WHEN COUNT(*) = 1 THEN MAX(units_per_package) END AS single_units,
            CASE WHEN COUNT(*) = 1 THEN MAX(package_id) END AS single_package_id,
            CASE WHEN COUNT(*) = 1 THEN MAX(catalog_code) END AS single_catalog_code,
            -- meta utili al client
            MAX(link_fi) AS link_fi,
            MAX(link_rcp) AS link_rcp,
            MAX(codice_atc) AS codice_atc,
            BOOL_OR(is_homeopathic) AS is_homeopathic
        FROM matched
        GROUP BY product_id
    ),
    ranked AS (
        SELECT
            *,
            CASE WHEN lower(display_name) LIKE qlower || '%' THEN 0 ELSE 1 END AS rank
        FROM aggregated
        ORDER BY
            CASE WHEN lower(display_name) LIKE qlower || '%' THEN 0 ELSE 1 END,
            lower(display_name)
        LIMIT p_limit
    )
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'country', 'it',
            'product_id', product_id,
            'display_name', display_name,
            'generic_name', generic_name,
            'principle', principle,
            'requires_prescription', requires_prescription,
            'variant_count', variant_count,
            'package_count', package_count,
            'single_strength_text', single_strength_text,
            'single_form_type', single_form_type,
            'single_package_label', single_package_label,
            'single_units', single_units,
            'single_package_id', single_package_id,
            'single_catalog_code', single_catalog_code,
            'link_fi', link_fi,
            'link_rcp', link_rcp,
            'codice_atc', codice_atc,
            'is_homeopathic', is_homeopathic
        )
    ), '[]'::jsonb)
    INTO result
    FROM ranked;

    RETURN result;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.search_catalog_products_v1(text, text, integer, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.search_catalog_products_v1(text, text, integer, boolean) TO authenticated;
