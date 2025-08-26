import os
import sys


def _prepare_qt_env():
    # Ensure Qt can find platform plugins when bundled
    meipass = getattr(sys, "_MEIPASS", None)
    plugin_paths = []
    qt_bin_paths = []
    if meipass:
        qt6_root = os.path.join(meipass, 'PyQt6', 'Qt6')
        plugin_paths.append(os.path.join(qt6_root, 'plugins'))
        # Optional secondary plugins dir if any packager places them there
        plugin_paths.append(os.path.join(meipass, 'qt6_plugins'))
        # Add Qt6/bin to PATH so Qt DLLs can be resolved
        qt_bin_paths.append(os.path.join(qt6_root, 'bin'))
    # Merge into QT_PLUGIN_PATH
    cur = os.environ.get('QT_PLUGIN_PATH', '')
    os.environ['QT_PLUGIN_PATH'] = os.pathsep.join([p for p in [cur, *plugin_paths] if p])
    # Explicitly point to platforms folder if present
    for base in plugin_paths:
        plat = os.path.join(base, 'platforms')
        if os.path.isdir(plat):
            os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', plat)
            break
    # Extend PATH with Qt bin dirs (if exist)
    if qt_bin_paths:
        os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH', ''), *qt_bin_paths])
    if os.name == 'nt':
        os.environ.setdefault('QT_QPA_PLATFORM', 'windows')


def main():
    _prepare_qt_env()
    from turkanime_api.gui import main as gui_main
    gui_main.run()


if __name__ == '__main__':
    main()
