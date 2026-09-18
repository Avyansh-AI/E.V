"""Import main.py on Linux by standing in for the Windows-only stack.

Verifies that the runtime module still loads (tool declarations, persona, EVLive)
when the audio, registry, clipboard and camera dependencies of Windows are not
available. Development tool only - not part of the shipped application.

Usage:
    python tools/main_smoke.py
"""
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# --- minimal stand-ins for the Windows-only stack -------------------------
sd = types.ModuleType("sounddevice")
sd.InputStream = object; sd.OutputStream = object
sd.query_devices = lambda *a, **k: []; sd.CallbackFlags = object; sd.default = object()
sd.sleep = lambda *a, **k: None
sys.modules["sounddevice"] = sd

wr = types.ModuleType("winreg")
for name in ("HKEY_CLASSES_ROOT","HKEY_CURRENT_USER","HKEY_LOCAL_MACHINE","KEY_READ","KEY_WRITE",
             "REG_SZ","HKEY_CLASSES_ROOT"):
    setattr(wr, name, 0)
class _FakeKey:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter(())
wr.OpenKey = lambda *a, **k: _FakeKey()
wr.QueryValueEx = lambda *a, **k: ("", 0)
wr.CloseKey = lambda *a, **k: None
wr.SetValueEx = lambda *a, **k: None
wr.DeleteValue = lambda *a, **k: None
wr.EnumKey = lambda *a, **k: (_ for _ in ()).throw(OSError())
wr.OpenKeyEx = wr.OpenKey
wr.EnumValue = lambda *a, **k: (_ for _ in ()).throw(OSError())
sys.modules["winreg"] = wr

for name in ("pycaw", "pycaw.pycaw", "comtypes", "pywinauto", "pyautogui", "pygetwindow"):
    sys.modules.setdefault(name, types.ModuleType(name))

sys.argv = ["main.py", "--no-ui"]
try:
    import main
    print("main.py imported OK")
    print("tool declarations:", len(getattr(main, "TOOL_DECLARATIONS", [])))
    print("EVLive present:", hasattr(main, "EVLive"))
    print("persona length:", len(main._load_system_prompt()), "chars")
except SystemExit as exc:
    print("main.py raised SystemExit:", exc)
except Exception as exc:
    import traceback; traceback.print_exc()
    print("main.py import error:", type(exc).__name__, exc)
