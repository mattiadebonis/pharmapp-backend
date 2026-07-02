-- Migration 051: aggiungere colonna `doctors.principal_channel TEXT`.
--
-- Motivazione: il redesign della card Rifornimento (tab Oggi, iOS) mostra UN
-- solo link canale per medico — quello "principale" configurato dall'utente
-- nelle impostazioni del medico. Il modello iOS `Doctor` ora persiste
-- `principalChannel` con i valori dell'enum `PrescriptionRequestChannel`
-- (`whatsapp` | `mail` | `copy` | `chiama`).
--
-- È un campo distinto da `preferenza_canale` (Literal telefono/whatsapp/email)
-- preesistente e mai usato dal client: i value-set non coincidono (qui serve
-- `mail`/`copy`, assenti là) e la semantica è specifica della card di
-- rifornimento. Nullable: i medici esistenti restano senza canale esplicito e
-- il client applica il fallback deterministico (mail → WhatsApp → copia).
--
-- Per `extra="forbid"` su `PharmaBaseModel`, questa migration DEVE essere
-- applicata prima del deploy del backend che accetta `principal_channel`,
-- altrimenti la upsert/update del medico fallirebbe sul DB.

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS principal_channel TEXT;
