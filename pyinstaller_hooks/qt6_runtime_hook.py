# Ensure Qt plugin path is set so that Qt can find its platform plugins (e.g., qwindows.dll)
import os, sys
from PyQt6 import QtCore

# Add PyInstaller temp dir Qt plugins and bundled plugins to QT_PLUGIN_PATH
paths = []
meipass = getattr(sys, "_MEIPASS", None)
if meipass:
    paths.append(os.path.join(meipass, 'PyQt6', 'Qt6', 'plugins'))
    paths.append(os.path.join(meipass, 'qt6_plugins'))
# Also add package plugin dirs when running unpackaged
try:
    import PyQt6
    base = os.path.dirname(PyQt6.__file__)
    paths.append(os.path.join(base, 'Qt6', 'plugins'))
except Exception:
    pass

cur = os.environ.get('QT_PLUGIN_PATH', '')
os.environ['QT_PLUGIN_PATH'] = os.pathsep.join([p for p in [cur, *paths] if p])

# Force platform to windows when on Windows
if os.name == 'nt':
    os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
