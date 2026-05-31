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
    _write(root / "ComfyUI" / "main.py", "def execute_prestartup_script():\n    return 'prestartup_script.py'\n")
    _write(root / "ComfyUI" / "nodes.py", "EXTENSION_WEB_DIRS = {}\nWEB_DIRECTORY = './web'\n")
    _write(
        root / "ComfyUI" / "server.py",
        "class PromptServer:\n    def __init__(self):\n        self.routes = []\n"
        '@routes.get("/extensions")\n'
        '@routes.get("/features")\n'
        '@routes.get("/system_stats")\n'
        "def get_extensions():\n    return EXTENSION_WEB_DIRS\n"
        "def system_stats():\n"
        "    torch_devices = comfy.model_management.get_all_torch_devices()\n"
        "    device_entries = []\n"
        "    comfy_package_versions = FrontendManager.get_comfy_package_versions()\n"
        "    return {'devices': device_entries, 'comfy_package_versions': comfy_package_versions}\n"
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
        '"execution_error" "node_id" "node_type" "traceback" "current_inputs" "current_outputs"\n',
    )
    _write(
        root / "ComfyUI" / "comfy_execution" / "progress.py",
        '"progress_state" "display_node_id" "parent_node_id" "real_node_id" supports_preview_metadata\n',
    )
    _write(
        root / "ComfyUI" / "folder_paths.py",
        'folder_names_and_paths["geometry_estimation"] = []\n'
        'folder_names_and_paths["detection"] = []\n'
        "def get_system_user_directory(name='system'):\n    return name\n"
        "def get_public_user_directory(user_id):\n    return user_id\n",
    )
    _write(
        root / "ComfyUI" / "comfy_api" / "feature_flags.py",
        '"supports_preview_metadata": True\n'
        '"extension": {"manager": {"supports_v4": True}}\n'
        '"node_replacements": True\n'
        "def get_server_features():\n    return {}\n",
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
    _write(root / "ComfyUI_frontend" / "src" / "scripts" / "app.ts", "rootGraph\nlastExecutionError\n")
    _write(
        root / "desktop" / "package.json",
        '{\n  "version": "0.9.4",\n  "config": {"comfyUI": {"version": "0.22.3"}}\n}\n',
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
