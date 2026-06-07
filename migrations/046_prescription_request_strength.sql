-- 046_prescription_request_strength.sql
-- Richiesta ricetta per-dosaggio: con i farmaci multi-dosaggio
-- (`medication_packages`) una richiesta può riferirsi a uno specifico
-- dosaggio (es. "10 mg") invece che all'intero farmaco. `strength_text`
-- è il testo dosaggio grezzo AIFA, NULL = richiesta a livello di farmaco
-- (legacy / dosaggio unico). Nessun vincolo: solo display + matching col
-- corrispondente `medication_packages.strength_text`.

ALTER TABLE prescription_requests
    ADD COLUMN IF NOT EXISTS strength_text text;
