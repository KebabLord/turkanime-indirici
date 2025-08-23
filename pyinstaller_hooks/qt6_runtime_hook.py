import os, sys

# Configure Qt plugin and bin paths before any PyQt6 import occurs.
meipass = getattr(sys, "_MEIPASS", None)
qt_plugin_paths = []
qt_bin_paths = []
if meipass:
    qt6_root = os.path.join(meipass, 'PyQt6', 'Qt6')
    qt_plugin_paths.append(os.path.join(qt6_root, 'plugins'))
    qt_bin_paths.append(os.path.join(qt6_root, 'bin'))

# Export QT_PLUGIN_PATH
cur = os.environ.get('QT_PLUGIN_PATH', '')
os.environ['QT_PLUGIN_PATH'] = os.pathsep.join([p for p in [cur, *qt_plugin_paths] if p])

# Export platform plugin path explicitly if present
for base in qt_plugin_paths:
    p = os.path.join(base, 'platforms')
    if os.path.isdir(p):
        os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', p)
        break

# Ensure Qt6/bin is on PATH for dependent DLL resolution
if qt_bin_paths:
    os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH', ''), *qt_bin_paths])

if os.name == 'nt':
    os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
