#!/bin/bash
# Focused Security / Contract / E2E Regression Gate - Local Validator
# Usage: ./scripts/focused_gate.sh [--fast|--e2e]

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RUN_PYTHON=true
RUN_E2E=true

if [[ "$1" == "--fast" ]]; then
    RUN_E2E=false
elif [[ "$1" == "--e2e" ]]; then
    RUN_PYTHON=false
fi

echo -e "${BOLD}Focused Security / Contract / E2E Regression Gate${NC}"
echo "Mirrors: .github/workflows/focused-regression-gate.yml"
echo "Note: this supplemental lane does not replace tests/TEST_SOP.md."
echo ""

PYTHON_PASSED=true
E2E_PASSED=true

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        echo -e "${RED}FAIL No Python interpreter found (need python or python3)${NC}"
        exit 2
    fi
fi

if [[ "$RUN_PYTHON" == "true" ]]; then
    echo -e "\n${BOLD}Focused Python Security & Contract Tests${NC}"
    echo "========================================"

    declare -a suites=(
        "Plugin Security:tests/test_plugins_security.py:10"
        "Metadata Contract:tests/test_metadata_contract.py:1"
        "Dependency Policy:tests/test_pipeline_dependency_policy.py:2"
        "Outbound Payload Safety:tests/test_outbound_payload_safety.py:4"
    )

    for suite in "${suites[@]}"; do
        IFS=':' read -r name path count <<< "$suite"
        echo -e "\n${YELLOW}Running $name ($count tests)...${NC}"

        if "$PYTHON_BIN" -m pytest -q "$path" --tb=short; then
            echo -e "${GREEN}PASS $name: PASS${NC}"
        else
            echo -e "${RED}FAIL $name: FAIL${NC}"
            PYTHON_PASSED=false
        fi
    done
fi

if [[ "$RUN_E2E" == "true" ]]; then
    echo -e "\n${BOLD}Focused E2E Regression Tests${NC}"
    echo "============================"

    if [[ ! -d "node_modules" ]]; then
        echo -e "${YELLOW}Installing npm dependencies...${NC}"
        npm ci
    fi

    echo -e "${YELLOW}Checking Playwright browsers...${NC}"
    npx playwright install chromium --with-deps

    echo -e "\n${YELLOW}Running E2E tests...${NC}"
    if npm test; then
        echo -e "${GREEN}PASS E2E Tests: PASS${NC}"
    else
        echo -e "${RED}FAIL E2E Tests: FAIL${NC}"
        E2E_PASSED=false
    fi
fi

echo -e "\n${BOLD}Focused Gate Summary${NC}"
echo "===================="

if [[ "$PYTHON_PASSED" == "true" ]] && [[ "$E2E_PASSED" == "true" ]]; then
    echo -e "${GREEN}${BOLD}PASS ALL FOCUSED CHECKS PASSED${NC}"
    echo -e "\n${GREEN}Focused gate is green; run the full TEST_SOP gate before acceptance.${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}FAIL FOCUSED GATE FAILED${NC}"
    [[ "$PYTHON_PASSED" == "false" ]] && echo -e "${RED}  Python tests: FAIL${NC}"
    [[ "$E2E_PASSED" == "false" ]] && echo -e "${RED}  E2E tests: FAIL${NC}"
    echo -e "\n${RED}Please fix the failing checks before pushing.${NC}"
    exit 1
fi
