# Prompt: Audit completo parsing AIFA tramite AI

> Da copia-incollare ad un'AI generalista con accesso a `WebSearch` + 
> `Read`/`Write` di file. Pensato per Claude Sonnet 4.5+ o GPT-4 class.
> 
> Allega al messaggio:
> 1. `pharmapp-backend/confezioni_fornitura.csv` (~1.4 MB, 158k righe — input)
> 2. `pharmapp-backend/scripts/parsers/aifa_package_parser.py` (parser corrente)
> 3. (opzionale) ultimo output di `SELECT audit_get_report()` come baseline
> 
> Il prompt qui sotto chiede output specifico: un file Python eseguibile +
> un report Markdown con le decisioni motivate.

---

## RUOLO

Sei un consulente esperto in parsing testuale strutturato + farmacologia AIFA italiana. Conosci:
- Le notazioni AIFA standard (`DESCRIZIONE` packaging), incluse le forme dispensative italiane (Compresse, Capsule, Bustine, Fiale, Flaconi, Penne preriempite, Siringhe, Cerotti transdermici, Spray nasali, Inalatori, Granuli omeopatici, ecc.)
- La differenza tra dose **terapeutica** (clinicamente rilevante) e numeri **accessori** che appaiono nelle descrizioni (peso capsula vuota, volume contenitore, numero di pezzi)
- Le unità di misura farmacologiche italiane: MICROGRAMMI/MCG/µg, MILLIGRAMMI/MG, GRAMMI/G, MILLILITRI/ML, UNITÀ INTERNAZIONALI/UI/IU, MEQ, MMOL, percentuale (%)
- Le notazioni speciali: trifasici contraccettivi (`X MG/Y MG + W MG/Y MG + Z MG/Y MG`), combinazioni a 2 PA (`X MG + Y MG`, `X MG/Y MG`), dose per erogazione/inalazione/ora (`X MCG/EROGAZIONE`, `Y MCG/ORA`), notazione omeopatica hahnemanniana (6K, 12K, 30K, 200K, MK = potenza Korsakov, **non** una dose MG)
- Quando un dosaggio è espresso in forma "verbose" con separatori `-` (es. `150 mg - Soluzione iniettabile - Uso sottocutaneo - Siringa preriempita...`)

## CONTESTO

PharmaApp è un'app iOS per la gestione di terapie farmacologiche. Il backend Python importa il catalogo AIFA dei medicinali da `confezioni_fornitura.csv` (~158k confezioni autorizzate in Italia) e lo espone tramite REST API. La qualità del parsing del campo `DESCRIZIONE` è critica: dall'estrazione corretta di `strength_text` (es. "25 MCG", "500 MG/30 MG") e `strength_value`/`strength_unit` dipendono le chip di selezione dosaggio mostrate all'utente quando crea una terapia.

Il parser corrente (in `aifa_package_parser.py`) è basato su regex Python e copre il 99.99% dei casi (tasso di parsing su "deve-avere-dose" = 100% post-fix). Restano 3 casi residui non riparabili con regex generiche:

1. **Typo AIFA**: `ELTAIR 100 MICROGRAMM/EROGAZIONEI SPRAY NASALE` (manca la "I" finale)
2. **Hukyndra**: `Soluzione iniettabile - Uso sottocutaneo - siringa pre-riempita (vetro) in penna preriempita 0,8 ml` (dose effettiva nel testo libero in lowercase)
3. **Variazioni minori** di formato dash-separated.

Inoltre ci sono 414 + 532 + 1.890 + 68 warning su validation rules secondarie (unit_count = 1 quando descrizione contiene `\d{2,}\s*compress`, package_type NULL su forme standard, volume_value NULL su sciroppi/soluzioni orali, varianti inconsistenti per cod_farmaco).

## OBIETTIVO

Produrre una **nuova generazione** di regole di parsing strutturate che:

