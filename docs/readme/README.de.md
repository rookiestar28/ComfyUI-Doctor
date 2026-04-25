# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | Deutsch | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor ist ein Echtzeit-Diagnose- und Debugging-Assistent fuer ComfyUI. Er erfasst Laufzeitfehler, erkennt wahrscheinlichen Node-Kontext, zeigt lokale Handlungsvorschlaege und kann optional einen LLM-Chat fuer tiefere Fehleranalyse nutzen.

## Aktueller Stand

- Host-Kompatibilitaetspruefungen fuer ComfyUI, ComfyUI frontend und Desktop wurden ergaenzt.
- Die Frontend-Einstellungen bevorzugen die aktuelle ComfyUI settings API; legacy fallback bleibt in einem Kompatibilitaetsadapter isoliert.
- Ausfuehrungsfehler koennen mit lineage aus aktuellen execution/progress events angereichert werden.
- Shared-server deployments koennen strict admin-token mode aktivieren; loopback convenience mode meldet klarere Warnungen.
- Server-side credential store dokumentiert Verschluesselungsmetadaten und das aktuelle encrypt-then-MAC design.
- Eine optionale coverage baseline lane wurde ergaenzt; die standardmaessige full validation flow bleibt unveraendert.

## Kernfunktionen

- Ueberwachung von console und traceback ab ComfyUI-Start.
- 58 JSON-Fehlermuster: 22 core patterns und 36 community extension patterns.
- Extraktion von node ID, name, class und custom-node path, sofern Host-Events genug Kontext liefern.
- Doctor sidebar mit Chat-, Statistics- und Settings-Tabs.
- LLM workflow fuer OpenAI-compatible APIs, Anthropic, Gemini, xAI, OpenRouter, Ollama und LMStudio.
- Privacy modes maskieren path, credential-looking values, email und private IP vor Cloud-LLM-Anfragen.
- Optionaler admin-gated server-side credential store mit encryption-at-rest.
- Diagnostics, statistics, plugin trust report, telemetry controls und community feedback preview/submit.
- Unterstuetzt Englisch, Traditionelles Chinesisch, Vereinfachtes Chinesisch, Japanisch, Koreanisch, Deutsch, Franzoesisch, Italienisch und Spanisch.

## Installation

### ComfyUI-Manager

1. ComfyUI oeffnen und **Manager** anklicken.
2. **Install Custom Nodes** auswaehlen.
3. Nach `ComfyUI-Doctor` suchen.
4. Installieren und ComfyUI neu starten.

### Manuelle Installation

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Nach dem Neustart sollte **Doctor** in der linken sidebar erscheinen.

## Grundlegende Nutzung

- **Automatische Diagnose**: Doctor erfasst Fehler, vergleicht bekannte Muster und zeigt die neueste Diagnose.
- **Doctor Sidebar**: Chat fuer aktuelle Fehler und LLM-Gespraeche; Statistics fuer Trends, Diagnose und health information; Settings fuer language, provider, model, privacy und credential source.
- **Smart Debug Node**: In workflow-Verbindungen einfuegen, um type, shape, dtype, device und Statistiken zu pruefen, ohne die Ausgabe zu veraendern.

## Dokumentation

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## Validierung

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## Lizenz

MIT License
