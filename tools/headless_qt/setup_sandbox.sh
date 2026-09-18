#!/usr/bin/env bash
# Rebuild the throwaway parts of this Linux sandbox: the virtualenv, the Python
# packages and the Qt stub libraries. Nothing here is needed on Windows.
set -e
cd "$(dirname "$0")/../.."          # repository root

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --disable-pip-version-check \
  PyQt6 psutil Pillow requests numpy discord.py google-genai google-generativeai \
  pyperclip send2trash playwright opencv-python-headless mss pytest

python3 tools/headless_qt/build_stubs.py .venv/bin/python

echo
echo "Sandbox ready. Run the interface preview with:"
echo "  LD_LIBRARY_PATH=/tmp/combo QT_QPA_PLATFORM=offscreen .venv/bin/python tools/preview_server.py --port 8000"
