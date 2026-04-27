-- Aggiunge campo `note` opzionale a `dose_events` per memorizzare la
-- motivazione testuale che l'utente fornisce quando registra (o salta)
-- una dose dal client. Mostrata in coda alla card "fatte" come
-- "Nota · {testo}". Persistita anche per `.skipped`.
--
-- Backwards compatible: NULL di default, nessun rename, nessun cambio
-- di tipo. Le righe esistenti restano invariate.

ALTER TABLE dose_events
    ADD COLUMN IF NOT EXISTS note TEXT;

-- Documentazione inline per chi ispeziona lo schema via psql/dump.
COMMENT ON COLUMN dose_events.note IS
    'Motivazione opzionale fornita dall''utente alla conferma o allo skip. '
    'Trim lato applicativo (vuoto -> NULL). UI mostra come "Nota · {testo}".';
