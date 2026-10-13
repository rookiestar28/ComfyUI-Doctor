"""The architecture guide must only name frontend modules that exist."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_DOC = PROJECT_ROOT / "docs" / "ARCHITECTURE.md"


def test_architecture_doc_references_only_existing_web_modules():
    text = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    referenced = sorted(set(re.findall(r"`(web/[^`\s]+)`", text)))

    missing = [path for path in referenced if not (PROJECT_ROOT / path).exists()]

    assert referenced, "docs/ARCHITECTURE.md should list frontend modules"
    assert missing == []
