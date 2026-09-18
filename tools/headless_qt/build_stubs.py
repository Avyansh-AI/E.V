"""Build the Qt stub libraries.

Only symbols that no other dependency of the consumer can provide are exported,
which keeps real libraries (fontconfig, freetype, ...) in charge of their own
symbols.
"""
import ctypes, os, re, subprocess, sys
from pathlib import Path

PY = sys.argv[1]
QTLIB = Path(subprocess.run([PY, "-c",
    "import PyQt6,pathlib;print(pathlib.Path(PyQt6.__file__).parent/'Qt6'/'lib')"],
    capture_output=True, text=True).stdout.strip())
PLUGINS = QTLIB.parent / "plugins"
OUT = Path("/tmp/combo")

TARGETS = ["libEGL.so.1", "libGL.so.1", "libdbus-1.so.3", "libxkbcommon.so.0"]
SEARCH_DIRS = ["/lib/x86_64-linux-gnu", "/usr/lib/x86_64-linux-gnu", "/lib64", "/usr/lib64",
               "/lib", "/usr/lib", str(QTLIB.parent / "lib")]

ldconfig = {}


def find_lib(name: str) -> Path | None:
    if name in ldconfig and Path(ldconfig[name]).exists():
        return Path(ldconfig[name])
    for directory in SEARCH_DIRS:
        path = Path(directory) / name
        if path.exists():
            return path
    return None


def defined_symbols(path: Path) -> set[str]:
    out = subprocess.run(["nm", "-D", "--defined-only", "--format=posix", str(path)],
                         capture_output=True, text=True).stdout
    symbols = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        symbols.add(line.split(" ", 1)[0].split("@")[0])
    return symbols


process = ctypes.CDLL(None)


def resolvable_here(name: str) -> bool:
    try:
        getattr(process, name)
        return True
    except Exception:
        return False


sym_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:@([^\s(]+))?$")
libs = sorted({p for p in list(QTLIB.glob("*.so*")) + list(PLUGINS.rglob("*.so")) if p.is_file()})

system_symbols: dict[str, set[str]] = {}
wanted: dict[str, dict[str, str | None]] = {t: {} for t in TARGETS}

for lib in libs:
    dt = subprocess.run(["readelf", "-dW", str(lib)], capture_output=True, text=True).stdout
    needed = set(re.findall(r"Shared library: \[([^\]]+)\]", dt))
    targets = [t for t in TARGETS if t in needed]
    if not targets:
        continue
    # every dependency of this consumer that exists on the system
    provided: set[str] = set()
    for dep in needed:
        if dep in TARGETS:
            continue
        if dep not in system_symbols:
            path = find_lib(dep)
            system_symbols[dep] = defined_symbols(path) if path else set()
        provided |= system_symbols[dep]

    dyn = subprocess.run(["readelf", "--dyn-syms", "-W", str(lib)], capture_output=True, text=True).stdout
    for line in dyn.splitlines():
        parts = line.split()
        if len(parts) < 8 or parts[6] != "UND" or parts[3] != "FUNC":
            continue
        match = sym_re.match(parts[7])
        if not match:
            continue
        name, version = match.group(1), match.group(2)
        if name.startswith("_") or name in provided or resolvable_here(name):
            continue
        for target in targets:
            wanted[target].setdefault(name, version)

for target, symbols in wanted.items():
    versions = sorted({v for v in symbols.values() if v})
    lines = []
    for index, (name, version) in enumerate(sorted(symbols.items())):
        internal = f"ev_{index}_{name}"
        lines.append(f'__attribute__((visibility("default"))) void {internal}(void) {{ }}')
        lines.append(f'__asm__(".symver {internal}, {name}@@{version}");' if version
                     else f'__asm__(".symver {internal}, {name}@@EVBASE");')
    lines.append('__attribute__((visibility("default"))) void ev_stub_anchor(void) { }')
    src = Path("/tmp/glstub") / f"{target}.c"
    src.write_text("\n".join(lines) + "\n")
    nodes = "".join(f'  "{v}" {{ }};\n' for v in versions)
    (Path("/tmp/glstub") / f"{target}.map").write_text('EVBASE { };\n' + nodes)
    out = OUT / target
    r = subprocess.run(["gcc", "-shared", "-fPIC", "-O0", str(src), "-o", str(out),
                        f"-Wl,-soname,{target}",
                        f"-Wl,--version-script={Path('/tmp/glstub') / (target + '.map')}"],
                       capture_output=True, text=True)
    print(target, len(symbols), "symbols,", len(versions), "versions",
          "ok" if r.returncode == 0 else r.stderr[:300])

# ---------------------------------------------------------------------------
# Building the stubs for a fresh sandbox:
#
#   python tools/headless_qt/build_stubs.py .venv/bin/python
#   export LD_LIBRARY_PATH=/tmp/combo QT_QPA_PLATFORM=offscreen
#
# Only symbols that no dependency of a Qt library can provide are exported, so
# real system libraries (fontconfig, freetype, ...) keep ownership of theirs.
# ---------------------------------------------------------------------------
