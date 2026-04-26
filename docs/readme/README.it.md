# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | Italiano | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor è un assistente di diagnostica e debug in tempo reale per ComfyUI. Cattura gli errori runtime, identifica il probabile contesto del nodo, mostra suggerimenti locali applicabili e può usare opzionalmente un workflow di chat LLM per una risoluzione dei problemi più approfondita.

## Ultimi aggiornamenti

Gli ultimi aggiornamenti sono mantenuti nel README inglese. Vedi [Latest Updates](../../README.md#latest-updates---click-to-expand).

## Funzionalità principali

- Cattura in tempo reale dell'output console/error di ComfyUI fin dall'avvio.
- Suggerimenti integrati da 58 pattern di errore basati su JSON, inclusi 22 core patterns e 36 community-extension patterns.
- Estrazione validata del contesto del nodo per errori recenti di esecuzione workflow quando ComfyUI fornisce dati evento sufficienti.
- Sidebar Doctor con tab Chat, Statistics e Settings.
- Analisi LLM opzionale tramite OpenAI-compatible services, Anthropic, Gemini, xAI, OpenRouter, Ollama e LMStudio, con gestione unificata di provider request/response.
- Privacy controls per richieste LLM in uscita, inclusi modi di sanitization per path, chiavi, email e IP.
- Credential store lato server opzionale con admin guarding e supporto encryption-at-rest.
- Diagnostics locali, statistics, plugin trust report, telemetry controls e strumenti community feedback preview/submit.
- JSON error envelopes coerenti per gli errori dell'API Doctor.
- Supporto completo di UI e suggerimenti in inglese, cinese tradizionale, cinese semplificato, giapponese, coreano, tedesco, francese, italiano e spagnolo.

## Screenshot

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## Installazione

### ComfyUI-Manager

1. Apri ComfyUI e fai clic su **Manager**.
2. Seleziona **Install Custom Nodes**.
3. Cerca `ComfyUI-Doctor`.
4. Installa e riavvia ComfyUI.

### Installazione manuale

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Riavvia ComfyUI dopo il clone. Doctor dovrebbe stampare i suoi diagnostics di avvio e registrare la voce sidebar `Doctor`.

## Uso di base

### Diagnostica automatica

Dopo l'installazione, Doctor registra passivamente l'output runtime di ComfyUI, rileva tracebacks, abbina pattern di errore noti e mostra l'ultima diagnosi nella sidebar e nel pannello report destro opzionale.
Quando si usa l'analisi LLM opzionale, Doctor costruisce il prompt context dalla stessa pipeline strutturata che gestisce sanitization, node context, execution logs, workflow pruning e informazioni di sistema.

### Sidebar Doctor

Apri **Doctor** nella sidebar sinistra di ComfyUI:

- **Chat**: rivedi l'ultimo contesto di errore e fai domande di debug successive.
- **Statistics**: ispeziona trend recenti degli errori, diagnostics, trust/health information, telemetry controls e feedback tools.
- **Settings**: scegli lingua, LLM provider, base URL, model, privacy mode, comportamento auto-open e credential storage lato server opzionale.

### Smart Debug Node

Fai clic destro sul canvas, aggiungi **Smart Debug Node** e posizionalo inline per ispezionare i dati in transito senza modificare l'output del workflow.

## Configurazione LLM opzionale

I cloud providers richiedono un credential fornito tramite session-only UI field, variabili d'ambiente o server store opzionale protetto da admin. Provider locali come Ollama e LMStudio possono funzionare senza cloud credential.
Doctor normalizza i formati provider-specific request/response per OpenAI-compatible APIs, Anthropic e Ollama, così chat, single-shot analysis, model listing e connectivity checks condividono lo stesso comportamento backend.

Impostazioni consigliate:

- Usa **Privacy Mode: Basic** o **Strict** per cloud providers.
- Usa variabili d'ambiente per ambienti condivisi o simili alla produzione.
- Imposta `DOCTOR_ADMIN_TOKEN` e `DOCTOR_REQUIRE_ADMIN_TOKEN=1` sui server condivisi.
- Mantieni il local-only loopback convenience mode solo per uso desktop single-user.

## Documentazione

- [User Guide](../USER_GUIDE.md): UI walkthrough, diagnostics, privacy modes, LLM setup e feedback flow.
- [Configuration and Security](../CONFIGURATION_SECURITY.md): environment variables, admin guard behavior, credential storage, outbound safety, telemetry e CSP notes.
- [API Reference](../API_REFERENCE.md): endpoint pubblici Doctor e debugger.
- [Validation Guide](../VALIDATION.md): comandi full-gate locali e lanes opzionali compatibility/coverage.
- [Plugin Guide](../PLUGIN_GUIDE.md): community plugin trust model e plugin authoring notes.
- [Plugin Migration](../PLUGIN_MIGRATION.md): migration tooling per plugin manifests e allowlists.
- [Outbound Safety](../OUTBOUND_SAFETY.md): static checker e outbound request safety rules.

## Pattern di errore supportati

I pattern sono archiviati come file JSON in `patterns/` e possono essere aggiornati senza modifiche al codice.

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

I community packs coprono attualmente modalità di errore comuni di ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, checkpoint, sampler, scheduler e CLIP.

## Validazione

Per la validazione locale CI-parity, usa il full-test script del progetto:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Il full gate copre secrets detection, pre-commit hooks, host-like startup validation, backend unit tests e frontend Playwright E2E tests. Vedi la [Validation Guide](../VALIDATION.md) per i comandi staged espliciti e le lanes opzionali.

## Requisiti

- Ambiente ComfyUI custom-node.
- Python 3.10 o più recente.
- Node.js 18 o più recente solo per frontend E2E validation.
- Non è richiesta alcuna runtime Python package dependency oltre all'ambiente bundled di ComfyUI e alla Python standard library.

## Licenza

MIT License

## Contribuire

Sono benvenuti contributi ai pattern e alla documentazione. Per modifiche al codice, esegui il full validation gate prima di aprire una pull request ed evita di committare stato locale generato, log, credentials o file interni di planning.
