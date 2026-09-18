"""Render the E.V. interface offscreen to PNG files.

This is a developer utility used for visual regression checks: it boots the
real Qt window, feeds it representative state (chat history, tool activity,
voice states) and writes screenshots to ``tools/preview_out``.

Usage (headless Linux sandboxes need the stub libraries from
``tools/headless_qt/``)::

    QT_QPA_PLATFORM=offscreen python tools/ui_preview.py
    QT_QPA_PLATFORM=offscreen python tools/ui_preview.py --live   # real data

On Windows simply run ``python tools/ui_preview.py``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT_DIR = Path(__file__).resolve().parent / "preview_out"


def _demo_messages(window) -> None:
    feed = window._inline_workspace._feed
    feed.clear_messages()
    feed.add_message("user", "You", "What's the weather in Oslo, and build me a one-page report afterwards?", "09:41")
    feed.add_message(
        "assistant",
        "E.V.",
        "Oslo is 11 °C with light rain and a 14 km/h north wind.\n\n"
        "Here is the plan for the report:\n\n"
        "1. Pull the weather summary\n"
        "2. Draft the briefing sections\n"
        "3. Export `oslo-weather.docx`\n\n"
        "```python\n"
        "forecast = weather.get('Oslo')\n"
        "report = build_report(forecast)\n"
        "```\n",
        "09:41",
    )
    feed.add_message("system", "System", "Document created · oslo-weather.docx", "09:42")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render E.V. UI previews")
    parser.add_argument("--out", default=str(OUT_DIR), help="output directory")
    parser.add_argument("--live", action="store_true", help="skip demo chat content")
    parser.add_argument("--width", type=int, default=1500)
    parser.add_argument("--height", type=int, default=840)
    args = parser.parse_args()

    from PyQt6.QtWidgets import QApplication

    import ui as ui_module

    app = QApplication.instance() or QApplication(sys.argv)
    window = ui_module.MainWindow(face_path=str(ui_module.LOGO_FILE))

    # The preview must render even when no API key is configured yet.
    window._check_config = lambda: True  # type: ignore[assignment]
    window._ready = True
    window._apply_state("LISTENING")

    if not args.live:
        _demo_messages(window)

    window.resize(args.width, args.height)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    shots = {
        "dashboard_listening.png": "LISTENING",
        "dashboard_thinking.png": "THINKING",
        "dashboard_speaking.png": "SPEAKING",
        "dashboard_muted.png": "MUTED",
    }
    for filename, state in shots.items():
        window._apply_state(state)
        window.hud._step()
        app.processEvents()
        pixmap = window.grab()
        path = out_dir / filename
        pixmap.save(str(path))
        print(f"wrote {path} ({pixmap.width()}x{pixmap.height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
