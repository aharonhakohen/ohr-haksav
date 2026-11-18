# -*- coding: utf-8 -*-
"""
Ohr HaKsav - Unified Word Export Options Dialog (v1.4.0)
Allows choosing title, subtitle, author, Hebrew font, and Sefer / Kuntres layout
(Standard Pages, Continuous Flow, or Traditional Two-Column Sefer Layout).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt

from ui.i18n import t


class WordExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("export_dialog_title"))
        self.resize(460, 340)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("📄 Microsoft Word (.docx) Export Settings")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(hdr)

        grp_meta = QGroupBox("Document Details")
        form = QFormLayout(grp_meta)
        form.setSpacing(8)

        self.inp_title = QLineEdit(t("export_default_title"))
        self.inp_title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        form.addRow("Title:", self.inp_title)

        self.inp_subtitle = QLineEdit("")
        self.inp_subtitle.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.inp_subtitle.setPlaceholderText("e.g., מסכת בבא קמא - פרק ב'")
        form.addRow("Subtitle:", self.inp_subtitle)

        self.inp_author = QLineEdit("")
        self.inp_author.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.inp_author.setPlaceholderText("Optional author / writer name")
        form.addRow("Author:", self.inp_author)
        layout.addWidget(grp_meta)

        grp_fmt = QGroupBox("Typography & Sefer Layout")
        fmt_form = QFormLayout(grp_fmt)
        fmt_form.setSpacing(8)

        self.cmb_layout = QComboBox()
        self.cmb_layout.addItem("Standard Single-Column (Page Break per Scan)", "standard")
        self.cmb_layout.addItem("Continuous Flow (No Forced Page Breaks)", "continuous")
        self.cmb_layout.addItem("Two-Column Sefer / Kuntres Layout (טורים)", "two_column")
        fmt_form.addRow("Layout Style:", self.cmb_layout)

        self.cmb_font = QComboBox()
        self.cmb_font.addItems(["David", "FrankRuehl", "Miriam", "Narkisim", "Times New Roman"])
        fmt_form.addRow("Hebrew Font:", self.cmb_font)

        self.chk_headers = QCheckBox("Include per-page headings & page markers ([דף 1])")
        self.chk_headers.setChecked(True)
        fmt_form.addRow("", self.chk_headers)
        layout.addWidget(grp_fmt)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("📄 Choose Save Location...")
        btn_ok.setObjectName("btn_primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_options(self) -> dict:
        return {
            "title": self.inp_title.text().strip() or t("export_default_title"),
            "subtitle": self.inp_subtitle.text().strip(),
            "author": self.inp_author.text().strip(),
            "layout_mode": self.cmb_layout.currentData(),
            "font_name": self.cmb_font.currentText(),
            "include_page_headers": self.chk_headers.isChecked()
        }
