import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_host_compatibility.py"
SPEC = importlib.util.spec_from_file_location("check_host_compatibility", SCRIPT_PATH)
host_compat = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = host_compat
SPEC.loader.exec_module(host_compat)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _create_minimal_reference(root: Path) -> None:
    _write(
        root / "ComfyUI" / "main.py",
        "file_log_outputs = [('DETAIL', 'comfyui_detail.log'), *get_file_log_outputs(args.verbose)]\n"
        "setup_logger(log_level=console_log_level, stdout=args.stdout, file_outputs=file_log_outputs)\n"
        "def execute_prestartup_script():\n    return 'prestartup_script.py'\n",
    )
    _write(root / "ComfyUI" / "nodes.py", "EXTENSION_WEB_DIRS = {}\nWEB_DIRECTORY = './web'\n")
    _write(root / "ComfyUI" / "requirements.txt", "comfyui-frontend-package==1.47.10\n")
    _write(
        root / "ComfyUI" / "comfy" / "cli_args.py",
        "LOG_LEVELS = ('DEBUG', 'DETAIL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')\n"
        "class VerboseAction(argparse.Action):\n    pass\n"
        "def get_console_log_level(outputs):\n    return 'INFO'\n"
        "def get_file_log_outputs(outputs):\n    return []\n"
        'parser.add_argument("--models-directory", type=is_valid_directory, '
        'help="Set the ComfyUI models directory. Overrides the models folder in --base-directory.")\n',
    )
    _write(
        root / "ComfyUI" / "server.py",
        "class PromptServer:\n    def __init__(self):\n        self.routes = []\n"
        '@routes.get("/extensions")\n'
        '@routes.get("/features")\n'
        '@routes.get("/system_stats")\n'
        "def get_extensions():\n    return EXTENSION_WEB_DIRS\n"
        "def queue_prompt(request, json_data):\n"
        "    extra_data = json_data['extra_data']\n"
        '    if "comfy_usage_source" not in extra_data:\n'
        '        usage_source = request.headers.get("Comfy-Usage-Source")\n'
        "        if usage_source:\n"
        '            extra_data["comfy_usage_source"] = usage_source\n'
        "def system_stats():\n"
        "    torch_devices = comfy.model_management.get_all_torch_devices()\n"
        "    device_entries = []\n"
        "    comfy_package_versions = FrontendManager.get_comfy_package_versions()\n"
        '    return {"devices": device_entries, "comfy_package_versions": comfy_package_versions, '
        '"deploy_environment": get_deploy_environment()}\n'
        "def _cancel_job_by_id(job_id):\n"
        "    return self.prompt_queue.interrupt_if_running(job_id)\n"
        "    classification = cancel_job(job_id, running, queued, history, interrupt, dequeue)\n"
        "    return classification in (CANCEL_RUNNING, CANCEL_PENDING)\n"
        '@routes.post("/api/jobs/{job_id}/cancel")\n'
        "async def cancel_job_by_id(request):\n    pass\n"
        '@routes.post("/api/jobs/cancel")\n'
        "async def cancel_jobs_batch(request):\n    pass\n"
        'if first_message and data.get("type") == "feature_flags":\n'
        '    self.sockets_metadata[sid]["feature_flags"] = client_flags\n'
        "    feature_flags.get_server_features()\n"
        "# Prefix every route with /api for easier matching for delegation.\n"
        'api_routes.route(route.method, "/api" + route.path)(route.handler, **route.kwargs)\n'
        "self.app.add_routes(api_routes)\n"
        "self.app.add_routes(self.routes)\n"
        "web.static('/extensions/' + name, dir)\n",
    )
    _write(
        root / "ComfyUI" / "execution.py",
        '"execution_error" "node_id" "node_type" "traceback" "current_inputs" "current_outputs"\n'
        'if io.Hidden.comfy_usage_source.name in hidden:\n'
        '    hidden_inputs_v3[io.Hidden.comfy_usage_source] = extra_data.get("comfy_usage_source", None)\n'
        'input_data_all[x] = [extra_data.get("comfy_usage_source", None)]\n'
        "output_ui = enrich_output_with_assets(output_ui)\n"
        '"executed" "output": output_ui\n'
        "def interrupt_if_running(self, prompt_id):\n"
        "    if self.currently_running == prompt_id:\n"
        "        comfy.model_management.interrupt_processing()\n",
    )
    _write(
        root / "ComfyUI" / "comfy_execution" / "jobs.py",
        "CANCEL_RUNNING = 'running'\n"
        "CANCEL_PENDING = 'pending'\n"
        "CANCEL_TERMINAL = 'terminal'\n"
        "CANCEL_UNKNOWN = 'unknown'\n"
        "def classify_job_for_cancel(job_id, running, queued, history):\n"
        "    return CANCEL_PENDING\n"
        "def cancel_job(job_id, running, queued, history, interrupt, dequeue):\n"
        "    return CANCEL_RUNNING\n",
    )
    _write(
        root / "ComfyUI" / "comfy_execution" / "progress.py",
        '"progress_state" "display_node_id" "parent_node_id" "real_node_id" supports_preview_metadata\n',
    )
    _write(
        root / "ComfyUI" / "folder_paths.py",
        'folder_names_and_paths["diffusion_models"] = []\n'
        'folder_names_and_paths["text_encoders"] = []\n'
        'folder_names_and_paths["clip_vision"] = []\n'
        'folder_names_and_paths["style_models"] = []\n'
        'folder_names_and_paths["photomaker"] = []\n'
        'folder_names_and_paths["classifiers"] = []\n'
        'folder_names_and_paths["model_patches"] = []\n'
        'folder_names_and_paths["audio_encoders"] = []\n'
        'folder_names_and_paths["background_removal"] = []\n'
        'folder_names_and_paths["frame_interpolation"] = []\n'
        'folder_names_and_paths["geometry_estimation"] = []\n'
        'folder_names_and_paths["optical_flow"] = []\n'
        'folder_names_and_paths["detection"] = []\n'
        'folder_names_and_paths["datasets"] = ([os.path.join(base_path, "datasets")], set())\n'
        "def get_system_user_directory(name='system'):\n    return name\n"
        "def get_public_user_directory(user_id):\n    return user_id\n",
    )
    _write(
        root / "ComfyUI" / "comfy_extras" / "nodes_dataset.py",
        'node_id="LoadImageDataSetFromFolder"\n'
        'node_id="LoadImageTextDataSetFromFolder"\n'
        'node_id="LoadVideoDataSetFromFolder"\n'
        'node_id="LoadVideoTextDataSetFromFolder"\n'
        'node_id="LoadTrainingDataset"\n',
    )
    _write(
        root / "ComfyUI" / "comfy_api" / "feature_flags.py",
        "_CORE_FEATURE_FLAGS = {\n"
        '"supports_preview_metadata": True\n'
        '"supports_model_type_tags": True\n'
        '"extension": {"manager": {"supports_v4": True}}\n'
        '"node_replacements": True\n'
        '"enable_telemetry": {"default": False}\n'
        "}\n"
        "def get_server_features():\n    return {}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "package.json",
        '{"name": "@comfyorg/comfyui-frontend", "version": "1.49.1"}\n',
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "types" / "extensionTypes.ts",
        "registerSidebarTab(tab)\nsetting: {\nget: <T = unknown>(id: string) => undefined\n"
        "set: <T = unknown>(id: string, value: T) => void\n}\n"
        "lastNodeErrors: Record<NodeId, NodeError> | null\n"
        "lastExecutionError: ExecutionErrorWsMessage | null\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "stores" / "workspaceStore.ts",
        "const sidebarTab = computed(() => useSidebarTabStore())\n"
        "Use `sidebarTab.registerSidebarTab` instead\n"
        "sidebarTab.value.registerSidebarTab(tab)\n"
        "Use `sidebarTab.unregisterSidebarTab` instead\n"
        "sidebarTab.value.unregisterSidebarTab(id)\n"
        "Use `sidebarTab.sidebarTabs` instead\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "stores" / "workspace" / "sidebarTabStore.ts",
        "defineStore('sidebarTab'\n"
        "const sidebarTabs = ref<SidebarTabExtension[]>([])\n"
        "const activeSidebarTabId = ref<string | null>(null)\n"
        "const registerSidebarTab = () => {}\n"
        "const unregisterSidebarTab = () => {}\n"
        "toggleSidebarTab\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "schemas" / "apiSchema.ts",
        "const zExecutionErrorWsMessage = z.object({ node_id: z.string(), node_type: z.string(), "
        "traceback: z.array(z.string()), current_inputs: z.any(), current_outputs: z.any() })\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "scripts" / "app.ts",
        "rootGraph\n"
        "lastExecutionError\n"
        "const hasPromptNodeErrors = Object.keys(response.node_errors).length > 0\n"
        "if (error.status === 403 && !hasPromptNodeErrors) {\n"
        "  showError(error)\n"
        "}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "utils" / "executionErrorUtil.ts",
        "export const NODE_LEVEL_VALIDATION_ERROR_TYPES = new Set([\n"
        "  'PARTNER_NODE_DISABLED',\n"
        "  'exception_during_validation',\n"
        "  'dependency_cycle'\n"
        "])\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "scripts" / "api.ts",
        "async queuePrompt(number, { output, workflow }) {\n"
        "  const body = {\n"
        "    extra_data: {\n"
        "      client_id: this.clientId,\n"
        "      comfy_usage_source: 'comfyui-frontend',\n"
        "    }\n"
        "  }\n"
        "  return body\n"
        "}\n"
        "async cancelJob(jobId: string) {\n"
        "  return this.fetchApi(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })\n"
        "}\n"
        "async cancelJobs(jobIds: string[]) {\n"
        "  return this.fetchApi('/jobs/cancel', { method: 'POST', body: JSON.stringify({ job_ids: jobIds }) })\n"
        "}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "platform" / "remote" / "comfyui" / "jobs" / "fetchJobs.ts",
        "async function fetchJobsRaw(fetchApi, statuses, maxItems = 200, offset = 0) {\n"
        "  const statusParam = statuses.join(',')\n"
        "  const url = `/jobs?status=${statusParam}&limit=${maxItems}&offset=${offset}`\n"
        "  return fetchApi(url)\n"
        "}\n"
        "export async function fetchHistory(fetchApi, maxItems = 200, offset = 0) {\n"
        "  return fetchHistoryPage(fetchApi, maxItems, offset)\n"
        "}\n"
        "export async function fetchHistoryPage(fetchApi, maxItems = 200, offset = 0) {\n"
        "  return fetchJobsRaw(fetchApi, ['completed', 'failed', 'cancelled'], maxItems, offset)\n"
        "}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "platform" / "settings" / "settingStore.ts",
        "const isVisible = setting.type !== 'hidden'\n"
        "const trackChanges = telemetry?.trackChanges ?? isVisible\n"
        "if (!trackChanges) return undefined\n"
        "const includeValues = telemetry?.includeValues ?? isVisible\n"
        "const event = settingChangedEvent(settingsById.value[key], key, applied)\n"
        "if (event) useTelemetry()?.trackSettingChanged(event)\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "platform" / "settings" / "types.ts",
        "type SettingTelemetryOptions =\n"
        "  | { trackChanges: false; includeValues?: never }\n"
        "  | { trackChanges?: true; includeValues?: boolean }\n"
        "export interface SettingParams { telemetry?: SettingTelemetryOptions }\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "platform" / "telemetry" / "initTelemetry.ts",
        "const IS_CLOUD_BUILD = __DISTRIBUTION__ === 'cloud'\n"
        "export async function initTelemetry() {\n"
        "  if (!IS_CLOUD_BUILD) return\n"
        "  setTelemetryRegistry(registry)\n"
        "}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "platform" / "telemetry" / "initHostTelemetry.ts",
        "const ENABLE_TELEMETRY_FEATURE = 'enable_telemetry'\n"
        "return remoteConfig.value.enable_telemetry === true\n"
        "if (!isHostTelemetryEnabled()) return\n"
        "if (!window.__comfyDesktop2?.Telemetry) return\n"
        "setTelemetryRegistry(registry)\n",
    )
    _write(
        root
        / "ComfyUI_frontend"
        / "src"
        / "lib"
        / "litegraph"
        / "src"
        / "subgraph"
        / "SubgraphNode.ts",
        "export class SubgraphNode extends LGraphNode implements BaseLGraph {\n"
        "  override readonly isVirtualNode = true as const\n"
        "  readonly subgraph: Subgraph\n"
        "  override isSubgraphNode(): this is SubgraphNode { return true }\n"
        "  override getInnerNodes(executableNodes) { return executableNodes }\n"
        "}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "lib" / "litegraph" / "src" / "LGraphNode.ts",
        "if (widgets?.length && this.serialize_widgets) {\n"
        "  o.widgets_values = []\n"
        "  o.widgets_values_named = {}\n"
        "  for (const [i, widget] of widgets.entries()) {\n"
        "    o.widgets_values[i] = serialisedVal\n"
        "    o.widgets_values_named[widget.name] = serialisedVal\n"
        "  }\n"
        "}\n",
    )
    _write(
        root
        / "ComfyUI_frontend"
        / "src"
        / "core"
        / "graph"
        / "subgraph"
        / "liftNodeErrorsToBoundary.ts",
        "const liftedExtraInfo = {\n"
        "  input_name: surface.hostInputName,\n"
        "  source_execution_id: executionId,\n"
        "  source_input_name: inputName\n"
        "}\n"
        "export function liftNodeErrorsToBoundary(rootGraph, nodeErrors) { return nodeErrors }\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "stores" / "executionErrorStore.ts",
        "const surfacedNodeErrors = computed(() =>\n"
        "  lastNodeErrors.value && app.isGraphReady\n"
        "    ? liftNodeErrorsToBoundary(app.rootGraph, lastNodeErrors.value)\n"
        "    : lastNodeErrors.value\n"
        ")\n",
    )
    _write(
        root
        / "ComfyUI_frontend"
        / "browser_tests"
        / "assets"
        / "missing"
        / "missing_model_nested_promoted_widget.json",
        '{"definitions":{"subgraphs":[{"id":"synthetic-subgraph","inputs":'
        '[{"name":"ckpt_name","type":"COMBO"}],"nodes":[{"id":2,'
        '"widgets_values":["synthetic_model.safetensors"]}]}]}}\n',
    )
    _write(
        root / "desktop" / "package.json",
        '{\n  "version": "0.9.4",\n  "config": {'
        '"frontend": {"version": "1.43.18"}, '
        '"comfyUI": {"version": "0.22.3"}}\n}\n',
    )
    _write(
        root / "desktop" / "todesktop.json",
        '{"appFiles":["assets/ComfyUI/**"],"extraResources":[{"from":"./assets"}],'
        '"filesForDistribution":["!assets/**"],"updateUrlBase":"https://updater.comfy.org"}\n',
    )
    _write(
        root / "desktop" / "src" / "main-process" / "comfyServer.ts",
        "userDirectoryPath\n"
        "inputDirectoryPath\n"
        "outputDirectoryPath\n"
        "path.join(this.basePath, 'user')\n"
        "'user-directory': this.userDirectoryPath\n"
        "'input-directory': this.inputDirectoryPath\n"
        "'output-directory': this.outputDirectoryPath\n"
        "'front-end-root': this.webRootPath\n"
        "'base-directory': this.basePath\n"
        "'database-url': this.databaseUrl\n"
        "'extra-model-paths-config': ComfyServerConfig.configPath\n",
    )
    _write(
        root / "desktop" / "src" / "virtualEnvironment.ts",
        "this.venvPath = path.join(basePath, '.venv')\nScripts', 'python.exe'\nbin', 'python'\n",
    )
    _write(
        root / "desktop" / "src" / "config" / "comfyConfigManager.ts",
        "DEFAULT_DIRECTORIES\n"
        "'custom_nodes'\n"
        "'input'\n"
        "'output'\n"
        "['user', ['default']]\n"
        "'models'\n"
        "const requiredSubdirs = ['models', 'input', 'user', 'output', 'custom_nodes']\n",
    )
    _write(
        root / "desktop" / "src" / "config" / "comfySettings.ts",
        "path.join(this.#basePath, 'user', 'default', 'comfy.settings.json')\n",
    )
    _write(
        root / "desktop" / "src" / "config" / "comfyServerConfig.ts",
        "parsedConfig.comfyui_desktop.base_path = basePath\n"
        "const customNodesPath = path.join(getAppResourcesPath(), 'ComfyUI', 'custom_nodes')\n"
        "parsedConfig.desktop_extensions = { custom_nodes: customNodesPath }\n",
    )
    _write(
        root / "desktop" / "src" / "services" / "cmCli.ts",
        "@trackEvent('migrate_flow:migrate_custom_nodes')\n"
        "path.join(this.virtualEnvironment.basePath, 'custom_nodes')\n"
        "path.join(this.virtualEnvironment.basePath, 'custom_nodes', 'ComfyUI-Manager')\n",
    )


