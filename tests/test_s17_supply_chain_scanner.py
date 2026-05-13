import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_supply_chain.py"
SPEC = importlib.util.spec_from_file_location("check_supply_chain", SCRIPT_PATH)
check_supply_chain = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_supply_chain
SPEC.loader.exec_module(check_supply_chain)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rule_ids(findings):
    return {finding.rule_id for finding in findings}


def test_clean_fixture_has_no_blocking_findings(tmp_path):
    write(
        tmp_path / "package.json",
        json.dumps({"dependencies": {"acorn": "^8.15.0"}, "devDependencies": {"vitest": "^1.2.0"}}),
    )
    write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "packages": {
                    "": {"name": "clean"},
                    "node_modules/acorn": {
                        "version": "8.15.0",
                        "resolved": "https://registry.npmjs.org/acorn/-/acorn-8.15.0.tgz",
                        "integrity": "sha512-test",
                    },
                }
            }
        ),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert findings == []


def test_scanner_detects_malicious_package_and_git_artifact(tmp_path):
    malicious_scope = "@" + "tanstack" + "/" + "setup"
    malicious_ref = "github:" + "tanstack" + "/router#79ac49eedf774dd4b0cfa308722bc463cfe5885c"
    write(
        tmp_path / "package.json",
        json.dumps({"optionalDependencies": {malicious_scope: malicious_ref}}),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert "deps.known-compromised-name" in rule_ids(findings)
    assert "deps.git-artifact" in rule_ids(findings)
    assert check_supply_chain._exit_code(findings, strict=False) == 1


def test_scanner_detects_lockfile_missing_integrity_and_bad_version(tmp_path):
    write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "packages": {
                    "": {"name": "bad"},
                    "node_modules/lightning": {
                        "version": "2.5.3",
                        "resolved": "https://registry.npmjs.org/lightning/-/lightning-2.5.3.tgz",
                    },
                }
            }
        ),
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert "deps.known-compromised-name" in rule_ids(findings)
    assert "deps.known-compromised-version" in rule_ids(findings)
    assert "deps.missing-integrity" in rule_ids(findings)


def test_scanner_detects_payload_filename_and_string_without_echoing_file_content(tmp_path, capsys):
    private_marker = "ghp_" + "A" * 36
    write(tmp_path / "node_modules" / "bad" / "router_runtime.js", f"value={private_marker}")
    write(tmp_path / ".vscode" / "tasks.json", "bun run " + "tanstack_runner.js")

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=True)
    check_supply_chain._print_text(findings)
    output = capsys.readouterr().out

    assert "payload.filename" in rule_ids(findings)
    assert "payload.string" in rule_ids(findings)
    assert private_marker not in output


def test_scanner_detects_high_risk_workflow_patterns(tmp_path):
    write(
        tmp_path / ".github" / "workflows" / "bad.yml",
        """
on:
  pull_request_target:

permissions:
  id-token: write

jobs:
  publish:
    steps:
      - uses: actions/cache@v4
        with:
          path: node_modules
          key: shared
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: npm ci
      - uses: some-vendor/action@v1
""",
    )

    findings = check_supply_chain.scan_repository(tmp_path, include_install_trees=False)

    assert "ci.pull-request-target-untrusted-code" in rule_ids(findings)
    assert "ci.cache-cross-trust" in rule_ids(findings)
    assert "ci.oidc-publish-boundary" in rule_ids(findings)
    assert "ci.mutable-action-ref" in rule_ids(findings)


def test_home_config_scan_is_opt_in(tmp_path):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    write(home / ".claude" / "settings.json", "filev2." + "getsession.org")
    write(repo / "package.json", json.dumps({"dependencies": {"acorn": "^8.15.0"}}))

    default_findings = check_supply_chain.scan_repository(repo, include_install_trees=False, home=home)
    opt_in_findings = check_supply_chain.scan_repository(
        repo,
        include_install_trees=False,
        include_home_config=True,
        home=home,
    )

    assert "payload.string" not in rule_ids(default_findings)
    assert "payload.string" in rule_ids(opt_in_findings)
