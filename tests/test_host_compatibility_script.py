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
        "@routes.get(\"/extensions\")\n"
        "def get_extensions():\n    return EXTENSION_WEB_DIRS\n"
        "web.static('/extensions/' + name, dir)\n",
    )
    _write(
        root / "ComfyUI" / "execution.py",
        '"execution_error" "node_id" "node_type" "traceback" "current_inputs" "current_outputs"\n',
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "types" / "extensionTypes.ts",
        "registerSidebarTab(tab)\nsetting: {\nget: <T = unknown>(id: string) => undefined\n"
        "set: <T = unknown>(id: string, value: T) => void\n}\n",
    )
    _write(
        root / "ComfyUI_frontend" / "src" / "schemas" / "apiSchema.ts",
        "const zExecutionErrorWsMessage = z.object({ node_id: z.string(), node_type: z.string(), "
        "traceback: z.array(z.string()), current_inputs: z.any(), current_outputs: z.any() })\n",
    )
    _write(root / "ComfyUI_frontend" / "src" / "scripts" / "app.ts", "rootGraph\nlastExecutionError\n")
    _write(
        root / "desktop" / "src" / "main-process" / "comfyServer.ts",
        "userDirectoryPath\npath.join(this.basePath, 'user')\n'base-directory': this.basePath\n",
    )
    _write(
        root / "desktop" / "src" / "virtualEnvironment.ts",
        "this.venvPath = path.join(basePath, '.venv')\nScripts', 'python.exe'\nbin', 'python'\n",
    )


def test_host_compatibility_smoke_passes_for_expected_surfaces(tmp_path):
    _create_minimal_reference(tmp_path)

    results = host_compat.run_checks(tmp_path)

    assert all(result.ok for result in results)


def test_host_compatibility_smoke_reports_missing_patterns(tmp_path):
    _create_minimal_reference(tmp_path)
    (tmp_path / "ComfyUI_frontend" / "src" / "types" / "extensionTypes.ts").write_text(
        "registerSidebarTab(tab)\n",
        encoding="utf-8",
    )

    results = host_compat.run_checks(tmp_path)
    failed = [result for result in results if not result.ok]

    assert len(failed) == 1
    assert failed[0].check.label == "extensionManager settings/sidebar API"
    assert "setting:" in failed[0].missing_patterns
