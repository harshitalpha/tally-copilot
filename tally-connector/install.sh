#!/bin/bash
# Tally Co-pilot Connector — one-line installer
# Usage: curl -fsSL https://yourproduct.com/install-connector.sh | bash

set -e

echo "=============================="
echo "Tally Co-pilot Connector Setup"
echo "=============================="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "Error: Python 3 is not installed. Install from https://python.org"
  exit 1
fi

PY=$(python3 -c "import sys; print(sys.version_info >= (3,10))")
if [ "$PY" != "True" ]; then
  echo "Error: Python 3.10 or newer is required"
  exit 1
fi

# Install
echo "Installing connector…"
pip3 install --quiet tally-copilot-connector

echo
echo "Installation complete."
echo
echo "To get started:"
echo "  1. Open the Tally Co-pilot dashboard → Onboarding → Generate pairing code"
echo "  2. Run:  tcc"
echo "  3. Enter the pairing code when prompted"
echo
