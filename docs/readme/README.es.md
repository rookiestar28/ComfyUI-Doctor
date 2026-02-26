# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | Español | [English](../README.md) | [Hoja de ruta y estado de desarrollo](../ROADMAP.md)

Un conjunto de diagnósticos continuos en tiempo de ejecución y en tiempo real para ComfyUI que incluye **análisis impulsado por IA**, **chat de depuración interactivo** y **más de 50 patrones de reparación**. Intercepta automáticamente todas las salidas del terminal desde el inicio, captura trazas completas de Python y ofrece sugerencias de corrección priorizadas con extracción de contexto a nivel de nodo. Ahora admite **gestión de patrones basada en JSON** con recarga en caliente y **soporte completo de i18n** para 9 idiomas (en, zh_TW, zh_CN, ja, de, fr, it, es, ko).

## Últimas actualizaciones (Ene 2026) - Clic para expandir

<details>
<summary><strong>Nueva Función: F14 Diagnóstico Proactivo (Chequeo de Salud + Firma de Intención)</strong></summary>

- Se ha añadido la sección **Diagnóstico (Diagnostics)** en la pestaña **Estadísticas (Statistics)**, para la solución proactiva de problemas de flujo de trabajo (sin LLM).
- **Chequeo de Salud (Health Check)**: Incluye comprobación de flujo de trabajo (lint), activos de entorno (env assets) y comprobaciones de privacidad, proporcionando sugerencias de corrección procesables.
- **Firma de Intención (Intent Signature)**: Sistema de inferencia de intención determinista, que proporciona **Top-K Intenciones + Evidencia**, ayudando a juzgar "qué está intentando hacer" el flujo de trabajo.
- Incluye refuerzo de UX: Respaldos seguros (ej. "No se detectó intención dominante") y mecanismos de saneamiento de evidencia mejorados.

</details>

<details>
<summary><strong>(v1.5.8) QoL: Auto-open Right Error Report Panel Toggle</strong></summary>

- Added a **dedicated toggle** in **Doctor → Settings** to control whether the **right-side error report panel** auto-opens when a new error is detected.
- **Default: ON** for new installs, and the choice is persisted.

</details>

<details>
<summary><strong>Gestión Inteligente de Presupuesto de Tokens (v1.5.0)</strong></summary>

**Gestión Contextual Inteligente (Optimización de Costos):**

- **Recorte automático**: Para LLM remotos (reducción del 60-80% de tokens)
- **Estrategia progresiva**: Poda de flujo de trabajo → eliminación de info del sistema → truncamiento de traza
- **Opt-in Local**: Recorte suave para Ollama/LMStudio (límite 12K/16K)
- **Observabilidad Mejorada**: Seguimiento de tokens paso a paso & Herramienta de validación A/B

**Resiliencia de Red:**

- **Backoff Exponencial**: Reintento automático para errores 429/5xx (con jitter)
- **Protección de Streaming**: Watchdog de 30s para fragmentos SSE estancados
- **Límites de Velocidad y Concurrencia**: Token bucket (30/min) + Semáforo de concurrencia (máx 3)

**Nueva Configuración:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | Habilitar presupuesto inteligente (Remoto) |
| `retry_max_attempts` | `3` | Max intentos |
| `stream_chunk_timeout` | `30` | Tiempo de espera de flujo (seg) |

</details>

<details>
<summary><strong>Corrección Importante: Gobernanza de Pipeline y Seguridad de Plugins (v1.4.5)</strong></summary>

**Refuerzo de Seguridad:**

- **Protección SSRF++**: Se reemplazaron las comprobaciones de subcadenas con un análisis adecuado de Host/Port; se bloquearon las redirecciones salientes (`allow_redirects=False`)
- **Embudo de Desinfección Saliente**: Un único límite (`outbound.py`) garantiza la desinfección de TODAS las cargas útiles externas; `privacy_mode=none` solo se permite para LLM locales verificados

**Sistema de Confianza de Plugins:**

- **Seguro por defecto**: Los plugins están deshabilitados por defecto, requieren una Lista de Permitidos (Allowlist) explícita + Manifiesto/SHA256
- **Clasificación de Confianza**: `trusted` (confiable) | `unsigned` (sin firmar) | `untrusted` (no confiable) | `blocked` (bloqueado)
- **Contención del Sistema de Archivos**: Contención por realpath, denegación de enlaces simbólicos, límites de tamaño, reglas estrictas de nombres de archivos
- **Firma HMAC Opcional**: Verificación de integridad de secreto compartido (no firma de clave pública)

**Gobernanza de Pipeline:**

- **Contratos de Metadatos**: Versionado de esquemas + validación posterior a la ejecución + Cuarentena para claves no válidas
- **Politique de Dependencias**: Aplicación de `requires/provides`; dependencia faltante → omitir etapa, estado `degraded` (degradado)
- **Contrapresión del Logger**: `DroppingQueue` con prioridad + métricas de descarte
- **Traspaso previo al inicio**: Desinstalación limpia del Logger antes de que SmartLogger tome el control

**Observabilidad:**

- Endpoint `/doctor/health`: Expone métricas de cola, recuentos de descarte, bloqueos SSRF y estado del pipeline

**Resultados de Pruebas**: 159 pruebas de Python aprobadas | 17 pruebas de Puerta de Enlace Fase 2

</details>

<details>
<summary><strong>Mejora: Puertas de Enlace CI y Herramientas de Plugins</strong></summary>

**T11 - Puerta de Enlace de Lanzamiento Fase 2:**

- Flujo de trabajo de GitHub Actions (`phase2-release-gate.yml`): Impone 9 suites pytest + E2E
- Script de validación local (`scripts/phase2_gate.py`): Admite modos `--fast` e `--e2e`

**T12 - Verificador Estático de Seguridad Saliente:**

