# Cosa ottiene Matryca Plumber con la v2.0 e lo Shadow DB

_Nota di lavoro — 2026-07-25, mentre gira il soak da 24h+ (r8) prima del rilascio beta._

## La tua traccia, verificata

> "15:07 è partito il SOAK di 24 ore per testare tutto quello che ho costruito nei giorni scorsi per la v2.0 di questo Matryca Plumber, quindi manca veramente poco al salto quantico della v2.0 in cui ci sarà uno shadow DB al supporto e per velocizzare tutte le operazioni di lettura dal database di Logseq, che cambierà moltissimo la potenza di questo sistema e lo renderà adatto al funzionamento come memoria principale super granulare e potente per gli agenti di intelligenza artificiale, con la granularità dei blocchi di Logseq al contrario delle pagine monolitiche di Obsidian e gli altri."

Ogni affermazione qui è **supportata** da quello che c'è nel codice e nella roadmap, con qualche precisazione tecnica che vale la pena aggiungere per raccontarla bene.

---

## 1. Cos'è davvero lo Shadow DB (i fatti)

Non è un nuovo database che sostituisce Logseq: è una **cache di lettura**, gestita interamente dal daemon di Matryca Plumber, che affianca — senza mai sostituire — i file Markdown.

- **Sorgente di verità**: resta sempre il Markdown su disco. Logseq OG continua a scrivere `.md`, Matryca Plumber continua a scrivere `.md` con OCC-safety (`st_mtime` + page lock, la stessa garanzia anti-corruzione che avete già in v1).
- **Shadow DB** (`shadow.sqlite`, dentro `.matryca_semantic_cache/`) è un **mirror sincronizzato** di quel Markdown, pensato per **letture** rapide: FTS5 (full-text search nativo di SQLite) per la ricerca testuale, e **CTE ricorsive** (Common Table Expressions) per leggere interi sottoalberi di blocchi con una singola query invece di ricostruirli in memoria ogni volta.
- **Sostituisce** il vecchio percorso v1.9.5: `master_catalog.json` letto interamente in RAM + BM25 calcolato in-process ad ogni ricerca. Quel percorso resta come **fallback automatico** — se lo Shadow DB non è "ready" (es. durante un rebuild, o un mismatch di schema), il sistema torna a leggere da Markdown/BM25 senza che l'utente se ne accorga.
- **È opt-in**: si attiva con `MATRYCA_SHADOW_DB_ENABLED=true`, default off. Chi non lo attiva ha esattamente il comportamento di oggi. Questo è il motivo per cui il rilascio è così controllato — non è un "big bang", è un acceleratore che si può accendere quando è pronto.

**La cosa concreta che cambia per chi lo usa:** letture "sub-50ms" invece di dover ricaricare/ricalcolare corpus BM25 in memoria a ogni richiesta. Per un agente AI che interroga il grafo decine o centinaia di volte in una sessione di lavoro, è la differenza tra un assistente che "pensa" a ogni domanda e uno che risponde all'istante.

## 2. La granularità a blocchi (perché è la parte più importante)

Qui la tua intuizione è corretta ed è **il** punto differenziante, non un dettaglio tecnico:

- Lo schema dello Shadow DB ha tabelle `pages`, `blocks`, `block_refs`, `blocks_fts` — il **blocco** (il singolo bullet di Logseq, con il suo `id::` UUID) è l'unità atomica indicizzata, non la pagina.
- Le query `query_subtree_by_block_uuid` (con CTE ricorsive) permettono di chiedere "dammi questo blocco e tutti i suoi figli fino a profondità N" — un'operazione che su un sistema page-based (come Obsidian, dove l'unità è il file/nota intera) semplicemente non esiste nella stessa forma: lì devi caricare tutta la nota e fare parsing testuale per trovare la sotto-sezione che ti interessa.
- Per un agente AI questo significa **recuperare esattamente il contesto che serve**, non l'intera pagina attorno. È memoria selettiva, non "tutto o niente" — più vicino a come funziona la memoria umana (richiami puntuali, non rilettura integrale di un capitolo) che a un semplice text search su file.

Questo è coerente con la citazione che avete già nel README: *"Logseq is building the best local outliner database. But AI Agent memory is at the very bottom of their roadmap. Matryca Plumber gives you that future today."* — lo Shadow DB è l'infrastruttura che rende quella promessa veloce e scalabile, non solo possibile.

