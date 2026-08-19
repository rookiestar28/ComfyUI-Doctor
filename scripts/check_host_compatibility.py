"""Check ComfyUI host compatibility surfaces used by ComfyUI-Doctor.

This script is intentionally lightweight. It validates that the local
`reference/` checkouts still expose the host APIs Doctor depends on; it does
not replace full host E2E validation.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SurfaceCheck:
    repo: str
    file: str
    label: str
    required_patterns: tuple[str, ...]
    forbidden_patterns: tuple[str, ...] = ()
    source_revision: str = ""
    applicable_lanes: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class FrontendRuntimeLane:
    id: str
    label: str
    version: str
    source_repo: str
    source_file: str
    source_revision: str
    setting_change_telemetry: bool
    async_setting_on_change: bool


@dataclass(frozen=True)
class CheckResult:
    check: SurfaceCheck
    ok: bool
    missing_file: bool = False
    missing_patterns: tuple[str, ...] = ()
    present_forbidden_patterns: tuple[str, ...] = ()


COMFYUI_REVISION = "c67885b14556cf3e4e061862925282d403d09862"  # pragma: allowlist secret
FRONTEND_REVISION = "569e65b30fbfe96743c7996e201a32bcf029a310"  # pragma: allowlist secret
DESKTOP_REVISION = "e2d964b7456cea8423c7b9d3371c612313c06baa"  # pragma: allowlist secret

FRONTEND_RUNTIME_LANES: tuple[FrontendRuntimeLane, ...] = (
    FrontendRuntimeLane(
        id="desktop-0.9.4",
        label="Desktop 0.9.4 bundle",
        version="1.43.18",
        source_repo="desktop",
        source_file="package.json",
        source_revision=DESKTOP_REVISION,
        setting_change_telemetry=False,
        async_setting_on_change=False,
    ),
    FrontendRuntimeLane(
        id="core-pin-1.49.6",
        label="ComfyUI package pin",
        version="1.49.6",
        source_repo="ComfyUI",
        source_file="requirements.txt",
        source_revision=COMFYUI_REVISION,
        setting_change_telemetry=True,
        async_setting_on_change=False,
    ),
    FrontendRuntimeLane(
        id="standalone-1.52.1+",
        label="standalone frontend source",
        version="1.52.1+",
        source_repo="ComfyUI_frontend",
        source_file="package.json",
        source_revision=FRONTEND_REVISION,
        setting_change_telemetry=True,
        async_setting_on_change=True,
    ),
)


CHECKS: tuple[SurfaceCheck, ...] = (
    SurfaceCheck(
        repo="ComfyUI",
        file="main.py",
        label="custom node prestartup loading",
        required_patterns=("prestartup_script.py", "execute_prestartup_script"),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="nodes.py",
        label="WEB_DIRECTORY registration",
        required_patterns=("EXTENSION_WEB_DIRS", "WEB_DIRECTORY"),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="extension static routes",
        required_patterns=('@routes.get("/extensions")', "EXTENSION_WEB_DIRS", "web.static('/extensions/'"),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="PromptServer route registry",
        required_patterns=("class PromptServer", "self.routes"),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="host /api route duplication",
        required_patterns=(
            "Prefix every route with /api",
            '"/api" + route.path',
            "self.app.add_routes(api_routes)",
            "self.app.add_routes(self.routes)",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="feature-flag websocket exchange",
        required_patterns=(
            'data.get("type") == "feature_flags"',
            'self.sockets_metadata[sid]["feature_flags"]',
            "feature_flags.get_server_features()",
            '@routes.get("/features")',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="system_stats current multi-device package versions",
        required_patterns=(
            '@routes.get("/system_stats")',
            "get_all_torch_devices",
            "device_entries",
            "comfy_package_versions",
            "FrontendManager.get_comfy_package_versions()",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="system_stats deploy environment",
        required_patterns=(
            "get_deploy_environment",
            '"deploy_environment": get_deploy_environment()',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="jobs namespace cancel endpoints",
        required_patterns=(
            'cancel_job(',
            "CANCEL_RUNNING",
            "CANCEL_PENDING",
            "interrupt_if_running",
            '@routes.post("/api/jobs/{job_id}/cancel")',
            '@routes.post("/api/jobs/cancel")',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="server.py",
        label="prompt usage source pass-through",
        required_patterns=(
            '"comfy_usage_source" not in extra_data',
            'request.headers.get("Comfy-Usage-Source")',
            'extra_data["comfy_usage_source"] = usage_source',
        ),
        note=(
            "Tracks host source-attribution pass-through only; Doctor must not "
            "attach secrets or private prompt data to usage-source metadata."
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="execution.py",
        label="execution_error websocket payload",
        required_patterns=(
            '"execution_error"',
            '"node_id"',
            '"node_type"',
            '"traceback"',
            '"current_inputs"',
            '"current_outputs"',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="execution.py",
        label="execution usage source hidden input",
        required_patterns=(
            "io.Hidden.comfy_usage_source.name in hidden",
            "hidden_inputs_v3[io.Hidden.comfy_usage_source]",
            'extra_data.get("comfy_usage_source", None)',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="execution.py",
        label="executed output asset enrichment tolerance",
        required_patterns=(
            "enrich_output_with_assets(output_ui)",
            '"executed"',
            '"output": output_ui',
        ),
        note=(
            "Doctor currently treats executed output as pass-through host data; "
            "this guard records upstream enrichment without requiring runtime parsing."
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="execution.py",
        label="prompt queue running job interrupt hook",
        required_patterns=(
            "def interrupt_if_running",
            "currently_running",
            "interrupt_processing",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy_execution/jobs.py",
        label="jobs cancel classification helpers",
        required_patterns=(
            "CANCEL_RUNNING",
            "CANCEL_PENDING",
            "CANCEL_TERMINAL",
            "CANCEL_UNKNOWN",
            "def cancel_job",
            "def classify_job_for_cancel",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy_execution/progress.py",
        label="progress_state lineage payload",
        required_patterns=(
            '"progress_state"',
            '"display_node_id"',
            '"parent_node_id"',
            '"real_node_id"',
            "supports_preview_metadata",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="folder_paths.py",
        label="current model folder anchors",
        required_patterns=(
            '"geometry_estimation"',
            '"detection"',
            "get_system_user_directory",
            "get_public_user_directory",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="folder_paths.py",
        label="current expanded model folder anchors",
        required_patterns=(
            '"diffusion_models"',
            '"text_encoders"',
            '"clip_vision"',
            '"style_models"',
            '"photomaker"',
            '"classifiers"',
            '"model_patches"',
            '"audio_encoders"',
            '"background_removal"',
            '"frame_interpolation"',
            '"optical_flow"',
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy_api/feature_flags.py",
        label="server feature flags",
        required_patterns=(
            '"supports_preview_metadata": True',
            '"extension": {"manager": {"supports_v4": True}}',
            '"node_replacements": True',
            '"enable_telemetry":',
            "def get_server_features",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/types/extensionTypes.ts",
        label="extensionManager execution error state",
        required_patterns=(
            "lastNodeErrors",
            "lastExecutionError",
            "ExecutionErrorWsMessage",
            "NodeError",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/scripts/api.ts",
        label="frontend queue prompt usage source",
        required_patterns=(
            "async queuePrompt(",
            "extra_data:",
            "comfy_usage_source: 'comfyui-frontend'",
        ),
        note="Tracks frontend prompt source attribution; Doctor does not queue prompts in this item.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/scripts/api.ts",
        label="frontend jobs cancel API",
        required_patterns=(
            "async cancelJob(",
            "/cancel",
            "async cancelJobs(",
            "'/jobs/cancel'",
            "job_ids: jobIds",
        ),
        note="Tracks host prompt/job cancellation API adoption; Doctor does not call these endpoints in this item.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/types/extensionTypes.ts",
        label="extensionManager settings/sidebar API",
        required_patterns=("registerSidebarTab", "setting:", "get: <T = unknown>", "set: <T = unknown>"),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/stores/workspaceStore.ts",
        label="deprecated sidebar wrapper fallback",
        required_patterns=(
            "const sidebarTab = computed(() => useSidebarTabStore())",
            "Use `sidebarTab.registerSidebarTab` instead",
            "sidebarTab.value.registerSidebarTab(tab)",
            "Use `sidebarTab.unregisterSidebarTab` instead",
            "sidebarTab.value.unregisterSidebarTab(id)",
            "Use `sidebarTab.sidebarTabs` instead",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/stores/workspace/sidebarTabStore.ts",
        label="current sidebarTab store API",
        required_patterns=(
            "defineStore('sidebarTab'",
            "const sidebarTabs = ref<SidebarTabExtension[]>([])",
            "const activeSidebarTabId = ref<string | null>(null)",
            "const registerSidebarTab =",
            "const unregisterSidebarTab =",
            "toggleSidebarTab",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/schemas/apiSchema.ts",
        label="frontend execution_error schema",
        required_patterns=(
            "zExecutionErrorWsMessage",
            "node_id:",
            "node_type:",
            "traceback:",
            "current_inputs:",
            "current_outputs:",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/scripts/app.ts",
        label="frontend rootGraph API",
        required_patterns=("rootGraph", "lastExecutionError"),
    ),
    SurfaceCheck(
        repo="desktop",
        file="package.json",
        label="Desktop current bundled host baseline",
        required_patterns=(
            '"version": "0.9.4"',
            '"comfyUI"',
            '"version": "0.22.3"',
        ),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/main-process/comfyServer.ts",
        label="Desktop base/user/input/output directories",
        required_patterns=(
            "userDirectoryPath",
            "inputDirectoryPath",
            "outputDirectoryPath",
            "path.join(this.basePath, 'user')",
            "'user-directory': this.userDirectoryPath",
            "'input-directory': this.inputDirectoryPath",
            "'output-directory': this.outputDirectoryPath",
            "'front-end-root': this.webRootPath",
            "'base-directory': this.basePath",
            "'database-url': this.databaseUrl",
            "'extra-model-paths-config': ComfyServerConfig.configPath",
        ),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/virtualEnvironment.ts",
        label="Desktop managed .venv layout",
        required_patterns=("this.venvPath = path.join(basePath, '.venv')", "Scripts', 'python.exe'", "bin', 'python'"),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/config/comfyConfigManager.ts",
        label="Desktop valid basePath shape",
        required_patterns=(
            "DEFAULT_DIRECTORIES",
            "'custom_nodes'",
            "'input'",
            "'output'",
            "['user', ['default']]",
            "'models'",
            "const requiredSubdirs = ['models', 'input', 'user', 'output', 'custom_nodes']",
        ),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/config/comfySettings.ts",
        label="Desktop settings path",
        required_patterns=("path.join(this.#basePath, 'user', 'default', 'comfy.settings.json')",),
    ),
    SurfaceCheck(
        repo="desktop",
        file="package.json",
        label="frontend runtime lane: Desktop bundle",
        required_patterns=('"frontend"', '"version": "1.43.18"'),
        source_revision=DESKTOP_REVISION,
        applicable_lanes=("desktop-0.9.4",),
        note="Setting-change telemetry from frontend v1.47.7 is absent in this bundled lane.",
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="requirements.txt",
        label="frontend runtime lane: ComfyUI package pin",
        required_patterns=("comfyui-frontend-package==1.49.6",),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("core-pin-1.49.6",),
        note=(
            "The package pin includes setting-change telemetry but predates the "
            "standalone asynchronous onChange contract."
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="package.json",
        label="frontend runtime lane: standalone source",
        required_patterns=('"version": "1.52.1"',),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Current standalone source contains telemetry and asynchronous onChange contracts.",
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="main.py",
        label="DynamicVRAM device applicability",
        required_patterns=(
            "def dynamic_vram_supported():",
            "if comfy.model_management.is_nvidia():",
            "if comfy.model_management.is_amd():",
            "if comfy.model_management.rocm_version >= (7, 14):",
            "enables_dynamic_vram() and dynamic_vram_supported()",
        ),
        forbidden_patterns=("comfy.model_management.is_nvidia() and not comfy.model_management.is_wsl()",),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.33.0+",),
        note=(
            "Source applicability only: NVIDIA includes WSL by omitting the old "
            "is_wsl exclusion; AMD requires ROCm 7.14 or later."
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="main.py",
        label="DynamicVRAM PyTorch threshold",
        required_patterns=(
            "comfy.model_management.torch_version_numeric < (2, 8)",
            "DynamicVRAM support requires Pytorch version 2.8 or later.",
            "Falling back to legacy ModelPatcher.",
        ),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.33.0+",),
        note="Feature threshold only; the independent base PyTorch minimum remains 2.7.",
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="README.md",
        label="minimum supported PyTorch version",
        required_patterns=("torch 2.7 is minimally supported",),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
        note="Source policy evidence only; Doctor's runtime diagnostic is aligned separately in R48.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/settings/types.ts",
        label="standalone settings onChange return type",
        required_patterns=("onChange?(newValue: TValue, oldValue?: TValue): void | Promise<void>",),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Standalone-only source contract; core 1.49.6 and Desktop 1.43.18 remain synchronous.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/settings/settingStore.ts",
        label="standalone settings awaited handler containment",
        required_patterns=(
            "async function callHandler(",
            "await setting?.onChange?.(newValue, oldValue)",
            "} catch (error) {",
            "console.warn(`[settings] onChange handler for ${setting?.id} failed`, error)",
            "const handled = callHandler(setting, newValue, oldValue)",
            "await handled",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Standalone host contains synchronous throws and rejected handler promises.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/lib/litegraph/src/LiteGraphGlobal.ts",
        label="named widget restore global default",
        required_patterns=("namedValuesRestore: boolean = false",),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Doctor retains positional-first diagnostics while the host default remains false.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/settings/constants/coreSettings.ts",
        label="named widget restore setting boundary",
        required_patterns=(
            "id: 'Comfy.Workflow.NamedValuesRestore',\n"
            "    name: 'Restore widget values by name',\n"
            "    type: 'boolean',\n"
            "    defaultValue: false,\n"
            "    experimental: true",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/lib/litegraph/src/LGraphNode.ts",
        label="named widget restore authority branch",
        required_patterns=(
            "if (namedValues && LiteGraph.namedValuesRestore)",
            "} else if (info.widgets_values) {",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="A future default/authority change requires an explicit Doctor precedence review.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/core/graph/subgraph/resolveConcretePromotedWidget.ts",
        label="promoted widget concrete source resolution",
        required_patterns=(
            "export function resolveConcretePromotedWidget(",
            "resolved: { node: sourceNode, nodePath, widget: sourceWidget }",
            "export function buildPromotedSourceExecutionId(",
            "createNodeExecutionId([...hostNodeIds, ...nodePath])",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Public source evidence for R49; Doctor production code must not import frontend internals.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/missingMedia/missingMediaScan.ts",
        label="missing media upload spec classification",
        required_patterns=(
            "if (!spec || !isComboInputSpec(spec)) return undefined",
            "if (spec.video_upload) return 'video'",
            "if (spec.image_upload || spec.animated_image_upload) return 'image'",
            "if (spec.audio_upload) return 'audio'",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Private host behavior is observed as source evidence only; R49 remains public-contract bounded.",
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy_api/feature_flags.py",
        label="model type tag feature flag",
        required_patterns=('"supports_model_type_tags": True', "_CORE_FEATURE_FLAGS"),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy/cli_args.py",
        label="models directory CLI override",
        required_patterns=(
            'parser.add_argument("--models-directory"',
            "is_valid_directory",
            "Overrides the models folder in --base-directory",
        ),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/remote/comfyui/jobs/fetchJobs.ts",
        label="cached history query without client id",
        required_patterns=(
            "async function fetchJobsRaw(",
            "const url = `/jobs?status=${statusParam}&limit=${maxItems}&offset=${offset}`",
            "export async function fetchHistory(",
            "export async function fetchHistoryPage(",
            "['completed', 'failed', 'cancelled']",
        ),
        forbidden_patterns=("client_id", "clientId"),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/settings/settingStore.ts",
        label="setting telemetry defaults",
        required_patterns=(
            "const isVisible = setting.type !== 'hidden'",
            "const trackChanges = telemetry?.trackChanges ?? isVisible",
            "const includeValues = telemetry?.includeValues ?? isVisible",
            "if (event) useTelemetry()?.trackSettingChanged(event)",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/settings/types.ts",
        label="setting telemetry opt-out type",
        required_patterns=(
            "type SettingTelemetryOptions",
            "trackChanges: false",
            "includeValues?: never",
            "telemetry?: SettingTelemetryOptions",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/telemetry/initTelemetry.ts",
        label="cloud telemetry initialization gate",
        required_patterns=(
            "const IS_CLOUD_BUILD = __DISTRIBUTION__ === 'cloud'",
            "if (!IS_CLOUD_BUILD) return",
            "setTelemetryRegistry(registry)",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/platform/telemetry/initHostTelemetry.ts",
        label="host telemetry initialization gate",
        required_patterns=(
            "const ENABLE_TELEMETRY_FEATURE = 'enable_telemetry'",
            "remoteConfig.value.enable_telemetry === true",
            "if (!isHostTelemetryEnabled()) return",
            "if (!window.__comfyDesktop2?.Telemetry) return",
            "setTelemetryRegistry(registry)",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/lib/litegraph/src/subgraph/SubgraphNode.ts",
        label="real SubgraphNode public shape",
        required_patterns=(
            "export class SubgraphNode extends LGraphNode implements BaseLGraph",
            "override readonly isVirtualNode = true as const",
            "override isSubgraphNode()",
            "readonly subgraph: Subgraph",
            "override getInnerNodes(",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=(
            "desktop-0.9.4",
            "core-pin-1.49.6",
            "standalone-1.52.1+",
        ),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/core/graph/subgraph/liftNodeErrorsToBoundary.ts",
        label="boundary error source provenance",
        required_patterns=(
            "input_name: surface.hostInputName",
            "source_execution_id: executionId",
            "source_input_name: inputName",
            "export function liftNodeErrorsToBoundary(",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/stores/executionErrorStore.ts",
        label="surfaced error derivation",
        required_patterns=(
            "const surfacedNodeErrors = computed(() =>",
            "lastNodeErrors.value && app.isGraphReady",
            "liftNodeErrorsToBoundary(app.rootGraph, lastNodeErrors.value)",
            ": lastNodeErrors.value",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="This is private host evidence; Doctor production code may use only public raw error state.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="browser_tests/assets/missing/missing_model_nested_promoted_widget.json",
        label="nested promoted missing-model serialization",
        required_patterns=(
            '"definitions"',
            '"subgraphs"',
            '"ckpt_name"',
            '"widgets_values"',
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="The fixture is read as inert text and is never executed.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/lib/litegraph/src/LGraphNode.ts",
        label="dual positional and named widget serialization",
        required_patterns=(
            "o.widgets_values = []",
            "o.widgets_values_named = {}",
            "o.widgets_values[i] = serialisedVal",
            "o.widgets_values_named[widget.name] = serialisedVal",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
        note="Current workflows may carry both positional and widget-name keyed values.",
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/utils/executionErrorUtil.ts",
        label="partner node validation classification",
        required_patterns=(
            "NODE_LEVEL_VALIDATION_ERROR_TYPES",
            "'PARTNER_NODE_DISABLED'",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/scripts/app.ts",
        label="partner policy 403 handling",
        required_patterns=(
            "const hasPromptNodeErrors =",
            "error.status === 403",
            "!hasPromptNodeErrors",
        ),
        source_revision=FRONTEND_REVISION,
        applicable_lanes=("standalone-1.52.1+",),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="folder_paths.py",
        label="datasets folder registration",
        required_patterns=('folder_names_and_paths["datasets"] =',),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy_extras/nodes_dataset.py",
        label="first-party dataset node registrations",
        required_patterns=(
            'node_id="LoadImageDataSetFromFolder"',
            'node_id="LoadImageTextDataSetFromFolder"',
            'node_id="LoadVideoDataSetFromFolder"',
            'node_id="LoadVideoTextDataSetFromFolder"',
            'node_id="LoadTrainingDataset"',
        ),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="comfy/cli_args.py",
        label="DETAIL logging CLI contract",
        required_patterns=(
            "LOG_LEVELS = ('DEBUG', 'DETAIL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')",
            "class VerboseAction",
            "def get_console_log_level",
            "def get_file_log_outputs",
        ),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
        note="Observed host logging surface only; Doctor does not ingest host log files.",
    ),
    SurfaceCheck(
        repo="ComfyUI",
        file="main.py",
        label="DETAIL file logging bootstrap",
        required_patterns=(
            "file_log_outputs = get_file_log_outputs(args.verbose)",
            "file_outputs=file_log_outputs",
        ),
        forbidden_patterns=("file_log_outputs = [('DETAIL', 'comfyui_detail.log')",),
        source_revision=COMFYUI_REVISION,
        applicable_lanes=("comfyui-core-v0.31.0+",),
        note="Observed host logging surface only; Doctor does not ingest host log files.",
    ),
    SurfaceCheck(
        repo="desktop",
        file="todesktop.json",
        label="Desktop packaged resource topology",
        required_patterns=(
            '"appFiles"',
            '"assets/ComfyUI/**"',
            '"extraResources"',
            '"filesForDistribution"',
            '"updateUrlBase"',
        ),
        source_revision=DESKTOP_REVISION,
        applicable_lanes=("desktop-0.9.4",),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/config/comfyServerConfig.ts",
        label="Desktop bundled extension topology",
        required_patterns=(
            "parsedConfig.comfyui_desktop.base_path = basePath",
            "path.join(getAppResourcesPath(), 'ComfyUI', 'custom_nodes')",
            "parsedConfig.desktop_extensions = { custom_nodes: customNodesPath }",
        ),
        source_revision=DESKTOP_REVISION,
        applicable_lanes=("desktop-0.9.4",),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/services/cmCli.ts",
        label="Desktop user custom-node restore topology",
        required_patterns=(
            "@trackEvent('migrate_flow:migrate_custom_nodes')",
            "path.join(this.virtualEnvironment.basePath, 'custom_nodes')",
            "path.join(this.virtualEnvironment.basePath, 'custom_nodes', 'ComfyUI-Manager')",
        ),
        source_revision=DESKTOP_REVISION,
        applicable_lanes=("desktop-0.9.4",),
    ),
)


# CRITICAL: keep reference inspection text-only; reference repositories are untrusted evidence.
def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None


def run_checks(reference_root: Path, checks: Sequence[SurfaceCheck] = CHECKS) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        path = reference_root / check.repo / Path(check.file)
        text = _read_text(path)
        if text is None:
            results.append(CheckResult(check=check, ok=False, missing_file=True))
            continue

        missing = tuple(pattern for pattern in check.required_patterns if pattern not in text)
        forbidden = tuple(pattern for pattern in check.forbidden_patterns if pattern in text)
        results.append(
            CheckResult(
                check=check,
                ok=not missing and not forbidden,
                missing_patterns=missing,
                present_forbidden_patterns=forbidden,
            )
        )
    return results


def format_results(results: Iterable[CheckResult]) -> str:
    lines = ["Host compatibility smoke check:", "Frontend runtime matrix:"]
    for lane in FRONTEND_RUNTIME_LANES:
        telemetry = "present" if lane.setting_change_telemetry else "absent"
        async_setting = "present" if lane.async_setting_on_change else "absent"
        lines.append(
            f"- {lane.id}: frontend {lane.version} "
            f"({lane.label}; setting-change telemetry {telemetry}; "
            f"async setting onChange {async_setting})"
        )
    lines.append("Surface checks:")
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        location = f"{result.check.repo}/{result.check.file}"
        lines.append(f"- {prefix}: {result.check.label} ({location})")
        if result.missing_file:
            lines.append("  Missing required reference file.")
        elif result.missing_patterns:
            missing = ", ".join(repr(pattern) for pattern in result.missing_patterns)
            lines.append(f"  Missing required pattern(s): {missing}")
        if result.present_forbidden_patterns:
            present = ", ".join(repr(pattern) for pattern in result.present_forbidden_patterns)
            lines.append(f"  Present forbidden pattern(s): {present}")
        if result.check.source_revision:
            lines.append(f"  Source revision: {result.check.source_revision}")
        if result.check.applicable_lanes:
            lines.append(f"  Applies to: {', '.join(result.check.applicable_lanes)}")
        if result.check.note:
            lines.append(f"  Note: {result.check.note}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate local host reference compatibility surfaces.")
    parser.add_argument(
        "--reference-root",
        default="reference",
        type=Path,
        help="Path to the directory containing ComfyUI, ComfyUI_frontend, and desktop reference checkouts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reference_root = args.reference_root.resolve()
    results = run_checks(reference_root)
    print(format_results(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
