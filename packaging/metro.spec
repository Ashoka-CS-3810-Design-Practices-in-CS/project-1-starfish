# PyInstaller spec for a one-folder desktop build [Should tier].
# Build from the repository root:  pyinstaller packaging/metro.spec
# The data/ folder is copied next to the executable, where main.py looks for it.

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "data" / name), "data")
           for name in ("stations.json", "lines.json", "segments.json", "transfers.json")],
    excludes=["networkx", "pytest", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DelhiMetroPlanner",
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="DelhiMetroPlanner")