- Analizador basado en AST (`scripts/check_outbound_safety.py`) detecta patrones de omisión
- 6 reglas de detección: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION`, etc.
- Flujo de trabajo CI + 8 pruebas unitarias + Documentación (`docs/OUTBOUND_SAFETY.md`)

**A8 - Herramientas de Migración de Plugins:**

- `scripts/plugin_manifest.py`: Genera manifiesto con hashes SHA256
- `scripts/plugin_allowlist.py`: Escanea plugins y sugiere configuración
- `scripts/plugin_validator.py`: Valida manifiesto y configuración
- `scripts/plugin_hmac_sign.py`: Genera firmas HMAC opcionales
- Documentación actualizada: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

<details>
<summary><strong>Mejora: Documentación CSP y Telemetría</strong></summary>

**S1 - Documentación de Cumplimiento CSP:**

- Se verificó que todos los activos se carguen localmente (`web/lib/`); las URL de CDN son solo de respaldo
- Se agregó la sección "CSP Compatibility" al README
- Auditoría de código completa (pendiente de verificación manual)

**S3 - Infraestructura de Telemetría Local:**

- Backend: `telemetry.py` (TelemetryStore, RateLimiter, detección de PII)
- 6 Endpoints de API: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- Frontend: Controles de UI de configuración para gestión de telemetría
- Seguridad: Verificación de origen (403 Cross-Origin), límite de carga útil de 1KB, lista permitida de campos
- **Desactivado por defecto**: Sin grabación/red a menos que se habilite explícitamente
- 81 cadenas i18n (9 claves × 9 idiomas)

**Resultados de Pruebas**: 27 Pruebas Unitarias de Telemetría | 8 Pruebas E2E

</details>

<details>
<summary><strong>Mejora: Refuerzo de Runner E2E y UI de Confianza/Salud</strong></summary>

**Refuerzo de Runner E2E (Soporte WSL `/mnt/c`):**

- Se corrigieron problemas de permisos de caché de traducción de Playwright en WSL
- Se agregó un directorio temporal escribible (`.tmp/playwright`) bajo el repositorio
- Anulación de `PW_PYTHON` para compatibilidad multiplataforma

**Panel de UI de Confianza y Salud:**

- Se agregó el panel "Trust & Health" a la pestaña Estadísticas (Statistics)
- Muestra: pipeline_status, ssrf_blocked, dropped_logs
- Lista de confianza de plugins (con insignias y razones)
- Endpoint de solo escaneo `GET /doctor/plugins` (sin importación de código)

**Resultados de Pruebas**: 61/61 Pruebas E2E Aprobadas | 159/159 Pruebas de Python Aprobadas

</details>

<details>
<summary><strong>Actualizaciones Anteriores (v1.4.0, Ene 2026)</strong></summary>

- Migración A7 Preact Completata (Fase 5A–5C: Islas de Chat/Estadísticas, registro, renderizado compartido, respaldos robustos).
- Refuerzo de Integración: Se fortaleció la cobertura de Playwright E2E.
- Correcciones de UI: Se corrigió la sincronización de la información sobre herramientas de la barra lateral.

</details>

<details>
<summary><strong>Panel de Estadísticas</strong></summary>

**¡Rastree la estabilidad de su ComfyUI de un vistazo!**

ComfyUI-Doctor ahora incluye un **Panel de Estadísticas** que proporciona información sobre tendencias de errores, problemas comunes y progreso de resolución.

**Características**:

- 📊 **Tendencias de errores**: Rastree errores durante 24h/7d/30d
- 🔥 **Top 5 Patrones**: Vea qué errores ocurren con más frecuencia
- 📈 **Desglose por categoría**: Visualice errores por categoría (Memoria, Flujo de trabajo, Carga de modelos, etc.)
- ✅ **Seguimiento de resolución**: Supervise errores resueltos vs no resueltos
- 🌍 **Soporte completo de i18n**: Disponible en los 9 idiomas

![Panel de Estadísticas](../../assets/statistics_panel.png)

**Cómo usar**:

1. Abra el panel lateral de Doctor (haga clic en el icono 🏥 a la izquierda)
2. Expanda la sección "📊 Estadísticas de Errores"
3. Vea análisis y tendencias de errores en tiempo real
4. Marque los errores como resueltos/ignorados para seguir su progreso

**API Backend**:

- `GET /doctor/statistics?time_range_days=30` - Obtener estadísticas
- `POST /doctor/mark_resolved` - Actualizar estado de resolución

**Cobertura de pruebas**: 17/17 pruebas de backend ✅ | 14/18 pruebas E2E (tasa de aprobación del 78%)

**Detalles de implementación**: Ver `.planning/260104-F4_STATISTICS_RECORD.md`

</details>

<details>
<summary><strong>CI de Validación de Patrones</strong></summary>

**¡Las comprobaciones de calidad automatizadas ahora protegen la integridad de los patrones!**

ComfyUI-Doctor ahora incluye **pruebas de integración continua** para todos los patrones de error, asegurando contribuciones sin defectos.

**Lo que valida T8**:

- ✅ **Formato JSON**: Los 8 archivos de patrones se compilan correctamente
- ✅ **Sintaxis Regex**: Los 57 patrones tienen expresiones regulares válidas
- ✅ **Integridad i18n**: Cobertura de traducción del 100% (57 patrones × 9 idiomas = 513 comprobaciones)
- ✅ **Cumplimiento de Esquema**: Campos requeridos (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **Calidad de Metadatos**: Rangos de prioridad válidos (50-95), IDs únicos, categorías correctas

**Integración con GitHub Actions**:

- Se activa en cada push/PR que afecte a `patterns/`, `i18n.py` o pruebas
- Se ejecuta en ~3 segundos con un coste de $0 (nivel gratuito de GitHub Actions)
- Bloquea fusiones si la validación falla

**Para contribuyentes**:

```bash
# Validación local antes del commit
python scripts/run_pattern_tests.py

