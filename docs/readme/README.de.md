# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | Deutsch | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [Roadmap & Entwicklungsstatus](../ROADMAP.md)

Eine kontinuierliche Echtzeit-Laufzeitdiagnose-Suite für ComfyUI mit **KI-gestützter Analyse**, **interaktivem Debugging-Chat** und **50+ Fehlerbehebungsmustern**. Fängt automatisch alle Terminalausgaben ab dem Start ab, erfasst vollständige Python-Tracebacks und liefert priorisierte Korrekturvorschläge mit Kontext-Extraktion auf Knotenebene. Unterstützt jetzt **JSON-basiertes Mustermanagement** mit Hot-Reload und **vollständige i18n-Unterstützung** für 9 Sprachen (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

## Neueste Updates (Jan 2026) - Zum Erweitern klicken

<details>
<summary><strong>Neues Feature: F14 Proaktive Diagnose (Health Checks + Intent Signature)</strong></summary>

- Im **Statistik (Statistics)** Tab wurde ein **Diagnose (Diagnostics)** Bereich hinzugefügt, um Workflow-Probleme proaktiv ohne LLM zu beheben.
- **Health Check**: Beinhaltet Workflow-Checks (Linting), Umgebungs-Assets (env assets) und Datenschutz-Checks sowie umsetzbare Korrekturvorschläge.
- **Intent Signature**: Deterministisches Absichts-Inferenzsystem, das **Top-K Absichten + Beweise** liefert, um zu beurteilen, was der Workflow "versucht zu tun".
- Enthält UX-Härtung: Sichere Fallbacks (z.B. "Keine dominante Absicht erkannt") und verbesserte Beweisbereinigung.

</details>

<details>
<summary><strong>(v1.5.8) QoL: Auto-open Right Error Report Panel Toggle</strong></summary>

- Added a **dedicated toggle** in **Doctor → Settings** to control whether the **right-side error report panel** auto-opens when a new error is detected.
- **Default: ON** for new installs, and the choice is persisted.

</details>

<details>
<summary><strong>Smart Token Budget Management (v1.5.0)</strong></summary>

**Intelligentes Kontextmanagement (Kostenoptimierung):**

- **Automatisches Trimming**: Für Remote-LLMs (60-80% Token-Reduktion)
- **Progressive Strategie**: Workflow-Pruning → Systeminfo entfernen → Traceback kürzen
- **Lokaler Opt-in**: Sanftes Trimming für Ollama/LMStudio (12K/16K Limits)
- **Erweiterte Observability**: Schritt-für-Schritt Token-Tracking & A/B Validierung

**Netzwerk-Resilienz:**

- **Exponentieller Backoff**: Automatischer Retry bei 429/5xx Fehlern (mit Jitter)
- **Streaming-Schutz**: 30s Timeout-Watchdog für blockierte SSE-Chunks
- **Rate & Concurrency Limits**: Token Bucket (30/Min) + Concurrency Semaphore (max 3)

**Neue Konfiguration:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | Smart Budget aktivieren (Remote) |
| `retry_max_attempts` | `3` | Max Retries |
| `stream_chunk_timeout` | `30` | Stream Timeout (Sek) |

</details>

<details>
<summary><strong>Wichtige Korrektur: R0/R13 Pipeline-Governance & Plugin-Sicherheit (v1.4.5)</strong></summary>

**Sicherheits-Härtung:**

- **SSRF-Schutz++**: Ersetzung von Teilstring-Prüfungen durch korrektes Host/Port-Parsing; Blockierung ausgehender Weiterleitungen (`allow_redirects=False`)
- **Outbound-Sanitization-Funnel**: Eine einzige Grenze (`outbound.py`) garantiert die Bereinigung ALLER externen Payloads; `privacy_mode=none` nur für verifizierte lokale LLMs erlaubt

**Plugin-Vertrauenssystem:**

- **Sicher-nach-Standard**: Plugins standardmäßig deaktiviert, explizite Allowlist + Manifest/SHA256 erforderlich
- **Vertrauensklassifizierung**: `trusted` (vertrauenswürdig) | `unsigned` (unsigniert) | `untrusted` (nicht vertrauenswürdig) | `blocked` (blockiert)
- **Dateisystem-Eindämmung**: realpath-Eindämmung, Symlink-Verweigerung, Größenbeschränkungen, strenge Dateinamenregeln
- **Optionale HMAC-Signierung**: Integritätsprüfung mit gemeinsamem Geheimnis (keine Public-Key-Signierung)

**Pipeline-Governance:**

- **Metadaten-Verträge**: Schema-Versionierung + Validierung nach Ausführung + Quarantäne für ungültige Schlüssel
- **Abhängigkeitsrichtlinie**: Erzwungenes `requires/provides`; fehlende Abhängigkeit → Stufe überspringen, Status `degraded` (beeinträchtigt)
- **Logger-Rückstau**: Prioritätsbewusste `DroppingQueue` + Drop-Metriken
- **Übergabe vor dem Start**: Saubere Deinstallation des Loggers, bevor der SmartLogger übernimmt

**Beobachtbarkeit:**

- `/doctor/health` Endpunkt: Stellt Warteschlangen-Metriken, Drop-Zähler, SSRF-Blöcke und Pipeline-Status bereit

**Testergebnisse**: 159 Python-Tests bestanden | 17 Phase-2-Gate-Tests

</details>

<details>
<summary><strong>Verbesserung: CI Gates & Plugin-Tools</strong></summary>

**T11 - Phase 2 Release CI Gate:**

- GitHub Actions Workflow (`phase2-release-gate.yml`): Erzwingt 4 Pytest-Suites + E2E
- Lokales Validierungsskript (`scripts/phase2_gate.py`): Unterstützt `--fast` und `--e2e` Modi

**T12 - Statischer Checker für Outbound-Sicherheit:**

- AST-basierter Analysator (`scripts/check_outbound_safety.py`) erkennt Umgehungsmuster
- 6 Erkennungsregeln: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION`, usw.
- CI Workflow + 8 Unit-Tests + Dokumentation (`docs/OUTBOUND_SAFETY.md`)

**A8 - Plugin-Migrationstools:**

- `scripts/plugin_manifest.py`: Generiert Manifest mit SHA256-Hashes
- `scripts/plugin_allowlist.py`: Scannt Plugins und schlägt Konfiguration vor
- `scripts/plugin_validator.py`: Validiert Manifest und Konfiguration
- `scripts/plugin_hmac_sign.py`: Generiert optionale HMAC-Signaturen
- Dokumentation aktualisiert: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

<details>
<summary><strong>Verbesserung: CSP-Doku & Telemetrie</strong></summary>

**S1 - CSP-Compliance-Doku:**

- Verifiziert, dass alle Assets lokal geladen werden (`web/lib/`); CDN-URLs nur als Fallback
- Abschnitt "CSP Compatibility" zur README hinzugefügt
- Code-Audit abgeschlossen (manuelle Verifizierung ausstehend)

**S3 - Lokale Telemetrie-Infrastruktur:**

- Backend: `telemetry.py` (TelemetryStore, RateLimiter, PII-Erkennung)
- 6 API-Endpunkte: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- Frontend: Einstellungs-UI-Steuerelemente für Telemetrie-Verwaltung
- Sicherheit: Origin-Check (403 Cross-Origin), 1KB Payload-Limit, Feld-Allowlist
- **Standardmäßig AUS**: Keine Aufzeichnung/Netzwerkaktivität, sofern nicht explizit aktiviert
- 81 i18n-Strings (9 Schlüssel × 9 Sprachen)

**Testergebnisse**: 27 Telemetrie-Unit-Tests | 8 E2E-Tests

</details>

<details>
<summary><strong>Verbesserung: E2E-Runner-Härtung & Vertrauens/Gesundheits-UI</strong></summary>

**E2E-Runner-Härtung (WSL `/mnt/c` Support):**

- Playwright-Übersetzungscache-Berechtigungsprobleme unter WSL behoben
- Schreibbares temporäres Verzeichnis (`.tmp/playwright`) unter Repo hinzugefügt
- `PW_PYTHON` Override für plattformübergreifende Kompatibilität

**Vertrauens- & Gesundheits-UI-Panel:**

- "Trust & Health" Panel zum Statistik (Statistics) Tab hinzugefügt
- Zeigt: pipeline_status, ssrf_blocked, dropped_logs
- Plugin-Vertrauensliste (mit Badges und Gründen)
- `GET /doctor/plugins` Nur-Scan-Endpunkt (kein Code-Import)

**Testergebnisse**: 61/61 E2E-Tests bestanden | 159/159 Python-Tests bestanden

</details>

<details>
<summary><strong>Frühere Updates (v1.4.0, Jan 2026)</strong></summary>

- A7 Preact-Migration abgeschlossen (Phase 5A–5C: Chat/Stats Islands, Registry, Shared Rendering, robuste Fallbacks).
- Integrationshärtung: Playwright E2E-Abdeckung gestärkt.
- UI-Korrekturen: Timing des Sidebar-Tooltips korrigiert.

</details>

<details>
<summary><strong>Statistik-Dashboard</strong></summary>

**Verfolgen Sie Ihre ComfyUI-Stabilität auf einen Blick!**

ComfyUI-Doctor enthält jetzt ein **Statistik-Dashboard**, das Einblicke in Fehlertrends, häufige Probleme und den Lösungsfortschritt bietet.

**Funktionen**:

- 📊 **Fehlertrends**: Verfolgen Sie Fehler über 24 Std./7 Tage/30 Tage
- 🔥 **Top 5 Muster**: Sehen Sie, welche Fehler am häufigsten auftreten
- 📈 **Kategorie-Aufschlüsselung**: Visualisieren Sie Fehler nach Kategorie (Speicher, Workflow, Modellladen usw.)
- ✅ **Lösungsverfolgung**: Überwachen Sie gelöste vs. ungelöste Fehler
- 🌍 **Vollständige i18n-Unterstützung**: Verfügbar in allen 9 Sprachen

![Statistik-Dashboard](../../assets/statistics_panel.png)

**Verwendung**:

1. Öffnen Sie das Doctor-Seitenleistenpanel (klicken Sie auf das 🏥-Symbol links)
2. Erweitern Sie den Abschnitt "📊 Fehlerstatistik"
3. Sehen Sie sich Echtzeit-Fehleranalysen und Trends an
4. Markieren Sie Fehler als gelöst/ignoriert, um Ihren Fortschritt zu verfolgen

**Backend-API**:

- `GET /doctor/statistics?time_range_days=30` - Statistiken abrufen
- `POST /doctor/mark_resolved` - Lösungsstatus aktualisieren

**Testabdeckung**: 17/17 Backend-Tests ✅ | 14/18 E2E-Tests (78% Erfolgsquote)

**Implementierungsdetails**: Siehe `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

<details>
<summary><strong>Pattern-Validierung CI</strong></summary>

**Automatisierte Qualitätsprüfungen schützen jetzt die Pattern-Integrität!**

ComfyUI-Doctor enthält jetzt **Continuous Integration Testing** für alle Fehlermuster, um fehlerfreie Beiträge zu gewährleisten.

**Was T8 validiert**:

- ✅ **JSON-Format**: Alle 8 Pattern-Dateien werden korrekt kompiliert
- ✅ **Regex-Syntax**: Alle 57 Muster haben gültige reguläre Ausdrücke
- ✅ **i18n-Vollständigkeit**: 100% Übersetzungsabdeckung (57 Muster × 9 Sprachen = 513 Prüfungen)
- ✅ **Schema-Konformität**: Erforderliche Felder (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Metadaten-Qualität**: Gültige Prioritätsbereiche (50-95), eindeutige IDs, korrekte Kategorien

**GitHub Actions Integration**:

- Wird bei jedem Push/PR ausgelöst, der `patterns/`, `i18n.py` oder Tests betrifft
- Läuft in ca. 3 Sekunden mit $0 Kosten (GitHub Actions Free Tier)
- Blockiert Merges, wenn die Validierung fehlschlägt

**Für Mitwirkende**:

```bash
# Lokale Validierung vor dem Commit
python scripts/run_pattern_tests.py

# Ausgabe:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (insgesamt 9 Sprachen)
```

**Testergebnisse**: 100% Erfolgsquote bei allen Prüfungen

**Implementierungsdetails**: Siehe `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

<details>
<summary><strong>Überarbeitung des Mustersystems (STAGE 1-3 abgeschlossen)</strong></summary>

ComfyUI-Doctor wurde einem umfassenden Architektur-Upgrade unterzogen mit **57+ Fehlermustern** und **JSON-basiertem Mustermanagement**!

**STAGE 1: Logger-Architektur-Fix**

- SafeStreamWrapper mit warteschlangenbasierter Hintergrundverarbeitung implementiert
- Deadlock-Risiken und Race Conditions eliminiert
- Konflikte beim Abfangen von Logs mit dem LogInterceptor von ComfyUI behoben

**STAGE 2: JSON-Mustermanagement (F2)**

- Neuer PatternLoader mit Hot-Reload-Funktion (kein Neustart erforderlich!)
- Muster werden jetzt in JSON-Dateien im Verzeichnis `patterns/` definiert
- 22 integrierte Muster in `patterns/builtin/core.json`
- Einfach zu erweitern und zu warten

**STAGE 3: Erweiterung der Community-Muster (F12)**

- **35 neue Community-Muster**, die beliebte Erweiterungen abdecken:
  - **ControlNet** (8 Muster): Modellladen, Vorverarbeitung, Bildgröße
  - **LoRA** (6 Muster): Ladefehler, Kompatibilität, Gewichtungsprobleme
  - **VAE** (5 Muster): Kodierungs-/Dekodierungsfehler, Präzision, Tiling
  - **AnimateDiff** (4 Muster): Modellladen, Frame-Anzahl, Kontextlänge
  - **IPAdapter** (4 Muster): Modellladen, Bildkodierung, Kompatibilität
  - **FaceRestore** (3 Muster): CodeFormer/GFPGAN-Modelle, Erkennung
  - **Sonstiges** (5 Muster): Checkpoints, Sampler, Scheduler, CLIP
- Vollständige i18n-Unterstützung für Englisch, Traditionelles Chinesisch und Vereinfachtes Chinesisch
- Gesamt: **57 Fehlermuster** (22 integriert + 35 Community)

**Vorteile**:

- ✅ Umfassendere Fehlerabdeckung
- ✅ Hot-Reload von Mustern ohne Neustart von ComfyUI
- ✅ Community kann Muster über JSON-Dateien beisteuern
- ✅ Sauberere, wartbare Codebasis

</details>

<details>
<summary><strong>Frühere Updates (Dez 2025)</strong></summary>

### F9: Erweiterung der Mehrsprachenunterstützung

Wir haben die Sprachunterstützung von 4 auf 9 Sprachen erweitert! ComfyUI-Doctor bietet jetzt Fehlervorschläge in:

- **English** Englisch (en)
- **繁體中文** Traditionelles Chinesisch (zh_TW)
- **简体中文** Vereinfachtes Chinesisch (zh_CN)
- **日本語** Japanisch (ja)
- **🆕 Deutsch** (de)
- **🆕 Français** Französisch (fr)
- **🆕 Italiano** Italienisch (it)
- **🆕 Español** Spanisch (es)
- **🆕 한국어** Koreanisch (ko)

Alle 57 Fehlermuster sind vollständig in alle Sprachen übersetzt, was eine konsistente Diagnosequalität weltweit gewährleistet.

### F8: Integration der Seitenleisteneinstellungen

Die Einstellungen wurden optimiert! Konfigurieren Sie Doctor direkt über die Seitenleiste:

- Klicken Sie auf das ⚙️-Symbol im Seitenleisten-Header, um auf alle Einstellungen zuzugreifen
- Sprachauswahl (9 Sprachen)
- KI-Anbieter Schnellumschaltung (OpenAI, DeepSeek, Groq, Gemini, Ollama usw.)
- Automatische Basis-URL-Eingabe beim Anbieterwechsel
- API-Schlüsselverwaltung (passwortgeschützte Eingabe)
- Konfiguration des Modellnamens
- Einstellungen werden sitzungsübergreifend mit localStorage gespeichert
- Visuelles Feedback beim Speichern (✅ Gespeichert! / ❌ Fehler)

Das ComfyUI-Einstellungsfeld zeigt jetzt nur noch den Aktivieren/Deaktivieren-Schalter an – alle anderen Einstellungen wurden für eine sauberere, integrierte Erfahrung in die Seitenleiste verschoben.

</details>

---

## Funktionen

- **Automatische Fehlerüberwachung**: Erfasst alle Terminalausgaben und erkennt Python-Tracebacks in Echtzeit
- **Intelligente Fehleranalyse**: 57+ Fehlermuster (22 integriert + 35 Community) mit umsetzbaren Vorschlägen
- **Knoten-Kontext-Extraktion**: Identifiziert, welcher Knoten den Fehler verursacht hat (Knoten-ID, Name, Klasse)
- **Systemumgebungs-Kontext**: Integriert automatisch Python-Version, installierte Pakete (pip list) und OS-Infos in die KI-Analyse
- **Mehrsprachenunterstützung**: 9 unterstützte Sprachen (Englisch, Traditionelles Chinesisch, Vereinfachtes Chinesisch, Japanisch, Deutsch, Französisch, Italienisch, Spanisch, Koreanisch)
- **JSON-basiertes Mustermanagement**: Hot-Reload von Fehlermustern ohne Neustart von ComfyUI
- **Community-Muster-Support**: Deckt ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore und mehr ab
- **Debug-Inspektor-Knoten**: Tiefe Inspektion von Daten, die durch Ihren Workflow fließen
- **Fehlerverlauf**: Hält einen Puffer der letzten Fehler über die API bereit
- **RESTful API**: Sieben Endpunkte für die Frontend-Integration
- **KI-gestützte Analyse**: Ein-Klick-LLM-Fehleranalyse mit Unterstützung für 8+ Anbieter (OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio und mehr)
- **Interaktive Chat-Schnittstelle**: Multi-Turn-KI-Debugging-Assistent, integriert in die ComfyUI-Seitenleiste
- **Interaktive Seitenleisten-UI**: Visuelles Fehlerpanel mit Knotenlokalisierung und Sofortdiagnose
- **Flexible Konfiguration**: Umfassendes Einstellungsfeld zur Anpassung des Verhaltens

### 🆕 KI-Chat-Schnittstelle

Die neue interaktive Chat-Schnittstelle bietet ein gesprächsbasiertes Debugging-Erlebnis direkt in der linken Seitenleiste von ComfyUI. Wenn ein Fehler auftritt, klicken Sie einfach auf "Analyze with AI", um eine Multi-Turn-Konversation mit Ihrem bevorzugten LLM zu beginnen.

<div align="center">
<img src="../../assets/chat-ui.png" alt="AI Chat Interface">
</div>

**Hauptmerkmale:**

- **Kontext-bewusst**: Fügt Fehlerdetails, Knoteninformationen und Workflow-Kontext automatisch hinzu
- **Umgebungs-bewusst**: Beinhaltet Python-Version, installierte Pakete und OS-Infos für genaues Debugging
- **Streaming-Antworten**: Echtzeit-LLM-Antworten mit korrekter Formatierung
- **Multi-Turn-Konversationen**: Stellen Sie Folgefragen, um Problemen auf den Grund zu gehen
- **Immer zugänglich**: Der Eingabebereich bleibt unten sichtbar (Sticky Positioning)
- **Unterstützt 8+ LLM-Anbieter**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio und mehr
- **Intelligentes Caching**: Paketliste wird für 24 Stunden zwischengespeichert, um Auswirkungen auf die Leistung zu vermeiden

**Verwendung:**

1. Wenn ein Fehler auftritt, öffnen Sie die Doctor-Seitenleiste (linkes Panel)
2. Klicken Sie im Fehlerkontextbereich auf die Schaltfläche "✨ Analyze with AI"
3. Die KI analysiert den Fehler automatisch und liefert Vorschläge
4. Setzen Sie das Gespräch fort, indem Sie Folgefragen in das Eingabefeld eingeben
5. Drücken Sie Enter oder klicken Sie auf "Send", um Ihre Nachricht abzusenden

> **💡 Kostenloser API-Tipp**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) bietet eine großzügige kostenlose Stufe ohne Kreditkarte an. Perfekt, um ohne Kosten mit KI-gestütztem Debugging zu beginnen!

---

## Installation

### Option 1: ComfyUI-Manager verwenden (Empfohlen)

1. Öffnen Sie ComfyUI und klicken Sie im Menü auf die Schaltfläche **Manager**
2. Wählen Sie **Install Custom Nodes**
3. Suchen Sie nach `ComfyUI-Doctor`
4. Klicken Sie auf **Install** und starten Sie ComfyUI neu

### Option 2: Manuelle Installation (Git Clone)

1. Navigieren Sie zu Ihrem ComfyUI-Verzeichnis für benutzerdefinierte Knoten:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Klonen Sie dieses Repository:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. Starten Sie ComfyUI neu

4. Achten Sie in der Konsole auf die Initialisierungsnachricht:

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

## Verwendung

### Passiver Modus (Automatisch)

Nach der Installation führt ComfyUI-Doctor automatisch Folgendes aus:

- Zeichnet alle Konsolenausgaben im Verzeichnis `logs/` auf
- Erkennt Fehler und liefert Vorschläge
- Protokolliert Systemumgebungsinformationen

**Beispiel Fehler-Output**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory): Ihr GPU-VRAM ist voll. Versuchen Sie:
   1. Batch-Größe reduzieren
   2. '--lowvram' Flag verwenden
   3. Andere GPU-Apps schließen
----------------------------------------
```

### Aktiver Modus (Debug-Knoten)

1. Rechtsklick auf den Canvas → `Add Node` → `Smart Debug Node`
2. Verbinden Sie den Knoten inline mit einer beliebigen Verbindung (unterstützt Wildcard-Eingabe `*`)
3. Führen Sie Ihren Workflow aus

**Beispiel-Output**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

Der Knoten leitet Daten weiter, ohne die Workflow-Ausführung zu beeinträchtigen.

---

## Frontend-UI

ComfyUI-Doctor bietet eine interaktive Seitenleisten-Schnittstelle für Echtzeit-Fehlerüberwachung und Diagnose.

### Zugriff auf das Doctor-Panel

Klicken Sie im ComfyUI-Menü (linke Seitenleiste) auf die Schaltfläche **🏥 Doctor**, um das Doctor-Panel zu öffnen. Das Panel wird von der rechten Seite des Bildschirms eingeblendet.

### Schnittstellenfunktionen

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Error Report">
</div>

Die Doctor-Schnittstelle besteht aus zwei Panels:

#### Linkes Seitenleistenpanel (Doctor-Seitenleiste)

Klicken Sie auf das **🏥 Doctor**-Symbol im linken ComfyUI-Menü, um darauf zuzugreifen:

- **Einstellungsfeld** (⚙️-Symbol): Konfigurieren Sie Sprache, KI-Anbieter, API-Schlüssel und Modellauswahl
- **Fehlerkontextkarte**: Wenn ein Fehler auftritt, wird Folgendes angezeigt:
  - **💡 Vorschlag**: Prägnanter, umsetzbarer Rat (z. B. "Überprüfen Sie die Eingabeverbindungen...")
  - **Zeitstempel**: Wann der Fehler aufgetreten ist
  - **Knotenkontext**: Knoten-ID und Name (falls zutreffend)
  - **✨ Analyze with AI**: Starten Sie interaktiven Chat für detailliertes Debugging
- **KI-Chat-Schnittstelle**: Multi-Turn-Konversation mit Ihrem LLM für eingehende Fehleranalysen
- **Sticky Eingabebereich**: Immer unten zugänglich für Folgefragen

#### Rechtes Fehlerpanel (Neueste Diagnose)

Echtzeit-Fehlerbenachrichtigungen in der oberen rechten Ecke:

![Doctor Error Report](../../assets/error-report.png)

- **Statusanzeige**: Farbiger Punkt zeigt den Systemzustand an
  - 🟢 **Grün**: System läuft normal, keine Fehler erkannt
  - 🔴 **Rot (pulsierend)**: Aktiver Fehler erkannt
- **Karte der neuesten Diagnose**: Zeigt den aktuellsten Fehler an mit:
  - **Fehlerzusammenfassung**: Kurze Fehlerbeschreibung (rotes Thema, für lange Fehler einklappbar)
  - **💡 Vorschlag**: Prägnanter, umsetzbarer Rat (grünes Thema)
  - **Zeitstempel**: Wann der Fehler aufgetreten ist
  - **Knotenkontext**: Knoten-ID, Name und Klasse
  - **🔍 Knoten auf Canvas lokalisieren**: Zentriert den problematischen Knoten automatisch und hebt ihn hervor

**Wichtige Designprinzipien**:

- ✅ **Prägnante Vorschläge**: Nur der umsetzbare Rat wird angezeigt (z. B. "Überprüfen Sie Eingabeverbindungen...") anstatt ausführlicher Fehlerbeschreibungen
- ✅ **Visuelle Trennung**: Fehlermeldungen (rot) und Vorschläge (grün) werden klar unterschieden
- ✅ **Intelligente Kürzung**: Lange Fehler zeigen die ersten 3 + letzten 3 Zeilen mit einklappbaren vollständigen Details
- ✅ **Echtzeit-Updates**: Beide Panels werden automatisch aktualisiert, wenn neue Fehler über WebSocket-Ereignisse auftreten

---

## KI-gestützte Fehleranalyse

ComfyUI-Doctor integriert sich in beliebte LLM-Dienste, um intelligente, kontextbewusste Debugging-Vorschläge bereitzustellen.

### Unterstützte KI-Anbieter

#### Cloud-Dienste

- **OpenAI** (GPT-4, GPT-4o usw.)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - ultraschnelle LPU-Inferenz)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Zugriff auf Claude, GPT-4 und 100+ Modelle)

