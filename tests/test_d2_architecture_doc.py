from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_PATH = ROOT / "docs" / "ARCHITECTURE.md"


REQUIRED_SECTIONS = [
    "# Architecture",
    "## Host Startup",
    "## Backend Layout",
    "## API Surface",
    "## Data Flows",
    "## Frontend Layout",
    "## Security and Storage Boundaries",
    "## Testing Architecture",
    "## Compatibility Principles",
]

REQUIRED_REFERENCES = [
    "openapi.json",
    "api_routes.py",
    "services/llm/",
    "services/security/",
    "services/infra/",
    "web/doctor_ui.js",
    "web/doctor_right_panel.js",
    "npm run test:integration",
    "npm run test:stress",
    "scripts/focused_gate.py",
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


def _read_architecture() -> str:
    return ARCHITECTURE_PATH.read_text(encoding="utf-8")


def test_d2_architecture_doc_exists_and_covers_required_sections():
    text = _read_architecture()

    for section in REQUIRED_SECTIONS:
        assert section in text, f"Missing architecture section: {section}"


def test_d2_architecture_doc_references_current_public_modules_and_lanes():
    text = _read_architecture()

    for reference in REQUIRED_REFERENCES:
        assert reference in text, f"Missing architecture reference: {reference}"


def test_d2_architecture_doc_stays_public_safe():
    text = _read_architecture()

    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert fragment not in text, f"Public architecture doc leaks internal fragment: {fragment}"