# Salida:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (9 idiomas en total)
```

**Resultados de las pruebas**: Tasa de aprobación del 100% en todas las comprobaciones

**Detalles de implementación**: Ver `.planning/260103-T8_IMPLEMENTATION_RECORD.md`

</details>

<details>
<summary><strong>Revisión del Sistema de Patrones (ETAPA 1-3 Completada)</strong></summary>

¡ComfyUI-Doctor ha sufrido una importante actualización arquitectónica con **más de 57 patrones de error** y **gestión de patrones basada en JSON**!

**ETAPA 1: Corrección de la Arquitectura del Logger**

- Se implementó SafeStreamWrapper con procesamiento en segundo plano basado en cola
- Se eliminaron riesgos de bloqueo y condiciones de carrera
- Se corrigieron conflictos de intercepción de registros con el LogInterceptor de ComfyUI

**ETAPA 2: Gestión de Patrones JSON (F2)**

- Nuevo PatternLoader con capacidad de recarga en caliente (¡sin necesidad de reiniciar!)
- Los patrones ahora se definen en archivos JSON bajo el directorio `patterns/`
- 22 patrones incorporados en `patterns/builtin/core.json`
- Fácil de extender y mantener

**ETAPA 3: Expansión de Patrones de la Comunidad (F12)**

- **35 nuevos patrones de la comunidad** que cubren extensiones populares:
  - **ControlNet** (8 patrones): Carga de modelos, preprocesamiento, tamaño de imagen
  - **LoRA** (6 patrones): Errores de carga, compatibilidad, problemas de peso
  - **VAE** (5 patrones): Fallos de codificación/decodificación, precisión, mosaico
  - **AnimateDiff** (4 patrones): Carga de modelos, recuento de fotogramas, longitud de contexto
  - **IPAdapter** (4 patrones): Carga de modelos, codificación de imagen, compatibilidad
  - **FaceRestore** (3 patrones): Modelos CodeFormer/GFPGAN, detección
  - **Varios** (5 patrones): Puntos de control, muestreadores, programadores, CLIP
- Soporte completo de i18n para Inglés, Chino Tradicional y Chino Simplificado
- Total: **57 patrones de error** (22 incorporados + 35 de la comunidad)

**Beneficios**:

- ✅ Cobertura de errores más completa
- ✅ Recarga en caliente de patrones sin reiniciar ComfyUI
- ✅ La comunidad puede contribuir patrones a través de archivos JSON
- ✅ Código base más limpio y mantenible

</details>

<details>
<summary><strong>Actualizaciones anteriores (Dic 2025)</strong></summary>

### F9: Expansión de Soporte Multilingüe

¡Hemos ampliado el soporte de idiomas de 9 a 9 idiomas! ComfyUI-Doctor ahora proporciona sugerencias de error en:

- **English** Inglés (en)
- **繁體中文** Chino Tradicional (zh_TW)
- **简体中文** Chino Simplificado (zh_CN)
- **日本語** Japonés (ja)
- **🆕 Deutsch** Alemán (de)
- **🆕 Français** Francés (fr)
- **🆕 Italiano** Italiano (it)
- **🆕 Español** (es)
- **🆕 한국어** Coreano (ko)

Los 57 patrones de error están completamente traducidos a todos los idiomas, asegurando una calidad de diagnóstico consistente en todo el mundo.

### F8: Integración de Configuración en la Barra Lateral

¡La configuración se ha simplificado! Configure Doctor directamente desde la barra lateral:

- Haga clic en el icono ⚙️ en el encabezado de la barra lateral para acceder a toda la configuración
- Selección de idioma (9 idiomas)
- Cambio rápido de Proveedor de IA (OpenAI, DeepSeek, Groq, Gemini, Ollama, etc.)
- Autocompletado de URL base al cambiar de proveedor
- Gestión de Clave API (entrada protegida por contraseña)
- Configuración de nombre de modelo
- La configuración persiste entre sesiones con localStorage
- Retroalimentación visual al guardar (✅ ¡Guardado! / ❌ Error)

El panel de Configuración de ComfyUI ahora solo muestra el interruptor Activar/Desactivar: todas las demás configuraciones se han movido a la barra lateral para una experiencia más limpia e integrada.

</details>

---

## Características

- **Monitoreo Automático de Errores**: Captura todas las salidas del terminal y detecta trazas de Python en tiempo real
- **Análisis Inteligente de Errores**: Más de 57 patrones de error (22 incorporados + 35 de la comunidad) con sugerencias procesables
- **Extracción de Contexto de Nodo**: Identifica qué nodo causó el error (ID de nodo, Nombre, Clase)
- **Contexto del Entorno del Sistema**: Incluye automáticamente la versión de Python, paquetes instalados (pip list) e información del sistema operativo en el análisis de IA
- **Soporte Multilingüe**: 9 idiomas compatibles (Inglés, Chino Tradicional, Chino Simplificado, Japonés, Alemán, Francés, Italiano, Español, Coreano)
- **Gestión de Patrones basada en JSON**: Recarga en caliente de patrones de error sin reiniciar ComfyUI
- **Soporte de Patrones de la Comunidad**: Cubre ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore y más
- **Nodo Inspector de Depuración**: Inspección profunda de los datos que fluyen a través de su flujo de trabajo
- **Historial de Errores**: Mantiene un búfer de errores recientes a través de la API
- **API RESTful**: Siete endpoints para integración frontend
- **Análisis impulsado por IA**: Análisis de errores LLM con un solo clic con soporte para más de 8 proveedores (OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio y más)
- **Interfaz de Chat Interactiva**: Asistente de depuración de IA de múltiples turnos integrado en la barra lateral de ComfyUI
- **UI de Barra Lateral Interactiva**: Panel de error visual con localización de nodos y diagnósticos instantáneos
- **Configuración Flexible**: Panel de configuración completo para personalizar el comportamiento

### 🆕 Interfaz de Chat de IA

La nueva interfaz de chat interactiva ofrece una experiencia de depuración conversacional directamente dentro de la barra lateral izquierda de ComfyUI. Cuando ocurre un error, simplemente haga clic en "Analyze with AI" para iniciar una conversación de múltiples turnos con su LLM preferido.

<div align="center">
<img src="../../assets/chat-ui.png" alt="Interfaz de Chat de IA">
</div>

**Características clave:**

- **Consciente del contexto**: Incluye automáticamente detalles del error, información del nodo y contexto del flujo de trabajo
- **Consciente del entorno**: Incluye versión de Python, paquetes instalados e información del sistema operativo para una depuración precisa
- **Respuestas en streaming**: Respuestas LLM en tiempo real con formato adecuado
- **Conversaciones de múltiples turnos**: Haga preguntas de seguimiento para profundizar en los problemas
- **Siempre accesible**: El área de entrada permanece visible en la parte inferior con posicionamiento fijo
- **Soporta más de 8 proveedores de LLM**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio y más
- **Caché Inteligente**: Lista de paquetes almacenada en caché durante 24 horas para evitar impacto en el rendimiento

**Cómo usar:**

1. Cuando ocurra un error, abra la barra lateral de Doctor (panel izquierdo)
2. Haga clic en el botón "✨ Analyze with AI" en el área de contexto del error
3. La IA analizará automáticamente el error y proporcionará sugerencias
4. Continúe la conversación escribiendo preguntas de seguimiento en el cuadro de entrada
5. Presione Entrar o haga clic en "Send" para enviar su mensaje

> **💡 Consejo de API Gratuita**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) ofrece un generoso nivel gratuito sin necesidad de tarjeta de crédito. ¡Perfecto para comenzar con la depuración impulsada por IA sin costo!

---

## Instalación

### Opción 1: Usando ComfyUI-Manager (Recomendado)

1. Abra ComfyUI y haga clic en el botón **Manager** en el menú
2. Seleccione **Install Custom Nodes**
3. Busque `ComfyUI-Doctor`
4. Haga clic en **Install** y reinicie ComfyUI

### Opción 2: Instalación Manual (Git Clone)

1. Navegue a su directorio de nodos personalizados de ComfyUI:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clone este repositorio:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. Reinicie ComfyUI

4. Busque el mensaje de inicialización en la consola:

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

## Uso

### Modo Pasivo (Automático)

Una vez instalado, ComfyUI-Doctor hace automáticamente lo siguiente:

- Registra todas las salidas de la consola en el directorio `logs/`
- Detecta errores y proporciona sugerencias
- Registra información del entorno del sistema

**Ejemplo de Salida de Error**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory): Su VRAM de GPU está llena. Intente:
   1. Reducir el tamaño del lote
   2. Usar la bandera '--lowvram'
   3. Cerrar otras aplicaciones de GPU
----------------------------------------
```