1. Copra **tutti** i pattern del CSV (anche edge case dipendenti dal contesto clinico del farmaco)
2. Sia **machine-readable** (Python regex compilate + funzioni decisionali) e **documentate** (per ogni regola, spiega quale farmaco/famiglia copre)
3. Usi **ricerca web** quando il pattern è ambiguo: cerca il farmaco specifico, leggi il foglietto illustrativo AIFA, capisci la dose terapeutica vera, codifica la regola
4. Sia **idempotente** — applicabile sul CSV completo per validare prima e dopo i fix

## INPUT

Allego:

- **`confezioni_fornitura.csv`**: 158.264 righe, 15 colonne (`CODICE_AIC`, `COD_FARMACO`, `COD_CONFEZIONE`, `DENOMINAZIONE`, `DESCRIZIONE`, `CODICE_DITTA`, `RAGIONE_SOCIALE`, `STATO_AMMINISTRATIVO`, `TIPO_PROCEDURA`, `FORMA`, `CODICE_ATC`, `PA_ASSOCIATI`, `FORNITURA`, `LINK_FI`, `LINK_RCP`). Solo `DESCRIZIONE` viene parsata; le altre sono già strutturate.
- **`aifa_package_parser.py`**: parser corrente (~460 righe Python con regex). Studialo come baseline.
- **Stato baseline**: 74.779 PARSED_OK / 74.324 OMEOPATICI / 2.387 UNPARSED_LEGITIMATE / 3 UNPARSED_BUG / 17 MISSING_PACKAGE_TYPE su 151.510 packages pubblici.

## TASK

### Fase A — Clusterizzazione pattern (no web search)

Leggi il CSV e raggruppa tutte le `DESCRIZIONE` (de-duplicate) per **scheletro strutturale**. Cioè:
- normalizza i numeri a `N`
- normalizza le unità (MG/MCG/UI/...) a `<UNIT>`
- normalizza i container (COMPRESSE/CAPSULE/...) a `<CONTAINER>`
- mantieni la struttura di separatori (`-`, `+`, `/`, virgola, parentesi)

Esempio:
```
"25 MICROGRAMMI COMPRESSE- 50 COMPRESSE IN BLISTER PVC/AL"
  → skeleton: "N <UNIT> <CONTAINER>- N <CONTAINER> IN BLISTER <MATERIALE>"

"0,180 MG/0,035 MG + 0,215 MG/0,035 MG + 0,250 MG/0,035 MG COMPRESSE..."
  → skeleton: "N <UNIT>/N <UNIT> + N <UNIT>/N <UNIT> + N <UNIT>/N <UNIT> <CONTAINER>..."
```

Produci una **tabella di scheletri** con conteggio frequenza (top 50 scheletri = top 50 pattern). Identifica quali scheletri sono ben parsati dal parser corrente e quali NO.

**Output Fase A**: `pattern_clusters.md` con tabella `[skeleton, count, parser_status, example_aic, example_descrizione]`.

### Fase B — Regole di parsing per ogni cluster (con web search dove serve)

Per ogni cluster (specialmente per quelli con `parser_status = MISS/PARTIAL`):

1. **Studia il cluster**: prendi 3-5 esempi reali. Quali farmaci sono? (`DENOMINAZIONE` + `PA_ASSOCIATI` + `CODICE_ATC`).
2. **Determina la dose terapeutica corretta**: 
   - Se ovvio dal pattern (es. "500 MG" classico), nessuna ricerca.
   - Se ambiguo (es. omeopatico "CAPSULE DA 800 MG" → la dose è la potenza K, non MG!), fai **web search**: `<DENOMINAZIONE> foglietto illustrativo AIFA posologia`. Verifica dalla scheda tecnica RCP cosa AIFA considera "dose terapeutica" per quel farmaco.
   - Per combinazioni multi-PA, verifica quali sono i PA del farmaco (`PA_ASSOCIATI`) e nell'ordine di apparizione.
