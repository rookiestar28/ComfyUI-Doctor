# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | Italiano | [Español](README.es.md) | [English](../README.md) | [Roadmap e stato di sviluppo](../ROADMAP.md)

Una suite di diagnostica runtime continua e in tempo reale per ComfyUI con **analisi basata su LLM**, **chat di debug interattiva** e **50+ modelli di correzione**. Intercetta automaticamente tutto l'output del terminale dall'avvio, cattura traceback Python completi e fornisce suggerimenti di correzione priorizzati con estrazione del contesto a livello di nodo. Ora supporta la **gestione dei pattern basata su JSON** con hot-reload e **supporto i18n completo** per 9 lingue (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

## Ultimi aggiornamenti (Gen 2026) - Clicca per espandere

<details>
<summary><strong>Gestione Intelligente del Budget dei Token (v1.5.0)</strong></summary>

**Gestione Contestuale Intelligente (Ottimizzazione dei Costi):**

- **Taglio automatico**: Per LLM remoti (riduzione del 60-80% dei token)
- **Strategia progressiva**: Potatura del flusso di lavoro → rimozione info sistema → troncamento traccia
- **Opt-in Locale**: Taglio leggero per Ollama/LMStudio (limiti 12K/16K)
- **Osservabilità Migliorata**: Tracciamento token passo-passo & Strumento di convalida A/B

**Resilienza di Rete:**

- **Backoff Esponenziale**: Riprova automatica per errori 429/5xx (con jitter)
- **Protezione Streaming**: Watchdog di 30s per chunk SSE bloccati
- **Limiti di Velocità & Concorrenza**: Token bucket (30/min) + Semaforo concorrenza (max 3)

**Nuova Configurazione:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | Abilita budget intelligente (Remoto) |
| `retry_max_attempts` | `3` | Max tentativi |
| `stream_chunk_timeout` | `30` | Timeout flusso (sec) |

</details>

---

<details>
<summary><strong>Correzione Importante: Governance della Pipeline & Sicurezza dei Plugin (v1.4.5)</strong></summary>

**Rafforzamento della Sicurezza:**

- **Protezione SSRF++**: Sostituiti i controlli delle sottostringhe con un'analisi Host/Port corretta; bloccati i reindirizzamenti in uscita (`allow_redirects=False`)
- **Imbuto di Sanificazione in Uscita**: Un singolo confine (`outbound.py`) garantisce la sanificazione per TUTTI i payload esterni; `privacy_mode=none` consentito solo per LLM locali verificati

**Sistema di Fiducia dei Plugin:**

- **Sicuro per impostazione predefinita**: Plugin disabilitati di default, richiedono Allowlist esplicita + Manifesto/SHA256
- **Classificazione di Fiducia**: `trusted` (fidato) | `unsigned` (non firmato) | `untrusted` (non fidato) | `blocked` (bloccato)
- **Contenimento del File System**: Contenimento realpath, rifiuto symlink, limiti di dimensione, regole rigorose per i nomi dei file
- **Firma HMAC Opzionale**: Verifica dell'integrità a segreto condiviso (non firma a chiave pubblica)

**Governance della Pipeline:**

- **Contratti di Metadati**: Versionamento dello schema + convalida post-esecuzione + Quarantena per chiavi non valide
- **Politica delle Dipendenze**: Applicazione di `requires/provides`; dipendenza mancante → salto fase, stato `degraded` (degradato)
- **Contropressione del Logger**: `DroppingQueue` con priorità + metriche di scarto
- **Passaggio Pre-avvio**: Disinstallazione pulita del Logger prima che SmartLogger prenda il sopravvento

**Osservabilità:**

- Endpoint `/doctor/health`: Espone metriche della coda, conteggi di scarto, blocchi SSRF e stato della pipeline

**Risultati dei Test**: 159 test Python superati | 17 test Gate Fase 2

</details>

---

<details>
<summary><strong>Miglioramento: CI Gates & Strumenti Plugin</strong></summary>

**T11 - Gate di Rilascio CI Fase 2:**

- Workflow GitHub Actions (`phase2-release-gate.yml`): Applica 4 suite pytest + E2E
- Script di convalida locale (`scripts/phase2_gate.py`): Supporta le modalità `--fast` e `--e2e`

**T12 - Controllo Statico Sicurezza in Uscita:**

- Analizzatore basato su AST (`scripts/check_outbound_safety.py`) rileva pattern di bypass
- 6 regole di rilevamento: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION`, ecc.
- Workflow CI + 8 test unitari + Documentazione (`docs/OUTBOUND_SAFETY.md`)

**A8 - Strumenti di Migrazione Plugin:**

- `scripts/plugin_manifest.py`: Genera manifesto con hash SHA256
- `scripts/plugin_allowlist.py`: Scansiona plugin e suggerisce configurazione
- `scripts/plugin_validator.py`: Convalida manifesto e configurazione
- `scripts/plugin_hmac_sign.py`: Genera firme HMAC opzionali
- Documentazione aggiornata: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

---

<details>
<summary><strong>Miglioramento: Doc CSP & Telemetria</strong></summary>

**S1 - Doc Conformità CSP:**

- Verificato che tutte le risorse vengano caricate localmente (`web/lib/`); URL CDN solo come fallback
- Aggiunta sezione "CSP Compatibility" al README
- Audit del codice completato (in attesa di verifica manuale)

**S3 - Infrastruttura Telemetria Locale:**

- Backend: `telemetry.py` (TelemetryStore, RateLimiter, rilevamento PII)
- 6 Endpoint API: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- Frontend: Controlli UI impostazioni per gestione telemetria
- Sicurezza: Controllo origine (403 Cross-Origin), limite payload 1KB, allowlist campi
- **OFF per default**: Nessuna registrazione/rete a meno che non sia esplicitamente abilitato
- 81 stringhe i18n (9 chiavi × 9 lingue)

**Risultati dei Test**: 27 Test Unitari Telemetria | 8 Test E2E

</details>

---

<details>
<summary><strong>Miglioramento: Rafforzamento Runner E2E & UI Fiducia/Salute</strong></summary>

**Rafforzamento Runner E2E (Supporto WSL `/mnt/c`):**

- Risolti problemi di permessi della cache di traduzione Playwright su WSL
- Aggiunta directory temporanea scrivibile (`.tmp/playwright`) sotto il repo
- Override `PW_PYTHON` per compatibilità multipiattaforma

**Pannello UI Fiducia & Salute:**

- Aggiunto pannello "Trust & Health" alla scheda Impostazioni
- Mostra: pipeline_status, ssrf_blocked, dropped_logs
- Elenco fiducia plugin (con badge e motivazioni)
- Endpoint solo scansione `GET /doctor/plugins` (nessuna importazione codice)

**Risultati dei Test**: 61/61 Test E2E Superati | 159/159 Test Python Superati

</details>

---

<details>
<summary><strong>Aggiornamenti Precedenti (v1.4.0, Gen 2026)</strong></summary>

- Migrazione A7 Preact Completata (Fase 5A–5C: Isole Chat/Stats, registro, rendering condiviso, fallback robusti).
- Rafforzamento Integrazione: Potenziata copertura Playwright E2E.
- Correzioni UI: Corretta tempistica tooltip barra laterale.

</details>

---

<details>
<summary><strong>Dashboard statistiche</strong></summary>

**Tieni traccia della stabilità di ComfyUI a colpo d'occhio!**

ComfyUI-Doctor ora include una **Dashboard statistiche** che fornisce approfondimenti sui trend degli errori, problemi comuni e progressi nella risoluzione.

**Caratteristiche**:

- 📊 **Trend errori**: Traccia gli errori su 24h/7g/30g
- 🔥 **Top 5 Pattern**: Vedi quali errori si verificano più frequentemente
- 📈 **Ripartizione categorie**: Visualizza gli errori per categoria (Memoria, Workflow, Caricamento modelli, ecc.)
- ✅ **Tracciamento risoluzione**: Monitora errori risolti vs irrisolti
- 🌍 **Supporto i18n completo**: Disponibile in tutte e 9 le lingue

![Dashboard statistiche](assets/statistics_panel.png)

**Come usare**:

1. Apri il pannello laterale Doctor (clicca l'icona 🏥 a sinistra)
2. Espandi la sezione "📊 Statistiche errori"
3. Visualizza analisi e trend degli errori in tempo reale
4. Contrassegna gli errori come risolti/ignorati per tracciare i tuoi progressi

**API Backend**:

- `GET /doctor/statistics?time_range_days=30` - Recupera statistiche
- `POST /doctor/mark_resolved` - Aggiorna lo stato di risoluzione

**Copertura test**: 17/17 test backend ✅ | 14/18 test E2E (tasso di superamento 78%)

**Dettagli implementazione**: Vedi `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

---

<details>
<summary><strong>CI validazione pattern</strong></summary>

**I controlli di qualità automatizzati ora proteggono l'integrità dei pattern!**

ComfyUI-Doctor ora include **test di integrazione continua** per tutti i pattern di errore, garantendo contributi a zero difetti.

**Cosa convalida**:

- ✅ **Formato JSON**: Tutti gli 8 file di pattern compilano correttamente
- ✅ **Sintassi Regex**: Tutti i 57 pattern hanno espressioni regolari valide
- ✅ **Completezza i18n**: Copertura traduzione 100% (57 pattern × 9 lingue = 513 controlli)
- ✅ **Conformità Schema**: Campi obbligatori (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Qualità Metadati**: Intervalli di priorità validi (50-95), ID univoci, categorie corrette

**Integrazione GitHub Actions**:

- Si attiva ad ogni push/PR che influenza `patterns/`, `i18n.py` o i test
- Esegue in ~3 secondi a costo $0 (GitHub Actions free tier)
- Blocca i merge se la validazione fallisce

**Per i contributori**:

```bash
# Validazione locale prima del commit
python run_pattern_tests.py

# Output:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (9 lingue totali)
```

**Risultati test**: Tasso di superamento 100% su tutti i controlli

**Dettagli implementazione**: Vedi `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

---

<details>
<summary><strong>Revisione del sistema pattern (STAGE 1-3 Completato)</strong></summary>

ComfyUI-Doctor ha subito un importante aggiornamento dell'architettura con **57+ pattern di errore** e **gestione pattern basata su JSON**!

**STAGE 1: Fix architettura Logger**

- Implementato SafeStreamWrapper con elaborazione in background basata su coda
- Eliminati rischi di deadlock e race condition
- Risolti conflitti di intercettazione log con LogInterceptor di ComfyUI

**STAGE 2: Gestione pattern JSON (F2)**

- Nuovo PatternLoader con capacità hot-reload (nessun riavvio necessario!)
- Pattern ora definiti in file JSON nella directory `patterns/`
- 22 pattern integrati in `patterns/builtin/core.json`
- Facile da estendere e mantenere

**STAGE 3: Espansione pattern community (F12)**

- **35 nuovi pattern community** che coprono estensioni popolari:
  - **ControlNet** (8 pattern): Caricamento modelli, pre-elaborazione, dimensionamento immagini
  - **LoRA** (6 pattern): Errori di caricamento, compatibilità, problemi di peso
  - **VAE** (5 pattern): Fallimenti codifica/decodifica, precisione, tiling
  - **AnimateDiff** (4 pattern): Caricamento modelli, conteggio frame, lunghezza contesto
  - **IPAdapter** (4 pattern): Caricamento modelli, codifica immagini, compatibilità
  - **FaceRestore** (3 pattern): Modelli CodeFormer/GFPGAN, rilevamento
  - **Varie** (5 pattern): Checkpoint, campionatori, scheduler, CLIP
- Supporto i18n completo per Inglese, Cinese Tradizionale e Cinese Semplificato
- Totale: **57 pattern di errore** (22 integrati + 35 community)

**Vantaggi**:

- ✅ Copertura errori più completa
- ✅ Hot-reload dei pattern senza riavviare ComfyUI
- ✅ La community può contribuire pattern tramite file JSON
- ✅ Codebase più pulita e mantenibile

</details>

---

<details>
<summary><strong>Aggiornamenti precedenti (Dic 2025)</strong></summary>

### F9: Espansione supporto multilingua

Abbiamo esteso il supporto linguistico da 4 a 9 lingue! ComfyUI-Doctor ora fornisce suggerimenti di errore in:

- **English** Inglese (en)
- **繁體中文** Cinese Tradizionale (zh_TW)
- **简体中文** Cinese Semplificato (zh_CN)
- **日本語** Giapponese (ja)
- **🆕 Deutsch** Tedesco (de)
- **🆕 Français** Francese (fr)
- **🆕 Italiano** (it)
- **🆕 Español** Spagnolo (es)
- **🆕 한국어** Coreano (ko)

Tutti i 57 pattern di errore sono completamente tradotti in tutte le lingue, garantendo una qualità diagnostica costante in tutto il mondo.

### F8: Integrazione impostazioni barra laterale

Le impostazioni sono state semplificate! Configura Doctor direttamente dalla barra laterale:

- Clicca l'icona ⚙️ nell'intestazione della barra laterale per accedere a tutte le impostazioni
- Selezione lingua (9 lingue)
- Cambio rapido Provider AI (OpenAI, DeepSeek, Groq, Gemini, Ollama, ecc.)
- Compilazione automatica Base URL al cambio provider
- Gestione API Key (input protetto da password)
- Configurazione nome modello
- Le impostazioni persistono tra le sessioni con localStorage
- Feedback visivo al salvataggio (✅ Salvato! / ❌ Errore)

Il pannello Impostazioni di ComfyUI ora mostra solo l'interruttore Abilita/Disabilita - tutte le altre impostazioni sono state spostate nella barra laterale per un'esperienza più pulita e integrata.

</details>

---

## Caratteristiche

- **Monitoraggio errori automatico**: Cattura tutto l'output del terminale e rileva traceback Python in tempo reale
- **Analisi errori intelligente**: 57+ pattern di errore (22 integrati + 35 community) con suggerimenti attivabili
- **Estrazione contesto nodo**: Identifica quale nodo ha causato l'errore (ID nodo, Nome, Classe)
- **Contesto ambiente di sistema**: Include automaticamente versione Python, pacchetti installati (pip list) e info OS nell'analisi AI
- **Supporto multilingua**: 9 lingue supportate (Inglese, Cinese Tradizionale, Cinese Semplificato, Giapponese, Tedesco, Francese, Italiano, Spagnolo, Coreano)
- **Gestione pattern basata su JSON**: Hot-reload dei pattern di errore senza riavviare ComfyUI
- **Supporto pattern community**: Copre ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore e altro
- **Nodo ispettore debug**: Ispezione profonda dei dati che fluiscono attraverso il tuo workflow
- **Cronologia errori**: Mantiene un buffer degli errori recenti via API
- **API RESTful**: Sette endpoint per l'integrazione frontend
- **Analisi potenziata da AI**: Analisi errori LLM in un clic con supporto per 8+ provider (OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio e altro)
- **Interfaccia chat interattiva**: Assistente di debug AI multi-turn integrato nella barra laterale di ComfyUI
- **UI barra laterale interattiva**: Pannello errori visivo con localizzazione nodo e diagnostica istantanea
- **Configurazione flessibile**: Pannello impostazioni completo per la personalizzazione del comportamento

### 🆕 Interfaccia Chat AI

La nuova interfaccia chat interattiva offre un'esperienza di debug conversazionale direttamente nella barra laterale sinistra di ComfyUI. Quando si verifica un errore, clicca semplicemente su "Analyze with AI" per avviare una conversazione multi-turn con il tuo LLM preferito.

<div align="center">
<img src="assets/chat-ui.png" alt="Interfaccia Chat AI">
</div>

**Caratteristiche principali:**

- **Consapevole del contesto**: Include automaticamente dettagli errore, informazioni nodo e contesto workflow
- **Consapevole dell'ambiente**: Include versione Python, pacchetti installati e info OS per un debug accurato
- **Risposte in streaming**: Risposte LLM in tempo reale con formattazione corretta
- **Conversazioni multi-turn**: Poni domande di follow-up per approfondire i problemi
- **Sempre accessibile**: L'area di input rimane visibile in basso con posizionamento sticky
- **Supporta 8+ Provider LLM**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio e altro
- **Smart Caching**: Elenco pacchetti memorizzato nella cache per 24 ore per evitare impatti sulle prestazioni

**Come usare:**

1. Quando si verifica un errore, apri la barra laterale Doctor (pannello sinistro)
2. Clicca il pulsante "✨ Analyze with AI" nell'area contesto errore
3. L'AI analizzerà automaticamente l'errore e fornirà suggerimenti
4. Continua la conversazione digitando domande di follow-up nella casella di input
5. Premi Invio o clicca "Send" per inviare il tuo messaggio

> **💡 Suggerimento API gratuita**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) offre un generoso piano gratuito senza carta di credito richiesta. Perfetto per iniziare con il debug basato su AI senza costi!

---

## Installazione

### Opzione 1: Usando ComfyUI-Manager (Consigliato)

1. Apri ComfyUI e clicca il pulsante **Manager** nel menu
2. Seleziona **Install Custom Nodes**
3. Cerca `ComfyUI-Doctor`
4. Clicca **Install** e riavvia ComfyUI

### Opzione 2: Installazione manuale (Git Clone)

1. Naviga nella tua directory custom nodes di ComfyUI:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clona questo repository:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. Riavvia ComfyUI

4. Cerca il messaggio di inizializzazione nella console:

   ```text
   [ComfyUI-Doctor] Initializing Smart Debugger...
   [ComfyUI-Doctor] Log file: .../logs/comfyui_debug_2025-12-28.log
   
   ==================== SYSTEM SNAPSHOT ====================
   OS: Windows 11
   Python: 3.12.3
   PyTorch: 2.0.1+cu118
   CUDA Available: True
   ...
   ```

---

## Utilizzo

### Modalità Passiva (Automatica)

Una volta installato, ComfyUI-Doctor automaticamente:

- Registra tutto l'output della console nella directory `logs/`
- Rileva errori e fornisce suggerimenti
- Registra le informazioni sull'ambiente di sistema

**Esempio Output Errore**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory): La tua VRAM GPU è piena. Prova:
   1. Ridurre la dimensione del batch
   2. Usare il flag '--lowvram'
   3. Chiudere altre app GPU
----------------------------------------
```

### Modalità Attiva (Nodo Debug)

1. Clicca con il tasto destro sulla canvas → `Add Node` → `Smart Debug Node`
2. Collega il nodo in linea con qualsiasi connessione (supporta input Jolly `*`)
3. Esegui il tuo workflow

**Esempio Output**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

Il nodo passa i dati senza influenzare l'esecuzione del workflow.

---

## UI Frontend

ComfyUI-Doctor fornisce un'interfaccia laterale interattiva per il monitoraggio e la diagnostica degli errori in tempo reale.

### Accesso al Pannello Doctor

Clicca il pulsante **🏥 Doctor** nel menu di ComfyUI (barra laterale sinistra) per aprire il pannello Doctor. Il pannello scorre dal lato destro dello schermo.

### Caratteristiche dell'Interfaccia

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Rapporto Errori">
</div>

L'interfaccia Doctor consiste in due pannelli:

#### Pannello Laterale Sinistro (Barra Laterale Doctor)

Clicca l'icona **🏥 Doctor** nel menu sinistro di ComfyUI per accedere a:

- **Pannello Impostazioni** (icona ⚙️): Configura lingua, provider AI, chiavi API e selezione modello
- **Scheda Contesto Errore**: Quando si verifica un errore, mostra:
  - **💡 Suggerimento**: Consiglio conciso e attuabile (es. "Controlla le connessioni in ingresso e assicurati che i requisiti del nodo siano soddisfatti.")
  - **Timestamp**: Quando si è verificato l'errore
  - **Contesto Nodo**: ID e nome del nodo (se applicabile)
  - **✨ Analyze with AI**: Avvia chat interattiva per debug dettagliato
- **Interfaccia Chat AI**: Conversazione multi-turn con il tuo LLM per un'analisi approfondita dell'errore
- **Area Input Sticky**: Sempre accessibile in basso per domande di follow-up

#### Pannello Errori Destro (Ultima Diagnosi)

Notifiche di errore in tempo reale nell'angolo in alto a destra:

![Rapporto Errore Doctor](./assets/error-report.png)

- **Indicatore di Stato**: Punto colorato che mostra la salute del sistema
  - 🟢 **Verde**: Sistema funzionante normalmente, nessun errore rilevato
  - 🔴 **Rosso (pulsante)**: Errore attivo rilevato
- **Scheda Ultima Diagnosi**: Visualizza l'errore più recente con:
  - **Riepilogo Errore**: Breve descrizione dell'errore (tema rosso, comprimibile per errori lunghi)
  - **💡 Suggerimento**: Consiglio conciso e attuabile (tema verde)
  - **Timestamp**: Quando si è verificato l'errore
  - **Contesto Nodo**: ID, nome e classe del nodo
  - **🔍 Localizza Nodo su Canvas**: Centra ed evidenzia automaticamente il nodo problematico

**Principi di Design Chiave**:

- ✅ **Suggerimenti Concisi**: Viene mostrato solo il consiglio attuabile (es. "Controlla connessioni in ingresso...") invece di descrizioni di errore prolisse
- ✅ **Separazione Visiva**: Messaggi di errore (rosso) e suggerimenti (verde) sono chiaramente distinti
- ✅ **Troncamento Intelligente**: Gli errori lunghi mostrano le prime 3 + ultime 3 righe con dettagli completi comprimibili
- ✅ **Aggiornamenti in Tempo Reale**: Entrambi i pannelli si aggiornano automaticamente quando si verificano nuovi errori tramite eventi WebSocket

---

## Analisi Errori Potenziata da AI

ComfyUI-Doctor si integra con popolari servizi LLM per fornire suggerimenti di debug intelligenti e consapevoli del contesto.

### Provider AI Supportati

#### Servizi Cloud

- **OpenAI** (GPT-4, GPT-4o, ecc.)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - inferenza LPU ultra-veloce)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Accesso a Claude, GPT-4 e 100+ modelli)

