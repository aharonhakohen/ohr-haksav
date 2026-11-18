# -*- coding: utf-8 -*-
"""
TorahNotesOCR - Hebrew RTL Text Editor (v1.4.0)
Full Right-to-Left (RTL) editing with:
- Torah abbreviations toolbar
- Low-confidence OCR line highlighting & F8 quick-jump
- Inline RTL Find & Replace (current page + entire notebook)
- Line/word statistics and mistake tracking
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLabel, QPushButton, QMenu, QToolButton, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QFont, QTextCursor, QTextOption, QAction,
    QColor, QTextFormat, QKeySequence, QShortcut
)
import difflib
import re

from ui.i18n import t

COMMON_ABBREVIATIONS = [
    ("בס\"ד", "בס\"ד"),
    ("רש\"י", "רש\"י"),
    ("תוס'", "תוס'"),
    ("רמב\"ם", "רמב\"ם"),
    ("ראב\"ד", "ראב\"ד"),
    ("רי\"ף", "רי\"ף"),
    ("רא\"ש", "רא\"ש"),
    ("גמ'", "גמ'"),
    ("משנה", "משנה"),
    ("ברייתא", "ברייתא"),
    ("נפק\"מ", "נפקא מינה"),
    ("קמ\"ל", "קא משמע לן"),
    ("סד\"א", "סלקא דעתך אמינא"),
    ("ח\"נ", "חצי נזק"),
    ("נ\"ש", "נזק שלם"),
    ("ברה\"ר", "רשות הרבים"),
    ("ברה\"י", "רשות היחיד"),
    ("עיי\"ש", "עיין שם"),
    ("עכ\"ד", "עד כאן דבריו"),
    ("וכו'", "וכולי"),
    ("וגו'", "וגומר"),
]


class HebrewTextEditor(QWidget):
    text_changed = pyqtSignal()
    line_focused = pyqtSignal(int)
    replace_all_pages_requested = pyqtSignal(str, str)  # (find_str, replace_str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_raw_text = ""
        self.line_confidences = []
        self._low_conf_lines = []
        self._low_conf_cursor_idx = -1
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Quick Abbreviation & Tools Bar
        self.abbrev_bar = QHBoxLayout()
        self.abbrev_bar.setSpacing(4)

        self.lbl_quick = QLabel(t("editor_quick_abbr"))
        self.lbl_quick.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 11px;")
        self.abbrev_bar.addWidget(self.lbl_quick)

        for abbr, full in [('בס"ד', 'בס"ד'), ('רש"י', 'רש"י'), ('תוס\'', 'תוספות')]:
            btn = QPushButton(abbr)
            btn.setToolTip(full)
            btn.setFixedHeight(24)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
            btn.clicked.connect(lambda checked, text=abbr: self.insert_text(text))
            self.abbrev_bar.addWidget(btn)

        # Categorized Torah Abbreviations Menu
        self.btn_more_abbr = QToolButton()
        self.btn_more_abbr.setText(t("abbr_menu_title"))
        self.btn_more_abbr.setFixedHeight(24)
        self.btn_more_abbr.setStyleSheet("""
            QToolButton {
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        self.btn_more_abbr.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.ab_menu = QMenu(self.btn_more_abbr)

        # Submenu 1: Seforim & Commentators
        menu_seforim = self.ab_menu.addMenu(t("abbr_group_seforim"))
        seforim_abbrs = [
            ('רש"י', 'רש"י'),
            ('תוס\'', 'תוספות'),
            ('רמב"ם', 'רמב"ם'),
            ('ראב"ד', 'ראב"ד'),
            ('רי"ף', 'רי"ף'),
            ('רא"ש', 'רא"ש'),
            ('משנה', 'משנה'),
            ('ברייתא', 'ברייתא'),
            ('גמ\'', 'גמרא'),
            ('שו"ע', 'שולחן ערוך'),
            ('טו"ר', 'טור')
        ]
        for a, full in seforim_abbrs:
            act = QAction(f"{a}  ({full})", self)
            act.triggered.connect(lambda checked, text=a: self.insert_text(text))
            menu_seforim.addAction(act)

        menu_terms = self.ab_menu.addMenu(t("abbr_group_talmud"))
        term_abbrs = [
            ('בס"ד', 'בס"ד'),
            ('נפק"מ', 'נפקא מינה'),
            ('קמ"ל', 'קא משמע לן'),
            ('סד"א', 'סלקא דעתך אמינא'),
            ('ח"נ', 'חצי נזק'),
            ('נ"ש', 'נזק שלם'),
            ('ברה"ר', 'רשות הרבים'),
            ('ברה"י', 'רשות היחיד'),
            ('עיי"ש', 'עיין שם'),
            ('עכ"ד', 'עד כאן דבריו'),
            ('וכו\'', 'וכולי'),
            ('וגו\'', 'וגומר')
        ]
        for a, full in term_abbrs:
            act = QAction(f"{a}  ({full})", self)
            act.triggered.connect(lambda checked, text=a: self.insert_text(text))
            menu_terms.addAction(act)

        self.btn_more_abbr.setMenu(self.ab_menu)
        self.abbrev_bar.addWidget(self.btn_more_abbr)

        self.abbrev_bar.addStretch()

        # Low-Confidence Quick Jump Pill (Visible only when uncertain lines exist)
        self.btn_next_uncertain = QPushButton("")
        self.btn_next_uncertain.setFixedHeight(24)
        self.btn_next_uncertain.setVisible(False)
        self.btn_next_uncertain.setToolTip("Jump to next low-confidence OCR line (F8)")
        self.btn_next_uncertain.setStyleSheet("""
            QPushButton {
                background-color: #fef3c7;
                color: #92400e;
                border: 1px solid #f59e0b;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fde68a;
            }
        """)
        self.btn_next_uncertain.clicked.connect(self.jump_to_next_low_confidence_line)
        self.abbrev_bar.addWidget(self.btn_next_uncertain)

        # Find & Replace Toggle Button
        self.btn_find_toggle = QPushButton("🔍")
        self.btn_find_toggle.setFixedHeight(24)
        self.btn_find_toggle.setToolTip("Find & Replace (Ctrl+F / Ctrl+H)")
        self.btn_find_toggle.setStyleSheet("padding: 2px 7px; font-size: 11px; border-radius: 4px;")
        self.btn_find_toggle.clicked.connect(self.toggle_find_bar)
        self.abbrev_bar.addWidget(self.btn_find_toggle)

        layout.addLayout(self.abbrev_bar)

        # Inline Collapsible Find & Replace Bar (Hidden by default)
        self.find_bar = QFrame()
        self.find_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(148, 163, 184, 0.14);
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 6px;
            }
        """)
        fb_layout = QVBoxLayout(self.find_bar)
        fb_layout.setContentsMargins(6, 5, 6, 5)
        fb_layout.setSpacing(4)

        row_find = QHBoxLayout()
        row_find.setSpacing(4)
        self.inp_find = QLineEdit()
        self.inp_find.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.inp_find.setPlaceholderText("Find word or phrase... / חפש מילה...")
        self.inp_find.returnPressed.connect(self.find_next)
        row_find.addWidget(self.inp_find, stretch=2)

        self.btn_find_prev = QPushButton("◀")
        self.btn_find_prev.setToolTip("Previous match")
        self.btn_find_prev.setFixedWidth(28)
        self.btn_find_prev.clicked.connect(self.find_prev)
        row_find.addWidget(self.btn_find_prev)

        self.btn_find_next = QPushButton("▶")
        self.btn_find_next.setToolTip("Next match")
        self.btn_find_next.setFixedWidth(28)
        self.btn_find_next.clicked.connect(self.find_next)
        row_find.addWidget(self.btn_find_next)

        self.btn_find_close = QPushButton("✕")
        self.btn_find_close.setFixedWidth(26)
        self.btn_find_close.setToolTip("Close Find & Replace (Esc)")
        self.btn_find_close.clicked.connect(lambda: self.find_bar.setVisible(False))
        row_find.addWidget(self.btn_find_close)
        fb_layout.addLayout(row_find)

        row_repl = QHBoxLayout()
        row_repl.setSpacing(4)
        self.inp_replace = QLineEdit()
        self.inp_replace.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.inp_replace.setPlaceholderText("Replace with... / החלף ב...")
        row_repl.addWidget(self.inp_replace, stretch=2)

        self.btn_replace_one = QPushButton("Replace")
        self.btn_replace_one.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_replace_one.clicked.connect(self.replace_current)
        row_repl.addWidget(self.btn_replace_one)

        self.btn_replace_page = QPushButton("All (Page)")
        self.btn_replace_page.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_replace_page.clicked.connect(self.replace_all_current_page)
        row_repl.addWidget(self.btn_replace_page)

        self.btn_replace_notebook = QPushButton("All Pages")
        self.btn_replace_notebook.setToolTip("Replace across EVERY page in this notebook")
        self.btn_replace_notebook.setStyleSheet("padding: 2px 8px; font-size: 11px; font-weight: bold;")
        self.btn_replace_notebook.clicked.connect(self._emit_replace_all_pages)
        row_repl.addWidget(self.btn_replace_notebook)
        fb_layout.addLayout(row_repl)

        self.lbl_find_status = QLabel("")
        self.lbl_find_status.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_find_status.setVisible(False)
        fb_layout.addWidget(self.lbl_find_status)

        self.find_bar.setVisible(False)
        layout.addWidget(self.find_bar)

        # Escape inside find bar closes it cleanly
        esc_sc = QShortcut(QKeySequence("Escape"), self.find_bar)
        esc_sc.activated.connect(self._close_find_bar)

        # Text Edit Area (Hebrew RTL)
        self.text_edit = QTextEdit()
        self.text_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        font = QFont("David", 15)
        font.setStyleHint(QFont.StyleHint.Serif)
        self.text_edit.setFont(font)

        opt = self.text_edit.document().defaultTextOption()
        opt.setTextDirection(Qt.LayoutDirection.RightToLeft)
        opt.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.text_edit.document().setDefaultTextOption(opt)

        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.cursorPositionChanged.connect(self._on_cursor_changed)
        layout.addWidget(self.text_edit)

        # Workflow Guidance Hint Banner
        self.workflow_card = QFrame()
        self.workflow_card.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 2px 6px;
            }
        """)
        wf_box = QHBoxLayout(self.workflow_card)
        wf_box.setContentsMargins(6, 4, 6, 4)
        self.lbl_workflow = QLabel(t("editor_workflow_hint"))
        self.lbl_workflow.setStyleSheet("color: #475569; font-size: 11.5px; font-weight: 500;")
        self.lbl_workflow.setWordWrap(True)
        wf_box.addWidget(self.lbl_workflow)
        layout.addWidget(self.workflow_card)

        # Advanced Stats Bar (Hidden by default, toggleable via View menu)
        self.stats_widget = QWidget()
        self.stats_bar = QHBoxLayout(self.stats_widget)
        self.stats_bar.setContentsMargins(4, 2, 4, 2)

        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: #64748b; font-size: 11px;")

        self.lbl_corrections = QLabel("")
        self.lbl_corrections.setStyleSheet("color: #059669; font-weight: bold; font-size: 11px;")

        self.stats_bar.addWidget(self.lbl_stats)
        self.stats_bar.addStretch()
        self.stats_bar.addWidget(self.lbl_corrections)

        self.stats_widget.setVisible(False)
        layout.addWidget(self.stats_widget)

        self._update_stats()

    def retranslate_ui(self):
        self.lbl_quick.setText(t("editor_quick_abbr"))
        self.btn_more_abbr.setText(t("abbr_menu_title"))
        if hasattr(self, "lbl_workflow"):
            self.lbl_workflow.setText(t("editor_workflow_hint"))
        self._update_uncertain_badge()
        self._update_stats()

    # --- Find & Replace ---
    def open_find_bar(self, focus_replace: bool = False):
        self.find_bar.setVisible(True)
        selected = self.text_edit.textCursor().selectedText()
        if selected and "\u2029" not in selected:
            self.inp_find.setText(selected)
        if focus_replace:
            self.inp_replace.setFocus()
            self.inp_replace.selectAll()
        else:
            self.inp_find.setFocus()
            self.inp_find.selectAll()

    def toggle_find_bar(self):
        if self.find_bar.isVisible():
            self._close_find_bar()
        else:
            self.open_find_bar(focus_replace=False)

    def _close_find_bar(self):
        self.find_bar.setVisible(False)
        self.text_edit.setFocus()

    def find_next(self) -> bool:
        query = self.inp_find.text()
        if not query:
            return False
        found = self.text_edit.find(query)
        if not found:
            # Wrap around to start
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)
            found = self.text_edit.find(query)
        self.lbl_find_status.setVisible(True)
        self.lbl_find_status.setText("Match found" if found else f"No matches for '{query}'")
        return found

    def find_prev(self) -> bool:
        query = self.inp_find.text()
        if not query:
            return False
        from PyQt6.QtGui import QTextDocument
        found = self.text_edit.find(query, QTextDocument.FindFlag.FindBackward)
        if not found:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text_edit.setTextCursor(cursor)
            found = self.text_edit.find(query, QTextDocument.FindFlag.FindBackward)
        self.lbl_find_status.setVisible(True)
        self.lbl_find_status.setText("Match found" if found else f"No matches for '{query}'")
        return found

    def replace_current(self):
        query = self.inp_find.text()
        repl = self.inp_replace.text()
        if not query:
            return
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == query:
            cursor.insertText(repl)
            self.find_next()
        else:
            if self.find_next():
                cursor = self.text_edit.textCursor()
                cursor.insertText(repl)
                self.find_next()

    def replace_all_current_page(self) -> int:
        query = self.inp_find.text()
        repl = self.inp_replace.text()
        if not query:
            return 0
        text = self.get_text()
        count = text.count(query)
        if count > 0:
            new_text = text.replace(query, repl)
            self.text_edit.setPlainText(new_text)
        self.lbl_find_status.setVisible(True)
        self.lbl_find_status.setText(f"Replaced {count} occurrence(s) on this page.")
        return count

    def _emit_replace_all_pages(self):
        query = self.inp_find.text()
        repl = self.inp_replace.text()
        if query:
            self.replace_all_pages_requested.emit(query, repl)

    # --- Low-Confidence Highlighting ---
    def set_line_confidences(self, confidences: list, threshold: float = 0.75):
        """
        Highlights lines whose OCR confidence falls below `threshold` in soft amber
        so proofreaders can spot uncertain lines at a glance and jump via F8.
        """
        self.line_confidences = list(confidences or [])
        self._low_conf_lines = [
            idx for idx, c in enumerate(self.line_confidences)
            if isinstance(c, (int, float)) and c < threshold
        ]
        self._low_conf_cursor_idx = -1
        self._apply_confidence_highlights()
        self._update_uncertain_badge()

    def _apply_confidence_highlights(self):
        selections = []
        doc = self.text_edit.document()
        bg_color = QColor(245, 158, 11, 55)  # Subtle amber highlight visible in both light & dark themes
        for line_idx in self._low_conf_lines:
            if 0 <= line_idx < doc.blockCount():
                block = doc.findBlockByNumber(line_idx)
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(bg_color)
                sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                cur = QTextCursor(block)
                cur.clearSelection()
                sel.cursor = cur
                selections.append(sel)
        self.text_edit.setExtraSelections(selections)

    def _update_uncertain_badge(self):
        cnt = len(self._low_conf_lines)
        if cnt > 0:
            self.btn_next_uncertain.setText(f"⚠ {cnt} uncertain (F8)")
            self.btn_next_uncertain.setVisible(True)
        else:
            self.btn_next_uncertain.setVisible(False)

    def jump_to_next_low_confidence_line(self) -> int:
        """Jumps the cursor to the next low-confidence line and returns its line index (or -1)."""
        if not self._low_conf_lines:
            return -1
        self._low_conf_cursor_idx = (self._low_conf_cursor_idx + 1) % len(self._low_conf_lines)
        target_line = self._low_conf_lines[self._low_conf_cursor_idx]
        self.go_to_line(target_line)
        self.text_edit.setFocus()
        return target_line

    # --- Standard Editor Operations ---
    def insert_text(self, text: str):
        cursor = self.text_edit.textCursor()
        cursor.insertText(text + " ")
        self.text_edit.setFocus()

    def set_text(self, text: str, raw_text: str = None, confidences: list = None):
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.original_raw_text = raw_text if raw_text is not None else text
        self.text_edit.blockSignals(False)
        if confidences is not None:
            self.set_line_confidences(confidences)
        else:
            self.set_line_confidences([])
        self._update_stats()

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def _on_text_changed(self):
        self._update_stats()
        self.text_changed.emit()

    def _on_cursor_changed(self):
        cursor = self.text_edit.textCursor()
        line_num = cursor.blockNumber()
        self.line_focused.emit(line_num)

    def set_stats_visible(self, visible: bool):
        """Toggle visibility of document statistics underneath the editor."""
        if hasattr(self, 'stats_widget'):
            self.stats_widget.setVisible(visible)

    def is_stats_visible(self) -> bool:
        if hasattr(self, 'stats_widget'):
            return not self.stats_widget.isHidden()
        return False

    def _update_stats(self):
        text = self.text_edit.toPlainText()
        words = len(re.findall(r'\S+', text))
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        self.lbl_stats.setText(t("editor_stats", words=words, chars=chars, lines=lines))

        if self.original_raw_text and self.original_raw_text != text:
            raw_words = re.findall(r'\S+', self.original_raw_text)
            cur_words = re.findall(r'\S+', text)
            sm = difflib.SequenceMatcher(None, raw_words, cur_words)
            diff_count = sum(1 for tag, _, _, _, _ in sm.get_opcodes() if tag in ('replace', 'delete', 'insert'))
            self.lbl_corrections.setText(t("editor_diff_ready", count=diff_count))
            self.lbl_corrections.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_corrections.setText(t("editor_diff_none"))
            self.lbl_corrections.setStyleSheet("color: #a6adc8; font-size: 11px;")

    def go_to_line(self, line_num: int):
        """Moves cursor to the start of specified line index and ensures it is visible."""
        doc = self.text_edit.document()
        if 0 <= line_num < doc.blockCount():
            block = doc.findBlockByNumber(line_num)
            cursor = self.text_edit.textCursor()
            cursor.setPosition(block.position())
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