3. **Definisci la regola**:
   - **Regex Python** (POSIX-compatible se possibile)
   - **Funzione di estrazione**: input → `(strength_text, strength_value, strength_unit, unit_count, package_type, volume_value, volume_unit)`
   - **Pre-condizione**: quando applicare questa regola (es. "se `tipo_procedura == 'Omeopatico'`", "se descrizione contiene `\bMK\b`")
   - **Esempi positivi** (3-5): descrizione → output atteso
   - **Esempi negativi** (1-2): cosa la regola NON deve matchare
4. **Annota la fonte web** (se usata): URL AIFA / produttore + 1 frase di razionale clinico.

**Output Fase B**: `parsing_rules.py` (codice Python eseguibile) con la struttura:

```python
@dataclass
class ParsingRule:
    rule_id: str                     # es. "R012_TRIFASIC_CONTRACEPTIVE"
    description: str                 # human-readable
    precondition: Callable[[dict], bool]  # filtra row CSV
    pattern: re.Pattern              # regex compilata
    extractor: Callable[[re.Match, dict], ParsedPackage]
    examples_pos: list[tuple[str, ParsedPackage]]  # input → output atteso
    examples_neg: list[str]
    web_sources: list[str]           # URL consultati (se applicabile)

RULES: list[ParsingRule] = [
    ParsingRule(
        rule_id="R001_SIMPLE_MG_TABLET",
        description="Compressa con dose singola MG/MCG: '500 MG COMPRESSE - 30 COMPRESSE...'",
        precondition=lambda row: row["FORMA"].lower().startswith("compress"),
        pattern=re.compile(r"^(\d+(?:[.,]\d+)?)\s*(MG|MCG)\s+COMPRESS"),
        extractor=lambda m, row: ParsedPackage(
            strength_text=f"{m.group(1)} {m.group(2).upper()}",
            strength_value=_parse_italian_number(m.group(1)),
            strength_unit=m.group(2).upper(),
            ...
        ),
        examples_pos=[
            ("500 MG COMPRESSE- 30 COMPRESSE IN BLISTER", ParsedPackage(strength_text="500 MG", ...)),
        ],
        examples_neg=["500 MG/30 MG COMPRESSE..."],
        web_sources=[],
    ),
    # ...
]
```

Le regole devono essere **ordinate per specificità** (più specifica prima). La funzione di dispatch applica la prima regola che matcha; se nessuna matcha, ritorna `ParsedPackage()` vuoto.

### Fase C — Decision tree visuale + report

Produci un `decision_tree.md` che disegna come un nuovo parser dovrebbe processare una `DESCRIZIONE`:

```
START
├── tipo_procedura == 'Omeopatico'?  ──YES──> NULL strength (regola R050)
├── descrizione matcha R012 trifasic? ──YES──> estrai 3 dosi
├── descrizione contiene ' - ' lowercase con mg? ──YES──> R023 verbose-dash
├── descrizione matcha N MG/UNIT compresse? ──YES──> R001 simple_mg_tablet
├── ...
└── fallback: R999 unknown ──> NULL + flag for manual review
```

Includi anche:
- **Lista farmaci/famiglie con regola dedicata** (es. "trifasici contraccettivi: Briladona, Nuvelle, Trinordiol — R012")
- **Catalogo unità ammesse** (whitelist completa con tutte le forme)
- **Container vocabulary**: lista termini riconosciuti come contenitori

### Fase D — Validation suite

Genera `test_parsing_rules.py` con almeno **120 test case parametrici**, distribuiti:
- 30 dose semplice (Tachipirina, Eutirox, Brufen, ecc.)
- 20 combinazioni a 2 PA (Augmentin, Tachidol, Spirometra)
- 10 combinazioni a 3+ PA (Stribild, trifasici)
- 15 cerotti/inalatori/spray (Durogesic, Ventolin, Nasonex)
- 15 vaccini/iniettabili (Fluarix, vaccino esavalente)
- 10 omeopatici (Aesculusplus, Ipiestal, granuli K)
- 10 verbose dash-separated (Hukyndra, Cosentyx)
- 10 sciroppi/gocce/soluzioni orali (Vicks Medinait, Phospho Lax)

