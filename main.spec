# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

esptool_hidden = collect_submodules('esptool')
esptool_datas = collect_data_files('esptool')  # esptool ships stub-flasher json/bin data it loads at runtime

app_datas = [
    ('tahzeeb.png', '.'),
    ('ota.bin', '.'),
    ('blink.bin', '.'),
] + esptool_datas

# ===== Main GUI app =====
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=app_datas,
    hiddenimports=esptool_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='tahzeeb.ico',
)

# ===== esptool CLI helper =====
# A onefile main.exe can't shell out to "sys.executable -m esptool" (that would
# just re-launch main.exe itself). Ship esptool as its own sibling executable
# that flash_utils.py invokes directly when running frozen.
esp_a = Analysis(
    ['esptool_helper.py'],
    pathex=[],
    binaries=[],
    datas=esptool_datas,
    hiddenimports=esptool_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
esp_pyz = PYZ(esp_a.pure)

esp_exe = EXE(
    esp_pyz,
    esp_a.scripts,
    esp_a.binaries,
    esp_a.datas,
    [],
    name='esptool_helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
