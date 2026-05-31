#!/bin/bash
# Deprecated compatibility wrapper for scripts/focused_gate.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "DEPRECATED: use scripts/focused_gate.sh for the focused security/contract/E2E gate." >&2
exec "$SCRIPT_DIR/focused_gate.sh" "$@"
