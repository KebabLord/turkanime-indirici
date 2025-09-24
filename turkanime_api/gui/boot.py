import os
import sys


def _prepare_qt_env():
    # CustomTkinter için özel hazırlık gerekmiyor, ama PATH güncellemeleri aynı
    pass


def main():
    _prepare_qt_env()
    from turkanime_api.gui import main as gui_main
    gui_main.run()


if __name__ == '__main__':
    main()
