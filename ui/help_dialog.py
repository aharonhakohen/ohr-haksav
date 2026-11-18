# -*- coding: utf-8 -*-
"""
Ohr HaKsav - Interactive User Guide & Training Tutorial Dialog
Provides comprehensive, illustrated documentation on studio features,
offline OCR workflow, keyboard shortcuts, and detailed step-by-step
instructions on training the AI handwriting memory engine and managing profiles.
"""

import os
import sys
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QTextBrowser, QLineEdit, QFrame,
    QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QFont

from ui.i18n import t, get_current_language
from installer.setup_gui import get_resource_path

DOCS_ONLINE_URL = "https://github.com/aharonhakohen/ohr-haksav#readme"


class HelpTutorialDialog(QDialog):
    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.setWindowTitle(t("help_dialog_title"))
        self.resize(840, 660)
        self.setMinimumSize(700, 520)

        # Set Window Icon
        ico_path = get_resource_path(os.path.join("assets", "ohr_haksav.ico"))
        if not os.path.exists(ico_path):
            ico_path = get_resource_path(os.path.join("assets", "ohr_haksav.png"))
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        self.is_hebrew = (get_current_language() == "he")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.is_hebrew else Qt.LayoutDirection.LeftToRight)

        self._init_ui(initial_tab)

    def _init_ui(self, initial_tab: int):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header Bar
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border-radius: 8px;
                border: 1px solid #334155;
            }
        """)
        hdr_box = QHBoxLayout(hdr_frame)
        hdr_box.setContentsMargins(16, 12, 16, 12)
        hdr_box.setSpacing(14)

        logo_path = get_resource_path(os.path.join("assets", "ohr_haksav.png"))
        if os.path.exists(logo_path):
            lbl_logo = QLabel()
            pix = QPixmap(logo_path).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_logo.setPixmap(pix)
            lbl_logo.setStyleSheet("background: transparent; border: none;")
            hdr_box.addWidget(lbl_logo)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        lbl_hdr_title = QLabel(
            "אור הכתב — מדריך למשתמש, הדרכה ואימון המערכת" if self.is_hebrew
            else "Ohr HaKsav — User Guide & Interactive Tutorial"
        )
        lbl_hdr_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #f8fafc; border: none; background: transparent;")
        title_vbox.addWidget(lbl_hdr_title)

        lbl_hdr_sub = QLabel(
            "מדריך מקיף לסריקת מחברות, פיענוח כתב יד תורני, אימון בנק הזיכרון וניהול פרופילים אישיים" if self.is_hebrew
            else "Comprehensive guide to digitizing handwritten Torah notes, training the AI memory engine, and profile management."
        )
        lbl_hdr_sub.setStyleSheet("font-size: 12px; color: #94a3b8; border: none; background: transparent;")
        title_vbox.addWidget(lbl_hdr_sub)

        hdr_box.addLayout(title_vbox)
        hdr_box.addStretch()

        badge_offline = QLabel("100% Offline" if not self.is_hebrew else "אופליין מלא 100%")
        badge_offline.setStyleSheet("""
            QLabel {
                background-color: #065f46;
                color: #a7f3d0;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 12px;
                border: 1px solid #10b981;
            }
        """)
        hdr_box.addWidget(badge_offline)

        main_layout.addWidget(hdr_frame)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #334155;
                font-weight: 600;
                font-size: 12px;
                padding: 8px 16px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1e3a8a;
                border-bottom: 2px solid #2563eb;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
            }
        """)

        # Add 5 Specialized Tabs
        self.browser_quickstart = QTextBrowser()
        self.browser_training = QTextBrowser()
        self.browser_tools = QTextBrowser()
        self.browser_shortcuts = QTextBrowser()
        self.browser_offline = QTextBrowser()

        for b in [self.browser_quickstart, self.browser_training, self.browser_tools, self.browser_shortcuts, self.browser_offline]:
            b.setOpenExternalLinks(True)
            b.setStyleSheet("border: none; background: #ffffff; color: #1e293b; padding: 12px;")

        self._populate_tabs_content()

        self.tabs.addTab(self.browser_quickstart, t("help_tab_quickstart"))
        self.tabs.addTab(self.browser_training, t("help_tab_training"))
        self.tabs.addTab(self.browser_tools, t("help_tab_tools"))
        self.tabs.addTab(self.browser_shortcuts, t("help_tab_shortcuts"))
        self.tabs.addTab(self.browser_offline, t("help_tab_offline"))

        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

        main_layout.addWidget(self.tabs, 1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        # Action: Jump into Memory Studio
        self.btn_open_memory = QPushButton(t("help_btn_open_memory"))
        self.btn_open_memory.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 16px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0d9488;
            }
        """)
        self.btn_open_memory.clicked.connect(self._handle_open_memory)
        bottom_bar.addWidget(self.btn_open_memory)

        # Action: View Online Docs
        btn_online = QPushButton("🌐 " + ("תיעוד מקוון" if self.is_hebrew else "Online Docs"))
        btn_online.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #2563eb;
                font-size: 12px;
                padding: 5px 12px;
                border: 1px solid #bfdbfe;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #eff6ff;
            }
        """)
        btn_online.clicked.connect(lambda: webbrowser.open(DOCS_ONLINE_URL))
        bottom_bar.addWidget(btn_online)

        bottom_bar.addStretch()

        btn_close = QPushButton(t("help_btn_close"))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)

        main_layout.addLayout(bottom_bar)

    def _handle_open_memory(self):
        self.accept()
        parent = self.parent()
        if parent and hasattr(parent, "open_dictionary_manager"):
            parent.open_dictionary_manager()

    def _populate_tabs_content(self):
        if self.is_hebrew:
            self._populate_hebrew_content()
        else:
            self._populate_english_content()

    def _populate_english_content(self):
        # 1. Quick Start
        self.browser_quickstart.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #1e3a8a; margin-top: 0;">🚀 3-Step Quick Start Workflow</h2>
            <p><b>Ohr HaKsav (אור הכתב)</b> is engineered to turn handwritten Torah notebook pages and shiurim into editable, beautifully formatted digital documents with zero cloud dependencies.</p>
            
            <table style="width: 100%; border-collapse: separate; border-spacing: 0 10px;">
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #2563eb; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">1</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">Attach Your Notes (Ctrl+O)</b><br>
                        Click <b>📁 Add Pages</b> or drag & drop photo files directly onto the left sidebar. Supported formats include JPG, PNG, WEBP, and TIFF. You can load an entire notebook at once.
                    </td>
                </tr>
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #059669; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">2</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">Run Neural OCR (F5 or Shift+F5)</b><br>
                        Click <b>⚡ Scan</b> to transcribe the active page, or choose <i>Scan All Pages</i> to transcribe the whole notebook in one click. The neural engine analyzes cursive Ashkenazi and Sefardi handwriting 100% offline.
                    </td>
                </tr>
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #d97706; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">3</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">Proofread & Export (Ctrl+E)</b><br>
                        Review the transcription side-by-side with your original handwriting in the right-to-left editor. Make quick corrections, then export to <b>Microsoft Word (.docx)</b> with clean formatting or <b>Plain Text (.txt)</b>.
                    </td>
                </tr>
            </table>

            <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 14px; border-radius: 4px; margin-top: 15px;">
                <b>💡 Pro Tip for Best OCR Accuracy:</b> Ensure photos are well-lit, laid flat, and right-side up. If your photo is sideways, press <kbd>Ctrl+]</kbd> to rotate it clockwise before scanning. If the ink is faint, press <kbd>Ctrl+I</kbd> to activate the Ink Enhancer!
            </div>
        </div>
        """)

        # 2. Training the System
        self.browser_training.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #0f766e; margin-top: 0;">🧠 Training the System & Handwriting Memory</h2>
            <p>Everyone's Hebrew cursive is unique — looped <i>Lamed</i>s, open <i>Mem</i>s, or custom shorthands. Ohr HaKsav features an adaptive <b>Self-Learning Memory Engine</b> that learns from your proofreading so it never repeats the same mistake twice!</p>
            
            <h3 style="color: #0f172a; margin-bottom: 6px;">How Training Works in 3 Easy Steps:</h3>
            <ol style="padding-left: 20px;">
                <li style="margin-bottom: 8px;"><b>Proofread in the Editor:</b> When OCR misreads a handwritten word (for example, reading <code>בדש</code> instead of <code>בס"ד</code>, or <code>חשה</code> instead of <code>משה</code>), simply edit the text in the right pane to the correct spelling.</li>
                <li style="margin-bottom: 8px;"><b>Click '💾 Save & Learn Mistakes' (<kbd>Ctrl+L</kbd>):</b> The learning engine instantly compares the raw OCR output against your corrected text across all modified pages, automatically extracts every fix, and records the learning pairs into your active handwriting profile.</li>
                <li style="margin-bottom: 8px;"><b>Automatic Future Correction:</b> The next time you scan this writer's notes, the system automatically replaces those OCR mistakes before displaying the text! The green badge at the bottom right will show how many rules were applied.</li>
                <li style="margin-bottom: 8px;"><b>Smart Close & Export Protection:</b> Never worry about forgetting to save your corrections! If you close the app or export your notes to Word while unlearned corrections exist, Ohr HaKsav automatically protects your work by prompting you or automatically saving all corrections into your memory profile!</li>
            </ol>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">Working with Handwriting Profiles:</h3>
            <p>Different writers have distinct penmanship. You can keep rules separated and organized using <b>Profiles</b>:</p>
            <ul>
                <li><b>Switching Profiles:</b> Click the Profile dropdown on the top toolbar (e.g. <code>👤 General (Default)</code>) to select or create a new profile.</li>
                <li><b>Multiple Writers:</b> Create separate profiles such as <i>"Rav's Shiur"</i>, <i>"Chavrusa Notes"</i>, or <i>"Self"</i>.</li>
                <li><b>Rule Stacking:</b> In the Profile Manager, you can check multiple profiles simultaneously to combine their learned rules!</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">The Handwriting Memory Studio (<kbd>Ctrl+M</kbd>):</h3>
            <p>Click the <b>🧠 Memory</b> button on the toolbar or press <kbd>Ctrl+M</kbd> to open the full Memory Studio where you can:</p>
            <ul>
                <li><b>Browse & Filter:</b> View all stored mistake replacement pairs, search by original or corrected word.</li>
                <li><b>Add Custom Rules:</b> Manually create new replacement pairs without needing to scan first.</li>
                <li><b>Export & Backup:</b> Export your learned profile as a <code>.json</code> file to share with other rebbeim or backup your computer.</li>
                <li><b>Import:</b> Load shared profile packages from other users.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">Torah Abbreviations & Roshei Teivot (<kbd>Ctrl+Shift+A</kbd>):</h3>
            <p>Ohr HaKsav has a pre-loaded lexicon of over 50 common Talmudic ראשי תיבות (e.g. רמב"ם, רש"י, תוס', נפק"מ, קמ"ל, עכ"ל). In the editor, click <b>Torah Abbreviations</b> to expand acronyms into their full wording automatically!</p>
        </div>
        """)

        # 3. Studio Tools
        self.browser_tools.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #1e3a8a; margin-top: 0;">🛠️ Studio Tools & Interface Guide</h2>
            <p>The workspace is split into three responsive panes designed for fast, high-volume document transcription:</p>

            <h3 style="color: #0f172a; margin-bottom: 6px;">1. Sidebar (Notebook Pages)</h3>
            <ul>
                <li><b>Page List:</b> Displays all attached pages with live status badges (<i>Scanned</i>, <i>Pending</i>).</li>
                <li><b>Add / Delete:</b> Add single or multiple images, or remove selected pages.</li>
                <li><b>Reordering:</b> Click any page to instantly switch the viewer and editor to that page.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 16px; margin-bottom: 6px;">2. High-Resolution Document Viewer</h3>
            <ul>
                <li><b>Automatic Desk Trimming:</b> If you photograph notebook paper resting on a dark desk, Ohr HaKsav automatically crops away the table borders before OCR begins!</li>
                <li><b>Rotation Controls (<kbd>Ctrl+]</kbd> / <kbd>Ctrl+[</kbd>):</b> Rotate 90° clockwise or counter-clockwise.</li>
                <li><b>Ink Enhancer / Contrast (<kbd>Ctrl+I</kbd>):</b> Boosts faint pencil or light ink against ruled notebook lines, significantly improving recognition accuracy on worn pages.</li>
                <li><b>Zoom & Pan:</b> Use mouse wheel or <kbd>Ctrl++</kbd> / <kbd>Ctrl+-</kbd> to zoom into fine details, or <kbd>Ctrl+0</kbd> to fit to window.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 16px; margin-bottom: 6px;">3. Proofreader & Text Editor (RTL)</h3>
            <ul>
                <li><b>Right-to-Left (RTL) Native:</b> Full bidirectional editing with proper Hebrew cursor navigation and vowel support.</li>
                <li><b>Quick Torah Headers:</b> One-click insertion of <code>בס"ד</code> or <code>בעז"ה</code> at the top of your document.</li>
                <li><b>Rashi Font Toggle:</b> Switch the editor typography to traditional <i>Ktav Rashi</i> font to match classic Torah commentators.</li>
                <li><b>Live Word & Line Statistics:</b> Press <kbd>Ctrl+Shift+S</kbd> to display live word, character, and line count indicators.</li>
            </ul>
        </div>
        """)

        # 4. Shortcuts
        self.browser_shortcuts.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #1e3a8a; margin-top: 0;">⌨️ Complete Keyboard Shortcuts Reference</h2>
            <p>Speed up your workflow using these standard keyboard shortcuts:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px;">
                <thead>
                    <tr style="background-color: #f1f5f9; text-align: left;">
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1; width: 35%;">Action</th>
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1; width: 25%;">Shortcut</th>
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1;">Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Add Pages</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+O</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Attach photos or scans</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Scan Active Page</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>F5</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Run offline neural OCR on selected page</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Scan All Pages</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Shift+F5</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Batch process entire notebook</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Save & Learn Mistakes</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+L</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Train memory bank with your fixes</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Memory Studio</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+M</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Manage learned rules and profiles</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Export to Word (.docx)</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+E</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Save formatted Word document</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Export to Text (.txt)</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+S</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Save UTF-8 plain text file</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Toggle Contrast / Ink</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+I</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Boost faint ink against paper lines</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Rotate Clockwise</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+]</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Rotate image 90 degrees CW</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Rotate Counter-CW</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+[</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Rotate image 90 degrees CCW</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Fit to Window</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+0</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Reset zoom to fit image pane</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Toggle Dark/Light Theme</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+T</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Switch visual color scheme</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Toggle Live Stats Bar</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+Shift+S</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Show/hide words & line counter</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>Check for Updates</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+U</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Open in-app update checker</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>User Guide & Tutorial</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>F1</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Open this interactive help dialog</td></tr>
                </tbody>
            </table>
        </div>
        """)

        # 5. Offline & Domain
        self.browser_offline.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #059669; margin-top: 0;">🌐 100% Offline Privacy & Network Administration</h2>
            
            <h3 style="color: #0f172a; margin-bottom: 6px;">Zero Cloud Dependencies & Total Data Security</h3>
            <p>Ohr HaKsav is architected specifically for sensitive Torah manuscripts, private chiddushim, and air-gapped Yeshiva environments:</p>
            <ul>
                <li><b>Local Execution:</b> The PyTorch neural network, lexicon tokenizers, and database run 100% locally on your machine's CPU.</li>
                <li><b>No Telemetry / No Tracking:</b> No personal data, photos, transcriptions, or mistake memory pairs are ever sent over the network.</li>
                <li><b>Isolated User Data:</b> All personal handwriting profiles and learned mistakes are stored safely in your user roaming profile at <code>%APPDATA%\\OhrHaKsav</code>, meaning upgrading or uninstalling application files never touches your data.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">Windows Server Domain & Institutional Deployment</h3>
            <p>For network administrators managing computer labs, yeshiva servers, or teachers center workstations:</p>
            <ul>
                <li><b>Pre-Flight Internet Check:</b> The updater performs an instant socket test (<10ms). On machines without Internet, it immediately falls back to offline mode without freezing.</li>
                <li><b>UNC Network Share Updates:</b> In <i>Update Source & Settings</i>, configure a shared domain folder (e.g. <code>\\\\newltcserver\\Installs\\OhrHaKsav</code>). When you drop <code>version.json</code> and <code>OhrHaKsav_Setup_v1.4.0.exe</code> into this share, all network workstations can detect and install updates locally with zero external internet traffic!</li>
                <li><b>Silent Background Polling:</b> The app quietly checks for updates on launch without disrupting teachers or students.</li>
            </ul>
        </div>
        """)

    def _populate_hebrew_content(self):
        # 1. צעדים ראשונים
        self.browser_quickstart.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7; color: #1e293b; direction: rtl; text-align: right;">
            <h2 style="color: #1e3a8a; margin-top: 0;">🚀 3 צעדים מהירים לפענוח ועריכת מחברות</h2>
            <p><b>אור הכתב</b> תוכנן במיוחד עבור לומדי תורה, מגידי שיעורים, רבנים ומחברי ספרים כדי להפוך מחברות שיעורים ודפי חידושי תורה בכתב יד לקבצים דיגיטליים ערוכים ומסודרים — 100% אופליין ללא תלות באינטרנט.</p>
            
            <table style="width: 100%; border-collapse: separate; border-spacing: 0 10px;">
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #2563eb; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">1</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">הוספת דפי המחברת (Ctrl+O)</b><br>
                        לחצו על <b>📁 הוסף דפים</b> או גררו קובצי תמונות ישירות לסרגל הצד הימני. התוכנה תומכת בתמונות מסמארטפון ומסורק (JPG, PNG, WEBP, TIFF). ניתן להעלות מחברת שלמה בבת אחת.
                    </td>
                </tr>
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #059669; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">2</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">סריקה וזיהוי נוירוני (F5 או Shift+F5)</b><br>
                        לחצו על כפתור <b>⚡ סרוק</b> כדי לפענח את הדף הנוכחי, או בחרו <i>סרוק את כל הדפים</i> לסריקה מרוכזת של המחברת. המנוע הנוירוני מזהה כתב יד אשכנזי וספרדי ברמת דיוק גבוהה.
                    </td>
                </tr>
                <tr>
                    <td style="width: 48px; vertical-align: top;">
                        <div style="background-color: #d97706; color: white; width: 36px; height: 36px; border-radius: 18px; text-align: center; line-height: 36px; font-weight: bold; font-size: 16px;">3</div>
                    </td>
                    <td style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <b style="font-size: 14px; color: #0f172a;">הגהה ויצוא למסמך Word (Ctrl+E)</b><br>
                        הטקסט המפוענח מוצג לצד התמונה המקורית. בצעו הגהה קלה בעורך, ולחצו על <b>📄 יצוא ➔ Microsoft Word (.docx)</b> לקבלת קובץ וורד מעוצב בכיוון ימין-לשמאל, מוכן להדפסה, קונטרס או שיתוף.
                    </td>
                </tr>
            </table>

            <div style="background-color: #eff6ff; border-right: 4px solid #3b82f6; padding: 10px 14px; border-radius: 4px; margin-top: 15px;">
                <b>💡 טיפ לדיוק מירבי:</b> ודאו שהדף מצולם ישר ומואר היטב. אם התמונה צולמה על הצד, לחצו על <kbd>Ctrl+]</kbd> לסיבוב הדף. אם הדיו חלש, לחצו על <kbd>Ctrl+I</kbd> להפעלת משפר הניגודיות!
            </div>
        </div>
        """)

        # 2. אימון המערכת וזיכרון טעויות
        self.browser_training.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7; color: #1e293b; direction: rtl; text-align: right;">
            <h2 style="color: #0f766e; margin-top: 0;">🧠 אימון המערכת ובנק הזיכרון לכתב יד</h2>
            <p>לכל כותב יש אופי ייחודי בכתב היד (לדוגמה: למ"ד מסולסלת, דל"ת הדומה לרי"ש, או קיצורים אישיים). 'אור הכתב' כולל <b>מנוע זיכרון לומד</b> המתעדכן מהתיקונים שלכם, כך שהמערכת לעולם אינה חוזרת על אותה טעות פעמיים!</p>
            
            <h3 style="color: #0f172a; margin-bottom: 6px;">כיצד מאמנים את המערכת ב-3 שלבים:</h3>
            <ol style="padding-right: 20px;">
                <li style="margin-bottom: 8px;"><b>בצעו הגהה בעורך:</b> כאשר המערכת שוגה במילה מסוימת (למשל, זיהתה <code>בדש</code> במקום <code>בס"ד</code>, או <code>חשה</code> במקום <code>משה</code>), פשוט תקנו את המילה בעורך הטקסט משמאל.</li>
                <li style="margin-bottom: 8px;"><b>לחצו על '💾 שמור ולמד טעויות' (<kbd>Ctrl+L</kbd>):</b> מנוע הלמידה משווה מיד בין הפלט הגולמי של הסריקה לבין הטקסט המתוקן שלכם בכל העמודים שנערכו, מחלץ את צמדי התיקון, ושומר אותם בפרופיל הפעיל שלכם.</li>
                <li style="margin-bottom: 8px;"><b>תיקון אוטומטי בסריקות הבאות:</b> בסריקות הבאות של כתב יד זה, המערכת תחליף ותתקן את הטעויות באופן אוטומטי עוד לפני שהטקסט מופיע על המסך! התגית הירוקה למטה תציג כמה תיקונים הוחלו.</li>
                <li style="margin-bottom: 8px;"><b>הגנה חכמה בסגירה ובייצוא:</b> לעולם לא תשכחו להטמיע! בעת סגירת התוכנה או ייצוא המסמך ל-Word, המערכת מזהה אוטומטית תיקונים שטרם נשמרו, ומציעה להטמיע את כל התיקונים מכל העמודים במאגר הזיכרון בלחיצה אחת!</li>
            </ol>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">עבודה עם פרופילים מרובים:</h3>
            <p>כתב ידו של מגיד השיעור שונה מכתב ידו של החברותא. ניתן להפריד בין הכותבים באמצעות <b>פרופילים אישיים</b>:</p>
            <ul>
                <li><b>החלפת פרופיל:</b> לחצו על תפריט הפרופיל בסרגל העליון (למשל <code>👤 כללי (ברירת מחדל)</code>) כדי לבחור או ליצור פרופיל חדש.</li>
                <li><b>פרופיל ייעודי לכל כותב:</b> צרו פרופילים כמו <i>"שיעורי הרב"</i>, <i>"מחברת חברותא"</i>, או <i>"כתב ידי האישי"</i>.</li>
                <li><b>שילוב פרופילים (Stacking):</b> במנהל הפרופילים ניתן לסמן מספר פרופילים יחד כדי להחיל את כללי הלמידה שלהם בו-זמנית!</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">סטודיו הזיכרון המלא (<kbd>Ctrl+M</kbd>):</h3>
            <p>לחצו על כפתור <b>🧠 בנק הזיכרון</b> בסרגל הכלים לפתיחת מנהל הזיכרון המלא שבו תוכלו:</p>
            <ul>
                <li><b>חיפוש וצפייה:</b> לראות את כל צמדי המילים שנלמדו ולחפש לפי מילה מקורית או תיקון.</li>
                <li><b>הוספת כללים ידנית:</b> להוסיף צמדי תיקון מראש מבלי להמתין לסריקה.</li>
                <li><b>גיבוי ויצוא:</b> לייצא פרופיל לקובץ <code>.json</code> כדי לגבות את הנתונים או להעביר למחשב אחר / לשתף עם מורים אחרים.</li>
                <li><b>יבוא:</b> לטעון מאגרי מילים ופרופילים מוכנים.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">ראשי תיבות תורניים (<kbd>Ctrl+Shift+A</kbd>):</h3>
            <p>התוכנה כוללת מאגר של למעלה מ-50 ראשי תיבות תורניים נפוצים (רמב"ם, רש"י, תוס', נפק"מ, קמ"ל, עכ"ל). לחצו בעורך על <b>ראשי תיבות</b> לפתיחת הקיצורים לפירושם המלא בלחיצה אחת!</p>
        </div>
        """)

        # 3. כלי הסטודיו
        self.browser_tools.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7; color: #1e293b; direction: rtl; text-align: right;">
            <h2 style="color: #1e3a8a; margin-top: 0;">🛠️ כלי הסטודיו ומבנה הממשק</h2>
            <p>סביבת העבודה מחולקת לשלושה חלקים מסונכרנים לעבודה נוחה ומהירה:</p>

            <h3 style="color: #0f172a; margin-bottom: 6px;">1. סרגל הצד (דפי המחברת)</h3>
            <ul>
                <li><b>רשימת הדפים:</b> מציגה את כל הדפים שנטענו עם חיווי מצב (<i>נסרק בהצלחה</i> / <i>ממתין לסריקה</i>).</li>
                <li><b>הוספה / מחיקה:</b> אפשרות להוסיף תמונות נוספות או למחוק דפים מיותרים.</li>
                <li><b>מעבר מהיר:</b> לחיצה על כל דף ברשימה מעבירה מיד את התצוגה והעורך לאותו דף.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 16px; margin-bottom: 6px;">2. צג התמונה ברזולוציה גבוהה</h3>
            <ul>
                <li><b>חיתוך שולחן אוטומטי:</b> בעת צילום דף המונח על שולחן כהה, המערכת מזהה וגוזרת את שולי השולחן אוטומטית לפני הסריקה!</li>
                <li><b>סיבוב התמונה (<kbd>Ctrl+]</kbd> / <kbd>Ctrl+[</kbd>):</b> סיבוב 90 מעלות ימינה או שמאלה עבור דפים שצולמו לרוחב.</li>
                <li><b>משפר ניגודיות ודיו (<kbd>Ctrl+I</kbd>):</b> מבליט שורות עפרון חלשות או דיו בהיר על גבי דפי שורות ומשפר משמעותית את הזיהוי.</li>
                <li><b>זום ותנועה:</b> שימוש בגלגלת העכבר, במקשי <kbd>Ctrl++</kbd> / <kbd>Ctrl+-</kbd>, או התאמה מלאה לחלון ב-<kbd>Ctrl+0</kbd>.</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 16px; margin-bottom: 6px;">3. עורך הטקסט וההגהה (מימין לשמאל)</h3>
            <ul>
                <li><b>תמיכה מלאה בעברית RTL:</b> כתיבה טבעית מימין לשמאל עם ניווט סמן מותאם ותמיכה בניקוד.</li>
                <li><b>כפתורי כותרת מהירים:</b> הוספה מהירה של <code>בס"ד</code> או <code>בעז"ה</code> בראש המסמך בלחיצת כפתור אחת.</li>
                <li><b>החלפה לכתב רש"י:</b> אפשרות להציג את הטקסט בגופן כתב רש"י מסורתי.</li>
                <li><b>סרגל סטטיסטיקה חי:</b> הצגת מונה מילים, תווים ושורות חי בסרגל התחתון (<kbd>Ctrl+Shift+S</kbd>).</li>
            </ul>
        </div>
        """)

        # 4. קיצורי מקשים
        self.browser_shortcuts.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7; color: #1e293b; direction: rtl; text-align: right;">
            <h2 style="color: #1e3a8a; margin-top: 0;">⌨️ טבלת קיצורי מקשים מלאה</h2>
            <p>לייעול העבודה ללא צורך בעכבר, ניתן להשתמש בקיצורי המקשים הבאים:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px;">
                <thead>
                    <tr style="background-color: #f1f5f9; text-align: right;">
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1; width: 35%;">פעולה</th>
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1; width: 25%;">קיצור מקשים</th>
                        <th style="padding: 8px 12px; border: 1px solid #cbd5e1;">תיאור</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>הוספת דפים</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+O</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">טעינת תמונות או סריקות חדשות</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>סריקת הדף הנוכחי</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>F5</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">הפעלת זיהוי כתב יד על הדף הפעיל</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>סריקת כל הדפים</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Shift+F5</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">סריקה מרוכזת של המחברת כולה</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>שמירה ואימון טעויות</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+L</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">אימון בנק הזיכרון לפי תיקוני ההגהה</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>סטודיו הזיכרון והמילון</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+M</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">ניהול כללי החלפה ופרופילים אישיים</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>יצוא למסמך Word (.docx)</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+E</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">שמירת מסמך וורד מעוצב מוכן להדפסה</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>יצוא לקובץ טקסט (.txt)</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+S</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">שמירת קובץ טקסט UTF-8 נקי</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>משפר ניגודיות ודיו</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+I</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">הבלטת כתב עפרון או דיו חלש</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>סיבוב ימינה</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+]</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">סיבוב התמונה 90 מעלות בכיוון השעון</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>סיבוב שמאלה</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+[</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">סיבוב התמונה 90 מעלות נגד השעון</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>התאמה מלאה לחלון</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+0</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">התאמת גודל התמונה למסך</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>החלפת ערכת נושא</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+T</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">מעבר בין מצב בהיר למצב כהה</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>הצגת סרגל מונה מילים</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+Shift+S</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">הצגה/הסתרה של מונה מילים ושורות</td></tr>
                    <tr style="background-color: #f8fafc;"><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>בדיקת עדכונים</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>Ctrl+U</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">פתיחת חלון בדיקת והתקנת עדכונים</td></tr>
                    <tr><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><b>מדריך למשתמש ואימון</b></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;"><kbd>F1</kbd></td><td style="padding: 8px 12px; border: 1px solid #cbd5e1;">פתיחת מדריך אינטראקטיבי זה</td></tr>
                </tbody>
            </table>
        </div>
        """)

        # 5. אופליין ואבטחה
        self.browser_offline.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7; color: #1e293b; direction: rtl; text-align: right;">
            <h2 style="color: #059669; margin-top: 0;">🌐 פרטיות אופליין מלאה וניהול רשת מוסדי</h2>
            
            <h3 style="color: #0f172a; margin-bottom: 6px;">אפס תלות בענן ואבטחת מידע מלאה</h3>
            <p>'אור הכתב' פותח במיוחד עבור סביבות ישיבתיות ומוסדיות, ללא צורך בחיבור לאינטרנט:</p>
            <ul>
                <li><b>ביצוע מקומי בלבד:</b> רשת ה-PyTorch הנוירונית, מילוני השפה ומאגרי הזיכרון רצים 100% על מעבד המחשב שלכם (CPU).</li>
                <li><b>ללא מעקב וללא ענן:</b> אף תמונה, טקסט מנוסח או תיקון הגהה אינם נשלחים לשום שרת חיצוני.</li>
                <li><b>בידוד נתוני משתמש:</b> כל הפרופילים והכללים שנלמדו נשמרים בתיקיית המשתמש המוגנת ב-<code>%APPDATA%\\OhrHaKsav</code>, כך ששדרוג גרסה לעולם אינו מוחק את הנתונים והאימונים שלכם!</li>
            </ul>

            <h3 style="color: #0f172a; margin-top: 18px; margin-bottom: 6px;">הפצה ברשת ארגונית ושרתי Windows Server</h3>
            <p>עבור מנהלי רשת במוסדות חינוך, מרפ"ד, חדרי מחשבים וישיבות:</p>
            <ul>
                <li><b>בדיקת חיבור מהירה (8ms):</b> מנגנון בדיקת העדכונים בודק קישוריות מיד. במחשבים ללא גישה לאינטרנט, הוא עובר מיד למצב אופליין ללא השהיות או קריסות.</li>
                <li><b>עדכונים מתיקיית שרת מקומית (UNC):</b> בלשונית <i>הגדרות ומקור עדכון</i>, ניתן להגדיר נתיב שרת מקומי (כגון <code>\\\\newltcserver\\Installs\\OhrHaKsav</code>). כאשר מנהל הרשת מניח בתיקייה זו את <code>version.json</code> ואת קובץ ההתקנה <code>OhrHaKsav_Setup_v1.4.0.exe</code>, כל המחשבים ברשת המקומית יזהו את העדכון ויוכלו להתקינו מקומית ללא אינטרנט!</li>
                <li><b>בדיקה שקטה ברקע:</b> בעת הפעלת התוכנה מתבצעת בדיקה מהירה ברקע המציגה באנר עדין בלבד כאשר ישנו עדכון חדש.</li>
            </ul>
        </div>
        """)
