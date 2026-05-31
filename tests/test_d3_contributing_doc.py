from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRIBUTING_PATH = ROOT / "CONTRIBUTING.md"
README_PATH = ROOT / "README.md"


REQUIRED_SECTIONS = [
    "# Contributing",
    "## Before You Start",
    "## Repository Orientation",
    "## Development Workflow",
    "## Testing Requirements",
    "## Documentation Expectations",
    "## Security and Privacy Boundaries",
    "## Pull Request Readiness",
]

REQUIRED_REFERENCES = [
    "docs/ARCHITECTURE.md",
    "docs/API_REFERENCE.md",
    "docs/VALIDATION.md",
    "tests/TEST_SOP.md",
    "tests/E2E_TESTING_NOTICE.md",
    "tests/E2E_TESTING_SOP.md",
    "npm run test:integration",
    "npm run test:stress",
    "python scripts/focused_gate.py",
    "docs/openapi.json",
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


def _read_contributing() -> str:
    return CONTRIBUTING_PATH.read_text(encoding="utf-8")


def test_d3_contributing_doc_exists_and_is_linked_from_readme():
    assert CONTRIBUTING_PATH.exists()

    readme = README_PATH.read_text(encoding="utf-8")
    assert "[CONTRIBUTING.md](CONTRIBUTING.md)" in readme


def test_d3_contributing_doc_covers_required_sections():
    text = _read_contributing()

    for section in REQUIRED_SECTIONS:
        assert section in text, f"Missing contributing section: {section}"


def test_d3_contributing_doc_references_public_workflow_sources():
    text = _read_contributing()

    for reference in REQUIRED_REFERENCES:
        assert reference in text, f"Missing contributing reference: {reference}"


def test_d3_contributing_doc_stays_public_safe():
    text = _read_contributing()

    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert fragment not in text, f"Contributing guide leaks internal fragment: {fragment}"
