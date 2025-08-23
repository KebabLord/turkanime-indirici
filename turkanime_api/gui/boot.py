import os
import sys


def _prepare_qt_env():
    # Ensure Qt can find platform plugins when bundled
    meipass = getattr(sys, "_MEIPASS", None)
    plugin_paths = []
    if meipass:
        plugin_paths.append(os.path.join(meipass, 'PyQt6', 'Qt6', 'plugins'))
        plugin_paths.append(os.path.join(meipass, 'qt6_plugins'))
    # Merge into QT_PLUGIN_PATH
    cur = os.environ.get('QT_PLUGIN_PATH', '')
    os.environ['QT_PLUGIN_PATH'] = os.pathsep.join([p for p in [cur, *plugin_paths] if p])
    if os.name == 'nt':
        os.environ.setdefault('QT_QPA_PLATFORM', 'windows')


def main():
    _prepare_qt_env()
    from turkanime_api.gui import main as gui_main
    gui_main.run()


if __name__ == '__main__':
    main()
