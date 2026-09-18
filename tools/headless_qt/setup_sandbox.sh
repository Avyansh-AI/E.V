#!/usr/bin/env bash
# One-shot setup for the headless preview sandbox: virtualenv, dependencies and
# the stub libraries Qt's offscreen plugin needs. Safe to re-run.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --disable-pip-version-check \
  PyQt6 psutil Pillow requests numpy discord.py google-genai google-generativeai pytest \
  pyperclip python-kasa beautifulsoup4 openpyxl python-pptx python-docx reportlab edge-tts \
  qrcode send2trash youtube-transcript-api opencv-python-headless mss playwright duckduckgo-search

mkdir -p /tmp/glstub /tmp/combo
if [ ! -f /tmp/combo/libGL.so.1 ]; then
  python3 tools/headless_qt/build_stubs.py .venv/bin/python
fi

echo "sandbox ready:"
echo "  export LD_LIBRARY_PATH=/tmp/combo QT_QPA_PLATFORM=offscreen"
echo "  .venv/bin/python -m pytest tests -q"
echo "  .venv/bin/python tools/main_smoke.py   # import chain without a Windows audio stack"