### Modo Activo (Nodo de Depuración)

1. Clic derecho en el lienzo → `Add Node` → `Smart Debug Node`
2. Conecte el nodo en línea con cualquier conexión (admite entrada comodín `*`)
3. Ejecute su flujo de trabajo

**Ejemplo de Salida**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

El nodo pasa los datos sin afectar la ejecución del flujo de trabajo.

---

## UI Frontend

ComfyUI-Doctor proporciona una interfaz de barra lateral interactiva para el monitoreo y diagnóstico de errores en tiempo real.

### Acceso al Panel Doctor

Haga clic en el botón **🏥 Doctor** en el menú de ComfyUI (barra lateral izquierda) para abrir el panel Doctor. El panel se desliza desde el lado derecho de la pantalla.

### Características de la Interfaz

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Informe de Error">
</div>

La interfaz de Doctor consta de dos paneles:

#### Panel Lateral Izquierdo (Barra Lateral Doctor)

Haga clic en el icono **🏥 Doctor** en el menú izquierdo de ComfyUI para acceder a:

- **Panel de Configuración** (icono ⚙️): Configure idioma, proveedor de IA, claves API y selección de modelo
- **Tarjeta de Contexto de Error**: Cuando ocurre un error, se muestra:
  - **💡 Sugerencia**: Consejo conciso y procesable (ej. "Verifique las conexiones de entrada y asegúrese de que se cumplan los requisitos del nodo.")
  - **Marca de tiempo**: Cuándo ocurrió el error
  - **Contexto del Nodo**: ID y nombre del nodo (si corresponde)
  - **✨ Analyze with AI**: Inicie chat interactivo para depuración detallada
- **Interfaz de Chat de IA**: Conversación de múltiples turnos con su LLM para un análisis profundo de errores
- **Área de Entrada Fija**: Siempre accesible en la parte inferior para preguntas de seguimiento

#### Panel de Error Derecho (Último Diagnóstico)

Notificaciones de error en tiempo real en la esquina superior derecha:

![Informe de Error Doctor](../../assets/error-report.png)

- **Indicador de Estado**: Punto de color que muestra la salud del sistema
  - 🟢 **Verde**: Sistema funcionando normalmente, no se detectaron errores
  - 🔴 **Rojo (pulsante)**: Error activo detectado
- **Tarjeta de Último Diagnóstico**: Muestra el error más reciente con:
  - **Resumen del Error**: Breve descripción del error (tema rojo, plegable para errores largos)
  - **💡 Sugerencia**: Consejo conciso y procesable (tema verde)
  - **Marca de tiempo**: Cuándo ocurrió el error
  - **Contexto del Nodo**: ID, nombre y clase del nodo
  - **🔍 Ubicar Nodo en Lienzo**: Centra y resalta automáticamente el nodo problemático

