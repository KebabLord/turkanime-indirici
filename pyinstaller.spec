# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# Discover PyQt6 Qt runtime locations at build time
try:
    import PyQt6  # type: ignore
    _qt_mod_dir = os.path.dirname(PyQt6.__file__)
    _qt6_bin_dir = os.path.join(_qt_mod_dir, 'Qt6', 'bin')
    _qt6_plugins_dir = os.path.join(_qt_mod_dir, 'Qt6', 'plugins')
except Exception:
    _qt6_bin_dir = None
    _qt6_plugins_dir = None

block_cipher = None

hiddenimports = collect_submodules('yt_dlp') + collect_submodules('curl_cffi') + collect_submodules('Crypto') + collect_submodules('PyQt6')
bin_data = [('bin', 'bin')] if os.path.isdir('bin') else []

# Important Qt DLLs that QtGui depends on in many environments
qt_extra_binaries = []
if _qt6_bin_dir and os.path.isdir(_qt6_bin_dir):
    for _dll in ('libEGL.dll', 'libGLESv2.dll', 'opengl32sw.dll', 'd3dcompiler_47.dll'):
        _p = os.path.join(_qt6_bin_dir, _dll)
        if os.path.exists(_p):
            # Place under PyQt6/Qt6/bin inside the bundle
            qt_extra_binaries.append((_p, 'PyQt6/Qt6/bin'))

qt_plugins_data = []
if _qt6_plugins_dir and os.path.isdir(_qt6_plugins_dir):
    # Bundle the entire plugins directory to be safe (platforms, imageformats, styles, etc.)
    qt_plugins_data.append((_qt6_plugins_dir, 'PyQt6/Qt6/plugins'))

a = Analysis([
    'turkanime_api/gui/boot.py',
],
             pathex=[],
             binaries=qt_extra_binaries,
             datas=[
                 ('docs/TurkAnimu.ico', 'docs'),
                 ('gereksinimler.json', '.'),
             ] + bin_data + qt_plugins_data,
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=['pyinstaller_hooks/qt6_runtime_hook.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='turkanime-gui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False,
          icon='docs/TurkAnimu.ico')
