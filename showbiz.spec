# PyInstaller build spec for Hollywood Moguls - produces a single-file executable.
# Build with:  pyinstaller showbiz.spec   (output in dist/)
import sys

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static')],
    # Socket.IO picks its async driver by name at runtime, so PyInstaller can't see it
    hiddenimports=['engineio.async_drivers.threading', 'simple_websocket'],
    excludes=['tkinter'],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HollywoodMoguls',
    console=True,          # the console window shows the join URL and keeps the server running
    upx=False,
    target_arch='arm64' if sys.platform == 'darwin' else None,
)
