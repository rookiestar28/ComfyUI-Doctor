#!/usr/bin/env python3
"""Repo-local supply-chain IOC scanner.

The scanner is intentionally static: it reads manifests, lockfiles, workflow
YAML, and selected config/install-tree files without executing package code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


FAIL_SEVERITIES = {"high", "critical"}
TEXT_FILE_LIMIT_BYTES = 2 * 1024 * 1024

KNOWN_COMPROMISED_PACKAGES = {
    "@tanstack/setup",
    "@beproduct/nestjs-auth",
    "@taskflow-corp/cli",
    "@tolka/cli",
    "@dirigible-ai/sdk",
    "safe-action",
    "ts-dna",
    "cross-stitch",
    "cmux-agent-mcp",
    "agentwork-cli",
    "git-branch-selector",
    "wot-api",
    "git-git-git",
    "nextmove-mcp",
    "ml-toolkit-ts",
    "mistralai",
    "guardrails-ai",
    "lightning",
}

KNOWN_COMPROMISED_PREFIXES = (
    "@tanstack/",
    "@mistralai/",
    "@uipath/",
    "@opensearch-project/",
    "@squawk/",
    "@tallyui/",
    "@draftauth/",
    "@draftlab/",
    "@ml-toolkit-ts/",
    "@mesadev/",
    "@supersurkhet/",
)

KNOWN_COMPROMISED_VERSIONS = {
    ("@tanstack/setup", "0.0.0-security"),
    ("mistralai", "1.9.10"),
    ("guardrails-ai", "0.6.6"),
    ("lightning", "2.5.3"),
}

ROOT_LIFECYCLE_SCRIPTS = {
    "preinstall",
    "install",
    "postinstall",
    "prepare",
    "prepack",
    "postpack",
}

ALLOWED_INSTALL_SCRIPT_PACKAGES = {
    "esbuild",
    "fsevents",
}

TRIAGE_CHECKLIST = """Supply-chain incident triage checklist

1. Stop activity
   - Pause dependency install, build, test, and publish jobs on the affected host or runner.
   - Preserve scanner output, workflow run ids, package versions, lockfile state, and timestamps.
   - Do not paste credentials, full config files, private logs, or environment dumps into public issues.

2. Classify finding
   - Dependency finding: inspect package name, version, lockfile entry, install time, and registry history.
   - Payload finding: isolate the machine, preserve the path, and remove persistence only after evidence capture.
   - CI finding: inspect workflow trigger, checkout target, cache scope, job permissions, and publish boundaries.
   - Registry finding: review recent package publishes, release tags, and generated archives.

3. Rotate credentials after evidence capture
   - Rotate source-control, registry, cloud, SSH, editor/AI-tool, and application credentials reachable from the affected host or runner.
   - Revoke broad tokens first when active misuse is plausible, then replace with least-privilege credentials.

4. Clean and rebuild
   - Purge affected CI caches.
   - Remove confirmed editor/AI-tool persistence hooks and payload files.
   - Reinstall dependencies from clean manifests and lockfiles.
   - Re-run the supply-chain scanner before resuming normal work.

5. Return to service
   - Confirm scanner passes.
   - Run the full repository validation gate.
   - Record sanitized evidence, commands, environment, known limitations, and follow-up actions in the internal incident record.
