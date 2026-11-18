# -*- coding: utf-8 -*-
"""
Ohr HaKsav - Visual Learning Guardrail Dialog (v1.4.0)
Displays extracted OCR-mistake -> proofread-correction pairs with checkboxes
so users can review and approve exactly what gets saved into their profile.
"""

from typing import List, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt


class LearnPreviewDialog(QDialog):
    def __init__(self, candidates: List[Tuple[int, str, str]], profile_name: str, parent=None):
        """
        candidates: list of (page_num, raw_text, corrected_text)
        """
        super().__init__(parent)
        self.candidates = candidates
        self.profile_name = profile_name
        self.checkboxes: List[QCheckBox] = []

        self.setWindowTitle("Confirm Handwriting Corrections to Learn")
        self.resize(580, 420)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        lbl_title = QLabel(f"🎓 Review Corrections for Profile: <b>{self.profile_name}</b>")
        lbl_title.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Uncheck any sentence rewrites or one-time edits you do NOT want applied automatically on future scans:"
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(lbl_sub)

        # Quick select/deselect row
        top_btns = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("Deselect All")
        btn_none.clicked.connect(lambda: self._set_all(False))
        top_btns.addWidget(btn_all)
        top_btns.addWidget(btn_none)
        top_btns.addStretch()
        layout.addLayout(top_btns)

        self.table = QTableWidget(len(self.candidates), 4)
        self.table.setHorizontalHeaderLabels(["Learn?", "Page", "OCR Read (Mistake)", "Your Fix (Correct)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        for row, (page_num, raw, corr) in enumerate(self.candidates):
            chk_wrap = QWidget()
            chk_lay = QHBoxLayout(chk_wrap)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(True)
            chk_lay.addWidget(chk)
            self.checkboxes.append(chk)
            self.table.setCellWidget(row, 0, chk_wrap)

            it_pg = QTableWidgetItem(f"Page {page_num}")
            it_pg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_pg.setFlags(it_pg.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, it_pg)

            it_raw = QTableWidgetItem(raw)
            it_raw.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_raw.setFlags(it_raw.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, it_raw)

            it_corr = QTableWidgetItem(corr)
            it_corr.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, it_corr)

        layout.addWidget(self.table)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Learn Checked Rules")
        btn_save.setObjectName("btn_success")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _set_all(self, checked: bool):
        for chk in self.checkboxes:
            chk.setChecked(checked)

    def get_approved_pairs(self) -> List[Tuple[int, str, str]]:
        """Returns list of (page_num, raw_text, corrected_text) for checked rows (respecting inline edits)."""
        approved = []
        for row, (page_num, raw, _orig_corr) in enumerate(self.candidates):
            if row < len(self.checkboxes) and self.checkboxes[row].isChecked():
                corr_item = self.table.item(row, 3)
                corr_val = corr_item.text().strip() if corr_item else _orig_corr
                if raw and corr_val and raw != corr_val:
                    approved.append((page_num, raw, corr_val))
        return approved
