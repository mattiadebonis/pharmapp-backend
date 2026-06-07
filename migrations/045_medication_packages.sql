-- 045_medication_packages.sql
-- Scorte per dosaggio: una confezione per ogni dosaggio (strength) usato in
-- posologia. Sostituisce il singolo `supplies` come fonte di verità delle
-- scorte (la tabella `supplies` resta come aggregato legacy per i client
-- vecchi). Un farmaco con più dosaggi (es. Eutirox 10 mg + 5 mg) ha una riga
-- per ognuno; lo step "Le confezioni" del wizard iOS le crea.
--
-- strength_text : testo dosaggio grezzo AIFA (es. "5 mg") — chiave logica
--                 di match con dosing_schedules.strength_text e display.
-- strength_mg   : valore numerico in mg per unità (per match/rate); NULL se
--                 non esprimibile (gocce mg/ml).
-- units_per_box : unità contenute in 1 scatola intera (es. 28).
-- box_count     : numero di scatole possedute.
-- current_units : unità totali a magazzino (può differire da
--                 units_per_box × box_count per scatole parziali).

CREATE TABLE IF NOT EXISTS medication_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    strength_text TEXT NOT NULL DEFAULT '',
    strength_mg NUMERIC,
    forma TEXT,
    dose_format TEXT,
    units_per_box INTEGER NOT NULL DEFAULT 1,
    box_count INTEGER NOT NULL DEFAULT 1,
    current_units DOUBLE PRECISION NOT NULL DEFAULT 0,
    refill_threshold_days INTEGER NOT NULL DEFAULT 7,
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    package_label TEXT,
    catalog_package_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT medication_packages_units_per_box_positive CHECK (units_per_box >= 1),
    CONSTRAINT medication_packages_box_count_non_negative CHECK (box_count >= 0),
    CONSTRAINT medication_packages_current_units_non_negative CHECK (current_units >= 0),
    CONSTRAINT medication_packages_refill_threshold_non_negative CHECK (refill_threshold_days >= 0),
    CONSTRAINT medication_packages_strength_mg_non_negative CHECK (strength_mg IS NULL OR strength_mg >= 0)
);

-- Più confezioni per medication (una per dosaggio): indice non-unique.
CREATE INDEX IF NOT EXISTS idx_medication_packages_medication_id
    ON medication_packages(medication_id);

-- RLS: le righe ereditano l'ownership della medication via profile chain.
-- Policy per-operazione `TO authenticated`, stessa convenzione di `supplies`
-- (migration 022). Il backend usa la service_role key e bypassa comunque RLS.
ALTER TABLE medication_packages ENABLE ROW LEVEL SECURITY;

CREATE POLICY medication_packages_select ON medication_packages
    FOR SELECT TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY medication_packages_insert ON medication_packages
    FOR INSERT TO authenticated
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY medication_packages_update ON medication_packages
    FOR UPDATE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY medication_packages_delete ON medication_packages
    FOR DELETE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE medication_packages FORCE ROW LEVEL SECURITY;
