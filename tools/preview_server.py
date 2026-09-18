"""Live preview server for the E.V. interface.

The real Qt window is rendered offscreen inside this process and the resulting
frames are served over HTTP, so the interface can be reviewed in a browser while
working on it. Nothing here is part of the shipped application: it is a
development utility.

Usage (headless Linux sandboxes need the stub libraries)::

    python tools/preview_server.py                 # http://localhost:8000
    python tools/preview_server.py --port 8123

The gallery re-renders on demand: press *Re-render* or open ``/rerender``.
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@dataclass(frozen=True)
class Scene:
    name: str
    title: str
    detail: str
    width: int = 1500
    height: int = 900


SCENES: tuple[Scene, ...] = (
    Scene("dashboard", "Dashboard", "Greeting, voice core, system status, quick actions, tasks, services", 1500, 900),
    Scene("dashboard_laptop", "Dashboard — laptop", "Same view at 1350×850 (rails intact, nothing clipped)", 1350, 850),
    Scene("dashboard_small", "Dashboard — small screen", "1180×800: the conversation rail collapses automatically", 1180, 800),
    Scene("state_thinking", "Working state", "Voice core in the THINKING state while a request runs", 1500, 900),
    Scene("state_muted", "Muted", "Microphone muted state", 1500, 900),
    Scene("conversation", "Conversation", "Streamed answer with markdown, code block and copy control", 1500, 900),
    Scene("activity", "Activity tab", "Tool activity cards: pending → running → completed", 1500, 900),
    Scene("error", "Error + retry", "Human-readable failure with Retry and Details", 1500, 900),
    Scene("history", "History tab", "Saved conversations grouped by recency", 1500, 900),
    Scene("settings_general", "Settings — General", "Startup, attention prompts, shortcuts, startup animation", 1500, 900),
    Scene("settings_ai", "Settings — AI", "Provider status, default provider, failover", 1500, 900),
    Scene("settings_voice", "Settings — Voice", "Microphone, wake word and engine state", 1500, 900),
    Scene("settings_automation", "Settings — Automation", "Hand tracking, browser automation, smart home", 1500, 900),
    Scene("settings_integrations", "Settings — Integrations", "Mobile connect and the Discord bridge", 1500, 900),
    Scene("settings_advanced", "Settings — Advanced", "Developer mode, logs, data folder, reload", 1500, 900),
    Scene("home", "Home Control", "Smart-home devices page", 1500, 900),
    Scene("boot", "Startup", "Short startup card with real progress and a skip hint", 1280, 800),
)

SCENE_INDEX = {scene.name: scene for scene in SCENES}


# ---------------------------------------------------------------------------
# Qt rendering thread
# ---------------------------------------------------------------------------
class Renderer:
    """Renders scenes with the real Qt window; runs inside the Qt event loop."""

    def __init__(self, warm: int = 0) -> None:
        self.warm = max(0, warm)
        self._jobs: "queue.Queue[Scene]" = queue.Queue()
        self._events: dict[str, threading.Event] = {}
        self.errors: dict[str, str] = {}
        self.ready = threading.Event()
        self._window = None
        self._window_size: tuple[int, int] | None = None
        self._shots: dict[str, bytes] = {}
        self._lock = threading.Lock()

    # -- public API ---------------------------------------------------------
    def request(self, scene: Scene, timeout: float = 120.0) -> bool:
        event = threading.Event()
        with self._lock:
            self._events[scene.name] = event
            self._shots.pop(scene.name, None)
        self._jobs.put(scene)
        return event.wait(timeout)

    def shot(self, name: str) -> bytes | None:
        with self._lock:
            return self._shots.get(name)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._shots

    def error(self, name: str) -> str | None:
        return self.errors.get(name)

    def stale(self) -> bool:
        """True when ui.py changed on disk after this process imported it."""
        try:
            return Path(self.ui.__file__).stat().st_mtime > self._ui_mtime
        except Exception:
            return False

    def reset(self) -> None:
        """Drop every cached frame and queue a fresh render of the whole gallery."""
        with self._lock:
            self._shots.clear()
        self.errors.clear()
        for scene in SCENES:
            self._jobs.put(scene)

    # -- Qt side ------------------------------------------------------------
    def attach(self, app: QApplication) -> None:
        """Bind to the QApplication and patch the window for previewing."""
        import ui  # noqa: WPS433 - the Qt app must already exist

        self.ui = ui
        self.app = app
        self._ui_mtime = Path(ui.__file__).stat().st_mtime
        ui.MainWindow._check_config = lambda self: True  # type: ignore[assignment]
        self._timer = QTimer()
        self._timer.timeout.connect(self._pump)
        self._timer.start(30)
        if self.warm:
            # Warm-up happens once the event loop is running, never before it.
            QTimer.singleShot(0, lambda: [self._jobs.put(scene) for scene in SCENES[: self.warm]])
        self.ready.set()

    def _pump(self) -> None:
        try:
            scene = self._jobs.get_nowait()
        except queue.Empty:
            return
        error = None
        try:
            png = self._render(scene)
            with self._lock:
                self._shots[scene.name] = png
        except Exception:
            error = traceback.format_exc()
            self.errors[scene.name] = error
            print(f"[preview] scene {scene.name} failed:\n{error}", flush=True)
        finally:
            with self._lock:
                event = self._events.get(scene.name)
            if event is not None:
                event.set()

    # -- scene helpers ------------------------------------------------------
    def _window_for(self, scene: Scene):
        size = (scene.width, scene.height)
        if self._window is None:
            self._window = self.ui.MainWindow(face_path=str(self.ui.LOGO_FILE))
            self._window.show()
            self._window_size = None
        if self._window_size != size:
            self._window.resize(*size)
            self._window_size = size
        return self._window

    def _settle(self, frames: int = 12) -> None:
        for _ in range(frames):
            self.app.processEvents()
            time.sleep(0.012)

    def _reset(self, window) -> None:
        window._set_page("dashboard")
        window._inline_workspace._feed.clear_messages()
        window._inline_workspace._task_card.clear_workspace()
        window._inline_workspace._activity_feed.clear()
        window._inline_workspace._activity_stage.reset()
        window._inline_workspace._set_tab(0)
        window._task_history.clear()
        window._activity_kind = ""
        window._set_activity_line("Idle — no task running.")
        window._muted = False
        window.hud.muted = False
        window._style_mute_btn()
        window._apply_state("LISTENING")
        window._refresh_dashboard_lists()
        window._tick_clock()
        window._update_metrics()

    def _render(self, scene: Scene) -> bytes:
        if scene.name == "boot":
            return self._render_boot(scene)

        window = self._window_for(scene)
        self._reset(window)
        window.showNormal()
        handler = getattr(self, f"_scene_{scene.name}", None)
        if handler is None:
            handler = self._scene_default
        handler(window)
        self._settle()
        pixmap = window.grab()
        return _png_bytes(pixmap)

    def _render_boot(self, scene: Scene) -> bytes:
        overlay = self.ui.BootSequenceOverlay()
        overlay.setGeometry(0, 0, scene.width, scene.height)
        overlay.showFullScreen()
        overlay.add_step("Loading settings")
        overlay.set_step_status("Loading settings", "done")
        overlay.add_step("Connecting providers")
        overlay.set_step_status("Connecting providers", "in_progress")
        overlay.set_progress(58, "Starting the voice engine")
        self._settle(8)
        pixmap = overlay.grab()
        overlay._skip()
        self._settle(2)
        overlay.deleteLater()
        return _png_bytes(pixmap)

    # -- individual scenes --------------------------------------------------
    def _scene_default(self, window) -> None:
        pass

    def _scene_state_thinking(self, window) -> None:
        window._apply_state("THINKING")
        window._log_sig.emit("You: draft a status update for the team")
        window._task_workspace_sig.emit(
            {
                "action": "start",
                "command": "Draft a status update for the team",
                "plan": ["Collect this week's notes", "Draft the update", "Save the file"],
            }
        )
        window._task_workspace_sig.emit(
            {
                "action": "activity",
                "phase": "start",
                "tool": "File",
                "title": "Reading notes.md",
                "detail": "notes/this-week.md",
            }
        )
        self._settle(6)

    def _scene_state_muted(self, window) -> None:
        window.set_muted_state(True)

    def _scene_conversation(self, window) -> None:
        feed = window._inline_workspace._feed
        feed.clear_messages()
        feed.add_message(
            "user",
            "You",
            "Summarise the release notes and save them as a short brief",
            "09:41",
        )
        feed.add_message(
            "assistant",
            "E.V.",
            "Here's the short version.\n\n"
            "**Highlights**\n\n"
            "1. Voice mode now handles interruptions mid-sentence\n"
            "2. Task view tracks every tool call end to end\n"
            "3. Settings were split into clear categories\n\n"
            "```python\n"
            "release = ReleaseNotes.parse('notes.md')\n"
            "brief = release.summarise(max_points=3)\n"
            "brief.save('release-brief.md')\n"
            "```\n\n"
            "Saved to `release-brief.md`.",
            "09:41",
            animate=False,
        )
        feed.add_message("system", "E.V.", "Document created · release-brief.md", "09:42")
        self._settle(4)

    def _scene_activity(self, window) -> None:
        workspace = window._inline_workspace
        workspace._set_tab(1)
        workspace._activity_stage.set_stage(3)
        for tool, title, detail, done in (
            ("Browser", "Opening Chrome", "https://example.com/pricing", True),
            ("Browser", "Reading the pricing table", "3 packages found", True),
            ("File", "Writing comparison.md", "C:/Users/You/Documents/comparison.md", False),
            ("Windows", "Opening the document", "waiting for the file to close", False),
        ):
            card = workspace._activity_feed.add_activity(tool, title, detail)
            if done:
                card.finish(success=True)
        self._settle(6)

    def _scene_error(self, window) -> None:
        feed = window._inline_workspace._feed
        feed.clear_messages()
        feed.add_message("user", "You", "Book a table at that restaurant again", "09:44")
        feed.add_error(
            "The browser engine could not start.",
            "playwright._impl._errors.Error: Executable doesn't exist at /ms-playwright/chromium/headless_shell",
            retry=lambda: None,
        )
        self._settle(4)

    def _scene_history(self, window) -> None:
        workspace = window._inline_workspace
        workspace._set_tab(2)
        self._settle(4)

    def _scene_settings_general(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("general")

    def _scene_settings_ai(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("ai")

    def _scene_settings_voice(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("voice")

    def _scene_settings_automation(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("automation")

    def _scene_settings_integrations(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("integrations")

    def _scene_settings_advanced(self, window) -> None:
        window._open_settings_page()
        window._settings_page._select_category("advanced")

    def _scene_home(self, window) -> None:
        window._set_page("home")


def _png_bytes(pixmap) -> bytes:
    """Serialise a QPixmap to PNG bytes without touching the filesystem."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


