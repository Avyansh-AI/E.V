<p align="center">
  <img src="assets/ev_logo.png" alt="E.V." width="220" />
</p>

<h1 align="center">E.V. — Personal AI Assistant</h1>

<p align="center">
  <strong>A Windows desktop assistant that talks, listens, and actually does the work</strong><br>
  voice + text · local tools · browser automation · documents · smart home
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?style=for-the-badge" alt="Windows" /></a>
  <a href="#ai-providers"><img src="https://img.shields.io/badge/ai-Gemini%20%2B%20OpenRouter-blue?style=for-the-badge" alt="Providers" /></a>
  <a href="#tools"><img src="https://img.shields.io/badge/tools-30%2B-green?style=for-the-badge" alt="Tools" /></a>
</p>

---

E.V. is a personal assistant that lives on your PC. You talk to it or type to it; it
plans the work, runs it with real tools, and shows you what it is doing as it goes —
opening applications, driving a browser, reading your screen, building documents,
filing away a downloads folder, or flipping a smart light.

It is local-first: your conversation store, memory and settings never leave your
machine, and credentials live in a local config file you control.

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [AI providers](#ai-providers)
- [Tools](#tools)
- [Voice](#voice)
- [Browser automation](#browser-automation)
- [Windows automation](#windows-automation)
- [Integrations](#integrations)
- [Settings](#settings)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Community and licence](#community-and-licence)

## What it does

**Conversation.** A single thread that mixes typed and spoken turns. Replies stream
in with markdown, syntax-highlighted code blocks and copy controls. Long answers do
not truncate — the panel scrolls.

**Real tasks, tracked.** Every request runs through Request → Planning → Executing →
Verifying → Completed, with a card per tool call that moves from Pending to Running
to Completed or Failed and shows how long it took. Nothing is simulated: if a step
did not happen, the card says so.

**Honest failures.** When something breaks you get one plain sentence, a **Retry**
button and the technical detail behind **Details**. Raw stack traces stay in the log.

**Memory.** E.V. remembers durable facts you mention ("I prefer dark themes", "my
project folder is X") and surfaces what it recalled next to the conversation.

**Voice.** Wake-word or push-to-talk interaction with live audio both ways, an
interruptible briefing, and a voice orb that reflects the real state of the mic.

**Documents and content.** Decks, spreadsheets, Word files, PDF exports, website
builds and screen summaries — generated into real files you can open.

**Home and integrations.** Smart-home devices, a Discord bridge, phone remote,
reminders and meeting alerts.

## Architecture

```
main.py ─────────────► EVLive: AI session, audio, routing
   │                        │
   │                        ├─► actions/      the tools (browser, files, office, …)
   │                        ├─► agent/        planner / executor / task queue
   │                        └─► memory/       long-term memory store
   ├─► ui.py ─────────► Qt interface (dashboard, chat, tasks, settings)
   ├─► or_client.py ──► OpenRouter fallback when Gemini is unavailable
   └─► discord_bot.py ► Discord bridge
```

| Component | Responsibility |
| --- | --- |
| `main.py` | Application entry point. Owns the live AI session (`EVLive`), the audio queues, command routing and shutdown. |
| `ui.py` | The whole interface: dashboard, conversation panel, task/activity cards, settings, overlays. |
| `actions/` | One module per capability — the assistant's hands. |
| `agent/` | Planning, execution and queueing for multi-step work. |
| `memory/` | Long-term memory loading, updates and prompt formatting. |
| `workspace_store.py` | Local SQLite store for conversations, memory and workspace state. |
| `or_client.py` | OpenRouter client with retry and model fallback. |
| `discord_bot.py` | Discord bridge (commands, mirrored chat, presence). |
| `dashboard/` | Optional local web dashboard served from your machine. |
| `plugins/` | Drop-in Python hooks (`on_ev_created`, `on_startup`, `on_text_command`). |

## Installation

**Requirements:** Windows 10/11, Python 3.11 or 3.12, a Gemini API key
(OpenRouter is optional but recommended).

```powershell
git clone https://github.com/Avyansh-AI/E.V.git
cd E.V

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install          # required for browser automation

python main.py
```

First launch shows a short setup dialog asking for your Gemini key, an optional
OpenRouter key, and your operating system. You can change all of it later in
Settings.

To start without a console window, use the launcher:

```powershell
start_ev.bat         # or double-click start_ev.vbs
```

`config/create_desktop_shortcut.ps1` creates a Desktop shortcut pointing at your
virtual environment. `python setup.py` installs the Python packages and the
Playwright browser in one go.

## Configuration

All configuration is plain JSON under `config/`. Files containing secrets are
git-ignored.

| File | Purpose |
| --- | --- |
| `config/api_keys.json` | Gemini and OpenRouter credentials. |
| `config/app_settings.json` | Startup, launcher position, provider defaults, prompts, developer mode. |
| `config/discord_bot.json` | Discord bot token, channel and enable flag. |
| `config/firebase_config.json` | Optional, only if you point the web dashboard at your own Firebase project. |

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "openrouter_api_key": ""
}
```

Nothing in the UI ever prints a key in full — provider rows show a masked preview and
password fields stay masked unless you explicitly reveal them.

## AI providers

1. **Google Gemini** (`gemini-2.5-flash` by default) drives the live voice session and
   text answers.
2. **OpenRouter** is the fallback. If Gemini is missing, rate-limited or unreachable,
   requests move to the OpenRouter model list in `or_client.py`, retrying a couple of
   times per model before moving on.

Pick the default provider and toggle automatic failover in **Settings → AI**. The
provider row tells you honestly whether a key is configured and lets you test the
connection.

## Tools

Tools are declared in `main.py` and implemented in `actions/`. Every one of them can
fail, and every failure is reported as a failure.

| Area | Tools |
| --- | --- |
| Applications and system | open/close apps, window control, volume, screenshots, power actions |
| Browser | `browser_control` — navigate, search, click, type, fill forms, tabs, history |
| Files | `file_controller`, `file_processor` — read, convert, organise folders, desktop cleanup |
| Documents | `office_builder`, `docx_tools`, `pdf_tools`, presentation and template workflows |
| Web | `web_search`, `website_builder` (builds and previews a local site) |
| Screen | `screen_processor`, `computer_control` — read and act on what is on screen |
| Communication | `send_message` (Instagram DMs and uploads), reminders, notifications |
| Life admin | weather, flights, YouTube summaries, meeting assistant, game updater |
| Home | smart-home devices: lights, fans, plugs, AC, TV |
| Coding | `dev_agent`, `code_helper`, `claude_code_bridge` |

Irreversible actions — deleting or overwriting files, sending messages on your
behalf, installing software — ask for confirmation first and state plainly what is
about to happen.

## Voice

- Live audio in and out through Gemini's live session (16 kHz in, 24 kHz out).
- **F4** toggles the microphone; wake-word mode keeps listening for "E.V.", "hey",
  "hi" or "hello" while muted.
- The orb on the dashboard reflects real state — listening, thinking, executing,
  speaking, muted, offline — and the mic level drives the waveform.
- The daily briefing is spoken at startup and stops immediately if you start talking.

Voice needs a working microphone and speakers; without them the assistant still works
by text.

## Browser automation

`actions/browser_control.py` drives a real Playwright browser — Chromium by default.
Navigation, search, clicking, typing, form filling, tab handling and screenshots all
report their stage back to the activity feed, so "Opening Chrome…" reflects a real
browser operation rather than a message.

If Playwright is not installed, the assistant says so instead of pretending to browse:

```powershell
pip install playwright
playwright install chromium
```

## Windows automation

Windows-specific behaviour is concentrated in `actions/desktop.py`,
`computer_settings.py`, `open_app.py` and the startup helpers in `ui.py`:

- Launch and focus applications, move and resize windows, control volume and media.
- File work across drives, including organising Downloads and the Desktop.
- Start-with-Windows registration (`--startup`), optional launch-minimised, and a
  startup animation that only runs on a real boot and can be turned off.
- Hand tracking via the webcam (MediaPipe) can move the pointer and trigger clicks;
  it is off by default and only runs when you open the preview strip.

Paths are derived from the application location — nothing is hard-coded to a
particular machine, so cloning the repository anywhere works.

## Integrations

- **Discord** — mirror the conversation to a channel, run commands from Discord, and
  see bot status in Settings → Integrations. Token stays in `discord_bot.json`.
- **Mobile Connect** — show a QR code, pair a phone, and drive E.V. from the phone's
  browser on your local network.
- **Smart home** — add devices with their provider details; they appear on the Home
  Control page and can be controlled by voice.
- **Web dashboard** — a local Flask dashboard (`dashboard/`) for status and remote
  control, bound to your machine.
- **Plugins** — add a `.py` file to `plugins/` exporting `on_ev_created(ev)`,
  `on_startup(ev)` and/or `on_text_command(text, source, ev=None)`. Return `True`
  from `on_text_command` to mark a command handled.

## Settings

Settings are grouped into six categories, and every control is wired to something
real:

| Category | What is in it |
| --- | --- |
| **General** | Launch at startup, launch minimised, update check, attention prompts, shortcuts and taskbar pinning, startup animation. |
| **AI** | Provider status, default provider, automatic failover, API key editing and connection tests. |
| **Voice** | Microphone state, engine state, wake word, mute toggle. |
| **Automation** | Hand tracking, Playwright status, smart-home devices. |
| **Integrations** | Mobile Connect (pair, QR, disconnect) and the Discord bridge. |
| **Advanced** | Developer mode, data folder, logs, reload configuration, version information. |

Developer mode (Advanced) reveals technical diagnostics such as full error details.
It is off by default.

## Development

```powershell
# run the assistant with a console for logs
python main.py

# tests
pip install pytest
pytest tests -q

# offscreen screenshots of the interface (developer tool)
python tools/ui_preview.py

# live browser preview of the interface (developer tool)
python tools/preview_server.py --port 8000
```

`tools/` is developer tooling and is not part of the shipped application. On headless
Linux, `tools/headless_qt/` documents how to render the Qt window without a display.

Guidelines:

- Keep the tool contract honest: a tool either did the thing or reports failure.
- Never print raw exceptions into the conversation; use `humanize_error` and keep the
  detail for Details/developer mode.
- Add a test for behaviour you change; `tests/` currently covers gesture helpers.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Initialisation required" on launch | Add your Gemini key in the setup dialog or `config/api_keys.json`. |
| Voice does not work | Check microphone permissions in Windows, confirm PortAudio is available (`pip install sounddevice`), and press F4 to unmute. |
| "The browser could not complete that step" | Run `playwright install chromium`, then test again from Settings → AI. |
| Browser opens but nothing happens | Close other Playwright-driven browsers; only one instance can own the profile. |
| Provider errors mid-conversation | E.V. switches to OpenRouter automatically when a key is configured, otherwise it tells you the provider failed. |
| Hand tracking shows "camera off" | Click the strip to start the camera; check no other app is holding the webcam. |
| Startup animation runs every launch | It should run once per boot; disable it in Settings → General. |
| Where are my logs and data? | Settings → Advanced → **Open data folder** / **View logs**. |

## Project structure

```
main.py                 runtime, AI session, routing
ui.py                   Qt interface
or_client.py            OpenRouter fallback client
discord_bot.py          Discord bridge
workspace_store.py      local SQLite store (conversations, memory)
smart_home_page.py      Home Control page
actions/                tools
agent/                  planner, executor, task queue
memory/                 long-term memory
plugins/                drop-in hooks
dashboard/              optional local web dashboard
config/                 settings and credentials (secrets git-ignored)
assets/                 logo, icon, background
tools/                  developer utilities (previews, asset generation)
tests/                  test suite
core/prompt.txt         E.V.'s system persona
```

## Community and licence

- Discord: https://discord.gg/gEYmJKKtq3

This project is licensed under a custom source-available licence — see `LICENSE` for
the full terms and `TRADEMARK.md` for branding details. Maintained by Suryaansh Tiwari.

Please keep attribution intact and your credentials secure when building on E.V.
