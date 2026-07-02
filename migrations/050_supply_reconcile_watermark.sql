-- 050: watermark di riconciliazione scorte.
--
-- `supply_reconciled_at` è l'istante fino al quale gli slot di terapia del
-- farmaco sono già stati "consumati" dalle confezioni (medication_packages).
-- Il client iOS avanza il watermark ogni volta che riconcilia: ogni slot con
-- due_at <= watermark è già regolato (scalato, o esplicitamente non scalato
-- perché la dose è stata segnata come saltata).
--
-- Per-farmaco e non per-confezione: uno slot multi-componente (weekly
-- overrides con più dosaggi) scala più confezioni atomicamente.
--
-- Backfill a now(): gli utenti esistenti non devono retro-consumare mesi di
-- terapia al primo avvio del client nuovo — il conteggio riparte da adesso.
ALTER TABLE medications ADD COLUMN IF NOT EXISTS supply_reconciled_at TIMESTAMPTZ;

UPDATE medications SET supply_reconciled_at = now() WHERE supply_reconciled_at IS NULL;