**Principios de Diseño Clave**:

- ✅ **Sugerencias Concisas**: Solo se muestra el consejo procesable (ej. "Verifique conexiones de entrada...") en lugar de descripciones de error detalladas
- ✅ **Separación Visual**: Los mensajes de error (rojo) y las sugerencias (verde) se distinguen claramente
- ✅ **Truncamiento Inteligente**: Los errores largos muestran las primeras 3 + últimas 3 líneas con detalles completos plegables
- ✅ **Actualizaciones en Tiempo Real**: Ambos paneles se actualizan automáticamente cuando ocurren nuevos errores a través de eventos WebSocket

---

## Análisis de Error impulsado por IA

ComfyUI-Doctor se integra con servicios LLM populares para proporcionar sugerencias de depuración inteligentes y conscientes del contexto.

### Proveedores de IA Soportados

#### Servicios en la Nube

- **OpenAI** (GPT-4, GPT-4o, etc.)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - inferencia LPU ultrarrápida)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Acceso a Claude, GPT-4 y más de 100 modelos)

#### Data-Driven Diagnostics Signature Packs

![Diagnostics](../../assets/Diagnostics.png)

El panel de Diagnóstico también admite **paquetes de firmas basados en JSON**.

- **Reglas basadas en datos**: Los paquetes de firmas son archivos JSON versionados.
- **Resultados rastreables**: Las coincidencias de paquetes incluyen la confianza y la procedencia de los metadatos.

#### Quick Community Feedback (GitHub PR)

![Diagnostics](../../assets/feedback.png)

La pestaña Estadísticas también incluye un panel **Quick Community Feedback** para preparar una carga útil limpia y abrir un PR de GitHub desde el servidor.

**Funciones**:
- Rellenado automático desde el último error
- Vista previa antes del envío
- Abre un PR a través de un token de GitHub del lado del servidor

#### Servicios Locales (No se requiere clave API)

- **Ollama** (`http://127.0.0.1:11434`) - Ejecute Llama, Mistral, CodeLlama localmente
- **LMStudio** (`http://localhost:1234/v1`) - Inferencia de modelo local con GUI

