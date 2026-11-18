# -*- coding: utf-8 -*-
"""
Ohr HaKsav (אור הכתב) - Offline Torah Notes & Handwriting OCR Studio
Main Application Entry Point with Instant Startup and Windows Taskbar Integration.
"""

import sys
import os

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set Windows AppUserModelID for crisp taskbar icon
if sys.platform == "win32":
    try:
        import ctypes
        myappid = 'TU.LTC.OhrHaKsav.OCR.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow

def main():
    # High DPI scaling support
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("OhrHaKsav")
    app.setApplicationDisplayName("אור הכתב - Ohr HaKsav")

    # Set icon
    base_dir = getattr(sys, '_MEIPASS', BASE_DIR)
    icon_path = os.path.join(base_dir, "assets", "ohr_haksav.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Support optional --splash flag if explicitly requested, otherwise launch instantly
    if "--splash" in sys.argv:
        from ui.splash_screen import ModernSplashScreen
        splash = ModernSplashScreen()
        splash.center_on_screen()
        splash.show()
        app.processEvents()

        window = MainWindow()
        window.center_on_screen()
        splash.finish(window)
        window.show()
    else:
        # Instant direct launch for maximum responsiveness (~1.1s startup)
        window = MainWindow()
        window.center_on_screen()
        window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
