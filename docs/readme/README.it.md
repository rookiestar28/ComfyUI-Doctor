# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | Italiano | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor e un assistente di diagnostica e debug in tempo reale per ComfyUI. Cattura errori runtime, identifica il probabile contesto del nodo, mostra suggerimenti locali e puo usare opzionalmente una chat LLM per analisi piu approfondite.

## Stato attuale

- Aggiunti controlli di compatibilita host per ComfyUI, ComfyUI frontend e Desktop.
- L'integrazione delle impostazioni frontend preferisce l'attuale ComfyUI settings API, con legacy fallback isolati in un adattatore di compatibilita.
- Gli errori di esecuzione possono essere arricchiti con lineage dagli eventi recenti execution/progress.
- Strict admin-token mode disponibile per server condivisi, con avvisi piu chiari per loopback convenience mode.
- Server-side credential store documenta metadati di cifratura e l'attuale design encrypt-then-MAC.
- Aggiunta una coverage baseline lane opzionale; il full validation flow predefinito resta invariato.

## Funzioni principali

- Monitoraggio di console e traceback dall'avvio di ComfyUI.
- 58 pattern di errore JSON: 22 core patterns e 36 community extension patterns.
- Estrazione di node ID, name, class e custom-node path quando gli eventi host lo consentono.
- Doctor sidebar con tab Chat, Statistics e Settings.
- Workflow LLM per OpenAI-compatible APIs, Anthropic, Gemini, xAI, OpenRouter, Ollama e LMStudio.
- Privacy modes per mascherare path, credential-looking values, email e private IP prima delle richieste Cloud LLM.
- Server-side credential store opzionale, admin-gated, con encryption-at-rest.
- Diagnostics, statistics, plugin trust report, telemetry controls e community feedback preview/submit.
- Supporto per inglese, cinese tradizionale, cinese semplificato, giapponese, coreano, tedesco, francese, italiano e spagnolo.

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

Dopo il riavvio, **Doctor** dovrebbe apparire nella sidebar sinistra.

## Uso di base

- **Diagnostica automatica**: Doctor cattura gli errori, li confronta con pattern noti e mostra l'ultima diagnosi.
- **Doctor Sidebar**: Chat per errore corrente e conversazioni LLM; Statistics per trend, diagnostica e health information; Settings per language, provider, model, privacy e credential source.
- **Smart Debug Node**: Inseriscilo in una connessione workflow per ispezionare type, shape, dtype, device e statistiche senza modificare l'output.

## Documentazione

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## Validazione

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## Licenza

MIT License
