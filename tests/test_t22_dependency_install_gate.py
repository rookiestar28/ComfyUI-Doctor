import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_supply_chain.py"
SPEC = importlib.util.spec_from_file_location("check_supply_chain_t22", SCRIPT_PATH)
check_supply_chain = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_supply_chain
SPEC.loader.exec_module(check_supply_chain)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rule_ids(findings):
    return {finding.rule_id for finding in findings}


def test_root_lifecycle_script_is_blocked(tmp_path):
    write(
        tmp_path / "package.json",
        json.dumps({"scripts": {"postinstall": "node setup.mjs"}, "dependencies": {"acorn": "^8.15.0"}}),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert "deps.root-lifecycle-script" in rule_ids(findings)
    assert check_supply_chain._exit_code(findings, strict=False) == 1


def test_unexpected_lockfile_install_script_is_blocked(tmp_path):
    write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "packages": {
                    "": {"name": "fixture"},
                    "node_modules/unreviewed-binary-helper": {
                        "version": "1.0.0",
                        "resolved": "https://registry.npmjs.org/unreviewed-binary-helper/-/unreviewed-binary-helper-1.0.0.tgz",
                        "integrity": "sha512-test",
                        "hasInstallScript": True,
                    },
                }
            }
        ),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert "deps.unexpected-install-script" in rule_ids(findings)
    assert check_supply_chain._exit_code(findings, strict=False) == 1


def test_reviewed_install_script_allowlist_passes(tmp_path):
    write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "packages": {
                    "": {"name": "fixture"},
                    "node_modules/esbuild": {
                        "version": "0.21.5",
                        "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.21.5.tgz",
                        "integrity": "sha512-test",
                        "hasInstallScript": True,
                    },
                    "node_modules/fsevents": {
                        "version": "2.3.3",
                        "resolved": "https://registry.npmjs.org/fsevents/-/fsevents-2.3.3.tgz",
                        "integrity": "sha512-test",
                        "hasInstallScript": True,
                    },
                }
            }
        ),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert findings == []


def test_full_test_scripts_run_supply_chain_gate_before_npm_install():
    windows_script = (REPO_ROOT / "scripts" / "run_full_tests_windows.ps1").read_text(encoding="utf-8")
    linux_script = (REPO_ROOT / "scripts" / "run_full_tests_linux.sh").read_text(encoding="utf-8")

    assert windows_script.index("Supply-chain dependency gate") < windows_script.index("npm install")
    assert linux_script.index("Supply-chain dependency gate") < linux_script.index("npm install")


def test_ci_workflows_run_supply_chain_gate_before_dependency_install():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    offenders = []
    for path in workflow_dir.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        install_positions = [
            index
            for needle in ("npm ci", "npm install", "pip install", "python -m pip install")
            if (index := text.find(needle)) >= 0
        ]
        if not install_positions:
            continue
        gate_position = text.find("scripts/check_supply_chain.py --skip-install-trees")
        if gate_position < 0 or gate_position > min(install_positions):
            offenders.append(path.name)

    assert offenders == []
