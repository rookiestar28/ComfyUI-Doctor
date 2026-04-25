"""Check ComfyUI host compatibility surfaces used by ComfyUI-Doctor.

This script is intentionally lightweight. It validates that the local
`reference/` checkouts still expose the host APIs Doctor depends on; it does
not replace full host E2E validation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


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
        repo="ComfyUI_frontend",
        file="src/types/extensionTypes.ts",
        label="extensionManager settings/sidebar API",
        required_patterns=("registerSidebarTab", "setting:", "get: <T = unknown>", "set: <T = unknown>"),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/schemas/apiSchema.ts",
        label="frontend execution_error schema",
        required_patterns=("zExecutionErrorWsMessage", "node_id:", "node_type:", "traceback:", "current_inputs:", "current_outputs:"),
    ),
    SurfaceCheck(
        repo="ComfyUI_frontend",
        file="src/scripts/app.ts",
        label="frontend rootGraph API",
        required_patterns=("rootGraph", "lastExecutionError"),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/main-process/comfyServer.ts",
        label="Desktop base/user/input/output directories",
        required_patterns=("userDirectoryPath", "path.join(this.basePath, 'user')", "'base-directory': this.basePath"),
    ),
    SurfaceCheck(
        repo="desktop",
        file="src/virtualEnvironment.ts",
        label="Desktop managed .venv layout",
        required_patterns=("this.venvPath = path.join(basePath, '.venv')", "Scripts', 'python.exe'", "bin', 'python'"),
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
