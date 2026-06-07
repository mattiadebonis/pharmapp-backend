-- 047_weekly_overrides_components.sql
-- Dosaggio variabile per-giorno: composizione completa. Il valore per-giorno
-- di `dosing_schedules.weekly_overrides` passa da numero (= unità) a lista di
-- componenti {units, strength_mg, strength_text}, così un giorno può combinare
-- più dosaggi (es. 1×5 mg + 1×2,5 mg).
--
-- La colonna resta jsonb (nessun cambio di tipo). Questo backfill è
-- idempotente: trasforma solo le righe che contengono ancora valori numerici
-- legacy `{"1": 1.0}` → `{"1": [{"units": 1.0, "strength_mg": <col>, ...}]}`.
-- Le righe già in formato lista vengono lasciate invariate. I reader (iOS +
-- Pydantic) tollerano comunque entrambe le shape: questo è una pulizia.

UPDATE dosing_schedules ds
SET weekly_overrides = (
    SELECT jsonb_object_agg(
        e.key,
        CASE
            WHEN jsonb_typeof(e.value) = 'number' THEN
                jsonb_build_array(
                    jsonb_strip_nulls(jsonb_build_object(
                        'units', e.value,
                        'strength_mg', to_jsonb(ds.strength_mg),
                        'strength_text', to_jsonb(ds.strength_text)
                    ))
                )
            ELSE e.value
        END
    )
    FROM jsonb_each(ds.weekly_overrides) AS e
)
WHERE ds.weekly_overrides IS NOT NULL
  AND ds.weekly_overrides <> '{}'::jsonb
  AND EXISTS (
      SELECT 1
      FROM jsonb_each(ds.weekly_overrides) AS e2
      WHERE jsonb_typeof(e2.value) = 'number'
  );
