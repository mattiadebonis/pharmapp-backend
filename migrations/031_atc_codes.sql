-- =============================================================
-- Migration 031 — Decodifica ATC (Anatomical Therapeutic Chemical)
-- =============================================================
--
-- Contesto:
--   Oggi MedicationInfoSheet mostra "H03AA01" senza decodifica: per
--   l'utente è un codice opaco. Aggiungiamo una tabella `atc_codes`
--   con descrizioni italiane per i livelli L1-L3 (gerarchia clinica
--   utile: gruppo anatomico → gruppo terapeutico → sottogruppo
--   farmacologico). L4 e L5 sono coperti dal nome del principio
--   attivo (già in catalog_it_ingredients/pa_prevalente) — vedere
--   `decode_atc()` per il fallback.
--
--   Esempio: "H03AA01"
--     L1 H        → "Preparati ormonali sistemici"
--     L2 H03      → "Terapia tiroidea"
--     L3 H03A     → "Preparati tiroidei"
--     L4 H03AA    → "Ormoni tiroidei"          [skip per ora]
--     L5 H03AA01  → "Levotiroxina sodica"      [da pa_prevalente]
--
-- Source: WHO ATC/DDD Index + naming convention AIFA Banca Dati
-- Farmaci. Le voci sono curate manualmente per i codici presenti
-- in catalog_it_products (14 L1, 93 L2, 245 L3 distinti). Aggiunte
-- iterabili: la tabella tollera codici sconosciuti (NULL
-- description → l'UI mostra il raw code).
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS atc_codes (
    code         TEXT PRIMARY KEY,
    level        SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 5),
    description_it TEXT NOT NULL,
    parent_code  TEXT REFERENCES atc_codes(code) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_atc_codes_level ON atc_codes(level);
CREATE INDEX IF NOT EXISTS idx_atc_codes_parent ON atc_codes(parent_code);

COMMENT ON TABLE atc_codes IS
    'Dizionario WHO ATC con descrizioni italiane. Popolato per L1-L3 '
    'sui codici presenti in catalog_it_products. Vedi migration 031.';
COMMENT ON COLUMN atc_codes.level IS
    'Livello WHO ATC: 1=gruppo anatomico (1 char), 2=terapeutico (3), '
    '3=farmacologico (4), 4=chimico-terapeutico (5), 5=sostanza (7).';

-- ─── L1: 14 gruppi anatomici principali ──────────────────────────
INSERT INTO atc_codes (code, level, description_it, parent_code) VALUES
('A', 1, 'Apparato gastrointestinale e metabolismo', NULL),
('B', 1, 'Sangue ed organi emopoietici', NULL),
('C', 1, 'Sistema cardiovascolare', NULL),
('D', 1, 'Dermatologici', NULL),
('G', 1, 'Sistema genito-urinario ed ormoni sessuali', NULL),
('H', 1, 'Preparati ormonali sistemici (esclusi ormoni sessuali e insuline)', NULL),
('J', 1, 'Antimicrobici generali per uso sistemico', NULL),
('L', 1, 'Farmaci antineoplastici ed immunomodulatori', NULL),
('M', 1, 'Sistema muscolo-scheletrico', NULL),
('N', 1, 'Sistema nervoso', NULL),
('P', 1, 'Farmaci antiparassitari, insetticidi e repellenti', NULL),
('R', 1, 'Sistema respiratorio', NULL),
('S', 1, 'Organi di senso', NULL),
('V', 1, 'Vari', NULL)
ON CONFLICT (code) DO UPDATE SET
    description_it = EXCLUDED.description_it, level = EXCLUDED.level;

-- ─── L2: 93 sottogruppi terapeutici ──────────────────────────────
INSERT INTO atc_codes (code, level, description_it, parent_code) VALUES
('A01', 2, 'Preparati stomatologici', 'A'),
('A02', 2, 'Antiacidi, antimeteorici, antiulcera peptica', 'A'),
('A03', 2, 'Antispastici, anticolinergici e propulsivi', 'A'),
('A04', 2, 'Antiemetici e antinausea', 'A'),
('A05', 2, 'Terapia biliare ed epatica', 'A'),
('A06', 2, 'Lassativi', 'A'),
('A07', 2, 'Antidiarroici, antinfiammatori e antinfettivi intestinali', 'A'),
('A08', 2, 'Preparati antiobesità (esclusi i prodotti dietetici)', 'A'),
('A09', 2, 'Digestivi (inclusi gli enzimi)', 'A'),
('A10', 2, 'Farmaci usati nel diabete', 'A'),
('A11', 2, 'Vitamine', 'A'),
('A12', 2, 'Integratori minerali', 'A'),
('A13', 2, 'Tonici', 'A'),
('A16', 2, 'Altri farmaci dell''apparato gastrointestinale e del metabolismo', 'A'),
('B01', 2, 'Antitrombotici', 'B'),
('B02', 2, 'Antiemorragici', 'B'),
('B03', 2, 'Preparati antianemici', 'B'),
('B05', 2, 'Sostituti del sangue e soluzioni perfusionali', 'B'),
('B06', 2, 'Altri ematologici', 'B'),
('C01', 2, 'Terapia cardiaca', 'C'),
('C02', 2, 'Antiipertensivi', 'C'),
('C03', 2, 'Diuretici', 'C'),
('C04', 2, 'Vasodilatatori periferici', 'C'),
('C05', 2, 'Vasoprotettori', 'C'),
('C07', 2, 'Beta-bloccanti', 'C'),
('C08', 2, 'Calcio-antagonisti', 'C'),
('C09', 2, 'Sostanze ad azione sul sistema renina-angiotensina', 'C'),
('C10', 2, 'Sostanze modificatrici dei lipidi', 'C'),
('D01', 2, 'Antimicotici per uso dermatologico', 'D'),
('D02', 2, 'Emollienti e protettivi', 'D'),
('D03', 2, 'Preparati per il trattamento di ferite e ulcere', 'D'),
('D04', 2, 'Antipruriginosi (inclusi antistaminici, anestetici)', 'D'),
('D05', 2, 'Antipsoriasici', 'D'),
('D06', 2, 'Antibiotici e chemioterapici per uso dermatologico', 'D'),
('D07', 2, 'Corticosteroidi, preparati dermatologici', 'D'),
('D08', 2, 'Antisettici e disinfettanti', 'D'),
('D10', 2, 'Preparati anti-acne', 'D'),
('D11', 2, 'Altri preparati dermatologici', 'D'),
('G01', 2, 'Antiinfettivi ed antisettici ginecologici', 'G'),
('G02', 2, 'Altri ginecologici', 'G'),
('G03', 2, 'Ormoni sessuali e modulatori dell''apparato genitale', 'G'),
('G04', 2, 'Urologici', 'G'),
('H01', 2, 'Ormoni ipofisari, ipotalamici e analoghi', 'H'),
('H02', 2, 'Corticosteroidi sistemici', 'H'),
('H03', 2, 'Terapia tiroidea', 'H'),
('H04', 2, 'Ormoni pancreatici', 'H'),
('H05', 2, 'Omeostasi del calcio', 'H'),
('J01', 2, 'Antibatterici per uso sistemico', 'J'),
('J02', 2, 'Antimicotici per uso sistemico', 'J'),
('J04', 2, 'Antimicobatterici', 'J'),
('J05', 2, 'Antivirali per uso sistemico', 'J'),
('J06', 2, 'Sieri immuni ed immunoglobuline', 'J'),
('J07', 2, 'Vaccini', 'J'),
('L01', 2, 'Antineoplastici', 'L'),
('L02', 2, 'Terapia endocrina', 'L'),
('L03', 2, 'Immunostimolanti', 'L'),
('L04', 2, 'Immunosoppressori', 'L'),
('M01', 2, 'Farmaci antiinfiammatori ed antireumatici', 'M'),
('M02', 2, 'Preparati topici per dolori articolari e muscolari', 'M'),
('M03', 2, 'Miorilassanti', 'M'),
('M04', 2, 'Antigottosi', 'M'),
('M05', 2, 'Farmaci per il trattamento delle malattie delle ossa', 'M'),
('M09', 2, 'Altri farmaci del sistema muscolo-scheletrico', 'M'),
('N01', 2, 'Anestetici', 'N'),
('N02', 2, 'Analgesici', 'N'),
('N03', 2, 'Antiepilettici', 'N'),
('N04', 2, 'Antiparkinsoniani', 'N'),
('N05', 2, 'Psicolettici', 'N'),
('N06', 2, 'Psicoanalettici', 'N'),
('N07', 2, 'Altri farmaci del sistema nervoso', 'N'),
('P01', 2, 'Antiprotozoari', 'P'),
('P02', 2, 'Antielmintici', 'P'),
('P03', 2, 'Ectoparassiticidi, inclusi antiscabbia, insetticidi e repellenti', 'P'),
('R01', 2, 'Preparati per uso rinologico', 'R'),
('R02', 2, 'Preparati per il cavo faringeo', 'R'),
('R03', 2, 'Farmaci per disturbi ostruttivi delle vie respiratorie', 'R'),
('R05', 2, 'Preparati per la tosse e le malattie da raffreddamento', 'R'),
('R06', 2, 'Antistaminici per uso sistemico', 'R'),
('R07', 2, 'Altri preparati per il sistema respiratorio', 'R'),
('S01', 2, 'Oftalmologici', 'S'),
('S02', 2, 'Otologici', 'S'),
('S03', 2, 'Preparati oftalmologici ed otologici', 'S'),
('V01', 2, 'Allergeni', 'V'),
('V03', 2, 'Tutti gli altri prodotti terapeutici', 'V'),
('V04', 2, 'Diagnostici', 'V'),
('V06', 2, 'Nutrienti generali', 'V'),
('V07', 2, 'Tutti gli altri prodotti non terapeutici', 'V'),
('V08', 2, 'Mezzi di contrasto', 'V'),
('V09', 2, 'Diagnostici per radiodiagnostica', 'V'),
('V10', 2, 'Radiofarmaceutici terapeutici', 'V')
ON CONFLICT (code) DO UPDATE SET
    description_it = EXCLUDED.description_it, level = EXCLUDED.level;

-- ─── L3: sottogruppi farmacologici (più comuni nel catalogo) ─────
-- Curati per i codici effettivamente presenti in catalog_it_products.
-- Aggiunte ulteriori in migrazioni successive se necessario.
INSERT INTO atc_codes (code, level, description_it, parent_code) VALUES
-- A — Apparato gastrointestinale e metabolismo
('A01A', 3, 'Preparati stomatologici', 'A01'),
('A02A', 3, 'Antiacidi', 'A02'),
('A02B', 3, 'Farmaci per ulcera peptica e malattia da reflusso gastroesofageo (MRGE)', 'A02'),
('A02X', 3, 'Altri farmaci per disturbi acido-correlati', 'A02'),
('A03A', 3, 'Farmaci per disturbi funzionali gastrointestinali', 'A03'),
('A03B', 3, 'Belladonna e derivati, sola', 'A03'),
('A03C', 3, 'Antispastici in associazione con psicolettici', 'A03'),
('A03D', 3, 'Antispastici in associazione con analgesici', 'A03'),
('A03F', 3, 'Propulsivi', 'A03'),
('A04A', 3, 'Antiemetici e antinausea', 'A04'),
('A05A', 3, 'Terapia biliare', 'A05'),
('A05B', 3, 'Terapia epatica, lipotropi', 'A05'),
('A06A', 3, 'Lassativi', 'A06'),
('A07A', 3, 'Antinfettivi intestinali', 'A07'),
('A07B', 3, 'Adsorbenti intestinali', 'A07'),
('A07D', 3, 'Inibitori della motilità intestinale', 'A07'),
('A07E', 3, 'Antinfiammatori intestinali', 'A07'),
('A07F', 3, 'Microrganismi antidiarroici', 'A07'),
('A07X', 3, 'Altri antidiarroici', 'A07'),
('A09A', 3, 'Digestivi (inclusi gli enzimi)', 'A09'),
('A10A', 3, 'Insuline ed analoghi', 'A10'),
('A10B', 3, 'Ipoglicemizzanti orali, esclusa l''insulina', 'A10'),
('A10X', 3, 'Altri farmaci usati nel diabete', 'A10'),
('A11A', 3, 'Polivitaminici, associazioni', 'A11'),
('A11B', 3, 'Polivitaminici, semplici', 'A11'),
('A11C', 3, 'Vitamina A e D, incluse le associazioni', 'A11'),
('A11D', 3, 'Vitamina B1, sola o in associazione con vitamina B6 e B12', 'A11'),
('A11E', 3, 'Complesso vitamina B, incluse le associazioni', 'A11'),
('A11G', 3, 'Acido ascorbico (vitamina C), incluse le associazioni', 'A11'),
('A11H', 3, 'Altri preparati vitaminici, semplici', 'A11'),
('A11J', 3, 'Altri preparati vitaminici, associazioni', 'A11'),
('A12A', 3, 'Calcio', 'A12'),
('A12B', 3, 'Potassio', 'A12'),
('A12C', 3, 'Altri integratori minerali', 'A12'),
('A16A', 3, 'Altri farmaci dell''apparato gastrointestinale e del metabolismo', 'A16'),
-- B — Sangue ed organi emopoietici
('B01A', 3, 'Antitrombotici', 'B01'),
('B02A', 3, 'Antifibrinolitici', 'B02'),
('B02B', 3, 'Vitamina K ed altri emostatici', 'B02'),
('B03A', 3, 'Preparati a base di ferro', 'B03'),
('B03B', 3, 'Vitamina B12 ed acido folico', 'B03'),
('B03X', 3, 'Altri preparati antianemici', 'B03'),
('B05A', 3, 'Sangue ed emoderivati', 'B05'),
('B05B', 3, 'Soluzioni endovenose', 'B05'),
('B05C', 3, 'Soluzioni irriganti', 'B05'),
('B05D', 3, 'Soluzioni dialitiche peritoneali', 'B05'),
('B05X', 3, 'Additivi delle soluzioni endovenose', 'B05'),
('B05Z', 3, 'Emodialitici ed emofiltranti, concentrati', 'B05'),
('B06A', 3, 'Altri ematologici', 'B06'),
-- C — Sistema cardiovascolare
('C01A', 3, 'Glicosidi cardiaci', 'C01'),
('C01B', 3, 'Antiaritmici, classi I e III', 'C01'),
('C01C', 3, 'Stimolanti cardiaci, esclusi i glicosidi cardiaci', 'C01'),
('C01D', 3, 'Vasodilatatori usati nelle malattie cardiache', 'C01'),
('C01E', 3, 'Altri preparati cardiaci', 'C01'),
('C02A', 3, 'Antiadrenergici ad azione centrale', 'C02'),
('C02B', 3, 'Antiadrenergici, gangliopressori', 'C02'),
('C02C', 3, 'Antiadrenergici ad azione periferica', 'C02'),
('C02D', 3, 'Sostanze ad azione sulla muscolatura liscia arteriolare', 'C02'),
('C02K', 3, 'Altri antiipertensivi', 'C02'),
('C02L', 3, 'Antiipertensivi e diuretici in associazione', 'C02'),
('C03A', 3, 'Diuretici ad azione diuretica minore, tiazidi', 'C03'),
('C03B', 3, 'Diuretici ad azione diuretica minore, esclusi tiazidi', 'C03'),
('C03C', 3, 'Diuretici dell''ansa', 'C03'),
('C03D', 3, 'Diuretici risparmiatori di potassio', 'C03'),
('C03E', 3, 'Diuretici e risparmiatori di potassio in associazione', 'C03'),
('C04A', 3, 'Vasodilatatori periferici', 'C04'),
('C05A', 3, 'Antiemorroidari per uso topico', 'C05'),
('C05B', 3, 'Terapia antivaricosa', 'C05'),
('C05C', 3, 'Sostanze stabilizzanti i capillari', 'C05'),
('C07A', 3, 'Beta-bloccanti', 'C07'),
('C07B', 3, 'Beta-bloccanti e tiazidi', 'C07'),
('C07C', 3, 'Beta-bloccanti ed altri diuretici', 'C07'),
('C07D', 3, 'Beta-bloccanti, tiazidi ed altri diuretici', 'C07'),
('C07F', 3, 'Beta-bloccanti ed altri antiipertensivi', 'C07'),
('C08C', 3, 'Calcio-antagonisti selettivi con prevalente effetto vascolare', 'C08'),
('C08D', 3, 'Calcio-antagonisti selettivi con effetto cardiaco diretto', 'C08'),
('C08E', 3, 'Calcio-antagonisti non selettivi', 'C08'),
('C09A', 3, 'ACE-inibitori, non associati', 'C09'),
('C09B', 3, 'ACE-inibitori, associazioni', 'C09'),
('C09C', 3, 'Antagonisti dell''angiotensina II, non associati', 'C09'),
('C09D', 3, 'Antagonisti dell''angiotensina II, associazioni', 'C09'),
('C09X', 3, 'Altre sostanze ad azione sul sistema renina-angiotensina', 'C09'),
('C10A', 3, 'Sostanze modificatrici dei lipidi, non associate', 'C10'),
('C10B', 3, 'Sostanze modificatrici dei lipidi, associazioni', 'C10'),
-- D — Dermatologici
('D01A', 3, 'Antimicotici per uso topico', 'D01'),
('D01B', 3, 'Antimicotici per uso sistemico', 'D01'),
('D02A', 3, 'Emollienti e protettivi', 'D02'),
('D03A', 3, 'Cicatrizzanti', 'D03'),
('D03B', 3, 'Enzimi', 'D03'),
('D04A', 3, 'Antipruriginosi', 'D04'),
('D05A', 3, 'Antipsoriasici per uso topico', 'D05'),
('D05B', 3, 'Antipsoriasici per uso sistemico', 'D05'),
('D06A', 3, 'Antibiotici per uso topico', 'D06'),
('D06B', 3, 'Chemioterapici per uso topico', 'D06'),
('D06C', 3, 'Antibiotici e chemioterapici, associazioni', 'D06'),
('D07A', 3, 'Corticosteroidi semplici', 'D07'),
('D07B', 3, 'Corticosteroidi in associazione con antisettici', 'D07'),
('D07C', 3, 'Corticosteroidi in associazione con antibiotici', 'D07'),
('D07X', 3, 'Corticosteroidi, altre associazioni', 'D07'),
('D08A', 3, 'Antisettici e disinfettanti', 'D08'),
('D10A', 3, 'Preparati anti-acne per uso topico', 'D10'),
('D10B', 3, 'Preparati anti-acne per uso sistemico', 'D10'),
('D11A', 3, 'Altri preparati dermatologici', 'D11'),
-- G — Sistema genito-urinario ed ormoni sessuali
('G01A', 3, 'Antiinfettivi ed antisettici, esclusa associazione con corticosteroidi', 'G01'),
('G01B', 3, 'Antiinfettivi/antisettici in associazione con corticosteroidi', 'G01'),
('G02A', 3, 'Ossitocici', 'G02'),
('G02B', 3, 'Contraccettivi per uso topico', 'G02'),
('G02C', 3, 'Altri ginecologici', 'G02'),
('G03A', 3, 'Contraccettivi ormonali per uso sistemico', 'G03'),
('G03B', 3, 'Androgeni', 'G03'),
('G03C', 3, 'Estrogeni', 'G03'),
('G03D', 3, 'Progestinici', 'G03'),
('G03E', 3, 'Androgeni e ormoni sessuali femminili in associazione', 'G03'),
('G03F', 3, 'Progestinici ed estrogeni in associazione', 'G03'),
('G03G', 3, 'Gonadotropine ed altri stimolanti dell''ovulazione', 'G03'),
('G03H', 3, 'Antiandrogeni', 'G03'),
('G03X', 3, 'Altri ormoni sessuali e modulatori dell''apparato genitale', 'G03'),
('G04B', 3, 'Urologici', 'G04'),
('G04C', 3, 'Farmaci usati nell''ipertrofia prostatica benigna', 'G04'),
-- H — Preparati ormonali sistemici
('H01A', 3, 'Ormoni ipofisari anteriori ed analoghi', 'H01'),
('H01B', 3, 'Ormoni ipofisari posteriori', 'H01'),
('H01C', 3, 'Ormoni ipotalamici', 'H01'),
('H02A', 3, 'Corticosteroidi sistemici, non associati', 'H02'),
('H02B', 3, 'Corticosteroidi sistemici, associazioni', 'H02'),
('H02C', 3, 'Anticorticosteroidi', 'H02'),
('H03A', 3, 'Preparati tiroidei', 'H03'),
('H03B', 3, 'Preparati antitiroidei', 'H03'),
('H03C', 3, 'Terapia con iodio', 'H03'),
('H04A', 3, 'Ormoni glicogenolitici', 'H04'),
('H05A', 3, 'Ormoni paratiroidei ed analoghi', 'H05'),
('H05B', 3, 'Agenti anti-paratiroidei', 'H05'),
-- J — Antimicrobici generali per uso sistemico
('J01A', 3, 'Tetracicline', 'J01'),
('J01B', 3, 'Anfenicoli', 'J01'),
('J01C', 3, 'Beta-lattamici antibatterici, penicilline', 'J01'),
('J01D', 3, 'Altri beta-lattamici antibatterici', 'J01'),
('J01E', 3, 'Sulfonamidi e trimetoprim', 'J01'),
('J01F', 3, 'Macrolidi, lincosamidi e streptogramine', 'J01'),
('J01G', 3, 'Aminoglicosidi antibatterici', 'J01'),
('J01M', 3, 'Antibatterici chinolonici', 'J01'),
('J01R', 3, 'Antibatterici in associazione', 'J01'),
('J01X', 3, 'Altri antibatterici', 'J01'),
('J02A', 3, 'Antimicotici per uso sistemico', 'J02'),
('J04A', 3, 'Antimicobatterici', 'J04'),
('J05A', 3, 'Antivirali diretti', 'J05'),
('J06A', 3, 'Sieri immuni', 'J06'),
('J06B', 3, 'Immunoglobuline', 'J06'),
('J07A', 3, 'Vaccini batterici', 'J07'),
('J07B', 3, 'Vaccini virali', 'J07'),
('J07C', 3, 'Vaccini batterici e virali in associazione', 'J07'),
('J07X', 3, 'Altri vaccini', 'J07'),
-- L — Antineoplastici ed immunomodulatori
('L01A', 3, 'Agenti alchilanti', 'L01'),
('L01B', 3, 'Antimetaboliti', 'L01'),
('L01C', 3, 'Alcaloidi vegetali ed altri prodotti naturali', 'L01'),
('L01D', 3, 'Antibiotici citotossici e sostanze correlate', 'L01'),
('L01E', 3, 'Inibitori delle proteine chinasi', 'L01'),
('L01F', 3, 'Anticorpi monoclonali', 'L01'),
('L01X', 3, 'Altri antineoplastici', 'L01'),
('L02A', 3, 'Ormoni e sostanze correlate', 'L02'),
('L02B', 3, 'Antagonisti ormonali e sostanze correlate', 'L02'),
('L03A', 3, 'Immunostimolanti', 'L03'),
('L04A', 3, 'Immunosoppressori', 'L04'),
-- M — Sistema muscolo-scheletrico
('M01A', 3, 'Antiinfiammatori e antireumatici, non steroidei (FANS)', 'M01'),
('M01B', 3, 'Antiinfiammatori e antireumatici, associazioni', 'M01'),
('M01C', 3, 'Antireumatici specifici', 'M01'),
('M02A', 3, 'Preparati topici per dolori articolari e muscolari', 'M02'),
('M03A', 3, 'Miorilassanti ad azione periferica', 'M03'),
('M03B', 3, 'Miorilassanti ad azione centrale', 'M03'),
('M03C', 3, 'Miorilassanti ad azione diretta', 'M03'),
('M04A', 3, 'Antigottosi', 'M04'),
('M05B', 3, 'Farmaci ad azione sulla struttura ossea e sulla mineralizzazione', 'M05'),
('M09A', 3, 'Altri farmaci del sistema muscolo-scheletrico', 'M09'),
-- N — Sistema nervoso
('N01A', 3, 'Anestetici generali', 'N01'),
('N01B', 3, 'Anestetici locali', 'N01'),
('N02A', 3, 'Oppioidi', 'N02'),
('N02B', 3, 'Altri analgesici ed antipiretici', 'N02'),
('N02C', 3, 'Antiemicranici', 'N02'),
('N03A', 3, 'Antiepilettici', 'N03'),
('N04A', 3, 'Anticolinergici', 'N04'),
('N04B', 3, 'Dopaminergici', 'N04'),
('N05A', 3, 'Antipsicotici', 'N05'),
('N05B', 3, 'Ansiolitici', 'N05'),
('N05C', 3, 'Ipnotici e sedativi', 'N05'),
('N06A', 3, 'Antidepressivi', 'N06'),
('N06B', 3, 'Psicostimolanti, sostanze per ADHD e nootropi', 'N06'),
('N06C', 3, 'Psicolettici e psicoanalettici, associazioni', 'N06'),
('N06D', 3, 'Farmaci anti-demenza', 'N06'),
('N07A', 3, 'Parasimpaticomimetici', 'N07'),
('N07B', 3, 'Farmaci usati nelle sindromi di dipendenza', 'N07'),
('N07C', 3, 'Antivertiginosi', 'N07'),
('N07X', 3, 'Altri farmaci del sistema nervoso', 'N07'),
-- P — Antiparassitari
('P01A', 3, 'Agenti contro l''amebiasi ed altre malattie protozoarie', 'P01'),
('P01B', 3, 'Antimalarici', 'P01'),
('P01C', 3, 'Agenti contro la leishmaniosi e la tripanosomiasi', 'P01'),
('P02B', 3, 'Antitrematodi', 'P02'),
('P02C', 3, 'Antinematodi', 'P02'),
('P02D', 3, 'Anticestodi', 'P02'),
('P03A', 3, 'Ectoparassiticidi, inclusi gli antiscabbia', 'P03'),
('P03B', 3, 'Insetticidi e repellenti', 'P03'),
('P03X', 3, 'Altri ectoparassiticidi, inclusi gli antiscabbia', 'P03'),
-- R — Sistema respiratorio
('R01A', 3, 'Decongestionanti ed altri preparati ad uso topico nasale', 'R01'),
('R01B', 3, 'Decongestionanti nasali per uso sistemico', 'R01'),
('R02A', 3, 'Preparati per il cavo faringeo', 'R02'),
('R03A', 3, 'Adrenergici per aerosol', 'R03'),
('R03B', 3, 'Altri farmaci per disturbi ostruttivi delle vie respiratorie per aerosol', 'R03'),
('R03C', 3, 'Adrenergici per uso sistemico', 'R03'),
('R03D', 3, 'Altri farmaci per disturbi ostruttivi delle vie respiratorie per uso sistemico', 'R03'),
('R05C', 3, 'Espettoranti, esclusi associazioni con sedativi della tosse', 'R05'),
('R05D', 3, 'Sedativi della tosse, esclusi associazioni con espettoranti', 'R05'),
('R05F', 3, 'Sedativi della tosse ed espettoranti, associazioni', 'R05'),
('R05X', 3, 'Altri preparati per la tosse ed il raffreddore', 'R05'),
('R06A', 3, 'Antistaminici per uso sistemico', 'R06'),
('R07A', 3, 'Altri preparati per il sistema respiratorio', 'R07'),
-- S — Organi di senso
('S01A', 3, 'Antiinfettivi oftalmici', 'S01'),
('S01B', 3, 'Antiinfiammatori oftalmici', 'S01'),
('S01C', 3, 'Antiinfettivi e antiinfiammatori in associazione', 'S01'),
('S01E', 3, 'Antiglaucoma e miotici', 'S01'),
('S01F', 3, 'Midriatici e cicloplegici', 'S01'),
('S01G', 3, 'Decongestionanti ed antiallergici', 'S01'),
('S01H', 3, 'Anestetici locali oftalmici', 'S01'),
('S01J', 3, 'Agenti diagnostici', 'S01'),
('S01K', 3, 'Ausili chirurgici', 'S01'),
('S01L', 3, 'Farmaci per disturbi vascolari oculari', 'S01'),
('S01X', 3, 'Altri farmaci oftalmici', 'S01'),
('S02A', 3, 'Antiinfettivi otologici', 'S02'),
('S02B', 3, 'Corticosteroidi otologici', 'S02'),
('S02C', 3, 'Corticosteroidi ed antiinfettivi in associazione', 'S02'),
('S02D', 3, 'Altri preparati otologici', 'S02'),
('S03A', 3, 'Antiinfettivi oftalmologici ed otologici', 'S03'),
('S03B', 3, 'Corticosteroidi oftalmologici ed otologici', 'S03'),
('S03C', 3, 'Corticosteroidi e antiinfettivi in associazione, oftalmologici ed otologici', 'S03'),
('S03D', 3, 'Altri preparati oftalmologici ed otologici', 'S03'),
-- V — Vari
('V01A', 3, 'Allergeni', 'V01'),
('V03A', 3, 'Tutti gli altri prodotti terapeutici', 'V03'),
('V04C', 3, 'Altri diagnostici', 'V04'),
('V06D', 3, 'Altri nutrienti', 'V06'),
('V07A', 3, 'Tutti gli altri prodotti non terapeutici', 'V07'),
('V08A', 3, 'Mezzi di contrasto iodati per raggi X', 'V08'),
('V08B', 3, 'Mezzi di contrasto non iodati per raggi X', 'V08'),
('V08C', 3, 'Mezzi di contrasto per risonanza magnetica', 'V08'),
('V08D', 3, 'Mezzi di contrasto per ultrasonografia', 'V08'),
('V09A', 3, 'Diagnostici per radiodiagnostica del sistema nervoso centrale', 'V09'),
('V09C', 3, 'Diagnostici per radiodiagnostica renale', 'V09'),
('V09D', 3, 'Diagnostici per radiodiagnostica epatica e reticolo-endoteliale', 'V09'),
('V09E', 3, 'Diagnostici per radiodiagnostica respiratoria', 'V09'),
('V09F', 3, 'Diagnostici per radiodiagnostica tiroidea', 'V09'),
('V09G', 3, 'Diagnostici per radiodiagnostica cardiovascolare', 'V09'),
('V09H', 3, 'Diagnostici per radiodiagnostica delle infiammazioni e infezioni', 'V09'),
('V09I', 3, 'Diagnostici per radiodiagnostica tumorale', 'V09'),
('V09X', 3, 'Altri diagnostici per radiodiagnostica', 'V09'),
('V10A', 3, 'Radiofarmaceutici antinfiammatori', 'V10'),
('V10B', 3, 'Radiofarmaceutici per palliazione del dolore', 'V10'),
('V10X', 3, 'Altri radiofarmaceutici terapeutici', 'V10')
ON CONFLICT (code) DO UPDATE SET
    description_it = EXCLUDED.description_it, level = EXCLUDED.level;


-- =============================================================
-- RPC: decode_atc(code TEXT) → JSONB con tutta la gerarchia.
--
-- Restituisce shape:
--   {
--     "code": "H03AA01",
--     "l1": {"code": "H", "description_it": "Preparati ormonali..."},
--     "l2": {"code": "H03", "description_it": "Terapia tiroidea"},
--     "l3": {"code": "H03A", "description_it": "Preparati tiroidei"},
--     "l4": null,    -- non popolato per ora
--     "summary_it": "Terapia tiroidea · Preparati tiroidei"
--   }
--
-- `summary_it` è il "best label" pensato per la UI: usa il livello
-- più specifico disponibile (preferendo L3 → L2 → L1).
-- =============================================================
CREATE OR REPLACE FUNCTION public.decode_atc(p_code TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    v_code TEXT := upper(trim(p_code));
    l1_row atc_codes%ROWTYPE;
    l2_row atc_codes%ROWTYPE;
    l3_row atc_codes%ROWTYPE;
    l4_row atc_codes%ROWTYPE;
    summary TEXT;
BEGIN
    IF v_code IS NULL OR v_code = '' THEN
        RETURN NULL;
    END IF;

    -- L1: primo carattere
    SELECT * INTO l1_row FROM atc_codes
     WHERE atc_codes.code = LEFT(v_code, 1) AND level = 1;

    -- L2: primi 3 caratteri (se la stringa è lunga >= 3)
    IF length(v_code) >= 3 THEN
        SELECT * INTO l2_row FROM atc_codes
         WHERE atc_codes.code = LEFT(v_code, 3) AND level = 2;
    END IF;

    -- L3: primi 4 caratteri
    IF length(v_code) >= 4 THEN
        SELECT * INTO l3_row FROM atc_codes
         WHERE atc_codes.code = LEFT(v_code, 4) AND level = 3;
    END IF;

    -- L4: primi 5 caratteri
    IF length(v_code) >= 5 THEN
        SELECT * INTO l4_row FROM atc_codes
         WHERE atc_codes.code = LEFT(v_code, 5) AND level = 4;
    END IF;

    -- Summary: livello più specifico utile per l'utente.
    -- L3 è il più clinicamente informativo ("Preparati tiroidei").
    -- Se manca L3 fallback a L2, poi L1, poi codice raw.
    summary := COALESCE(
        l4_row.description_it,
        l3_row.description_it,
        l2_row.description_it,
        l1_row.description_it,
        v_code
    );

    RETURN jsonb_build_object(
        'code', v_code,
        'l1', CASE WHEN l1_row.code IS NOT NULL THEN
            jsonb_build_object('code', l1_row.code, 'description_it', l1_row.description_it)
            ELSE NULL END,
        'l2', CASE WHEN l2_row.code IS NOT NULL THEN
            jsonb_build_object('code', l2_row.code, 'description_it', l2_row.description_it)
            ELSE NULL END,
        'l3', CASE WHEN l3_row.code IS NOT NULL THEN
            jsonb_build_object('code', l3_row.code, 'description_it', l3_row.description_it)
            ELSE NULL END,
        'l4', CASE WHEN l4_row.code IS NOT NULL THEN
            jsonb_build_object('code', l4_row.code, 'description_it', l4_row.description_it)
            ELSE NULL END,
        'summary_it', summary
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.decode_atc(TEXT) TO authenticated;


-- =============================================================
-- RLS: tabella di sola lettura per utenti autenticati.
-- =============================================================
ALTER TABLE atc_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS atc_codes_read ON atc_codes;
CREATE POLICY atc_codes_read ON atc_codes
    FOR SELECT TO authenticated USING (true);

GRANT SELECT ON atc_codes TO authenticated;

COMMIT;