> **💡 Compatibilidad Multiplataforma**: Las URL predeterminadas pueden anularse mediante variables de entorno:
>
> - `OLLAMA_BASE_URL` - Endpoint personalizado de Ollama (predeterminado: `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - Endpoint personalizado de LMStudio (predeterminado: `http://localhost:1234/v1`)
>
> Esto evita conflictos entre instancias de Ollama en Windows y WSL2, o al ejecutar en configuraciones Docker/personalizadas.

### Configuración

![Panel de Configuración](../../assets/settings.png)

Configure el análisis de IA en el panel **Barra Lateral Doctor** → **Settings**:

1. **AI Provider**: Seleccione del menú desplegable. La URL base se completará automáticamente.
2. **AI Base URL**: El endpoint de la API (autopoblado, pero personalizable)
3. **AI API Key**: Su clave API (déjelo en blanco para LLM locales como Ollama/LMStudio)
4. **AI Model Name**:
   - Seleccione un modelo de la lista desplegable (poblada automáticamente desde la API de su proveedor)
   - Haga clic en el botón de actualización 🔄 para recargar los modelos disponibles
   - O marque "Ingresar nombre de modelo manualmente" para escribir un nombre de modelo personalizado
5. **Modo de Privacidad**: Seleccione el nivel de desinfección de PII para servicios de IA en la nube (ver la sección [Modo de Privacidad (Desinfección de PII)](#modo-de-privacidad-desinfección-de-pii) a continuación para detalles)

### Uso del Análisis de IA

1. El panel de Doctor se abre automáticamente cuando ocurre un error.
2. Revise las sugerencias integradas o haga clic en el botón ✨ Analyze with AI en la tarjeta de error.
3. Espere a que el LLM analice el error (típicamente 3-10 segundos).
4. Revise las sugerencias de depuración generadas por la IA.

**Nota de Seguridad**: Su clave API se transmite de forma segura desde el frontend al backend solo para la solicitud de análisis. Nunca se registra ni se almacena de forma persistente.

### Modo de Privacidad (Desinfección de PII)

ComfyUI-Doctor incluye **desinfección automática de PII (Información de Identificación Personal)** para proteger su privacidad al enviar mensajes de error a servicios de IA en la nube.

**Tres Niveles de Privacidad**:

| Nivel | Descripción | Qué se Elimina | Recomendado Para |
| ----- | ----------- | --------------- | --------------- |
| **None** | Sin desinfección | Nada | LLM Locales (Ollama, LMStudio) |
| **Basic** (Predeterminado) | Protección estándar | Rutas de usuario, claves API, correos electrónicos, direcciones IP | La mayoría de usuarios con LLM en la nube |
| **Strict** | Privacidad máxima | Todo lo de Basic + IPv6, huellas digitales SSH | Requisitos Empresariales/Cumplimiento |

**Qué se Desinfecta** (Nivel Basic):

- ✅ Rutas de usuario de Windows: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Inicio de Linux/macOS: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ Claves API: `sk-abc123...` → `<API_KEY>`
- ✅ Direcciones de correo electrónico: `user@example.com` → `<EMAIL>`
- ✅ IPs privadas: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ Credenciales de URL: `https://user:pass@host` → `https://<USER>@host`

**Qué NO se Elimina**:

- ❌ Mensajes de error (necesarios para la depuración)
- ❌ Nombres de modelos, nombres de nodos
- ❌ Estructura del flujo de trabajo
- ❌ Rutas de archivos públicos (`/usr/bin/python`)

**Configurar Modo de Privacidad**: Abra Barra Lateral Doctor → Settings → Menú desplegable 🔒 Privacy Mode. Los cambios se aplican inmediatamente a todas las solicitudes de análisis de IA.

**Cumplimiento GDPR**: Esta función respalda el Artículo 25 del GDPR (Protección de datos desde el diseño) y se recomienda para implementaciones empresariales.

### Panel de Estadísticas

![Panel de Estadísticas](../../assets/statistics_panel.png)

El **Panel de Estadísticas** proporciona información en tiempo real sobre sus patrones de error de ComfyUI y tendencias de estabilidad.

**Características**:

- **📊 Tendencias de Errores**: Errores totales y recuentos de las últimas 24h/7d/30d
- **🔥 Patrones de Error Principales**: Los 5 tipos de error más frecuentes con recuentos de ocurrencia
- **📈 Desglose por Categoría**: Desglose visual por categoría de error (Memoria, Flujo de trabajo, Carga de modelos, Marco, Genérico)
- **✅ Seguimiento de Resolución**: Rastree errores resueltos, no resueltos e ignorados
- **🧭 Controles de estado**: Marca el último error como Resuelto / No resuelto / Ignorado desde la pestaña Estadísticas
- **🛡️ Confianza y Salud (Trust & Health)**: Ver métricas `/doctor/health` e informe de confianza de plugins (solo escaneo)
- **📊 Telemetría Anónima (Anonymous Telemetry) (En construcción 🚧)**: Búfer local opcional para eventos de uso (cambiar/ver/borrar/exportar)

**Cómo Usar**:

1. Abra la barra lateral Doctor (clic en icono 🏥 a la izquierda)
2. Encuentre la sección plegable **📊 Estadísticas de Errores**
3. Haga clic para expandir y ver sus análisis de errores
4. Usa los botones **Marcar como** para establecer el estado del último error (Resuelto / No resuelto / Ignorado)
5. Desplácese hasta la parte inferior de la pestaña Estadísticas para encontrar **Confianza y Salud** y **Telemetría Anónima**.

**Controles de estado**:

- Los botones solo se habilitan cuando hay un timestamp del último error disponible
- Las actualizaciones de estado se guardan en el historial y actualizan automáticamente la tasa de resolución

**Entendiendo los Datos**:

- **Total (30d)**: Errores acumulados en los últimos 30 días
- **Last 24h**: Errores en las últimas 24 horas (ayuda a identificar problemas recientes)
- **Resolution Rate (Tasa de Resolución)**: Muestra el progreso hacia la resolución de problemas conocidos
  - 🟢 **Resolved**: Problemas que ha solucionado
  - 🟠 **Unresolved**: Problemas activos que requieren atención
  - ⚪ **Ignored**: Problemas no críticos que ha decidido ignorar
- **Top Patterns**: Identifica qué tipos de error necesitan atención prioritaria
- **Categories**: Le ayuda a comprender si los problemas están relacionados con la memoria, problemas de flujo de trabajo, fallos de carga de modelos, etc.

**Persistencia del Estado del Panel**: El estado abierto/cerrado del panel se guarda en el localStorage de su navegador, por lo que su preferencia persiste entre sesiones.

### Ejemplo de Configuración de Proveedor

| Proveedor        | URL Base                                                   | Ejemplo de Modelo            |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI           | `https://api.openai.com/v1`                                | `gpt-4o`                     |
| DeepSeek         | `https://api.deepseek.com/v1`                              | `deepseek-chat`              |
| Groq             | `https://api.groq.com/openai/v1`                           | `llama-3.1-70b-versatile`    |
| Gemini           | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-flash`           |
| Ollama (Local)   | `http://localhost:11434/v1`                                | `llama3.1:8b`                |
| LMStudio (Local) | `http://localhost:1234/v1`                                 | Modelo cargado en LMStudio   |

---

## Configuración

You can also customize ComfyUI-Doctor behavior via the **Doctor sidebar → Settings** tab.

### 1. Show error notifications (Mostrar notificaciones de error)

**Función**: Activa/desactiva las tarjetas de notificación de error flotantes (toasts) en la esquina superior derecha.
**Uso**: Desactive si prefiere verificar los errores manualmente en la barra lateral sin interrupciones visuales.

### 2. Auto-open panel on error (Abrir panel automáticamente al error)

**Function**: Automatically opens the **right-side error report panel** when a new error is detected.
**Usage**: **Default: ON**. Disable if you prefer to keep the panel closed and open it manually.

### 3. Error Check Interval (ms)

**Función**: Frecuencia de comprobaciones de error frontend-backend (en milisegundos). Predeterminado: `2000`.
**Uso**: Valores más bajos (ej. 500) dan retroalimentación más rápida pero aumentan la carga; valores más altos (ej. 5000) ahorran recursos.

### 4. Suggestion Language (Idioma de sugerencia)

**Función**: Idioma para informes de diagnóstico y sugerencias de Doctor.
**Uso**: Actualmente admite Inglés, Chino Tradicional, Chino Simplificado y Japonés (más próximamente). Los cambios se aplican a nuevos errores.

### 5. Enable Doctor (requires restart)

**Función**: Interruptor principal para el sistema de interceptación de registros.
**Uso**: Desactive para deshabilitar completamente la funcionalidad principal de Doctor (requiere reinicio de ComfyUI).

### 6. AI Provider

**Función**: Seleccione su proveedor de servicios LLM preferido de un menú desplegable.
**Opciones**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Local), LMStudio (Local), Personalizado.
**Uso**: Al seleccionar un proveedor, se completa automáticamente la URL base adecuada. Para proveedores locales (Ollama/LMStudio), una alerta muestra los modelos disponibles.

### 7. AI Base URL

**Función**: El endpoint de la API para su servicio LLM.
**Uso**: Se completa automáticamente cuando selecciona un proveedor, pero se puede personalizar para endpoints autohospedados o personalizados.

### 8. AI API Key

**Función**: Su clave API para autenticación con servicios LLM en la nube.
**Uso**: Requerido para proveedores de nube (OpenAI, DeepSeek, etc.). Deje en blanco para LLM locales (Ollama, LMStudio).
**Seguridad**: La clave se transmite solo durante las solicitudes de análisis y nunca se registra ni se conserva.

### 9. AI Model Name

**Función**: Especifique qué modelo utilizar para el análisis de errores.
**Uso**:

- **Modo Menú Desplegable** (predeterminado): Seleccione un modelo de la lista poblada automáticamente. Haga clic en el botón de actualización 🔄 para recargar los modelos disponibles.
- **Modo Entrada Manual**: Marque "Ingresar nombre de modelo manualmente" para escribir un nombre de modelo personalizado (ej. `gpt-4o`, `deepseek-chat`, `llama3.1:8b`).
- Los modelos se obtienen automáticamente de la API de su proveedor seleccionado cuando cambia de proveedor o hace clic en actualizar.
- Para LLMs locales (Ollama/LMStudio), el desplegable muestra todos los modelos disponibles localmente.

> Nota: **Confianza y Salud (Trust & Health)** y **Telemetría Anónima (Anonymous Telemetry)** se han movido a la pestaña **Estadísticas (Statistics)**.

> Nota: **F14 Diagnóstico Proactivo (Proactive Diagnostics)** es accesible desde la pestaña **Estadísticas (Statistics)** → sección **Diagnóstico (Diagnostics)**.
> Utilice **Run / Refresh** para generar un informe, ver la lista de problemas y utilizar las acciones proporcionadas (como localizar nodo).
> Si necesita mostrar el informe en otro idioma, cambie primero el **Suggestion Language** en la configuración.

---

## Endpoints de API

### GET `/debugger/last_analysis`

Recuperar el análisis de error más reciente:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**Ejemplo de Respuesta**:

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"],
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

Recuperar historial de errores (últimas 20 entradas):

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

Cambiar el idioma de sugerencia (ver sección Cambio de Idioma).

### POST `/doctor/analyze`

Analizar un error utilizando el servicio LLM configurado.

**Carga útil**:

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

**Respuesta**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

Verificar la validez de la clave API probando la conexión con el proveedor LLM.

**Carga útil**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**Respuesta**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

Listar modelos disponibles del proveedor LLM configurado.

**Carga útil**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**Respuesta**:

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

## Archivos de Registro

Todos los registros se almacenan en:

```text
<ComfyUI user directory>/ComfyUI-Doctor/logs/
```

Formato de nombre de archivo: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

El sistema conserva automáticamente los 10 archivos de registro más recientes (configurable a través de `config.json`).

---

## Configuración

Cree `config.json` para personalizar el comportamiento:

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

**Parámetros**:

- `max_log_files`: Número máximo de archivos de registro a conservar
- `buffer_limit`: Tamaño del búfer de rastreo (recuento de líneas)
- `traceback_timeout_seconds`: Tiempo de espera para trazas incompletas
- `history_size`: Número de errores a mantener en el historial
- `default_language`: Idioma de sugerencia predeterminado
- `enable_api`: Habilitar endpoints de API
- `privacy_mode`: Nivel de desinfección de PII - `"none"`, `"basic"` (predeterminado), o `"strict"`

---

## Patrones de Error Soportados

ComfyUI-Doctor puede detectar y proporcionar sugerencias para:

- Desajustes de tipo (ej. fp16 vs float32)
- Desajustes de dimensión
- Memoria CUDA/MPS agotada (OOM)
- Errores de multiplicación de matrices
- Conflictos de dispositivo/tipo
- Módulos Python faltantes
- Fallos de aserción
- Errores de Clave/Atributo
- Desajustes de forma (Shape mismatches)
- Errores de archivo no encontrado
- Errores de carga de SafeTensors
- Fallos de ejecución de CUDNN
- Biblioteca InsightFace faltante
- Desajustes de Modelo/VAE
- JSON de aviso no válido

Y más...

---

## Consejos

1. **Emparejar con ComfyUI Manager**: Instale nodos personalizados faltantes automáticamente
2. **Verificar archivos de registro**: Se registran trazas completas para informes de problemas
3. **Usar la barra lateral incorporada**: Haga clic en el icono 🏥 Doctor en el menú izquierdo para diagnósticos en tiempo real
4. **Depuración de Nodos**: Conecte nodos de depuración para inspeccionar el flujo de datos sospechoso

---

## Licencia

Licencia MIT

---

## Contribuir

¡Las contribuciones son bienvenidas! Siéntase libre de enviar un Pull Request.

**Reportar Problemas**: ¿Encontró un error o tiene una sugerencia? Abra un problema en GitHub.
**Enviar PRs**: Ayude a mejorar el código base con correcciones de errores o mejoras generales.
**Solicitudes de Funciones**: ¿Tiene ideas para nuevas funciones? Por favor, háganoslo saber.


### GET /doctor/secrets/status (S8)
**Uso:** Obtiene el estado de los ajustes de proveedores del Almacén avanzado de claves (Advanced Key Store).
**Limitaciones de autenticación:** Si se define un `DOCTOR_ADMIN_TOKEN` en el entorno, es necesario incluirlo.
```json
{
    "success": true,
    "providers": {
        "openai": { "source": "server_store" },
        "anthropic": { "source": "env" }
    }
}
```

### PUT /doctor/secrets (S8)
**Uso:** Inserte o actualice una clave en el almacén de un servidor local.
**Limitaciones de autenticación:** Si se define un `DOCTOR_ADMIN_TOKEN` en el entorno, es necesario incluirlo.
```json
{
    "provider": "openai",
    "key": "sk-...",
    "token": "admin-token-value"
}
```
Valor devuelto:
```json
{
    "success": true,
    "message": "Key for openai stored successfully."
}
```

### DELETE /doctor/secrets/{provider} (S8)
**Uso:** Elimine las credenciales que se han guardado en el servidor actual.
**Limitaciones de autenticación:** Si se ha añadido un `DOCTOR_ADMIN_TOKEN` de antemano el área pertinente, deberá indicarse al llamar o de otro modo no se lograría.
**Ejemplo de respuesta devuelta:**
```json
{
    "success": true,
    "message": "Deleted stored key for openai"
}
```

### POST /doctor/mark_resolved (F15)
**Uso:** El usuario podrá designar si las fallas experimentadas con esta opción concreta han dejado o no de suponer impedimento. Estados en los que se hallan (con `resolved`, `unresolved`, `ignored`).
Esto ayuda a realizar cálculos globales relativos a si un dilema ha persistido.
**Carga útil de solicitud:**
```json
{
    "timestamp": "2026-02-27T00:00:00Z",
    "status": "resolved"
}
```

### POST /doctor/feedback/preview (F16)
**Uso:** Exportar las impresiones recogidas en el dispositivo front-end para proporcionar una primera visión del progreso, lo que serviría a efectos previos para enviar este último al repositorio Pull Request correspondiente por parte del público y evitar un eventual acceso de carácter privado e indeseable.
**Carga útil de solicitud:**
```json
{
    "pattern_candidate": {
        "id": "my_new_error_pattern",
        "regex": "CUDA out of memory",
        "category": "memory",
        "priority": 80,
        "notes": "Verified locally."
    },
    "suggestion_candidate": {
        "language": "en",
        "message": "Reduce batch size to 1."
    },
    "error_context": { 
        "last_error": "CUDA out of memory",
        "timestamp": "2026-02-27T12:00:00+00:00"
    }
}
```
**Respuesta:**
```json
{
    "success": true,
    "submission_id": "20260227_...",
    "preview": { ... },
    "warnings": []
}
```

### POST /doctor/feedback/submit (F16)
**Uso:** La comunicación del feedback anterior ahora va a subirse formalmente al Pull Request de GitHub del usuario público, insertando estos recursos como un elemento adicional o parte en la librería primaria `ComfyUI-Doctor`. Debe preparase allí un token particular `DOCTOR_GITHUB_TOKEN` exclusivo para permitir que lo antes indicado finalice sin obstáculo.
**Límites de acceso autorizado:** Está estrechamente acotado bajo una asignación para los servidores como `DOCTOR_ADMIN_TOKEN`.
**Carga útil de solicitud:**
```json
{
    "submission_id": "20260227_...",
    "token": "admin-token-value"
}
```
```json
{
    "success": true,
    "github": {
        "pr_url": "https://github.com/rookiestar28/ComfyUI-Doctor/pull/123"
    }
}
```

### GET /doctor/health
**Uso:** Pida al sistema información pertinente en lo respectivo a su funcionamiento idóneo base actual; los componentes a examinar, claro (esto no lleva ninguna comprobación, si bien facilita una recolección simple de diagnósticos previos ya recogidos).
**Respuesta:**
```json
{
    "success": true,
    "health": {
        "logger": { "dropped_messages": 0 },
        "ssrf": { "blocked_total": 0 },
        "last_analysis": { "timestamp": "...", "pipeline_status": "ok" }
    }
}
```

### GET /doctor/plugins
**Uso:** Se proporciona acceso para ver una sección indicando aquéllos analistas internos habilitados para funcionar conjuntamente bajo una base validada y cómo estarían configurados internamente.
**Respuesta:**
```json
{
    "success": true,
    "plugins": {
        "config": { "enabled": true, "signature_required": false },
        "plugins": [
            { "file": "system_analyzer.py", "trust": "trusted", "reason": "bundled" }
        ]
    }
}
```

### GET /doctor/telemetry/status (S3)
**Uso:** Constate en qué medida el subsistema se oculta e infórmese sobre estadísticas relevantes en curso en el acto.
**Respuesta:**
```json
{
  "success": true,
  "enabled": true,
  "stats": {
    "count": 5
  }
}
```

### GET /doctor/telemetry/buffer (S3)
**Uso:** Revisar sin demérito lo ya memorizado aún no propagado mediante el servicio interno antes expuesto sin la presencia del individuo responsable (caché de datos no identificable).
**Respuesta:**
```json
{
  "success": true,
  "events": [...]
}
```

### POST /doctor/telemetry/track (S3)
**Uso:** (Esto procede para incorporaciones aportadas libremente en primer nivel, u ocurridas si de presentarse cualquier anomalía), guarde sin identificarse este incidente con destino en una copia interina interna.

### POST /doctor/telemetry/clear (S3)
**Uso:** Depure definitivamente, toda traza local para registros remanentes no revelables que contuviese un almacenamiento interno local de telemetría de índole transitorio.
**Respuesta:**
```json
{ "success": true }
```

### GET /doctor/telemetry/export (S3)
**Uso:** Almacene bajo una entidad local del usuario este registro parcial en vista de posibles consultas subsiguientes, bajo archivo principal JSON base de formato común.

### POST /doctor/telemetry/toggle (S3)
**Uso:** Modifique de entre habilitado y cancelado el flujo en caso de optar recoger cifras telemétricas o no en incógnito, siendo en caso inverso omitido todo acto respectivo.
```json
{
  "enabled": true
}
```

### POST /doctor/health_ack (F14)
**Uso:** Punto en la ruta excepcional para notificaciones u obligar confirmar si recibe reporte de actividad general pertinente al propio sistema o de no poseer esto interés (Acknowledge) mediante: `acknowledged`, `ignored`, `resolved` como alternativas primordiales en su respectivo rango de actividad.