Per ogni test, l'AI deve ricavare l'`expected_output` dal CSV (se la regola lo parsa correttamente) o da web search (per quelli che oggi falliscono).

## QUANDO USARE WEB SEARCH

Fai web search **solo** se:
1. Il pattern è ambiguo (es. trovare quale tra due numeri in descrizione è la dose terapeutica vera)
2. L'unità non è ovvia (es. omeopatici dove "MG" potrebbe essere peso del veicolo)
3. Il farmaco è un combo speciale dove l'ordine dei PA importa (es. amoxicillina/ac. clavulanico standard 875/125 vs varianti)
4. Stai dubitando se un pattern raro è un bug AIFA o una variante legittima

**Non** fare web search per dose ovvie (compresse 500 MG di paracetamolo) — sarebbe spreco.

Per ogni web search citare: query usata + URL fonte (preferenza: aifa.gov.it, farmaci.agenziafarmaco.gov.it, foglietti.it, banca dati farmaci ufficiale).

## CRITERI DI SUCCESSO

Il nuovo `parsing_rules.py` deve:

- [ ] Coprire **≥ 99.99%** dei 151k packages pubblici autorizzati (target: zero `UNPARSED_BUG`)
- [ ] Mantenere backward compat con il parser corrente sui 92 test esistenti (`test_aifa_parser.py` + `test_aifa_parser_golden.py`)
- [ ] Risolvere i 3 casi residui (Eltair, Hukyndra x2)
- [ ] Risolvere i 414 V06 (unit_count = 1 ma `\d{2,} compress` in desc) — molti sono fix-able
- [ ] Risolvere i 532 V07 (package_type NULL su forme standard)
- [ ] Avere ogni regola **testata** con almeno 1 esempio positivo e 1 negativo
- [ ] Includere **rationale clinico** per ogni regola omeopatica / combinazione / edge case
- [ ] Essere **eseguibile out-of-the-box**: `python -c "from parsing_rules import parse; print(parse('25 MICROGRAMMI COMPRESSE- 50 ...'))"`

## DELIVERABLES (in ordine)

1. **`pattern_clusters.md`** — tabella scheletri + frequenza + status
2. **`parsing_rules.py`** — eseguibile, ~50-100 regole con regex, extractor, examples
3. **`decision_tree.md`** — flow visuale + lista famiglie/regole + whitelist unità + vocabolario container
4. **`test_parsing_rules.py`** — 120+ test parametrici (pytest format)
5. **`web_research_log.md`** — log delle ricerche web fatte: `[farmaco, query, URL, finding, regola creata]`
6. **`audit_diff.md`** — confronto before/after: per ogni AIC dove le nuove regole differiscono dal parser corrente, mostra entrambi e il rationale

## STILE / VINCOLI

- Codice Python 3.12, formato leggibile, commenti in italiano
- Regex POSIX-compatibili dove possibile (per riusarle anche server-side PG)
- Mantieni Python `re` standard library — no `regex` esterna
- Output completo: niente snippet "...", deve essere copy-paste eseguibile
- Se il task supera il limite di token, prioritizza Deliverables 1-3 e accenna 4-6 con scaffolding
- Lavora **in parallelo**: clusterizza tutto il CSV prima di scrivere singole regole

## NOTE OPERATIVE

