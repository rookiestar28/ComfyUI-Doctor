import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = ROOT / "docs" / "SECURITY_AUDIT.md"
SCRIPT_PATH = ROOT / "scripts" / "security_audit.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "security-audit.yml"


REQUIRED_DOC_FRAGMENTS = [
    "# Security Audit",
    "## Cadence",
    "## Automated Checks",
    "## Manual Checks",
    "## Compliance Mapping",
    "## Report Handling",
    "OWASP ZAP baseline scan",
    "Semgrep CLI reference",
    "Snyk GitHub Actions",
    "tests/TEST_SOP.md",
]

REQUIRED_TEMPLATE_FRAGMENTS = [
    "# 2026 Q2 Security Audit",
    "## Audit Rules",
    "## Automated Checks",
    "## Manual Security Scenarios",
    "## Compliance Mapping",
    "## Findings",
    "## Remediation Validation",
    "## Sign-Off",
    "SSRF metadata endpoint attempts",
    "XSS chat input attempts",
    "Path traversal attempts",
    "OWASP Top 10",
    "CWE Top 25",
]

REQUIRED_WORKFLOW_FRAGMENTS = [
    "cron: '0 9 1 1,4,7,10 *'",
    "workflow_dispatch:",
    "permissions:\n  contents: read",
    "python scripts/security_audit.py --output security-audit-template.md --force",
    "python scripts/check_supply_chain.py --skip-install-trees",
    "python scripts/check_outbound_safety.py",
    "python scripts/focused_gate.py --fast",
    "semgrep scan",
    "npx snyk test --severity-threshold=high",
    "zap-baseline.py",
    "actions/upload-artifact@v4",
]

FORBIDDEN_PUBLIC_FRAGMENTS = [
    ".planning",
    "reference/",
    "REFERENCE/",
    "ROADMAP",
    "IMPLEMENTATION_RECORD",
    "command log",
    "validation evidence",
    ".sessions",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_template() -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--date", "2026-05-31", "--quarter", "Q2"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_s7_security_audit_doc_covers_required_public_sop():
    text = _read(DOC_PATH)

    for fragment in REQUIRED_DOC_FRAGMENTS:
        assert fragment in text, f"Missing security-audit doc fragment: {fragment}"


def test_s7_security_audit_template_is_deterministic_and_complete():
    first = _run_template()
    second = _run_template()

    assert first == second
    for fragment in REQUIRED_TEMPLATE_FRAGMENTS:
        assert fragment in first, f"Missing audit-template fragment: {fragment}"


def test_s7_security_audit_workflow_defines_quarterly_gates():
    text = _read(WORKFLOW_PATH)

    assert "pull_request_target" not in text
    assert "id-token: write" not in text
    for fragment in REQUIRED_WORKFLOW_FRAGMENTS:
        assert fragment in text, f"Missing security-audit workflow fragment: {fragment}"


def test_s7_public_security_audit_surfaces_stay_public_safe():
    combined = "\n".join([_read(DOC_PATH), _run_template()])

    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert fragment not in combined, f"Security audit public surface leaks: {fragment}"