#### Lokale Dienste (Kein API-Schlüssel erforderlich)

- **Ollama** (`http://127.0.0.1:11434`) - Llama, Mistral, CodeLlama lokal ausführen
- **LMStudio** (`http://localhost:1234/v1`) - Lokale Modellinferenz mit GUI

> **💡 Plattformübergreifende Kompatibilität**: Standard-URLs können über Umgebungsvariablen überschrieben werden:
>
> - `OLLAMA_BASE_URL` - Benutzerdefinierter Ollama-Endpunkt (Standard: `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - Benutzerdefinierter LMStudio-Endpunkt (Standard: `http://localhost:1234/v1`)
>
> Dies verhindert Konflikte zwischen Windows- und WSL2-Ollama-Instanzen oder beim Ausführen in Docker/benutzerdefinierten Setups.

### Konfiguration

![Einstellungsfeld](../../assets/settings.png)

Konfigurieren Sie die KI-Analyse im Panel **Doctor-Seitenleiste** → **Settings**:

1. **KI-Anbieter**: Wählen Sie aus dem Dropdown-Menü. Die Basis-URL wird automatisch ausgefüllt.
2. **KI-Basis-URL**: Der API-Endpunkt (automatisch ausgefüllt, aber anpassbar)
3. **KI-API-Schlüssel**: Ihr API-Schlüssel (leer lassen für lokale LLMs wie Ollama/LMStudio)
4. **KI-Modellname**:
   - Wählen Sie ein Modell aus der Dropdown-Liste (automatisch von der API Ihres Anbieters ausgefüllt)
   - Klicken Sie auf die 🔄 Aktualisieren-Schaltfläche, um verfügbare Modelle neu zu laden
   - Oder aktivieren Sie "Modellnamen manuell eingeben", um einen benutzerdefinierten Modellnamen einzugeben
5. **Datenschutzmodus**: Wählen Sie die PII-Bereinigungsstufe für Cloud-KI-Dienste (siehe Abschnitt [Datenschutzmodus (PII-Bereinigung)](#datenschutzmodus-pii-bereinigung) unten für Details)

### Verwendung der KI-Analyse

1. Das Doctor-Panel öffnet sich automatisch, wenn ein Fehler auftritt.
2. Überprüfen Sie die integrierten Vorschläge oder klicken Sie auf die Schaltfläche ✨ Analyze with AI auf der Fehlerkarte.
3. Warten Sie, bis das LLM den Fehler analysiert hat (typischerweise 3-10 Sekunden).
4. Überprüfen Sie die KI-generierten Debugging-Vorschläge.

**Sicherheitshinweis**: Ihr API-Schlüssel wird nur für die Analyseanfrage sicher vom Frontend zum Backend übertragen. Er wird niemals protokolliert oder dauerhaft gespeichert.

### Datenschutzmodus (PII-Bereinigung)

ComfyUI-Doctor enthält eine automatische **PII (Personally Identifiable Information) Bereinigung**, um Ihre Privatsphäre beim Senden von Fehlermeldungen an Cloud-KI-Dienste zu schützen.

**Drei Datenschutzstufen**:

| Stufe | Beschreibung | Was entfernt wird | Empfohlen für |
| ----- | ----------- | --------------- | --------------- |
| **None** | Keine Bereinigung | Nichts | Lokale LLMs (Ollama, LMStudio) |
| **Basic** (Standard) | Standardschutz | Benutzerpfade, API-Schlüssel, E-Mails, IP-Adressen | Die meisten Benutzer mit Cloud-LLMs |
| **Strict** | Maximaler Datenschutz | Alles von Basic + IPv6, SSH-Fingerabdrücke | Enterprise/Compliance-Anforderungen |

**Was bereinigt wird** (Basic-Stufe):

- ✅ Windows-Benutzerpfade: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOS-Home: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API-Schlüssel: `sk-abc123...` → `<API_KEY>`
- ✅ E-Mail-Adressen: `user@example.com` → `<EMAIL>`
- ✅ Private IPs: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ URL-Anmeldeinformationen: `https://user:pass@host` → `https://<USER>@host`

**Was NICHT entfernt wird**:

- ❌ Fehlermeldungen (für Debugging benötigt)
- ❌ Modellnamen, Knotennamen
- ❌ Workflow-Struktur
- ❌ Öffentliche Dateipfade (`/usr/bin/python`)

**Datenschutzmodus konfigurieren**: Doctor-Seitenleiste öffnen → Settings → 🔒 Privacy Mode Dropdown. Änderungen gelten sofort für alle KI-Analyseanfragen.

**DSGVO-Konformität**: Diese Funktion unterstützt DSGVO Artikel 25 (Datenschutz durch Technikgestaltung) und wird für Enterprise-Bereitstellungen empfohlen.

### Statistik-Dashboard

![Statistik-Panel](../../assets/statistics_panel.png)

Das **Statistik-Dashboard** bietet Echtzeit-Einblicke in Ihre ComfyUI-Fehlermuster und Stabilitätstrends.

**Funktionen**:

- **📊 Fehlertrends**: Gesamtfehler und Zählungen für die letzten 24 Std./7 Tage/30 Tage
- **🔥 Top-Fehlermuster**: Top 5 der häufigsten Fehlertypen mit Vorkommensanzahl
- **📈 Kategorie-Aufschlüsselung**: Visuelle Aufschlüsselung nach Fehlerkategorie (Speicher, Workflow, Modellladen, Framework, Generisch)
- **✅ Lösungsverfolgung**: Verfolgen Sie gelöste, ungelöste und ignorierte Fehler
- **🧭 Status-Steuerung**: Den neuesten Fehler im Statistik-Tab als Gelöst / Ungelöst / Ignoriert markieren
- **🛡️ Vertrauen & Gesundheit (Trust & Health)**: `/doctor/health` Metriken und Plugin-Vertrauensbericht anzeigen (nur Scan)
- **📊 Anonyme Telemetrie (Anonymous Telemetry) (Im Aufbau 🚧)**: Opt-in lokaler Puffer für Nutzungsereignisse (Umschalten/Anzeigen/Löschen/Exportieren)

**Verwendung**:

1. Doctor-Seitenleiste öffnen (🏥-Symbol links klicken)
2. Den einklappbaren Abschnitt **📊 Fehlerstatistik** finden
3. Klicken zum Erweitern und Anzeigen Ihrer Fehleranalysen
4. Mit den **Mark as**-Schaltflächen den Status des neuesten Fehlers setzen (Gelöst / Ungelöst / Ignoriert)
5. Scrollen Sie zum Ende des Statistik-Tabs, um **Vertrauen & Gesundheit** und **Anonyme Telemetrie** zu finden.

**Steuerung des Lösungsstatus**:

- Schaltflächen sind nur aktiv, wenn ein Zeitstempel für den neuesten Fehler verfügbar ist
- Status-Updates werden in der Historie gespeichert und aktualisieren die Lösungsquote automatisch

**Verständnis der Daten**:

- **Total (30d)**: Kumulative Fehler in den letzten 30 Tagen
- **Last 24h**: Fehler in den letzten 24 Stunden (hilft bei der Identifizierung aktueller Probleme)
- **Resolution Rate (Lösungsquote)**: Zeigt den Fortschritt bei der Lösung bekannter Probleme
  - 🟢 **Gelöst**: Probleme, die Sie behoben haben
  - 🟠 **Ungelöst**: Aktive Probleme, die Aufmerksamkeit erfordern
  - ⚪ **Ignoriert**: Unkritische Probleme, die Sie ignorieren
- **Top Patterns**: Identifiziert, welche Fehlertypen priorisierte Aufmerksamkeit benötigen
- **Categories**: Hilft Ihnen zu verstehen, ob Probleme speicherbezogen, Workflow-Probleme, Modellladefehler usw. sind

**Panel-Status-Persistenz**: Der Status "geöffnet/geschlossen" des Panels wird im localStorage Ihres Browsers gespeichert, sodass Ihre Präferenz sitzungsübergreifend erhalten bleibt.

### Beispiel Provider-Setup

| Anbieter         | Basis-URL                                                  | Modell-Beispiel              |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI           | `https://api.openai.com/v1`                                | `gpt-4o`                     |
| DeepSeek         | `https://api.deepseek.com/v1`                              | `deepseek-chat`              |
| Groq             | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`    |
| Gemini           | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`           |
| Ollama (Lokal)   | `http://localhost:11434/v1`                                | `llama3.1:8b`                |
| LMStudio (Lokal) | `http://localhost:1234/v1`                                 | In LMStudio geladenes Modell |

---

## Einstellungen

You can also customize ComfyUI-Doctor behavior via the **Doctor sidebar → Settings** tab.

### 1. Show error notifications (Fehlerbenachrichtigungen anzeigen)

**Funktion**: Schaltet schwebende Fehlerbenachrichtigungskarten (Toasts) in der oberen rechten Ecke um.
**Verwendung**: Deaktivieren, wenn Sie Fehler lieber manuell in der Seitenleiste ohne visuelle Unterbrechungen überprüfen möchten.

### 2. Auto-open panel on error (Panel bei Fehler automatisch öffnen)

**Function**: Automatically opens the **right-side error report panel** when a new error is detected.
**Usage**: **Default: ON**. Disable if you prefer to keep the panel closed and open it manually.

### 3. Error Check Interval (ms)

**Funktion**: Häufigkeit der Frontend-Backend-Fehlerprüfungen (in Millisekunden). Standard: `2000`.
**Verwendung**: Niedrigere Werte (z. B. 500) geben schnelleres Feedback, erhöhen aber die Last; höhere Werte (z. B. 5000) sparen Ressourcen.

### 4. Suggestion Language (Vorschlagssprache)

**Funktion**: Sprache für Diagnoseberichte und Doctor-Vorschläge.
**Verwendung**: Unterstützt derzeit Englisch, Traditionelles Chinesisch, Vereinfachtes Chinesisch, Japanisch (weitere folgen bald). Änderungen gelten für neue Fehler.

### 5. Enable Doctor (requires restart)

**Funktion**: Hauptschalter für das Log-Abfangsystem.
**Verwendung**: Ausschalten, um die Kernfunktionalität von Doctor vollständig zu deaktivieren (erfordert ComfyUI-Neustart).

### 6. AI Provider

**Funktion**: Wählen Sie Ihren bevorzugten LLM-Dienstanbieter aus einem Dropdown-Menü.
**Optionen**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Lokal), LMStudio (Lokal), Benutzerdefiniert.
**Verwendung**: Durch Auswahl eines Anbieters wird die entsprechende Basis-URL automatisch ausgefüllt. Für lokale Anbieter (Ollama/LMStudio) zeigt ein Alarm verfügbare Modelle an.

### 7. AI Base URL

**Funktion**: Der API-Endpunkt für Ihren LLM-Dienst.
**Verwendung**: Automatisch ausgefüllt, wenn Sie einen Anbieter auswählen, kann aber für selbst gehostete oder benutzerdefinierte Endpunkte angepasst werden.

### 8. AI API Key

**Funktion**: Ihr API-Schlüssel zur Authentifizierung bei Cloud-LLM-Diensten.
**Verwendung**: Erforderlich für Cloud-Anbieter (OpenAI, DeepSeek usw.). Leer lassen für lokale LLMs (Ollama, LMStudio).
**Sicherheit**: Der Schlüssel wird nur während der Analyseanfragen übertragen und niemals protokolliert oder dauerhaft gespeichert.

### 9. AI Model Name

**Funktion**: Geben Sie an, welches Modell für die Fehleranalyse verwendet werden soll.
**Verwendung**:

- **Dropdown-Modus** (Standard): Wählen Sie ein Modell aus der automatisch ausgefüllten Dropdown-Liste. Klicken Sie auf die 🔄 Aktualisieren-Schaltfläche, um verfügbare Modelle neu zu laden.
- **Manueller Eingabemodus**: Aktivieren Sie "Modellnamen manuell eingeben", um einen benutzerdefinierten Modellnamen einzugeben (z. B. `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- Modelle werden automatisch von der API Ihres ausgewählten Anbieters abgerufen, wenn Sie den Anbieter ändern oder auf Aktualisieren klicken.
- Für lokale LLMs (Ollama/LMStudio) zeigt das Dropdown alle lokal verfügbaren Modelle an.

> Hinweis: **Vertrauen & Gesundheit (Trust & Health)** und **Anonyme Telemetrie (Anonymous Telemetry)** wurden in den **Statistik (Statistics)** Tab verschoben.

> Hinweis: **F14 Proaktive Diagnose (Proactive Diagnostics)** ist über den Tab **Statistik (Statistics)** → Bereich **Diagnose (Diagnostics)** zugänglich.
> Verwenden Sie **Run / Refresh**, um einen Bericht zu erstellen, die Problemliste anzuzeigen und die bereitgestellten Aktionen (z. B. Knoten lokalisieren) zu nutzen.
> Wenn Sie den Bericht in einer anderen Sprache anzeigen müssen, ändern Sie zuerst die **Suggestion Language** in den Einstellungen.

---

## API-Endpunkte

### GET `/debugger/last_analysis`

Die letzte Fehleranalyse abrufen:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**Antwort-Beispiel**:

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

Fehlerverlauf abrufen (letzte 20 Einträge):

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

Die Vorschlagssprache ändern (siehe Abschnitt Sprachumschaltung).

### POST `/doctor/analyze`

Einen Fehler mit dem konfigurierten LLM-Dienst analysieren.

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

**Antwort**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

API-Schlüsselgültigkeit durch Testen der Verbindung zum LLM-Anbieter überprüfen.

**Payload**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**Antwort**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

Verfügbare Modelle vom konfigurierten LLM-Anbieter auflisten.

**Payload**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**Antwort**:

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

## Log-Dateien

Alle Logs werden gespeichert in:

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

Dateinamenformat: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

Das System behält automatisch die 10 neuesten Log-Dateien (konfigurierbar über `config.json`).

---

## Konfiguration

Erstellen Sie `config.json`, um das Verhalten anzupassen:

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

**Parameter**:

- `max_log_files`: Maximale Anzahl der zu behaltenden Log-Dateien
- `buffer_limit`: Traceback-Puffergröße (Zeilenanzahl)
- `traceback_timeout_seconds`: Timeout für unvollständige Tracebacks
- `history_size`: Anzahl der Fehler im Verlauf
- `default_language`: Standardsprache für Vorschläge
- `enable_api`: API-Endpunkte aktivieren
- `privacy_mode`: PII-Beschränkungsstufe - `"none"`, `"basic"` (Standard) oder `"strict"`

---

## Unterstützte Fehlermuster

ComfyUI-Doctor kann erkennen und Vorschläge liefern für:

- Typkonflikte (z. B. fp16 vs float32)
- Dimensionskonflikte
- CUDA/MPS Speicher knapp (OOM)
- Matrixmultiplikationsfehler
- Geräte-/Typkonflikte
- Fehlende Python-Module
- Assertionsfehler
- Schlüssel-/Attributfehler
- Formkonflikte (Shape Mismatches)
- Datei-nicht-gefunden-Fehler
- SafeTensors-Ladefehler
- CUDNN-Ausführungsfehler
- Fehlende InsightFace-Bibliothek
- Modell/VAE-Nichtübereinstimmungen
- Ungültiges Prompt-JSON

Und mehr...

---

## Tipps

1. **Mit ComfyUI Manager koppeln**: Fehlende benutzerdefinierte Knoten automatisch installieren
2. **Log-Dateien prüfen**: Vollständige Tracebacks werden für die Fehlerberichterstattung aufgezeichnet
3. **Integrierte Seitenleiste verwenden**: Klicken Sie auf das 🏥 Doctor-Symbol im linken Menü für Echtzeit-Diagnosen
4. **Knoten-Debugging**: Debug-Knoten verbinden, um verdächtigen Datenfluss zu inspizieren

---

## Lizenz

MIT License

---

## Mitwirken

Beiträge sind willkommen! Fühlen Sie sich frei, einen Pull Request einzureichen.

**Probleme melden**: Einen Fehler gefunden oder einen Vorschlag? Eröffnen Sie ein Issue auf GitHub.
**PRs einreichen**: Helfen Sie, die Codebasis mit Fehlerbehebungen oder allgemeinen Verbesserungen zu optimieren.
**Feature-Anfragen**: Haben Sie Ideen für neue Funktionen? Lassen Sie es uns bitte wissen.