## 3. "Memoria principale per gli agenti AI" — cosa c'è oggi e cosa manca ancora

Qui vale la pena essere precisi per non promettere più di quanto la beta copra:

- **Nella beta v2.0.0-beta.1**: lo Shadow DB copre il **read path** — bootstrap, ricostruzione, routing sanitario (health-gated), FTS5, CTE. Questo è già sufficiente per accelerare drasticamente ogni lettura che gli agenti fanno tramite MCP/CLI.
- **Fuori scope della beta, già in roadmap (Fase 4)**: la "biological memory" — tabelle come `memory_nodes`, `memory_edges`, `memory_episodes`, `memory_procedures` sono **già disegnate nello schema** (ispirate a un modello di memoria biologica, vedi `ROADMAP_V2_BIOLOGICAL_MEMORY.md`), ma non fanno parte di questo rilascio. Sono il prossimo salto: non solo "leggere più veloce" ma un vero **grafo di memoria** con episodi, procedure, consolidamento — la parte che trasforma lo Shadow DB da acceleratore a vera e propria memoria cognitiva per l'agente.

Quindi la frase corretta per raccontarlo al mondo è: **"la v2.0 beta pone le fondamenta ad altissima velocità per la memoria degli agenti AI — la granularità a blocchi e l'infrastruttura di lettura sono già qui; la memoria biologica/episodica arriva nella fase successiva sulla stessa infrastruttura."**

## 4. Perché il soak di 24 ore non è burocrazia, è la parte che conta

Vale la pena raccontarlo anche questo, perché rende il lancio più credibile, non meno:

- Il team (io, in questo caso) ha già trovato e **corretto un bug reale** durante questo processo: un timeout che non copriva l'intera operazione di lettura tra processi (`multiprocessing.Queue`), che in condizioni di stress poteva far superare il deadline configurato senza un fallback pulito. È stato isolato, corretto, testato (anche con test randomizzati/fuzz), rivisto in PR e mergiato.
- Da lì: rebuild del pacchetto candidato, verifica dell'integrità del wheel (hash, provenienza) su un vault reale copiato, un **probe di accensione** (ON) mirato che ha validato rebuild, health, ricerca, lettura di sottoalberi e recovery controllata — e ora un **soak esteso di ~25 ore** sullo stesso vault reale, per catturare quello che un test rapido non può vedere: comportamento su cicli lunghi, riavvii, watcher di file (creazione/modifica/rinomina/cancellazione), e garanzia che il Markdown originale resti bit-per-bit invariato.
- Questo è esattamente lo standard che serve per una feature che tocca la modalità in cui un agente AI legge la tua conoscenza personale: **niente scorciatoie prima di fidarsi**.

## 5. Il messaggio per raccontarlo al mondo

Elementi (tecnici + emotivi) che puoi usare:

1. **Il salto di potenza è reale e misurabile**: da un catalogo JSON caricato in RAM e BM25 ricalcolato ogni volta, a un database SQLite con full-text search nativo e query ad albero in sub-50ms.
2. **La granularità a blocchi è l'unica vera differenza architetturale con Obsidian**: non è marketing, è nello schema — l'unità è il blocco con il suo UUID, non il file.
3. **Nulla si rompe per chi non lo vuole**: opt-in, default-off, fallback automatico a Markdown/BM25 se qualcosa non è pronto. Il Markdown resta sempre l'unica fonte di verità — non stai chiedendo a nessuno di fidarsi di un database opaco.
4. **Il rigore del rilascio è parte della storia**: un bug reale trovato e risolto prima del lancio, un soak di un giorno intero sul vault vero, non su dati sintetici — è il tipo di cura che serve quando l'obiettivo finale è diventare la memoria di un agente AI.
5. **La direzione è più grande della beta**: questo è il primo mattone di un'infrastruttura che porterà a una vera memoria episodica/biologica per gli agenti — la beta non è la destinazione, è la fondazione veloce su cui costruirla.

---

_Documento di lavoro, non un gate di rilascio — nessuna correlazione con `docs/quality/issue-bodies/v2-beta-readiness.md`, che resta l'unica fonte di verità per la decisione di rilascio._
