# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | Español

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor es un asistente de diagnostico y depuracion en tiempo real para ComfyUI. Captura errores de ejecucion, identifica el contexto probable del nodo, muestra sugerencias locales y puede usar opcionalmente un chat LLM para analisis mas profundos.

## Estado actual

- Se agregaron comprobaciones de compatibilidad de host para ComfyUI, ComfyUI frontend y Desktop.
- La integracion de configuracion frontend prefiere la API actual de ComfyUI settings y mantiene los legacy fallbacks aislados en un adaptador de compatibilidad.
- Los errores de ejecucion pueden enriquecerse con lineage desde eventos recientes execution/progress.
- Strict admin-token mode disponible para servidores compartidos, con advertencias mas claras para loopback convenience mode.
- Server-side credential store documenta metadatos de cifrado y el diseno actual encrypt-then-MAC.
- Se agrego una coverage baseline lane opcional; el full validation flow predeterminado no cambia.

## Funciones principales

- Monitoreo de console y traceback desde el inicio de ComfyUI.
- 58 patrones de error JSON: 22 core patterns y 36 community extension patterns.
- Extraccion de node ID, name, class y custom-node path cuando los eventos del host lo permiten.
- Doctor sidebar con pestanas Chat, Statistics y Settings.
- Workflow LLM para OpenAI-compatible APIs, Anthropic, Gemini, xAI, OpenRouter, Ollama y LMStudio.
- Privacy modes para ocultar path, credential-looking values, email y private IP antes de solicitudes Cloud LLM.
- Server-side credential store opcional, admin-gated, con encryption-at-rest.
- Diagnostics, statistics, plugin trust report, telemetry controls y community feedback preview/submit.
- Soporte para ingles, chino tradicional, chino simplificado, japones, coreano, aleman, frances, italiano y espanol.

## Instalacion

### ComfyUI-Manager

1. Abre ComfyUI y haz clic en **Manager**.
2. Selecciona **Install Custom Nodes**.
3. Busca `ComfyUI-Doctor`.
4. Instala y reinicia ComfyUI.

### Instalacion manual

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Despues de reiniciar, **Doctor** deberia aparecer en la sidebar izquierda.

## Uso basico

- **Diagnostico automatico**: Doctor captura errores, los compara con patrones conocidos y muestra el ultimo diagnostico.
- **Doctor Sidebar**: Chat para el error actual y conversaciones LLM; Statistics para tendencias, diagnosticos y health information; Settings para language, provider, model, privacy y credential source.
- **Smart Debug Node**: Insertalo en una conexion workflow para inspeccionar type, shape, dtype, device y estadisticas sin modificar la salida.

## Documentacion

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## Validacion

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## Licencia

MIT License
