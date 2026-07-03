-- 052: campo àncora per la ricalendarizzazione delle dosi («Sposta orario»).
-- Quando l'utente sposta una dose del giorno corrente, l'evento mantiene
-- status=pending e due_at = nuovo orario; rescheduled_from conserva lo slot
-- ORIGINALE proiettato dalla posologia. Serve a: (a) far combaciare l'evento
-- con lo slot originale lato client (niente card duplicata), (b) dedup del
-- materializer, (c) ripristino scorte in caso di skip. NULL = mai spostata.
ALTER TABLE dose_events ADD COLUMN IF NOT EXISTS rescheduled_from TIMESTAMPTZ;

COMMENT ON COLUMN dose_events.rescheduled_from IS
  'Slot originale della posologia quando l''utente ha spostato la dose (solo giorno corrente). NULL = mai spostata.';
