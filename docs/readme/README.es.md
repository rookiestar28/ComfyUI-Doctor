# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | Español | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor es un asistente de diagnóstico y depuración en tiempo real para ComfyUI. Captura errores en runtime, identifica el contexto de node más probable, muestra sugerencias locales accionables y puede usar opcionalmente un workflow de chat LLM para una solución de problemas más profunda.

## Últimas actualizaciones

Las últimas actualizaciones se mantienen en el README en inglés. Consulta [Latest Updates](../../README.md#latest-updates---click-to-expand).

## Funciones principales

- Captura en tiempo real de la salida console/error de ComfyUI desde el inicio.
- Sugerencias integradas desde 58 patrones de error basados en JSON, incluidos 22 core patterns y 36 community-extension patterns.
- Extracción validada del contexto de node para errores recientes de ejecución de workflow cuando ComfyUI proporciona suficientes datos de eventos.
- Sidebar Doctor con pestañas Chat, Statistics y Settings.
- Análisis LLM opcional mediante OpenAI-compatible services, Anthropic, Gemini, xAI, OpenRouter, Ollama y LMStudio, con manejo unificado de provider request/response.
- Privacy controls para solicitudes LLM salientes, incluidos modos de sanitization para rutas, claves, correos e IP.
- Credential store opcional del lado del servidor con admin guarding y soporte encryption-at-rest.
- Diagnostics locales, statistics, plugin trust report, telemetry controls y herramientas community feedback preview/submit.
- JSON error envelopes consistentes para fallos de la API Doctor.
- Soporte completo de UI y sugerencias en inglés, chino tradicional, chino simplificado, japonés, coreano, alemán, francés, italiano y español.

## Capturas de pantalla

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## Instalación

### ComfyUI-Manager

1. Abre ComfyUI y haz clic en **Manager**.
2. Selecciona **Install Custom Nodes**.
3. Busca `ComfyUI-Doctor`.
4. Instala y reinicia ComfyUI.

### Instalación manual

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Reinicia ComfyUI después de clonar. Doctor debería imprimir sus diagnostics de inicio y registrar la entrada de sidebar `Doctor`.

## Uso básico

### Diagnóstico automático

Después de la instalación, Doctor registra pasivamente la salida runtime de ComfyUI, detecta tracebacks, compara patrones de error conocidos y muestra el diagnóstico más reciente en la sidebar y en el panel de informe derecho opcional.
Cuando se usa el análisis LLM opcional, Doctor construye el prompt context desde la misma pipeline estructurada que maneja sanitization, node context, execution logs, workflow pruning e información del sistema.

### Sidebar Doctor

Abre **Doctor** en la sidebar izquierda de ComfyUI:

- **Chat**: revisa el contexto del error más reciente y haz preguntas de depuración de seguimiento.
- **Statistics**: inspecciona tendencias recientes de errores, diagnostics, trust/health information, telemetry controls y feedback tools.
- **Settings**: elige idioma, LLM provider, base URL, model, privacy mode, comportamiento auto-open y credential storage opcional del lado del servidor.

### Smart Debug Node

Haz clic derecho en el canvas, agrega **Smart Debug Node** y colócalo inline para inspeccionar los datos que pasan sin cambiar la salida del workflow.

## Configuración LLM opcional

Los cloud providers requieren un credential proporcionado mediante session-only UI field, variables de entorno o el server store opcional protegido por admin. Providers locales como Ollama y LMStudio pueden ejecutarse sin cloud credential.
Doctor normaliza los formatos provider-specific request/response para OpenAI-compatible APIs, Anthropic y Ollama, de modo que chat, single-shot analysis, model listing y connectivity checks compartan el mismo comportamiento backend.

Valores recomendados:

- Usa **Privacy Mode: Basic** o **Strict** para cloud providers.
- Usa variables de entorno para entornos compartidos o similares a producción.
- Configura `DOCTOR_ADMIN_TOKEN` y `DOCTOR_REQUIRE_ADMIN_TOKEN=1` en servidores compartidos.
- Mantén el local-only loopback convenience mode solo para uso desktop de un único usuario.

## Documentación

- [User Guide](../USER_GUIDE.md): UI walkthrough, diagnostics, privacy modes, LLM setup y feedback flow.
- [Configuration and Security](../CONFIGURATION_SECURITY.md): environment variables, admin guard behavior, credential storage, outbound safety, telemetry y CSP notes.
- [API Reference](../API_REFERENCE.md): endpoints públicos de Doctor y debugger.
- [Validation Guide](../VALIDATION.md): comandos full-gate locales y lanes opcionales de compatibility/coverage.
- [Plugin Guide](../PLUGIN_GUIDE.md): community plugin trust model y plugin authoring notes.
- [Plugin Migration](../PLUGIN_MIGRATION.md): migration tooling para plugin manifests y allowlists.
- [Outbound Safety](../OUTBOUND_SAFETY.md): static checker y outbound request safety rules.

## Patrones de error soportados

Los patrones se almacenan como archivos JSON en `patterns/` y pueden actualizarse sin cambios de código.

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

Los community packs cubren actualmente modos de fallo comunes de ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, checkpoint, sampler, scheduler y CLIP.

## Validación

Para validación local CI-parity, usa el full-test script del proyecto:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

El full gate cubre secrets detection, pre-commit hooks, host-like startup validation, backend unit tests y frontend Playwright E2E tests. Consulta la [Validation Guide](../VALIDATION.md) para comandos staged explícitos y lanes opcionales.

## Requisitos

- Entorno ComfyUI custom-node.
- Python 3.10 o más reciente.
- Node.js 18 o más reciente solo para frontend E2E validation.
- No se requiere runtime Python package dependency adicional más allá del bundled environment de ComfyUI y la Python standard library.

## Licencia

MIT License

## Contribuir

Las contribuciones de patrones y documentación son bienvenidas. Para cambios de código, ejecuta el full validation gate antes de abrir una pull request y evita commitear estado local generado, logs, credentials o archivos internos de planning.