"""

PAYLOAD_FILENAMES = {
    "router_init.js",
    "router_runtime.js",
    "tanstack_runner.js",
}

PAYLOAD_PATTERNS = {
    "github:tanstack/router#79ac49eedf774dd4b0cfa308722bc463cfe5885c",
    "@tanstack/setup",
    "filev2.getsession.org",
    "seed1.getsession.org",
    "seed2.getsession.org",
    "seed3.getsession.org",
    "git-tanstack.com",
    "gh-token-monitor",
    "A Mini Shai-Hulud has Appeared",
    "bun run tanstack_runner.js",
    "claude@users.noreply.github.com",
}

SKIP_DIRS = {
    ".git",
    ".planning",
    ".pytest_cache",
    ".sessions",
    ".tmp",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "reference",
    "playwright-report",
    "test-results",
    "user",
}

SKIP_FILES = {
    "scripts/check_supply_chain.py",
    "tests/test_s17_supply_chain_scanner.py",
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    message: str
    package: str | None = None
    version: str | None = None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _add(
    findings: list[Finding],
    *,
    rule_id: str,
    severity: str,
    path: Path,
    root: Path,
    message: str,
    package: str | None = None,
    version: str | None = None,
) -> None:
    findings.append(
        Finding(
            rule_id=rule_id,
            severity=severity,
            path=_rel(path, root),
            message=message,
            package=package,
            version=version,
        )
    )


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _is_known_compromised_name(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in KNOWN_COMPROMISED_PACKAGES or any(
        normalized.startswith(prefix) for prefix in KNOWN_COMPROMISED_PREFIXES
    )


def _iter_dependency_specs(package_json: dict[str, Any]) -> list[tuple[str, str, str]]:
    specs: list[tuple[str, str, str]] = []
    for section in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
        "bundledDependencies",
        "bundleDependencies",
    ):
        value = package_json.get(section)
        if isinstance(value, dict):
            for name, version in value.items():
                specs.append((str(name), str(version), section))
        elif isinstance(value, list):
            for name in value:
                specs.append((str(name), "", section))
    return specs


def scan_package_json(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    data = _load_json(path)
    if not isinstance(data, dict):
        return findings

    for name, version, section in _iter_dependency_specs(data):
        normalized = name.lower()
        if _is_known_compromised_name(normalized):
            _add(
                findings,
                rule_id="deps.known-compromised-name",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message=f"{section} references a package name/scope present in the IOC watchlist.",
            )
        if "github:tanstack/router#79ac49eedf774dd4b0cfa308722bc463cfe5885c" in version:
            _add(
                findings,
                rule_id="deps.git-artifact",
                severity="high",
                path=path,
                root=root,
                package=name,
                version="[redacted-spec]",
                message="Dependency spec references the reported malicious TanStack git artifact.",
            )
        elif re.search(r"^(git\+|github:|git://|https://github\.com/)", version, re.I):
            _add(
                findings,
                rule_id="deps.git-artifact",
                severity="high",
                path=path,
                root=root,
                package=name,
                version="[redacted-spec]",
                message="Dependency spec uses a git/GitHub artifact instead of a registry tarball.",
            )
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for script_name in sorted(ROOT_LIFECYCLE_SCRIPTS.intersection(scripts)):
            _add(
                findings,
                rule_id="deps.root-lifecycle-script",
                severity="high",
                path=path,
                root=root,
                message=f"Root package.json defines lifecycle script '{script_name}', which runs during install/publish flows.",
            )
    return findings


def _package_name_from_lock_path(lock_path: str) -> str:
    prefix = "node_modules/"
    if prefix in lock_path:
        return lock_path.rsplit(prefix, 1)[1]
    return lock_path


def scan_package_lock(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    data = _load_json(path)
    if not isinstance(data, dict):
        return findings

    packages = data.get("packages")
    if not isinstance(packages, dict):
        return findings

    for lock_path, meta in packages.items():
        if not lock_path or not str(lock_path).startswith("node_modules/") or not isinstance(meta, dict):
            continue
        name = str(meta.get("name") or _package_name_from_lock_path(str(lock_path))).lower()
        version = str(meta.get("version") or "")
        if _is_known_compromised_name(name):
            _add(
                findings,
                rule_id="deps.known-compromised-name",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message="Lockfile contains package name/scope present in the IOC watchlist.",
            )
        if (name, version) in KNOWN_COMPROMISED_VERSIONS:
            _add(
                findings,
                rule_id="deps.known-compromised-version",
                severity="critical",
                path=path,
                root=root,
                package=name,
                version=version,
                message="Lockfile contains a package version present in the known malicious artifact list.",
            )
        resolved = str(meta.get("resolved") or "")
        if "github:tanstack/router#79ac49eedf774dd4b0cfa308722bc463cfe5885c" in resolved:
            _add(
                findings,
                rule_id="deps.git-artifact",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message="Lockfile resolved artifact matches the reported malicious TanStack git reference.",
            )
        elif re.search(r"(git\+|github:|git://|git-tanstack\.com)", resolved, re.I):
            _add(
                findings,
                rule_id="deps.git-artifact",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message="Lockfile resolved artifact uses git/GitHub instead of a registry tarball.",
            )
        if not meta.get("integrity"):
            _add(
                findings,
                rule_id="deps.missing-integrity",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message="npm lockfile package entry lacks integrity metadata.",
            )
        if meta.get("hasInstallScript") is True and name not in ALLOWED_INSTALL_SCRIPT_PACKAGES:
            _add(
                findings,
                rule_id="deps.unexpected-install-script",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version,
                message="npm lockfile package entry declares an install script outside the reviewed allowlist.",
            )
    return findings


def scan_python_manifest(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    candidates = re.findall(r"(?im)^\s*['\"]?([A-Za-z0-9_.-]+(?:-[A-Za-z0-9_.-]+)*)['\"]?\s*(?:[<>=!~]=?\s*([A-Za-z0-9_.+-]+))?", text)
    for name, version in candidates:
        normalized = name.lower().replace("_", "-")
        if normalized in KNOWN_COMPROMISED_PACKAGES:
            _add(
                findings,
                rule_id="deps.known-compromised-name",
                severity="high",
                path=path,
                root=root,
                package=name,
                version=version or None,
                message="Python manifest references a package name present in the IOC watchlist.",
            )
        if version and (normalized, version) in KNOWN_COMPROMISED_VERSIONS:
            _add(
                findings,
                rule_id="deps.known-compromised-version",
                severity="critical",
                path=path,
                root=root,
                package=name,
                version=version,
                message="Python manifest references a version present in the known malicious artifact list.",
            )
    return findings


def _iter_files(root: Path, include_install_trees: bool) -> list[Path]:
    files: list[Path] = []
    install_tree_names = {"node_modules", ".venv", ".venv-wsl", "venv"}
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        filtered: list[str] = []
        for dirname in dirnames:
            if dirname in SKIP_DIRS:
                continue
            if dirname in install_tree_names and not include_install_trees:
                continue
            filtered.append(dirname)
        dirnames[:] = filtered
        for filename in filenames:
            path = current_path / filename
            if _rel(path, root) in SKIP_FILES:
                continue
            files.append(path)
    return files


def scan_payload_indicators(root: Path, include_install_trees: bool) -> list[Finding]:
    findings: list[Finding] = []
    interesting_suffixes = {".js", ".mjs", ".json", ".yaml", ".yml", ".toml", ".txt", ".lock"}
    for path in _iter_files(root, include_install_trees=include_install_trees):
        name = path.name
        if name in PAYLOAD_FILENAMES:
            _add(
                findings,
                rule_id="payload.filename",
                severity="high",
                path=path,
                root=root,
                message="Known Mini Shai-Hulud payload filename found.",
            )
        if path.suffix.lower() not in interesting_suffixes:
            continue
        try:
            if path.stat().st_size > TEXT_FILE_LIMIT_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PAYLOAD_PATTERNS:
            if pattern in text:
                _add(
                    findings,
                    rule_id="payload.string",
                    severity="high",
                    path=path,
                    root=root,
                    message=f"Known Mini Shai-Hulud indicator string found: {pattern}",
                )
                break
    return findings


def scan_workflow(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    has_pull_request_target = re.search(r"(?m)^\s*pull_request_target\s*:", text) is not None
    checks_out_pr_head = bool(
        re.search(r"github\.event\.pull_request\.head\.(sha|ref|repo)", text)
        or re.search(r"refs/pull/\$\{\{\s*github\.event\.pull_request\.number", text)
    )
    if has_pull_request_target and checks_out_pr_head:
        _add(
            findings,
            rule_id="ci.pull-request-target-untrusted-code",
            severity="high",
            path=path,
            root=root,
            message="Workflow uses pull_request_target while checking out pull-request controlled code.",
        )

    if re.search(r"(?im)id-token\s*:\s*write", text) and re.search(
        r"(?im)(npm\s+(ci|install|test|run)|pip\s+install|python\s+setup\.py|uses:\s*actions/cache@)",
        text,
    ):
        _add(
            findings,
            rule_id="ci.oidc-publish-boundary",
            severity="high",
            path=path,
            root=root,
            message="Workflow grants OIDC id-token write while running package/cache code in the same workflow.",
        )

    if "uses: actions/cache@" in text and has_pull_request_target:
        _add(
            findings,
            rule_id="ci.cache-cross-trust",
            severity="high",
            path=path,
            root=root,
            message="Workflow combines pull_request_target with cache use; review trust-boundary separation.",
        )

    for match in re.finditer(r"(?im)uses:\s*([^\s#]+)", text):
        ref = match.group(1)
        if ref.startswith("./") or "@" not in ref:
            continue
        action, action_ref = ref.rsplit("@", 1)
        if action.lower().startswith("actions/"):
            continue
        if not re.fullmatch(r"[a-f0-9]{40}", action_ref):
            _add(
                findings,
                rule_id="ci.mutable-action-ref",
                severity="medium",
                path=path,
                root=root,
                message=f"Third-party action '{action}' is not pinned to a full commit SHA.",
            )
    return findings


def scan_workflows(root: Path) -> list[Finding]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    findings: list[Finding] = []
    for path in sorted(workflow_dir.glob("*")):
        if path.suffix.lower() in {".yml", ".yaml"}:
            findings.extend(scan_workflow(path, root))
    return findings


def scan_manifests(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    package_json = root / "package.json"
    if package_json.exists():
        findings.extend(scan_package_json(package_json, root))
    package_lock = root / "package-lock.json"
    if package_lock.exists():
        findings.extend(scan_package_lock(package_lock, root))
    for pattern in ("requirements*.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"):
        for path in root.glob(pattern):
            findings.extend(scan_python_manifest(path, root))
    return findings


def scan_home_config(root: Path, home: Path | None) -> list[Finding]:
    if home is None:
        home = Path.home()
    findings: list[Finding] = []
    targets = [
        home / ".claude" / "settings.json",
        home / ".vscode" / "tasks.json",
        home / ".vscode" / "settings.json",
        home / ".claude" / "router_init.js",
        home / ".claude" / "router_runtime.js",
        home / ".vscode" / "router_init.js",
        home / ".vscode" / "router_runtime.js",
    ]
    for path in targets:
        if not path.exists():
            continue
        if path.name in PAYLOAD_FILENAMES:
            _add(
                findings,
                rule_id="payload.filename",
                severity="high",
                path=path,
                root=root,
                message="Known Mini Shai-Hulud payload filename found in opt-in home config scan.",
            )
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PAYLOAD_PATTERNS:
            if pattern in text:
                _add(
                    findings,
                    rule_id="payload.string",
                    severity="high",
                    path=path,
                    root=root,
                    message=f"Known Mini Shai-Hulud indicator string found in opt-in home config scan: {pattern}",
                )
                break
    return findings


def scan_repository(
    root: Path,
    *,
    include_install_trees: bool = True,
    include_home_config: bool = False,
    home: Path | None = None,
) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    findings.extend(scan_manifests(root))
    findings.extend(scan_payload_indicators(root, include_install_trees=include_install_trees))
    findings.extend(scan_workflows(root))
    if include_home_config:
        findings.extend(scan_home_config(root, home))
    return sorted(findings, key=lambda item: (item.severity, item.rule_id, item.path, item.package or ""))


def _print_text(findings: list[Finding]) -> None:
    if not findings:
        print("PASS supply-chain scanner found no blocking indicators.")
        return
    print(f"Supply-chain scanner findings: {len(findings)}")
    for finding in findings:
        package = f" package={finding.package}" if finding.package else ""
        version = f" version={finding.version}" if finding.version else ""
        print(f"{finding.severity.upper()} {finding.rule_id} {finding.path}{package}{version} - {finding.message}")


def print_triage_checklist() -> None:
    print(TRIAGE_CHECKLIST.rstrip())


def _exit_code(findings: list[Finding], strict: bool) -> int:
    if strict:
        return 1 if findings else 0
    return 1 if any(finding.severity in FAIL_SEVERITIES for finding in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Static supply-chain IOC scanner for ComfyUI-Doctor.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument(
        "--skip-install-trees",
        action="store_true",
        help="Skip repo-local node_modules/.venv trees during payload filename/string scan.",
    )
    parser.add_argument(
        "--include-home-config",
        action="store_true",
        help="Opt in to targeted home .claude/.vscode IOC checks. Does not print file contents.",
    )
    parser.add_argument(
        "--print-triage-checklist",
        action="store_true",
        help="Print a sanitized supply-chain incident response checklist and exit without scanning.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.print_triage_checklist:
        print_triage_checklist()
        return 0
    findings = scan_repository(
        Path(args.root),
        include_install_trees=not args.skip_install_trees,
        include_home_config=args.include_home_config,
    )
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2, sort_keys=True))
    else:
        _print_text(findings)
    return _exit_code(findings, args.strict)


if __name__ == "__main__":
    sys.exit(main())
