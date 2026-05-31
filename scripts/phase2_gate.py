#!/usr/bin/env python3
"""Deprecated compatibility wrapper for scripts/focused_gate.py."""

import sys
from pathlib import Path


def main() -> int:
    print(
        "DEPRECATED: use scripts/focused_gate.py for the focused security/contract/E2E gate.",
        file=sys.stderr,
    )
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "scripts"))

    from focused_gate import main as focused_main

    return focused_main()


if __name__ == "__main__":
    sys.exit(main())
