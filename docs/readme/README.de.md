# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | Deutsch | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor ist ein Echtzeit-Diagnose- und Debugging-Assistent für ComfyUI. Er erfasst Laufzeitfehler, identifiziert wahrscheinlichen Node-Kontext, zeigt umsetzbare lokale Hinweise an und kann optional einen LLM-Chat-Workflow für tiefere Fehlersuche verwenden.

## Neueste Änderungen

Die neuesten Änderungen werden in der englischen README gepflegt. Siehe [Latest Updates](../../README.md#latest-updates---click-to-expand).

## Kernfunktionen

- Echtzeit-Erfassung von ComfyUI console/error-Ausgaben ab dem Start.
- Integrierte Vorschläge aus 58 JSON-basierten Fehlermustern, darunter 22 core patterns und 36 community-extension patterns.
- Validierte Node-Kontextextraktion für aktuelle workflow-Ausführungsfehler, wenn ComfyUI genügend Ereignisdaten bereitstellt.
- Doctor-Sidebar mit Chat-, Statistics- und Settings-Tabs.
- Optionale LLM-Analyse über OpenAI-compatible services, Anthropic, Gemini, xAI, OpenRouter, Ollama und LMStudio mit einheitlicher provider request/response-Verarbeitung.
- Privacy controls für ausgehende LLM-Anfragen, einschließlich Sanitization-Modi für Pfade, Schlüssel, E-Mails und IP-Adressen.
- Optionaler serverseitiger credential store mit admin guarding und encryption-at-rest support.
- Lokale diagnostics, statistics, plugin trust report, telemetry controls und community feedback preview/submit tools.
- Konsistente JSON error envelopes für Doctor API-Fehler.
- Vollständige UI- und Vorschlagssprachunterstützung für Englisch, traditionelles Chinesisch, vereinfachtes Chinesisch, Japanisch, Koreanisch, Deutsch, Französisch, Italienisch und Spanisch.

## Screenshots

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## Installation

### ComfyUI-Manager

1. Öffne ComfyUI und klicke auf **Manager**.
2. Wähle **Install Custom Nodes**.
3. Suche nach `ComfyUI-Doctor`.
4. Installiere es und starte ComfyUI neu.

### Manuelle Installation

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Starte ComfyUI nach dem Clone neu. Doctor sollte seine Startdiagnose ausgeben und den `Doctor`-Sidebar-Eintrag registrieren.

## Grundlegende Verwendung

### Automatische Diagnose

Nach der Installation zeichnet Doctor die ComfyUI-Laufzeitausgabe passiv auf, erkennt Tracebacks, gleicht bekannte Fehlermuster ab und zeigt die neueste Diagnose in der Sidebar und im optionalen rechten Berichtspanel an.
Bei optionaler LLM-Analyse erstellt Doctor den prompt context über dieselbe strukturierte Pipeline, die Sanitization, Node-Kontext, Ausführungslogs, workflow pruning und Systeminformationen verarbeitet.

### Doctor-Sidebar

Öffne **Doctor** in der linken Sidebar von ComfyUI:

- **Chat**: aktuellen Fehlerkontext prüfen und weitere Debugging-Fragen stellen.
- **Statistics**: aktuelle Fehlertrends, diagnostics, trust/health information, telemetry controls und feedback tools prüfen.
- **Settings**: Sprache, LLM provider, base URL, model, privacy mode, Auto-Open-Verhalten und optionalen serverseitigen credential storage auswählen.

### Smart Debug Node

Klicke mit der rechten Maustaste auf den Canvas, füge **Smart Debug Node** hinzu und platziere ihn inline, um durchlaufende Daten zu prüfen, ohne den workflow output zu verändern.

## Optionale LLM-Einrichtung

Cloud provider benötigen ein credential, das über das session-only UI field, Umgebungsvariablen oder den optionalen admin-gated server store bereitgestellt wird. Lokale provider wie Ollama und LMStudio können ohne cloud credential laufen.
Doctor normalisiert provider-specific request/response-Formate für OpenAI-compatible APIs, Anthropic und Ollama, sodass chat, single-shot analysis, model listing und connectivity checks dasselbe Backend-Verhalten teilen.

Empfohlene Defaults:

- Für cloud provider **Privacy Mode: Basic** oder **Strict** verwenden.
- In gemeinsam genutzten oder produktionsähnlichen Umgebungen Umgebungsvariablen verwenden.
- Auf gemeinsam genutzten Servern `DOCTOR_ADMIN_TOKEN` und `DOCTOR_REQUIRE_ADMIN_TOKEN=1` setzen.
- Den local-only loopback convenience mode nur für Single-User-Desktop-Nutzung behalten.

## Dokumentation

- [User Guide](../USER_GUIDE.md): UI walkthrough, diagnostics, privacy modes, LLM setup und feedback flow.
- [Configuration and Security](../CONFIGURATION_SECURITY.md): environment variables, admin guard behavior, credential storage, outbound safety, telemetry und CSP notes.
- [API Reference](../API_REFERENCE.md): öffentliche Doctor- und debugger endpoints.
- [Validation Guide](../VALIDATION.md): lokale full-gate commands und optionale compatibility/coverage lanes.
- [Plugin Guide](../PLUGIN_GUIDE.md): community plugin trust model und plugin authoring notes.
- [Plugin Migration](../PLUGIN_MIGRATION.md): migration tooling für plugin manifests und allowlists.
- [Outbound Safety](../OUTBOUND_SAFETY.md): static checker und outbound request safety rules.

## Unterstützte Fehlermuster

Patterns werden als JSON-Dateien unter `patterns/` gespeichert und können ohne Codeänderungen aktualisiert werden.

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

Community packs decken derzeit häufige Fehlermodi für ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, checkpoint, sampler, scheduler und CLIP ab.

## Validierung

Für lokale CI-parity validation verwende das full-test script des Projekts:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Das full gate umfasst secrets detection, pre-commit hooks, host-like startup validation, backend unit tests und frontend Playwright E2E tests. Explizite staged commands und optionale lanes stehen im [Validation Guide](../VALIDATION.md).

## Anforderungen

- ComfyUI custom-node environment.
- Python 3.10 oder neuer.
- Node.js 18 oder neuer nur für frontend E2E validation.
- Zur Laufzeit ist keine zusätzliche Python package dependency über ComfyUIs bundled environment und die Python standard library hinaus erforderlich.

## Lizenz

MIT License

## Mitwirken

Beiträge zu Patterns und Dokumentation sind willkommen. Führe bei Codeänderungen vor dem Öffnen eines pull request das vollständige validation gate aus und vermeide das Committen generierter lokaler Zustände, Logs, credentials oder interner planning files.