def test_host_compatibility_smoke_passes_for_expected_surfaces(tmp_path):
    _create_minimal_reference(tmp_path)

    results = host_compat.run_checks(tmp_path)

    assert all(result.ok for result in results)


def test_host_compatibility_smoke_reports_missing_patterns(tmp_path):
    _create_minimal_reference(tmp_path)
    (tmp_path / "ComfyUI_frontend" / "src" / "types" / "extensionTypes.ts").write_text(
        "registerSidebarTab(tab)\n"
        "lastNodeErrors: Record<NodeId, NodeError> | null\n"
        "lastExecutionError: ExecutionErrorWsMessage | null\n",
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "extensionManager settings/sidebar API"
    assert "setting:" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_current_sidebar_store(tmp_path):
    _create_minimal_reference(tmp_path)
    (tmp_path / "ComfyUI_frontend" / "src" / "stores" / "workspace" / "sidebarTabStore.ts").write_text(
        "defineStore('sidebarTab'\n",
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "current sidebarTab store API"
    assert "const registerSidebarTab =" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_last_node_errors(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "types" / "extensionTypes.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace("lastNodeErrors", "legacyNodeErrors"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "extensionManager execution error state"
    assert "lastNodeErrors" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_system_stats_package_versions(tmp_path):
    _create_minimal_reference(tmp_path)
    server_path = tmp_path / "ComfyUI" / "server.py"
    server_path.write_text(
        server_path.read_text(encoding="utf-8").replace("comfy_package_versions", "frontend_package_versions"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "system_stats current multi-device package versions"
    assert "comfy_package_versions" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_current_model_folder_anchor(tmp_path):
    _create_minimal_reference(tmp_path)
    folder_paths_path = tmp_path / "ComfyUI" / "folder_paths.py"
    folder_paths_path.write_text(
        folder_paths_path.read_text(encoding="utf-8").replace('"geometry_estimation"', '"depth_estimation"'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "current model folder anchors"
    assert '"geometry_estimation"' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_desktop_current_baseline(tmp_path):
    _create_minimal_reference(tmp_path)
    package_path = tmp_path / "desktop" / "package.json"
    package_path.write_text(
        package_path.read_text(encoding="utf-8").replace('"version": "0.22.3"', '"version": "0.21.0"'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "Desktop current bundled host baseline"
    assert '"version": "0.22.3"' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_deprecated_sidebar_fallback(tmp_path):
    _create_minimal_reference(tmp_path)
    (tmp_path / "ComfyUI_frontend" / "src" / "stores" / "workspaceStore.ts").write_text(
        "const sidebarTab = computed(() => useSidebarTabStore())\n",
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "deprecated sidebar wrapper fallback"
    assert "sidebarTab.value.registerSidebarTab(tab)" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_api_route_duplication(tmp_path):
    _create_minimal_reference(tmp_path)
    server_path = tmp_path / "ComfyUI" / "server.py"
    server_path.write_text(
        server_path.read_text(encoding="utf-8").replace('"/api" + route.path', '"/v2" + route.path'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "host /api route duplication"
    assert '"/api" + route.path' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_server_usage_source_pass_through(tmp_path):
    _create_minimal_reference(tmp_path)
    server_path = tmp_path / "ComfyUI" / "server.py"
    server_path.write_text(
        server_path.read_text(encoding="utf-8").replace('"Comfy-Usage-Source"', '"Legacy-Source"'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "prompt usage source pass-through"
    assert 'request.headers.get("Comfy-Usage-Source")' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_execution_usage_source_hidden_input(tmp_path):
    _create_minimal_reference(tmp_path)
    execution_path = tmp_path / "ComfyUI" / "execution.py"
    execution_path.write_text(
        execution_path.read_text(encoding="utf-8").replace("io.Hidden.comfy_usage_source", "io.Hidden.legacy_source"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "execution usage source hidden input"
    assert "io.Hidden.comfy_usage_source.name in hidden" in failed[0].missing_patterns
    assert "hidden_inputs_v3[io.Hidden.comfy_usage_source]" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_frontend_queue_usage_source(tmp_path):
    _create_minimal_reference(tmp_path)
    api_path = tmp_path / "ComfyUI_frontend" / "src" / "scripts" / "api.ts"
    api_path.write_text(
        api_path.read_text(encoding="utf-8").replace("comfy_usage_source: 'comfyui-frontend'", "usage_source: 'legacy'"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "frontend queue prompt usage source"
    assert "comfy_usage_source: 'comfyui-frontend'" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_expanded_model_folder_anchor(tmp_path):
    _create_minimal_reference(tmp_path)
    folder_paths_path = tmp_path / "ComfyUI" / "folder_paths.py"
    folder_paths_path.write_text(
        folder_paths_path.read_text(encoding="utf-8").replace('"background_removal"', '"legacy_background"'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "current expanded model folder anchors"
    assert '"background_removal"' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_executed_asset_enrichment_anchor(tmp_path):
    _create_minimal_reference(tmp_path)
    execution_path = tmp_path / "ComfyUI" / "execution.py"
    execution_path.write_text(
        execution_path.read_text(encoding="utf-8").replace("enrich_output_with_assets(output_ui)", "output_ui"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "executed output asset enrichment tolerance"
    assert "enrich_output_with_assets(output_ui)" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_system_stats_deploy_environment(tmp_path):
    _create_minimal_reference(tmp_path)
    server_path = tmp_path / "ComfyUI" / "server.py"
    server_path.write_text(
        server_path.read_text(encoding="utf-8").replace("get_deploy_environment", "get_legacy_environment"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "system_stats deploy environment"
    assert "get_deploy_environment" in failed[0].missing_patterns
    assert '"deploy_environment": get_deploy_environment()' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_jobs_cancel_endpoint(tmp_path):
    _create_minimal_reference(tmp_path)
    server_path = tmp_path / "ComfyUI" / "server.py"
    server_path.write_text(
        server_path.read_text(encoding="utf-8").replace("/api/jobs/{job_id}/cancel", "/api/jobs/{job_id}/stop"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "jobs namespace cancel endpoints"
    assert '@routes.post("/api/jobs/{job_id}/cancel")' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_prompt_queue_interrupt_hook(tmp_path):
    _create_minimal_reference(tmp_path)
    execution_path = tmp_path / "ComfyUI" / "execution.py"
    execution_path.write_text(
        execution_path.read_text(encoding="utf-8").replace("def interrupt_if_running", "def legacy_interrupt"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "prompt queue running job interrupt hook"
    assert "def interrupt_if_running" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_jobs_cancel_classification_helper(tmp_path):
    _create_minimal_reference(tmp_path)
    jobs_path = tmp_path / "ComfyUI" / "comfy_execution" / "jobs.py"
    jobs_path.write_text(
        jobs_path.read_text(encoding="utf-8").replace("CANCEL_TERMINAL", "CANCEL_DONE"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "jobs cancel classification helpers"
    assert "CANCEL_TERMINAL" in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_enable_telemetry_feature_flag(tmp_path):
    _create_minimal_reference(tmp_path)
    feature_flags_path = tmp_path / "ComfyUI" / "comfy_api" / "feature_flags.py"
    feature_flags_path.write_text(
        feature_flags_path.read_text(encoding="utf-8").replace('"enable_telemetry":', '"legacy_telemetry":'),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "server feature flags"
    assert '"enable_telemetry":' in failed[0].missing_patterns


def test_host_compatibility_smoke_reports_missing_frontend_jobs_cancel_api(tmp_path):
    _create_minimal_reference(tmp_path)
    api_path = tmp_path / "ComfyUI_frontend" / "src" / "scripts" / "api.ts"
    api_path.write_text(
        api_path.read_text(encoding="utf-8").replace("async cancelJobs", "async stopJobs"),
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "frontend jobs cancel API"
    assert "async cancelJobs(" in failed[0].missing_patterns


PRE_T28_CHECK_LABELS = {
    "custom node prestartup loading",
    "WEB_DIRECTORY registration",
    "extension static routes",
    "PromptServer route registry",
    "host /api route duplication",
    "feature-flag websocket exchange",
    "system_stats current multi-device package versions",
    "system_stats deploy environment",
    "jobs namespace cancel endpoints",
    "prompt usage source pass-through",
    "execution_error websocket payload",
    "execution usage source hidden input",
    "executed output asset enrichment tolerance",
    "prompt queue running job interrupt hook",
    "jobs cancel classification helpers",
    "progress_state lineage payload",
    "current model folder anchors",
    "current expanded model folder anchors",
    "server feature flags",
    "extensionManager execution error state",
    "frontend queue prompt usage source",
    "frontend jobs cancel API",
    "extensionManager settings/sidebar API",
    "deprecated sidebar wrapper fallback",
    "current sidebarTab store API",
    "frontend execution_error schema",
    "frontend rootGraph API",
    "Desktop current bundled host baseline",
    "Desktop base/user/input/output directories",
    "Desktop managed .venv layout",
    "Desktop valid basePath shape",
    "Desktop settings path",
}


def _failed_results(root: Path):
    return [result for result in host_compat.run_checks(root) if not result.ok]


def test_t28_preserves_all_preexisting_surface_checks():
    labels = {check.label for check in host_compat.CHECKS}

    assert len(PRE_T28_CHECK_LABELS) == 32
    assert PRE_T28_CHECK_LABELS <= labels


def test_t28_records_three_distinct_frontend_runtime_lanes():
    lanes = getattr(host_compat, "FRONTEND_RUNTIME_LANES", ())

    assert [
        (lane.id, lane.version, lane.setting_change_telemetry)
        for lane in lanes
    ] == [
        ("desktop-0.9.4", "1.43.18", False),
        ("core-pin-1.47.10", "1.47.10", True),
        ("standalone-1.49.1+", "1.49.1+", True),
    ]


def test_t28_runtime_lane_source_versions_fail_in_isolation(tmp_path):
    cases = (
        (
            "desktop",
            Path("desktop/package.json"),
            '"version": "1.43.18"',
            '"version": "1.43.17"',
            "frontend runtime lane: Desktop bundle",
        ),
        (
            "core",
            Path("ComfyUI/requirements.txt"),
            "comfyui-frontend-package==1.47.10",
            "comfyui-frontend-package==1.47.9",
            "frontend runtime lane: ComfyUI package pin",
        ),
        (
            "standalone",
            Path("ComfyUI_frontend/package.json"),
            '"version": "1.49.1"',
            '"version": "1.49.0"',
            "frontend runtime lane: standalone source",
        ),
    )

    for case_name, relative_path, current, mutated, expected_label in cases:
        root = tmp_path / case_name
        _create_minimal_reference(root)
        path = root / relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace(current, mutated),
            encoding="utf-8",
        )

        failed = _failed_results(root)

        assert len(failed) == 1
        assert failed[0].check.label == expected_label
        assert current in failed[0].missing_patterns


def test_t28_reports_missing_model_type_tag_feature(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI" / "comfy_api" / "feature_flags.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"supports_model_type_tags": True',
            '"supports_legacy_model_tags": True',
        ),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "model type tag feature flag"
    assert '"supports_model_type_tags": True' in failed[0].missing_patterns


def test_t28_reports_missing_models_directory_cli_override(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI" / "comfy" / "cli_args.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace("--models-directory", "--legacy-models-directory"),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "models directory CLI override"
    assert 'parser.add_argument("--models-directory"' in failed[0].missing_patterns


def test_t28_rejects_client_id_in_cached_history_query_contract(tmp_path):
    _create_minimal_reference(tmp_path)
    path = (
        tmp_path
        / "ComfyUI_frontend"
        / "src"
        / "platform"
        / "remote"
        / "comfyui"
        / "jobs"
        / "fetchJobs.ts"
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "&offset=${offset}`",
            "&offset=${offset}&client_id=synthetic`",
        ),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "cached history query without client id"
    assert "client_id" in failed[0].present_forbidden_patterns


def test_t28_reports_missing_setting_telemetry_defaults(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "platform" / "settings" / "settingStore.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "const trackChanges = telemetry?.trackChanges ?? isVisible",
            "const trackChanges = false",
        ),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "setting telemetry defaults"
    assert "const trackChanges = telemetry?.trackChanges ?? isVisible" in failed[0].missing_patterns


def test_t28_reports_missing_setting_telemetry_opt_out_type(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "platform" / "settings" / "types.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace("trackChanges: false", "trackChanges: true"),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "setting telemetry opt-out type"
    assert "trackChanges: false" in failed[0].missing_patterns


def test_t28_reports_missing_cloud_telemetry_initialization_gate(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "platform" / "telemetry" / "initTelemetry.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace("if (!IS_CLOUD_BUILD) return", "if (false) return"),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "cloud telemetry initialization gate"
    assert "if (!IS_CLOUD_BUILD) return" in failed[0].missing_patterns


def test_t28_reports_missing_host_telemetry_initialization_gate(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "platform" / "telemetry" / "initHostTelemetry.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "remoteConfig.value.enable_telemetry === true",
            "remoteConfig.value.enable_telemetry !== false",
        ),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "host telemetry initialization gate"
    assert "remoteConfig.value.enable_telemetry === true" in failed[0].missing_patterns


def test_t28_reports_missing_real_subgraph_node_shape(tmp_path):
    _create_minimal_reference(tmp_path)
    path = (
        tmp_path
        / "ComfyUI_frontend"
        / "src"
        / "lib"
        / "litegraph"
        / "src"
        / "subgraph"
        / "SubgraphNode.ts"
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("override isSubgraphNode()", "override isLegacyNode()"),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "real SubgraphNode public shape"
    assert "override isSubgraphNode()" in failed[0].missing_patterns


def test_t28_reports_missing_boundary_error_provenance(tmp_path):
    _create_minimal_reference(tmp_path)
    path = (
        tmp_path
        / "ComfyUI_frontend"
        / "src"
        / "core"
        / "graph"
        / "subgraph"
        / "liftNodeErrorsToBoundary.ts"
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("source_execution_id", "legacy_execution_id"),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "boundary error source provenance"
    assert "source_execution_id: executionId" in failed[0].missing_patterns


def test_t28_reports_missing_surfaced_error_derivation(tmp_path):
    _create_minimal_reference(tmp_path)
    path = tmp_path / "ComfyUI_frontend" / "src" / "stores" / "executionErrorStore.ts"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "liftNodeErrorsToBoundary(app.rootGraph, lastNodeErrors.value)",
            "lastNodeErrors.value",
        ),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "surfaced error derivation"
    assert "liftNodeErrorsToBoundary(app.rootGraph, lastNodeErrors.value)" in failed[0].missing_patterns


def test_t28_reports_missing_nested_promoted_model_serialization(tmp_path):
    _create_minimal_reference(tmp_path)
    path = (
        tmp_path
        / "ComfyUI_frontend"
        / "browser_tests"
        / "assets"
        / "missing"
        / "missing_model_nested_promoted_widget.json"
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace('"subgraphs"', '"legacy_subgraphs"'),
        encoding="utf-8",
    )

    failed = _failed_results(tmp_path)

    assert len(failed) == 1
    assert failed[0].check.label == "nested promoted missing-model serialization"
    assert '"subgraphs"' in failed[0].missing_patterns


def test_t28_reports_missing_expanded_desktop_topology(tmp_path):
    cases = (
        (
            "package",
            Path("desktop/todesktop.json"),
            '"extraResources"',
            '"legacyResources"',
            "Desktop packaged resource topology",
        ),
        (
            "bundled",
            Path("desktop/src/config/comfyServerConfig.ts"),
            "parsedConfig.desktop_extensions = { custom_nodes: customNodesPath }",
            "parsedConfig.legacy_extensions = { custom_nodes: customNodesPath }",
            "Desktop bundled extension topology",
        ),
        (
            "user",
            Path("desktop/src/services/cmCli.ts"),
            "path.join(this.virtualEnvironment.basePath, 'custom_nodes')",
            "path.join(this.virtualEnvironment.basePath, 'legacy_nodes')",
            "Desktop user custom-node restore topology",
        ),
    )

    for case_name, relative_path, current, mutated, expected_label in cases:
        root = tmp_path / case_name
        _create_minimal_reference(root)
        path = root / relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace(current, mutated),
            encoding="utf-8",
        )

        failed = _failed_results(root)

        assert len(failed) == 1
        assert failed[0].check.label == expected_label
        assert current in failed[0].missing_patterns


def test_t28_new_checks_report_source_revision_and_applicable_lanes(tmp_path):
    _create_minimal_reference(tmp_path)
    new_checks = [check for check in host_compat.CHECKS if check.label not in PRE_T28_CHECK_LABELS]

    assert len(new_checks) >= 16
    assert all(check.source_revision for check in new_checks)
    assert all(check.applicable_lanes for check in new_checks)

    formatted = host_compat.format_results(host_compat.run_checks(tmp_path))

    assert "Frontend runtime matrix:" in formatted
    assert "desktop-0.9.4: frontend 1.43.18" in formatted
    assert "core-pin-1.47.10: frontend 1.47.10" in formatted
    assert "standalone-1.49.1+: frontend 1.49.1+" in formatted
    assert "Source revision:" in formatted
    assert "Applies to:" in formatted


def test_t28_reference_source_is_never_executed(tmp_path):
    _create_minimal_reference(tmp_path)
    marker = tmp_path / "reference-side-effect-marker"
    main_path = tmp_path / "ComfyUI" / "main.py"
    main_path.write_text(
        main_path.read_text(encoding="utf-8")
        + "\nfrom pathlib import Path\n"
        + f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)

    assert all(result.ok for result in results)
    assert not marker.exists()


def test_t29_records_current_revisions_and_new_contract_families():
    labels = {check.label for check in host_compat.CHECKS}

    assert host_compat.COMFYUI_REVISION == "9cf91339b708a245762fa38ffeec9702b381e0db"  # pragma: allowlist secret
    assert host_compat.FRONTEND_REVISION == "e0ef062918a47b3b8f4f7b2b26cb1dfb881d4a6d"  # pragma: allowlist secret
    assert {
        "dual positional and named widget serialization",
        "partner node validation classification",
        "partner policy 403 handling",
        "datasets folder registration",
        "first-party dataset node registrations",
        "DETAIL logging CLI contract",
        "DETAIL file logging bootstrap",
    } <= labels


def test_t29_new_contract_anchors_fail_in_isolation(tmp_path):
    cases = (
        (
            "named-widgets",
            Path("ComfyUI_frontend/src/lib/litegraph/src/LGraphNode.ts"),
            "o.widgets_values_named[widget.name] = serialisedVal",
            "o.legacy_widget_values[widget.name] = serialisedVal",
            "dual positional and named widget serialization",
        ),
        (
            "partner-classification",
            Path("ComfyUI_frontend/src/utils/executionErrorUtil.ts"),
            "'PARTNER_NODE_DISABLED'",
            "'LEGACY_PARTNER_DISABLED'",
            "partner node validation classification",
        ),
        (
            "partner-policy",
            Path("ComfyUI_frontend/src/scripts/app.ts"),
            "error.status === 403",
            "error.status === 400",
            "partner policy 403 handling",
        ),
        (
            "datasets-folder",
            Path("ComfyUI/folder_paths.py"),
            'folder_names_and_paths["datasets"] =',
            'folder_names_and_paths["legacy_datasets"] =',
            "datasets folder registration",
        ),
        (
            "dataset-nodes",
            Path("ComfyUI/comfy_extras/nodes_dataset.py"),
            'node_id="LoadTrainingDataset"',
            'node_id="LoadLegacyTrainingDataset"',
            "first-party dataset node registrations",
        ),
        (
            "detail-cli",
            Path("ComfyUI/comfy/cli_args.py"),
            "def get_file_log_outputs",
            "def get_legacy_log_outputs",
            "DETAIL logging CLI contract",
        ),
        (
            "detail-bootstrap",
            Path("ComfyUI/main.py"),
            "file_log_outputs = [('DETAIL', 'comfyui_detail.log')",
            "file_log_outputs = [('DETAIL', 'comfyui_legacy.log')",
            "DETAIL file logging bootstrap",
        ),
    )

    for case_name, relative_path, current, mutated, expected_label in cases:
        root = tmp_path / case_name
        _create_minimal_reference(root)
        path = root / relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace(current, mutated),
            encoding="utf-8",
        )

        failed = _failed_results(root)

        assert len(failed) == 1
        assert failed[0].check.label == expected_label
        assert current in failed[0].missing_patterns