# ---------------------------------------------------------------------------
# HTTP gallery
# ---------------------------------------------------------------------------
GALLERY = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>E.V. — interface preview</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --bg: #05070b; --panel: #0b1017; --border: rgba(255,255,255,.08);
    --text: #eef4fa; --dim: #78879a; --accent: #5cd3ff;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 "Segoe UI", system-ui, sans-serif;
  }
  header {
    position: sticky; top: 0; z-index: 5; backdrop-filter: blur(14px);
    background: rgba(5,7,11,.86); border-bottom: 1px solid var(--border);
    padding: 16px 24px; display: flex; align-items: center; gap: 14px;
  }
  header h1 { font-size: 16px; margin: 0; letter-spacing: .4px; }
  header .sub { color: var(--dim); font-size: 12px; }
  header .spacer { flex: 1; }
  button {
    background: rgba(255,255,255,.04); color: var(--text); cursor: pointer;
    border: 1px solid var(--border); border-radius: 10px; padding: 8px 14px;
    font: inherit;
  }
  button:hover { border-color: rgba(92,211,255,.45); background: rgba(92,211,255,.10); }
  main { padding: 22px 24px 60px; display: grid; gap: 22px; grid-template-columns: 1fr; }
  figure {
    margin: 0; background: var(--panel); border: 1px solid var(--border);
    border-radius: 16px; overflow: hidden;
  }
  figure header {
    position: static; background: transparent; border-bottom: 1px solid var(--border);
    padding: 12px 16px; display: block; backdrop-filter: none;
  }
  figure h2 { margin: 0 0 2px; font-size: 13px; font-weight: 600; }
  figure p { margin: 0; color: var(--dim); font-size: 12px; }
  figure img { display: block; width: 100%; height: auto; background: #05070b; }
  .err { margin: 10px 16px 16px; padding: 10px 12px; border-radius: 10px;
         border: 1px solid rgba(255,95,109,.35); background: rgba(255,95,109,.08);
         color: #ffd7dc; font: 12px/1.45 "Cascadia Mono", Menlo, monospace;
         white-space: pre-wrap; }
  .note { color: var(--dim); font-size: 12px; padding: 0 24px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>E.V. — interface preview</h1>
    <div class="sub">Rendered from the real Qt window, offscreen. __COUNT__ views.</div>
  </div>
  <div class="spacer"></div>
  <button onclick="rerender()">Re-render all</button>
</header>
<p class="note" id="note">Frames refresh automatically while this tab is open.</p>
<main>
__CARDS__
</main>
<script>
let stamp = Date.now();
function paint() {
  document.querySelectorAll('figure img').forEach(img => {
    const base = img.dataset.src;
    img.src = base + '?t=' + stamp;
  });
}
async function rerender() {
  await fetch('/rerender', {method: 'POST'});
  stamp = Date.now();
  setTimeout(refresh, 400);
}
async function refresh() {
  const res = await fetch('/state');
  const data = await res.json();
  const meta = data._meta || {};
  const note = document.getElementById('note');
  if (meta.stale) {
    note.textContent = 'ui.py changed since the server started — restart the preview server to see the new code.';
    note.style.color = '#ffb648';
  } else {
    note.textContent = 'Frames refresh automatically while this tab is open.';
    note.style.color = '';
  }
  document.querySelectorAll('figure').forEach(fig => {
    const name = fig.dataset.scene;
    const state = data[name] || {};
    const err = fig.querySelector('.err');
    if (state.error) {
      if (!err) {
        const div = document.createElement('div');
        div.className = 'err';
        div.textContent = state.error;
        fig.appendChild(div);
      } else {
        err.textContent = state.error;
      }
      fig.querySelector('img').style.opacity = .35;
    } else {
      if (err) err.remove();
      fig.querySelector('img').style.opacity = 1;
    }
  });
}
window.addEventListener('load', () => {
  paint();
  setInterval(() => { stamp = Date.now(); paint(); refresh(); }, 5000);
});
</script>
</body>
</html>
"""


def _card_html(scene: Scene, error: str | None) -> str:
    error_html = f'<div class="err">{escape(error)}</div>' if error else ""
    return f"""<figure data-scene="{escape(scene.name)}">
  <header>
    <h2>{escape(scene.title)} <span style="color:var(--dim);font-weight:400">· {scene.width}×{scene.height}</span></h2>
    <p>{escape(scene.detail)}</p>
  </header>
  <img data-src="/shot/{escape(scene.name)}.png" alt="{escape(scene.title)}" loading="lazy">
  {error_html}
</figure>"""


class Handler(BaseHTTPRequestHandler):
    renderer: RenderThread

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        if self.path.startswith("/shot/"):
            return
        super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            cards = "\n".join(
                _card_html(scene, self.renderer.error(scene.name)) for scene in SCENES
            )
            html = GALLERY.replace("__CARDS__", cards).replace("__COUNT__", str(len(SCENES)))
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/state":
            import json

            payload = {
                scene.name: {"error": self.renderer.error(scene.name), "ready": self.renderer.has(scene.name)}
                for scene in SCENES
            }
            payload["_meta"] = {"stale": self.renderer.stale()}
            self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
            return

        if path.startswith("/shot/"):
            name = path[len("/shot/"):]
            if name.endswith(".png"):
                name = name[:-4]
            scene = SCENE_INDEX.get(name)
            if scene is None:
                self._send(404, b"unknown scene", "text/plain")
                return
            if not self.renderer.has(name):
                self.renderer.request(scene)
            png = self.renderer.shot(name)
            if png is None:
                self._send(500, b"render failed - see server log", "text/plain")
                return
            self._send(200, png, "image/png")
            return

        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path == "/rerender":
            self.renderer.reset()
            self._send(200, b'{"ok":true}', "application/json")
            return
        self._send(404, b"not found", "text/plain")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a live preview of the E.V. interface")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--warm", type=int, default=3, help="scenes rendered before the server answers")
    args = parser.parse_args()

    # Qt owns the main thread; the HTTP server answers from a worker thread and
    # queues renders back into this loop.
    app = QApplication([])
    renderer = Renderer(warm=args.warm)
    renderer.attach(app)
    print("[preview] Qt renderer ready", flush=True)

    Handler.renderer = renderer
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="ev-preview-http", daemon=True)
    thread.start()
    print(f"[preview] http://{args.host}:{args.port}/  ({len(SCENES)} views)", flush=True)

    try:
        return app.exec()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
