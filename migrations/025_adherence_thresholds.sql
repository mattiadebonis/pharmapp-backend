-- Aggiunge campo `late_threshold_minutes` opzionale a `dosing_schedules`
-- per definire la soglia clinica oltre la quale una dose presa è
-- classificata come "ritardo" (giallo) anziché "regolare" (verde).
-- Rende la classificazione contestuale al farmaco: insulina ~5 min,
-- vitamine ~6h. NULL = usa il default applicativo (30 minuti).
--
-- Backwards compatible: NULL di default, nessun rename, nessun cambio
-- di tipo. Le righe esistenti restano invariate.

ALTER TABLE dosing_schedules
    ADD COLUMN IF NOT EXISTS late_threshold_minutes INTEGER
        CHECK (late_threshold_minutes IS NULL OR late_threshold_minutes BETWEEN 1 AND 720);

COMMENT ON COLUMN dosing_schedules.late_threshold_minutes IS
    'Minuti oltre due_at per classificare la dose come "in ritardo" (giallo). '
    'NULL → default applicativo (30 min). Range 1..720.';
