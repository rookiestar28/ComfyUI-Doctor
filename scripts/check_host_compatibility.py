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
    note: str = ""


@dataclass(frozen=True)
class CheckResult:
    check: SurfaceCheck
    ok: bool
    missing_file: bool = False
    missing_patterns: tuple[str, ...] = ()


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
        file="comfy_api/feature_flags.py",
        label="server feature flags",
        required_patterns=(
            '"supports_preview_metadata": True',
            '"extension": {"manager": {"supports_v4": True}}',
            '"node_replacements": True',
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
)


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
        results.append(CheckResult(check=check, ok=not missing, missing_patterns=missing))
    return results


def format_results(results: Iterable[CheckResult]) -> str:
    lines = ["Host compatibility smoke check:"]
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        location = f"{result.check.repo}/{result.check.file}"
        lines.append(f"- {prefix}: {result.check.label} ({location})")
        if result.missing_file:
            lines.append("  Missing required reference file.")
        elif result.missing_patterns:
            missing = ", ".join(repr(pattern) for pattern in result.missing_patterns)
            lines.append(f"  Missing required pattern(s): {missing}")
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
