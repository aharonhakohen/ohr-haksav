# -*- coding: utf-8 -*-
"""
Ohr HaKsav - In-App Update Notification Banner
Displays a modern, non-intrusive notification banner across the top of the main window
when a new version is detected, offering immediate in-app installation or details.
"""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton
)
from PyQt6.QtCore import Qt
from ui.i18n import t


class UpdateBanner(QFrame):
    def __init__(self, on_install_clicked, on_details_clicked, parent=None):
        super().__init__(parent)
        self.on_install_clicked = on_install_clicked
        self.on_details_clicked = on_details_clicked
        self.remote_data = {}
        self.setObjectName("update_banner")
        self.setFixedHeight(44)
        self._current_theme = "light"
        self._init_ui()
        self.hide()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # Icon
        self.lbl_icon = QLabel("⚡")
        self.lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        layout.addWidget(self.lbl_icon)

        # Message
        self.lbl_msg = QLabel()
        self.lbl_msg.setStyleSheet("font-size: 13px; font-weight: 600; border: none; background: transparent;")
        layout.addWidget(self.lbl_msg)

        layout.addStretch()

        # Action 1: Install Update Now (prominent)
        self.btn_install = QPushButton(t("update_banner_btn_install"))
        self.btn_install.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 16px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
        """)
        self.btn_install.clicked.connect(self._handle_install)
        layout.addWidget(self.btn_install)

        # Action 2: What's New / Details
        self.btn_details = QPushButton(t("update_banner_btn_details"))
        self.btn_details.setObjectName("btn_banner_details")
        self.btn_details.clicked.connect(self._handle_details)
        layout.addWidget(self.btn_details)

        # Dismiss / Close
        self.btn_dismiss = QToolButton()
        self.btn_dismiss.setText("✕")
        self.btn_dismiss.setToolTip("Dismiss for this session")
        self.btn_dismiss.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                color: #64748b;
                font-size: 13px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QToolButton:hover {
                color: #0f172a;
                background-color: #cbd5e1;
                border-radius: 3px;
            }
        """)
        self.btn_dismiss.clicked.connect(self.hide)
        layout.addWidget(self.btn_dismiss)

        self.apply_theme("light")

    def apply_theme(self, theme_mode: str = "light"):
        self._current_theme = theme_mode
        if theme_mode == "dark":
            self.setStyleSheet("""
                QFrame#update_banner {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                }
                QFrame#update_banner QLabel {
                    color: #f1f5f9;
                }
            """)
            self.btn_details.setStyleSheet("""
                QPushButton#btn_banner_details {
                    background-color: transparent;
                    color: #a7f3d0;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 4px 12px;
                    border: 1px solid #059669;
                    border-radius: 5px;
                }
                QPushButton#btn_banner_details:hover {
                    background-color: #064e3b;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#update_banner {
                    background-color: #ecfdf5;
                    border: 1px solid #a7f3d0;
                    border-radius: 6px;
                }
                QFrame#update_banner QLabel {
                    color: #065f46;
                }
            """)
            self.btn_details.setStyleSheet("""
                QPushButton#btn_banner_details {
                    background-color: transparent;
                    color: #065f46;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 4px 12px;
                    border: 1px solid #10b981;
                    border-radius: 5px;
                }
                QPushButton#btn_banner_details:hover {
                    background-color: #d1fae5;
                }
            """)

    def show_update(self, version: str, data: dict, lang: str = "en"):
        self.remote_data = data
        self.lbl_msg.setText(t("update_banner_msg", version=version))
        self.btn_install.setText(t("update_banner_btn_install"))
        self.btn_details.setText(t("update_banner_btn_details"))
        self.apply_theme(self._current_theme)
        self.show()

    def _handle_install(self):
        if self.on_install_clicked:
            self.on_install_clicked(self.remote_data)

    def _handle_details(self):
        if self.on_details_clicked:
            self.on_details_clicked(self.remote_data)