- Il CSV usa `;` come delimiter e quote `"` (campi virgolettati con quote interne escapate `""`)
- L'encoding è UTF-8
- Numeri italiani con virgola decimale (`1,3` invece di `1.3`); migliaia con punto (`1.234` invece di `1,234`)
- `\b` (word boundary) in Python regex funziona; per riuso PG sostituire con `\y`
- `\d` funziona in Python; per PG sostituire con `[0-9]`
- Container vocabulary noto (whitelist completa): vedi `_CONTAINER_TYPES` nel parser corrente — estendila se trovi nuovi termini

## ESEMPI DI INPUT-OUTPUT ATTESI

### Esempio 1 — semplice
```
INPUT:  "500 MG COMPRESSE- 20 COMPRESSE IN BLISTER PVC/AL"
OUTPUT: ParsedPackage(
    strength_text="500 MG", strength_value=500.0, strength_unit="MG",
    unit_count=20, package_type="Compresse",
    volume_value=None, volume_unit=""
)
RULE:   R001_SIMPLE_DOSE_TABLET
```

### Esempio 2 — trifasico contraccettivo (NECESSITA web search per validare)
```
INPUT:  "0,180 MG/0,035 MG + 0,215 MG/0,035 MG + 0,250 MG/0,035 MG COMPRESSE RIVESTITE CON FILM- 21 COMPRESSE"
WEB:    "Briladona Trifase AIFA" → conferma 3 fasi etinilestradiolo+levonorgestrel
OUTPUT: ParsedPackage(
    strength_text="0,180 MG/0,035 MG + 0,215 MG/0,035 MG + 0,250 MG/0,035 MG",
    strength_value=0.180, strength_unit="MG/0,035MG",
    unit_count=21, package_type="Compresse",
    volume_value=None, volume_unit=""
)
RULE:   R012_TRIFASIC_CONTRACEPTIVE
```

### Esempio 3 — omeopatico (NECESSITA web search per capire che K è potenza)
```
INPUT:  "GRANULI IN CAPSULE RIGIDE- 2 CAPSULE 6K, 2 CAPSULE 12K, 2 CAPSULE 30K, 22 CAPSULE 35K, 1 CAPSULA 200K, 1 CAPSULA MK - CAPSULE DA 800 MG"
WEB:    "Aesculusplus omeopatico AIFA" → conferma notazione Korsakov; 800 MG è peso veicolo
OUTPUT: ParsedPackage(
    strength_text="",  # NULL: dose omeopatica non esprimibile come MG
    strength_value=None, strength_unit="",
    unit_count=30,  # somma capsule totali nella confezione
    package_type="Capsule",
    volume_value=None, volume_unit=""
)
RULE:   R050_HOMEOPATHIC_K_POTENCY
```

### Esempio 4 — verbose dash-separated (NECESSITA web search)
```
INPUT:  "120 mg - Soluzione Iniettabile - Uso sottocutaneo - Siringa preriempita (vetro) in penna preriempita 0,8 ml (150 mg/ml) - 1 penna preriempita"
WEB:    "Hukyndra 120 mg/0,8 ml AIFA" → adalimumab biosimilare
OUTPUT: ParsedPackage(
    strength_text="120 MG/0,8 ML",
    strength_value=120.0, strength_unit="MG/0,8ML",
    unit_count=1, package_type="Penna Preriempita",
    volume_value=0.8, volume_unit="ML"
)
RULE:   R023_VERBOSE_DASH_SEPARATED
```

---

## CHIUSURA

Quando hai prodotto tutti i 6 deliverable, scrivi una sezione finale `## SUMMARY` con:
- Numero totale di regole create
- Coverage previsto (rispetto ai 158k packages CSV)
- Casi residui non risolvibili automaticamente (lista AIC + motivazione)
- Tempo stimato di esecuzione del nuovo parser su tutto il CSV
- Sezione "Open Questions" con ambiguità che richiedono decisione umana (es. "il farmaco X ha 2 dosi in DESCRIZIONE ma RCP ne menziona solo 1, mi serve conferma utente")

Iniziamo. Quando sei pronta, dai conferma e produci `pattern_clusters.md` come primo step.
