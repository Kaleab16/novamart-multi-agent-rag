#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo
echo "======================================"
echo " NovaMart — Local Verification"
echo "======================================"

echo
echo "[1/4] Running automated tests..."
.venv/bin/python -m pytest -q

echo
echo "[2/4] Checking Python syntax..."
.venv/bin/python -m compileall -q main.py config.py src
echo "Python syntax: PASS"

echo
echo "[3/4] Checking runtime entrypoint import..."
(
  cd runtime
  AWS_DEFAULT_REGION=us-east-1 PYTHONPATH=. \
    ../.venv/bin/python -c \
    "import main; print('Runtime import: PASS')"
)

echo
echo "[4/4] Checking infrastructure template and configuration..."
grep -q "udacity-agentcore" infrastructure/starter_stack.yaml
grep -q "WORKFLOW_STATE_TABLE" config.py
echo "Expected project configuration: PASS"

echo
echo "======================================"
echo " LOCAL VERIFICATION PASSED"
echo "======================================"
echo
echo "This verifies local tests, syntax, imports,"
echo "and basic configuration only."
echo "It does NOT verify AWS integration or deployment."