#### Servizi Locali (Nessuna API Key Richiesta)

- **Ollama** (`http://127.0.0.1:11434`) - Esegui Llama, Mistral, CodeLlama localmente
- **LMStudio** (`http://localhost:1234/v1`) - Inferenza modello locale con GUI

> **💡 Compatibilità Cross-Platform**: Gli URL predefiniti possono essere sovrascritti tramite variabili d'ambiente:
>
> - `OLLAMA_BASE_URL` - Endpoint Ollama personalizzato (default: `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - Endpoint LMStudio personalizzato (default: `http://localhost:1234/v1`)
>
> Questo previene conflitti tra istanze Ollama Windows e WSL2, o quando si esegue in Docker/setup personalizzati.

### Configurazione

![Pannello Impostazioni](./assets/settings.png)

Configura l'analisi AI nel pannello **Barra Laterale Doctor** → **Settings**:

1. **AI Provider**: Seleziona dal menu a discesa. La Base URL si compilerà automaticamente.
2. **AI Base URL**: L'endpoint API (auto-popolato, ma personalizzabile)
3. **AI API Key**: La tua chiave API (lascia vuoto per LLM locali come Ollama/LMStudio)
4. **AI Model Name**:
   - Seleziona un modello dalla lista a discesa (popolata automaticamente dall'API del tuo provider)
   - Clicca il pulsante di aggiornamento 🔄 per ricaricare i modelli disponibili
   - O spunta "Inserisci nome modello manualmente" per digitare un nome modello personalizzato
5. **Modalità Privacy**: Seleziona il livello di sanificazione PII per i servizi AI cloud (vedi sezione [Modalità Privacy (Sanificazione PII)](#modalità-privacy-sanificazione-pii) sotto per dettagli)

### Utilizzo Analisi AI

1. Il pannello Doctor si apre automaticamente quando si verifica un errore.
2. Rivedi i suggerimenti integrati, o clicca il pulsante ✨ Analyze with AI sulla scheda errore.
3. Attendi che l'LLM analizzi l'errore (tipicamente 3-10 secondi).
4. Rivedi i suggerimenti di debug generati dall'AI.

**Nota sulla Sicurezza**: La tua chiave API viene trasmessa in modo sicuro dal frontend al backend solo per la richiesta di analisi. Non viene mai registrata o memorizzata in modo persistente.

### Modalità Privacy (Sanificazione PII)

ComfyUI-Doctor include la **sanificazione automatica PII (Personally Identifiable Information)** per proteggere la tua privacy quando invii messaggi di errore ai servizi AI cloud.

**Tre Livelli di Privacy**:

| Livello | Descrizione | Cosa viene rimosso | Consigliato Per |
| ----- | ----------- | --------------- | --------------- |
| **None** | Nessuna sanificazione | Nulla | LLM Locali (Ollama, LMStudio) |
| **Basic** (Default) | Protezione standard | Percorsi utente, API key, email, indirizzi IP | La maggior parte degli utenti con LLM Cloud |
| **Strict** | Massima privacy | Tutto del Basic + IPv6, fingerprint SSH | Requisiti Enterprise/Compliance |

**Cosa viene Sanificato** (Livello Basic):

- ✅ Percorsi utente Windows: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Home Linux/macOS: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API key: `sk-abc123...` → `<API_KEY>`
- ✅ Indirizzi email: `user@example.com` → `<EMAIL>`
- ✅ IP Privati: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ Credenziali URL: `https://user:pass@host` → `https://<USER>@host`

**Cosa NON viene Rimosso**:

- ❌ Messaggi di errore (necessari per il debug)
- ❌ Nomi modelli, nomi nodi
- ❌ Struttura workflow
- ❌ Percorsi file pubblici (`/usr/bin/python`)

**Configura Modalità Privacy**: Apri Barra Laterale Doctor → Settings → Menu a discesa 🔒 Privacy Mode. I cambiamenti si applicano immediatamente a tutte le richieste di analisi AI.

**Conformità GDPR**: Questa funzionalità supporta l'Articolo 25 GDPR (Protezione dei dati fin dalla progettazione) ed è raccomandata per le implementazioni aziendali.

### Dashboard Statistiche

![Pannello Statistiche](assets/statistics_panel.png)

La **Dashboard Statistiche** fornisce approfondimenti in tempo reale sui pattern di errore e sui trend di stabilità del tuo ComfyUI.

**Caratteristiche**:

- **📊 Trend Errori**: Errori totali e conteggi per le ultime 24h/7g/30g
- **🔥 Pattern Errore Top**: I 5 tipi di errore più frequenti con conteggi delle occorrenze
- **📈 Ripartizione Categorie**: Ripartizione visiva per categoria di errore (Memoria, Workflow, Caricamento Modelli, Framework, Generico)
- **✅ Tracciamento Risoluzione**: Traccia errori risolti, irrisolti e ignorati
- **🧭 Controlli stato**: Marca l’ultimo errore come Risolto / Irrisolto / Ignorato dalla scheda Statistiche

**Come Usare**:

1. Apri la barra laterale Doctor (clicca icona 🏥 a sinistra)
2. Trova la sezione comprimibile **📊 Statistiche Errori**
3. Clicca per espandere e visualizzare le tue analisi degli errori
4. Usa i pulsanti **Segna come** per impostare lo stato dell’ultimo errore (Risolto / Irrisolto / Ignorato)

**Controlli dello stato di risoluzione**:

- I pulsanti sono abilitati solo quando è disponibile il timestamp dell’ultimo errore
- Gli aggiornamenti di stato vengono salvati nella cronologia e aggiornano automaticamente il tasso di risoluzione

**Comprendere i Dati**:

- **Total (30d)**: Errori cumulativi negli ultimi 30 giorni
- **Last 24h**: Errori nelle ultime 24 ore (aiuta a identificare problemi recenti)
- **Resolution Rate (Tasso di Risoluzione)**: Mostra i progressi verso la risoluzione dei problemi noti
  - 🟢 **Resolved**: Problemi che hai risolto
  - 🟠 **Unresolved**: Problemi attivi che richiedono attenzione
  - ⚪ **Ignored**: Problemi non critici che hai scelto di ignorare
- **Top Patterns**: Identifica quali tipi di errore necessitano di attenzione prioritaria
- **Categories**: Ti aiuta a capire se i problemi sono legati alla memoria, problemi di workflow, fallimenti nel caricamento modelli, ecc.

**Persistenza Stato Pannello**: Lo stato aperto/chiuso del pannello è salvato nel localStorage del tuo browser, quindi la tua preferenza persiste tra le sessioni.

### Esempio Setup Provider

| Provider         | Base URL                                                   | Esempio Modello              |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI           | `https://api.openai.com/v1`                                | `gpt-4o`                     |
| DeepSeek         | `https://api.deepseek.com/v1`                              | `deepseek-chat`              |
| Groq             | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`    |
| Gemini           | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`           |
| Ollama (Locale)  | `http://localhost:11434/v1`                                | `llama3.1:8b`                |
| LMStudio (Locale)| `http://localhost:1234/v1`                                 | Modello caricato in LMStudio |

---

## Impostazioni

Puoi personalizzare il comportamento di ComfyUI-Doctor tramite il pannello Impostazioni di ComfyUI (Icona Ingranaggio).

### 1. Show error notifications (Mostra notifiche errore)

**Funzione**: Attiva/disattiva le schede di notifica errore fluttuanti (toasts) nell'angolo in alto a destra.
**Utilizzo**: Disabilita se preferisci controllare gli errori manualmente nella barra laterale senza interruzioni visive.

### 2. Auto-open panel on error (Apri automaticamente pannello su errore)

**Funzione**: Espande automaticamente la barra laterale Doctor quando viene rilevato un nuovo errore.
**Utilizzo**: **Consigliato**. Fornisce accesso immediato ai risultati diagnostici senza clic manuali.

### 3. Error Check Interval (ms)

**Funzione**: Frequenza dei controlli errore frontend-backend (in millisecondi). Default: `2000`.
**Utilizzo**: Valori più bassi (es. 500) danno feedback più rapido ma aumentano il carico; valori più alti (es. 5000) risparmiano risorse.

### 4. Suggestion Language (Lingua suggerimenti)

**Funzione**: Lingua per i report diagnostici e i suggerimenti del Doctor.
**Utilizzo**: Attualmente supporta Inglese, Cinese Tradizionale, Cinese Semplificato e Giapponese (altre in arrivo). I cambiamenti si applicano ai nuovi errori.

### 5. Enable Doctor (requires restart)

**Funzione**: Interruttore principale per il sistema di intercettazione log.
**Utilizzo**: Spegni per disabilitare completamente le funzionalità principali di Doctor (richiede riavvio ComfyUI).

### 6. AI Provider

**Funzione**: Seleziona il tuo fornitore di servizi LLM preferito da un menu a discesa.
**Opzioni**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Locale), LMStudio (Locale), Custom.
**Utilizzo**: Selezionando un provider si compila automaticamente la Base URL appropriata. Per provider locali (Ollama/LMStudio), un avviso mostra i modelli disponibili.

### 7. AI Base URL

**Funzione**: L'endpoint API per il tuo servizio LLM.
**Utilizzo**: Compilato automaticamente quando selezioni un provider, ma può essere personalizzato per endpoint self-hosted o personalizzati.

### 8. AI API Key

**Funzione**: La tua chiave API per l'autenticazione con servizi LLM cloud.
**Utilizzo**: Richiesto per provider cloud (OpenAI, DeepSeek, ecc.). Lascia vuoto per LLM locali (Ollama, LMStudio).
**Sicurezza**: La chiave viene trasmessa solo durante le richieste di analisi e non viene mai registrata o persistita.

### 9. AI Model Name

**Funzione**: Specifica quale modello usare per l'analisi degli errori.
**Utilizzo**:

- **Modalità Dropdown** (default): Seleziona un modello dalla lista popolata automaticamente. Clicca il pulsante di aggiornamento 🔄 per ricaricare i modelli disponibili.
- **Modalità Input Manuale**: Spunta "Inserisci nome modello manualmente" per digitare un nome modello personalizzato (es. `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- I modelli vengono recuperati automaticamente dall'API del tuo provider selezionato quando cambi provider o clicchi aggiorna.
- Per gli LLM locali (Ollama/LMStudio), il menu a discesa mostra tutti i modelli disponibili localmente.

### 10. Fiducia e Salute (Trust & Health)

**Funzione**: Visualizza lo stato di salute del sistema e il rapporto di fiducia dei plugin.
**Utilizzo**: Clicca sul pulsante di aggiornamento 🔄 per recuperare i dati di `/doctor/health`.

**Visualizza**:

- **Pipeline Status**: Stato attuale della pipeline di analisi
- **SSRF Blocked**: Conteggio delle richieste in uscita sospette bloccate
- **Dropped Logs**: Conteggio dei messaggi di log scartati a causa della contropressione
- **Plugin Trust List**: Mostra tutti i plugin rilevati con badge di stato:
  - 🟢 **Trusted**: Plugin in whitelist con manifesto valido
  - 🟡 **Unsigned**: Plugin senza manifesto (usare con cautela)
  - 🔴 **Blocked**: Plugin in blacklist

### 11. Telemetria Anonima (In Costruzione 🚧)

**Funzione**: Adesione facoltativa alla raccolta di dati anonimi sull'utilizzo per aiutare a migliorare Doctor.
**Stato**: **In Costruzione** — Attualmente solo locale, nessun caricamento in rete.

**Controlli**:

- **Toggle**: Abilita/disabilita la registrazione della telemetria (default: OFF)
- **View Buffer**: Ispeziona gli eventi nel buffer prima del caricamento
- **Clear All**: Elimina tutti i dati di telemetria nel buffer
- **Export**: Scarica i dati nel buffer come JSON per la revisione

**Garanzie di Privacy**:

- ✅ **Solo Opt-in**: Nessun dato viene registrato fino all'attivazione esplicita
- ✅ **Solo Locale**: Attualmente memorizza i dati solo localmente (`Upload destination: None`)
- ✅ **Rilevamento PII**: Filtra automaticamente le informazioni sensibili
- ✅ **Trasparenza Totale**: Visualizza/esporta tutti i dati prima di qualsiasi caricamento futuro

---

## Endpoint API

### GET `/debugger/last_analysis`

Recupera l'analisi dell'errore più recente:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**Esempio Risposta**:

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja"],
  "last_error": "Traceback...",
  "suggestion": "SUGGESTION: ...",
  "timestamp": "2025-12-28T06:49:11",
  "node_context": {
    "node_id": "42",
    "node_name": "KSampler",
    "node_class": "KSamplerNode",
    "custom_node_path": "ComfyUI-Impact-Pack"
  }
}
```

### GET `/debugger/history`

Recupera la cronologia errori (ultime 20 voci):

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

Cambia la lingua dei suggerimenti (vedi sezione Cambio Lingua).

### POST `/doctor/analyze`

Analizza un errore usando il servizio LLM configurato.

**Payload**:

```json
{
  "error": "Traceback...",
  "node_context": {...},
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "en"
}
```

**Risposta**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

Verifica la validità della chiave API testando la connessione al provider LLM.

**Payload**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**Risposta**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

Elenca i modelli disponibili dal provider LLM configurato.

**Payload**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**Risposta**:

```json
{
  "success": true,
  "models": [
    {"id": "llama3.1:8b", "name": "llama3.1:8b"},
    {"id": "mistral:7b", "name": "mistral:7b"}
  ],
  "message": "Found 2 models"
}
```

---

## File di Log

Tutti i log sono memorizzati in:

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

Formato nome file: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

Il sistema mantiene automaticamente i 10 file di log più recenti (configurabile tramite `config.json`).

---

## Configurazione

Crea `config.json` per personalizzare il comportamento:

```json
{
  "max_log_files": 10,
  "buffer_limit": 100,
  "traceback_timeout_seconds": 5.0,
  "history_size": 20,
  "default_language": "zh_TW",
  "enable_api": true,
  "privacy_mode": "basic"
}
```

**Parametri**:

- `max_log_files`: Numero massimo di file di log da mantenere
- `buffer_limit`: Dimensione buffer traceback (conteggio righe)
- `traceback_timeout_seconds`: Timeout per traceback incompleti
- `history_size`: Numero di errori da mantenere nella cronologia
- `default_language`: Lingua predefinita dei suggerimenti
- `enable_api`: Abilita endpoint API
- `privacy_mode`: Livello di sanificazione PII - `"none"`, `"basic"` (default), o `"strict"`

---

## Pattern di Errore Supportati

ComfyUI-Doctor può rilevare e fornire suggerimenti per:

- Discrepanze di tipo (es. fp16 vs float32)
- Discrepanze di dimensione
- CUDA/MPS memoria esaurita (OOM)
- Errori di moltiplicazione matrici
- Conflitti dispositivo/tipo
- Moduli Python mancanti
- Fallimenti asserzione
- Errori Chiave/Attributo
- Discrepanze forma (Shape mismatches)
- Errori file non trovato
- Errori caricamento SafeTensors
- Fallimenti esecuzione CUDNN
- Libreria InsightFace mancante
- Discrepanze Modello/VAE
- Prompt JSON non valido

E altro...

---

## Suggerimenti

1. **Abbina con ComfyUI Manager**: Installa nodi personalizzati mancanti automaticamente
2. **Controlla file di log**: Traceback completi sono registrati per la segnalazione problemi
3. **Usa la barra laterale integrata**: Clicca l'icona 🏥 Doctor nel menu sinistro per diagnostica in tempo reale
4. **Debug Nodo**: Collega nodi Debug per ispezionare flussi di dati sospetti

---

## Licenza

MIT License

---

## Contribuire

I contributi sono benvenuti! Sentiti libero di inviare una Pull Request.

**Segnala Problemi**: Trovato un bug o hai un suggerimento? Apri un issue su GitHub.
**Invia PR**: Aiuta a migliorare la codebase con correzioni di bug o miglioramenti generali.
**Richieste Funzionalità**: Hai idee per nuove funzionalità? Faccelo sapere per favore.
