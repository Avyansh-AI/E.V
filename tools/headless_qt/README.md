# Headless Qt helpers

Qt's offscreen plugin needs `libGL`, `libEGL`, `libxkbcommon` and `libdbus-1`,
which are not present in the minimal Linux sandbox used for automated checks.
`build_stubs.py` generates tiny stand-in libraries for them so the real Qt
window can be rendered without a display.

```bash
python tools/headless_qt/build_stubs.py .venv/bin/python   # writes /tmp/combo
export LD_LIBRARY_PATH=/tmp/combo QT_QPA_PLATFORM=offscreen
python tools/preview_server.py                             # live browser preview
python tools/ui_preview.py                                 # one-shot screenshots
```

On Windows none of this is needed: run the scripts directly.
