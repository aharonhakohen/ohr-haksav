# -*- coding: utf-8 -*-
"""
TorahNotesOCR - Main Application Window
Modern, sleek, side-by-side OCR & handwriting transcription studio.
Features a native Windows Menu Bar, stacked workflow action buttons,
high-contrast typography, and dynamic English/Hebrew UI localization.
"""

import os
import sys
import json
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QListWidget, QListWidgetItem, QPushButton, 
    QLabel, QProgressBar, QFileDialog, QMessageBox, 
    QToolBar, QStatusBar, QFrame, QInputDialog,
    QMenuBar, QMenu, QToolButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QImage, QAction, QKeySequence

from ui.image_viewer import DocumentViewer
from ui.text_editor import HebrewTextEditor
from ui.update_banner import UpdateBanner
from ui.theme import DARK_THEME, LIGHT_THEME
from ui.i18n import t, I18nManager, SETTINGS_PATH, get_current_language, get_app_data_dir
from core.ocr_engine import OCREngine
from core.learning_engine import LearningEngine
from core.logger import log

SESSION_PATH = os.path.join(get_app_data_dir(), "active_session.json")

def get_resource_path(rel_path: str) -> str:
    """Resolve path to resource file for both PyInstaller and source development."""
    if hasattr(sys, '_MEIPASS'):
        c1 = os.path.join(sys._MEIPASS, rel_path)
        if os.path.exists(c1):
            return c1
        c2 = os.path.join(sys._MEIPASS, os.path.basename(rel_path))
        if os.path.exists(c2):
            return c2
    if getattr(sys, 'frozen', False):
        c3 = os.path.join(os.path.dirname(sys.executable), rel_path)
        if os.path.exists(c3):
            return c3
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c4 = os.path.join(base_dir, rel_path)
    if os.path.exists(c4):
        return c4
    return rel_path


class OCRWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, ocr_engine: OCREngine, learning_engine: LearningEngine, image_path: str, rotation: int = 0):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.learning_engine = learning_engine
        self.image_path = image_path
        self.rotation = rotation

    def run(self):
        try:
            from PIL import ImageOps
            pil_img = Image.open(self.image_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            if self.rotation % 360 != 0:
                pil_img = pil_img.rotate(-self.rotation, expand=True)

            def progress_callback(cur, tot, msg):
                self.progress.emit(cur, tot, msg)

            raw_result = self.ocr_engine.recognize_page(pil_img, progress_callback=progress_callback)
            corrected_text, applied_rules = self.learning_engine.apply_corrections(raw_result["full_text"])

            final_result = {
                "raw_text": raw_result["full_text"],
                "text": corrected_text,
                "lines": raw_result["lines"],
                "corrections_applied": len(applied_rules),
                "rules_details": applied_rules
            }
            self.finished.emit(final_result)
        except Exception as e:
            self.error.emit(str(e))


class ModelPreWarmWorker(QThread):
    def __init__(self, ocr_engine: OCREngine):
        super().__init__()
        self.ocr_engine = ocr_engine

    def run(self):
        try:
            log.info("Background model pre-warming started...")
            self.ocr_engine.load_model()
            log.info("Background model pre-warming complete. Neural OCR model ready.")
        except Exception as e:
            log.debug(f"Pre-warm skipped: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.resize(1200, 780)
        self.setMinimumSize(960, 600)

        # Set Window Icon
        icon_path = get_resource_path(os.path.join("assets", "ohr_haksav.png"))
        if not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join("assets", "ohr_haksav.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Core Engines
        self.learning_engine = LearningEngine()
        self.ocr_engine = OCREngine()

        # State
        self.pages: List[Dict[str, Any]] = []
        self.current_page_idx = -1
        self.is_dark_theme = False  # Default to clean, modern Light Mode
        self._load_theme_setting()
        self.active_worker = None
        self._batch_scanning = False
        self._remote_update_data = None
        self._startup_update_worker = None

        self._init_ui()
        self._refresh_profiles_ui()
        self._retranslate_ui()
        self.apply_theme()

        self.setAcceptDrops(True)
        self._prewarm_worker = None

        # Interactive line synchronization between Viewer and Proofreading Editor
        self.viewer.line_clicked.connect(self._on_viewer_line_clicked)
        self.editor.line_focused.connect(self._on_editor_line_focused)

        # Restore previous session if present (draft protection)
        QTimer.singleShot(400, self.check_restore_previous_session)

        # Pre-warm neural vision model in background for instantaneous first scan
        QTimer.singleShot(800, self._start_model_prewarm)

        # Silent background update check after app UI loads
        QTimer.singleShot(2500, self._start_startup_update_check)

    def _init_ui(self):
        # 1. Native Windows Menu Bar
        self._create_menu_bar()

        # 2. Central Layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 6, 8, 8)
        main_layout.setSpacing(6)

        # 3. Streamlined Action Toolbar
        self._create_top_toolbar(main_layout)

        # 3.5 In-App Update Notification Banner (Hidden by default, slides down if update available)
        self.update_banner = UpdateBanner(
            on_install_clicked=self._on_banner_install_clicked,
            on_details_clicked=self._on_banner_details_clicked,
            parent=central
        )
        main_layout.addWidget(self.update_banner)

        # 4. Main 3-Pane Splitter (Sidebar | Document Viewer | Text Editor)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)

        sidebar_frame = self._create_sidebar()
        content_splitter.addWidget(sidebar_frame)

        viewer_frame = self._create_viewer_panel()
        content_splitter.addWidget(viewer_frame)

        editor_frame = self._create_editor_panel()
        content_splitter.addWidget(editor_frame)

        content_splitter.setSizes([190, 500, 500])
        main_layout.addWidget(content_splitter, 1)

        # 5. Status Bar
        self._create_status_bar(main_layout)

    def _create_menu_bar(self):
        mb = self.menuBar()

        # File Menu
        self.m_file = mb.addMenu(t("menu_file"))
        self.act_file_add = QAction(t("menu_file_add"), self)
        self.act_file_add.setShortcut(QKeySequence("Ctrl+O"))
        self.act_file_add.triggered.connect(self.attach_images_dialog)
        self.m_file.addAction(self.act_file_add)

        self.act_file_remove = QAction(t("menu_file_remove"), self)
        self.act_file_remove.setShortcut(QKeySequence("Delete"))
        self.act_file_remove.triggered.connect(self.remove_selected_page)
        self.m_file.addAction(self.act_file_remove)

        self.act_file_clear = QAction(t("menu_file_clear"), self)
        self.act_file_clear.triggered.connect(self.clear_all_pages)
        self.m_file.addAction(self.act_file_clear)

        self.m_file.addSeparator()

        self.act_file_exp_word = QAction(t("menu_file_export_word"), self)
        self.act_file_exp_word.setShortcut(QKeySequence("Ctrl+E"))
        self.act_file_exp_word.triggered.connect(self.export_to_docx_dialog)
        self.m_file.addAction(self.act_file_exp_word)

        self.act_file_exp_txt = QAction(t("menu_file_export_txt"), self)
        self.act_file_exp_txt.setShortcut(QKeySequence("Ctrl+S"))
        self.act_file_exp_txt.triggered.connect(self.export_to_txt_dialog)
        self.m_file.addAction(self.act_file_exp_txt)

        self.m_file.addSeparator()

        self.act_file_exit = QAction(t("menu_file_exit"), self)
        self.act_file_exit.setShortcut(QKeySequence("Alt+F4"))
        self.act_file_exit.triggered.connect(self.close)
        self.m_file.addAction(self.act_file_exit)

        # Scan & OCR Menu
        self.m_scan = mb.addMenu(t("menu_scan"))
        self.act_scan_curr = QAction(t("menu_scan_current"), self)
        self.act_scan_curr.setShortcut(QKeySequence("F5"))
        self.act_scan_curr.triggered.connect(self.scan_current_page)
        self.m_scan.addAction(self.act_scan_curr)

        self.act_scan_all = QAction(t("menu_scan_all"), self)
        self.act_scan_all.setShortcut(QKeySequence("Shift+F5"))
        self.act_scan_all.triggered.connect(self.scan_all_pages)
        self.m_scan.addAction(self.act_scan_all)

        self.m_scan.addSeparator()

        self.act_scan_contrast = QAction(t("menu_scan_enhance"), self)
        self.act_scan_contrast.setShortcut(QKeySequence("Ctrl+I"))
        self.act_scan_contrast.triggered.connect(self.toggle_image_contrast)
        self.m_scan.addAction(self.act_scan_contrast)

        # Learning & Profiles Menu
        self.m_learn = mb.addMenu(t("menu_learning"))
        self.act_learn_save = QAction(t("menu_learning_save"), self)
        self.act_learn_save.setShortcut(QKeySequence("Ctrl+L"))
        self.act_learn_save.triggered.connect(self.learn_current_corrections)
        self.m_learn.addAction(self.act_learn_save)

        self.act_learn_studio = QAction(t("menu_learning_studio"), self)
        self.act_learn_studio.setShortcut(QKeySequence("Ctrl+M"))
        self.act_learn_studio.triggered.connect(self.open_dictionary_manager)
        self.m_learn.addAction(self.act_learn_studio)

        self.act_learn_new_prof = QAction(t("menu_learning_new_profile"), self)
        self.act_learn_new_prof.triggered.connect(self._quick_new_profile)
        self.m_learn.addAction(self.act_learn_new_prof)

        # View Menu
        self.m_view = mb.addMenu(t("menu_view"))
        self.act_view_cw = QAction(t("menu_view_rotate_cw"), self)
        self.act_view_cw.setShortcut(QKeySequence("Ctrl+]"))
        self.act_view_cw.triggered.connect(self.rotate_image_cw)
        self.m_view.addAction(self.act_view_cw)

        self.act_view_ccw = QAction(t("menu_view_rotate_ccw"), self)
        self.act_view_ccw.setShortcut(QKeySequence("Ctrl+["))
        self.act_view_ccw.triggered.connect(self.rotate_image_ccw)
        self.m_view.addAction(self.act_view_ccw)

        self.m_view.addSeparator()

        self.act_view_zi = QAction(t("menu_view_zoom_in"), self)
        self.act_view_zi.setShortcut(QKeySequence("Ctrl++"))
        self.act_view_zi.triggered.connect(lambda: self.viewer.zoom_in())
        self.m_view.addAction(self.act_view_zi)

        self.act_view_zo = QAction(t("menu_view_zoom_out"), self)
        self.act_view_zo.setShortcut(QKeySequence("Ctrl+-"))
        self.act_view_zo.triggered.connect(lambda: self.viewer.zoom_out())
        self.m_view.addAction(self.act_view_zo)

        self.act_view_fit = QAction(t("menu_view_fit"), self)
        self.act_view_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.act_view_fit.triggered.connect(lambda: self.viewer.fit_to_window())
        self.m_view.addAction(self.act_view_fit)

        self.m_view.addSeparator()

        self.act_view_theme = QAction(t("menu_view_theme"), self)
        self.act_view_theme.setShortcut(QKeySequence("Ctrl+T"))
        self.act_view_theme.triggered.connect(self.toggle_theme)
        self.m_view.addAction(self.act_view_theme)

        self.act_view_stats = QAction(t("menu_view_stats"), self)
        self.act_view_stats.setCheckable(True)
        self.act_view_stats.setChecked(False)
        self.act_view_stats.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_view_stats.toggled.connect(self.toggle_stats_bar)
        self.m_view.addAction(self.act_view_stats)

        # Language Menu
        self.m_lang = mb.addMenu(t("menu_language"))
        self.act_lang_en = QAction(t("menu_lang_en"), self)
        self.act_lang_en.triggered.connect(lambda: self._set_lang("en"))
        self.m_lang.addAction(self.act_lang_en)

        self.act_lang_he = QAction(t("menu_lang_he"), self)
        self.act_lang_he.triggered.connect(lambda: self._set_lang("he"))
        self.m_lang.addAction(self.act_lang_he)

        # Help Menu
        self.m_help = mb.addMenu(t("menu_help"))
        self.act_help_guide = QAction(t("menu_help_guide"), self)
        self.act_help_guide.setShortcut(QKeySequence("F1"))
        self.act_help_guide.triggered.connect(self.open_help_dialog)
        self.m_help.addAction(self.act_help_guide)

        self.act_help_updates = QAction(t("menu_help_check_updates"), self)
        self.act_help_updates.setShortcut(QKeySequence("Ctrl+U"))
        self.act_help_updates.triggered.connect(self.open_update_dialog)
        self.m_help.addAction(self.act_help_updates)

        self.m_help.addSeparator()

        self.act_help_about = QAction(t("menu_help_about"), self)
        self.act_help_about.triggered.connect(self.open_about_dialog)
        self.m_help.addAction(self.act_help_about)

    def _set_lang(self, lang: str):
        I18nManager.instance().set_language(lang)
        self._retranslate_ui()

    def _create_top_toolbar(self, parent_layout):
        bar = QHBoxLayout()
        bar.setSpacing(6)

        # 1. Brand Logo & Title Hub (immune to clipping with Fixed policy)
        self.brand_widget = QWidget()
        brand_box = QHBoxLayout(self.brand_widget)
        brand_box.setContentsMargins(0, 0, 4, 0)
        brand_box.setSpacing(6)

        logo_path = get_resource_path(os.path.join("assets", "ohr_haksav.png"))
        if os.path.exists(logo_path):
            self.lbl_logo = QLabel()
            pix = QIcon(logo_path).pixmap(26, 26)
            self.lbl_logo.setPixmap(pix)
            self.lbl_logo.setFixedSize(26, 26)
            brand_box.addWidget(self.lbl_logo)

        self.lbl_brand = QLabel(f"<b>{t('brand_name')}</b>")
        self.lbl_brand.setStyleSheet("font-size: 15px; color: #89b4fa;")
        self.lbl_brand.setMinimumWidth(100)
        brand_box.addWidget(self.lbl_brand)

        self.brand_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bar.addWidget(self.brand_widget)

        # Separator
        self.sep_brand = QFrame()
        self.sep_brand.setFrameShape(QFrame.Shape.VLine)
        self.sep_brand.setStyleSheet("color: #313244;")
        bar.addWidget(self.sep_brand)

        # 2. Add Pages Button
        self.btn_attach = QPushButton(f"📁 {t('btn_add_pages_short')}")
        self.btn_attach.setObjectName("btn_primary")
        self.btn_attach.setToolTip(t("btn_attach_tooltip"))
        self.btn_attach.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_attach.clicked.connect(self.attach_images_dialog)
        bar.addWidget(self.btn_attach)

        # 3. Stacked Scan Dropdown Button
        self.btn_scan = QToolButton()
        self.btn_scan.setText(f"⚡ {t('btn_scan_menu')}")
        self.btn_scan.setObjectName("btn_success")
        self.btn_scan.setToolTip(t("btn_scan_tooltip"))
        self.btn_scan.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_scan.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_scan.clicked.connect(self.scan_current_page)

        self.scan_menu = QMenu(self.btn_scan)
        self.act_scan_dropdown_curr = self.scan_menu.addAction(t("btn_scan_current_opt"))
        self.act_scan_dropdown_curr.triggered.connect(self.scan_current_page)
        self.act_scan_dropdown_all = self.scan_menu.addAction(t("btn_scan_all_opt"))
        self.act_scan_dropdown_all.triggered.connect(self.scan_all_pages)
        self.btn_scan.setMenu(self.scan_menu)
        bar.addWidget(self.btn_scan)

        # 4. Save & Learn Button
        self.btn_learn = QPushButton(f"💾 {t('btn_learn_short')}")
        self.btn_learn.setToolTip(t("btn_learn_tooltip"))
        self.btn_learn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_learn.clicked.connect(self.learn_current_corrections)
        bar.addWidget(self.btn_learn)

        # 5. Stacked Export Dropdown Button
        self.btn_export = QToolButton()
        self.btn_export.setText(f"📄 {t('btn_export_menu')}")
        self.btn_export.setToolTip(t("btn_export_tooltip"))
        self.btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_export.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        
        self.export_menu = QMenu(self.btn_export)
        self.act_exp_dropdown_docx = self.export_menu.addAction(t("btn_export_word_opt"))
        self.act_exp_dropdown_docx.triggered.connect(self.export_to_docx_dialog)
        self.act_exp_dropdown_txt = self.export_menu.addAction(t("btn_export_txt_opt"))
        self.act_exp_dropdown_txt.triggered.connect(self.export_to_txt_dialog)
        self.btn_export.setMenu(self.export_menu)
        bar.addWidget(self.btn_export)

        # Spacer pushes utilities to right
        bar.addStretch()

        # 6. Unified Profile Dropdown (Stacked Selection + Management)
        self.btn_profile = QToolButton()
        self.btn_profile.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_profile.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.profile_menu = QMenu(self.btn_profile)
        self.btn_profile.setMenu(self.profile_menu)
        bar.addWidget(self.btn_profile)

        # 7. Memory Studio Button
        self.btn_dict = QPushButton(f"🧠 {t('btn_memory_short')}")
        self.btn_dict.setToolTip(t("btn_memory_tooltip"))
        self.btn_dict.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_dict.clicked.connect(self.open_dictionary_manager)
        bar.addWidget(self.btn_dict)

        # 8. Theme Toggle Button
        self.btn_theme = QPushButton("🌓")
        self.btn_theme.setToolTip(t("btn_theme_tooltip"))
        self.btn_theme.setFixedSize(28, 26)
        self.btn_theme.setStyleSheet("padding: 0px; font-size: 13px;")
        self.btn_theme.clicked.connect(self.toggle_theme)
        bar.addWidget(self.btn_theme)

        # 9. Language Pill Button
        self.btn_lang = QPushButton(t("btn_lang"))
        self.btn_lang.setToolTip(t("btn_lang_tooltip"))
        self.btn_lang.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_lang.clicked.connect(self.toggle_language)
        bar.addWidget(self.btn_lang)

        # 10. Interactive User Guide & Tutorial Button
        self.btn_help = QPushButton("❓")
        self.btn_help.setFixedSize(26, 26)
        self.btn_help.setStyleSheet("padding: 0px; font-size: 13px; font-weight: bold;")
        self.btn_help.setToolTip(t("btn_help_tooltip"))
        self.btn_help.clicked.connect(self.open_help_dialog)
        bar.addWidget(self.btn_help)

        # 11. Compact About Button
        self.btn_about = QPushButton("ℹ")
        self.btn_about.setFixedSize(26, 26)
        self.btn_about.setStyleSheet("padding: 0px; font-size: 13px; font-weight: bold;")
        self.btn_about.setToolTip(t("btn_about_tooltip"))
        self.btn_about.clicked.connect(self.open_about_dialog)
        bar.addWidget(self.btn_about)

        parent_layout.addLayout(bar)

    def _create_sidebar(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        self.lbl_pages = QLabel(t("sidebar_title"))
        self.lbl_pages.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 12px;")
        hdr.addWidget(self.lbl_pages)
        hdr.addStretch()

        self.btn_add_page = QPushButton(t("btn_add_short"))
        self.btn_add_page.setStyleSheet("padding: 2px 8px; font-size: 11px; font-weight: bold;")
        self.btn_add_page.setToolTip(t("sidebar_add_tooltip"))
        self.btn_add_page.clicked.connect(self.attach_images_dialog)
        hdr.addWidget(self.btn_add_page)

        self.btn_remove_page = QPushButton(t("btn_del_short"))
        self.btn_remove_page.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_remove_page.setToolTip(t("sidebar_remove_tooltip"))
        self.btn_remove_page.clicked.connect(self.remove_selected_page)
        hdr.addWidget(self.btn_remove_page)
        layout.addLayout(hdr)

        self.list_pages = QListWidget()
        self.list_pages.currentRowChanged.connect(self.on_page_selected)
        layout.addWidget(self.list_pages)

        return frame

    def _create_viewer_panel(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        v_bar = QHBoxLayout()
        v_bar.setSpacing(4)

        self.lbl_viewer = QLabel(t("viewer_title"))
        self.lbl_viewer.setStyleSheet("font-weight: bold; color: #a6adc8; font-size: 12px;")
        v_bar.addWidget(self.lbl_viewer)
        v_bar.addStretch()

        self.btn_cw = QPushButton("↻ 90°")
        self.btn_cw.setStyleSheet("padding: 3px 8px; font-size: 12px;")
        self.btn_cw.setToolTip(t("btn_cw_tooltip"))
        self.btn_cw.clicked.connect(self.rotate_image_cw)
        v_bar.addWidget(self.btn_cw)

        self.btn_ccw = QPushButton("↺ 90°")
        self.btn_ccw.setStyleSheet("padding: 3px 8px; font-size: 12px;")
        self.btn_ccw.setToolTip(t("btn_ccw_tooltip"))
        self.btn_ccw.clicked.connect(self.rotate_image_ccw)
        v_bar.addWidget(self.btn_ccw)

        self.btn_contrast = QPushButton(t("btn_contrast"))
        self.btn_contrast.setStyleSheet("padding: 3px 8px; font-size: 12px;")
        self.btn_contrast.setToolTip(t("btn_contrast_tooltip"))
        self.btn_contrast.clicked.connect(self.toggle_image_contrast)
        v_bar.addWidget(self.btn_contrast)

        self.btn_fit = QPushButton(t("btn_fit"))
        self.btn_fit.setStyleSheet("padding: 3px 8px; font-size: 12px;")
        self.btn_fit.setToolTip(t("btn_fit_tooltip"))
        self.btn_fit.clicked.connect(lambda: self.viewer.fit_to_window())
        v_bar.addWidget(self.btn_fit)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setStyleSheet("padding: 2px 8px; font-size: 13px; font-weight: bold;")
        self.btn_zoom_in.setToolTip(t("btn_zoom_in_tooltip"))
        self.btn_zoom_in.clicked.connect(lambda: self.viewer.zoom_in())
        v_bar.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setStyleSheet("padding: 2px 8px; font-size: 13px; font-weight: bold;")
        self.btn_zoom_out.setToolTip(t("btn_zoom_out_tooltip"))
        self.btn_zoom_out.clicked.connect(lambda: self.viewer.zoom_out())
        v_bar.addWidget(self.btn_zoom_out)

        layout.addLayout(v_bar)

        self.viewer = DocumentViewer()
        layout.addWidget(self.viewer)

        return frame

    def _create_editor_panel(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        self.lbl_editor = QLabel(t("editor_title"))
        self.lbl_editor.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 12px;")
        hdr.addWidget(self.lbl_editor)
        hdr.addStretch()

        self.lbl_learned_badge = QLabel("")
        self.lbl_learned_badge.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 11px;")
        hdr.addWidget(self.lbl_learned_badge)

        layout.addLayout(hdr)

        self.editor = HebrewTextEditor()
        self.editor.text_changed.connect(self.on_text_edited)
        layout.addWidget(self.editor)

        return frame

    def _create_status_bar(self, parent_layout):
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(280)
        bar.addWidget(self.progress_bar)

        self.lbl_status = QLabel(t("status_ready"))
        self.lbl_status.setStyleSheet("color: #a6adc8; font-size: 12px;")
        bar.addWidget(self.lbl_status)

        bar.addStretch()

        self.lbl_learned_counter = QLabel("")
        self.lbl_learned_counter.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 11px;")
        bar.addWidget(self.lbl_learned_counter)
        self.update_learned_count_badge()

        parent_layout.addLayout(bar)

    def toggle_language(self):
        I18nManager.instance().toggle_language()
        self._retranslate_ui()

    def _retranslate_ui(self):
        is_hebrew = (I18nManager.instance().current_lang == "he")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_hebrew else Qt.LayoutDirection.LeftToRight)

        self.setWindowTitle(t("app_title"))
        self.lbl_brand.setText(f"<b>{t('brand_name')}</b>")

        # Menu bar
        self.m_file.setTitle(t("menu_file"))
        self.act_file_add.setText(t("menu_file_add"))
        self.act_file_remove.setText(t("menu_file_remove"))
        self.act_file_clear.setText(t("menu_file_clear"))
        self.act_file_exp_word.setText(t("menu_file_export_word"))
        self.act_file_exp_txt.setText(t("menu_file_export_txt"))
        self.act_file_exit.setText(t("menu_file_exit"))

        self.m_scan.setTitle(t("menu_scan"))
        self.act_scan_curr.setText(t("menu_scan_current"))
        self.act_scan_all.setText(t("menu_scan_all"))
        self.act_scan_contrast.setText(t("menu_scan_enhance"))

        self.m_learn.setTitle(t("menu_learning"))
        self.act_learn_save.setText(t("menu_learning_save"))
        self.act_learn_studio.setText(t("menu_learning_studio"))
        self.act_learn_new_prof.setText(t("menu_learning_new_profile"))

        self.m_view.setTitle(t("menu_view"))
        self.act_view_cw.setText(t("menu_view_rotate_cw"))
        self.act_view_ccw.setText(t("menu_view_rotate_ccw"))
        self.act_view_zi.setText(t("menu_view_zoom_in"))
        self.act_view_zo.setText(t("menu_view_zoom_out"))
        self.act_view_fit.setText(t("menu_view_fit"))
        self.act_view_theme.setText(t("menu_view_theme"))
        if hasattr(self, "act_view_stats"):
            self.act_view_stats.setText(t("menu_view_stats"))

        self.m_lang.setTitle(t("menu_language"))
        self.act_lang_en.setText(t("menu_lang_en"))
        self.act_lang_he.setText(t("menu_lang_he"))

        self.m_help.setTitle(t("menu_help"))
        if hasattr(self, "act_help_guide"):
            self.act_help_guide.setText(t("menu_help_guide"))
        if getattr(self, "_remote_update_data", None) and self._remote_update_data.get("version"):
            v = self._remote_update_data.get("version")
            self.act_help_updates.setText(f"{t('menu_help_check_updates')} (v{v} {t('status_update_available')})")
        else:
            self.act_help_updates.setText(t("menu_help_check_updates"))
        self.act_help_about.setText(t("menu_help_about"))
        if hasattr(self, "btn_help"):
            self.btn_help.setToolTip(t("btn_help_tooltip"))

        if hasattr(self, "update_banner") and self.update_banner.isVisible() and getattr(self, "_remote_update_data", None):
            self.update_banner.show_update(
                self._remote_update_data.get("version", ""),
                self._remote_update_data,
                lang=get_current_language()
            )

        # Action Toolbar
        self.btn_attach.setText(f"📁 {t('btn_add_pages_short')}")
        self.btn_attach.setToolTip("""<b>📁 Add Pages (Ctrl+O)</b><br>Step 1: Attach photos or scans of handwritten Torah notes from your computer or phone.""")

        self.btn_scan.setText(f"⚡ {t('btn_scan_menu')}")
        self.btn_scan.setToolTip("""<b>⚡ Scan Page (F5)</b><br>Step 2: Run offline neural handwriting recognition on the active notebook page.""")
        self.act_scan_dropdown_curr.setText(t("btn_scan_current_opt"))
        self.act_scan_dropdown_all.setText(t("btn_scan_all_opt"))

        self.btn_learn.setText(f"🎓 {t('btn_learn_short')}")
        self.btn_learn.setMinimumWidth(self.btn_learn.fontMetrics().horizontalAdvance(self.btn_learn.text()) + 32)
        self.btn_learn.setToolTip("""<b>🎓 Save & Learn Mistakes (Ctrl+L)</b><br>Step 3: Saves your proofreading fixes into the handwriting memory bank so future scans automatically correct these words!""")

        self.btn_export.setText(f"📄 {t('btn_export_menu')}")
        self.btn_export.setToolTip(t("btn_export_tooltip"))
        self.act_exp_dropdown_docx.setText(t("btn_export_word_opt"))
        self.act_exp_dropdown_txt.setText(t("btn_export_txt_opt"))

        self.btn_dict.setText(f"🧠 {t('btn_memory_short')}")
        self.btn_dict.setToolTip(t("btn_memory_tooltip"))

        self.btn_theme.setToolTip(t("btn_theme_tooltip"))
        self.btn_lang.setText(t("btn_lang"))
        self.btn_lang.setToolTip(t("btn_lang_tooltip"))
        self.btn_about.setToolTip(t("btn_about_tooltip"))

        # Refresh dynamic profile dropdown text
        self._refresh_profiles_ui()
        self._update_learn_button_status()

        # Sidebar
        self.lbl_pages.setText(t("sidebar_title"))
        self.btn_add_page.setText(t("btn_add_short"))
        self.btn_add_page.setToolTip(t("sidebar_add_tooltip"))
        self.btn_remove_page.setText(t("btn_del_short"))
        self.btn_remove_page.setToolTip(t("sidebar_remove_tooltip"))

        # Viewer
        self.lbl_viewer.setText(t("viewer_title"))
        self.btn_cw.setToolTip(t("btn_cw_tooltip"))
        self.btn_ccw.setToolTip(t("btn_ccw_tooltip"))
        self.btn_contrast.setText(t("btn_contrast"))
        self.btn_contrast.setToolTip(t("btn_contrast_tooltip"))
        self.btn_fit.setText(t("btn_fit"))
        self.btn_fit.setToolTip(t("btn_fit_tooltip"))
        self.btn_zoom_in.setToolTip(t("btn_zoom_in_tooltip"))
        self.btn_zoom_out.setToolTip(t("btn_zoom_out_tooltip"))

        # Editor
        self.lbl_editor.setText(t("editor_title"))
        self.editor.retranslate_ui()

        # Status
        self.lbl_status.setText(t("status_ready"))
        self.update_learned_count_badge()

    # --- Drag & Drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp', '.pdf')
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isfile(p) and p.lower().endswith(valid_exts):
                paths.append(p)
            elif os.path.isdir(p):
                for root, _, fnames in os.walk(p):
                    for fn in sorted(fnames):
                        if fn.lower().endswith(valid_exts):
                            paths.append(os.path.join(root, fn))
        if paths:
            self.add_images(paths)
            event.acceptProposedAction()

    def attach_images_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("sidebar_add_tooltip"),
            "",
            "Torah Notebook Documents (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff *.webp);;PDF Documents (*.pdf);;Images (*.png *.jpg *.jpeg);;All Files (*)"
        )
        if files:
            self.add_images(files)

    def add_images(self, file_paths: List[str]):
        from PIL import ImageOps
        initial_count = len(self.pages)
        log.info(f"Adding {len(file_paths)} item(s) to notebook session...")

        expanded_paths = []
        for path in file_paths:
            if path.lower().endswith(".pdf"):
                try:
                    import fitz
                    doc = fitz.open(path)
                    base_name = os.path.splitext(os.path.basename(path))[0]
                    cache_dir = os.path.join(get_app_data_dir(), "pdf_cache", base_name)
                    os.makedirs(cache_dir, exist_ok=True)
                    log.info(f"Extracting {len(doc)} page(s) from PDF '{os.path.basename(path)}'...")
                    for page_idx in range(len(doc)):
                        page = doc[page_idx]
                        pix = page.get_pixmap(dpi=200)
                        out_img = os.path.join(cache_dir, f"{base_name}_p{page_idx + 1:02d}.png")
                        pix.save(out_img)
                        expanded_paths.append(out_img)
                except Exception as e:
                    log.error(f"Error rendering PDF '{path}': {e}")
                    QMessageBox.warning(self, "PDF Import Warning", f"Could not extract pages from {os.path.basename(path)}:\n{e}")
            else:
                expanded_paths.append(path)

        for path in expanded_paths:
            fname = os.path.basename(path)
            init_rot = 0
            try:
                with Image.open(path) as im:
                    im_trans = ImageOps.exif_transpose(im)
                    w, h = im_trans.size
                    if w > h * 1.15:
                        import numpy as np
                        import cv2
                        small = im_trans.convert("L").resize((300, 200))
                        arr_sm = np.array(small)
                        sob_y = cv2.Sobel(arr_sm, cv2.CV_64F, 0, 1, ksize=3)
                        sob_x = cv2.Sobel(arr_sm, cv2.CV_64F, 1, 0, ksize=3)
                        if float(np.mean(np.abs(sob_x))) > float(np.mean(np.abs(sob_y))) * 1.08:
                            init_rot = 90
                            log.info(f"Auto-orient on attach: {fname} is sideways ({w}x{h}). Default rotation set to 90° CW.")
            except Exception:
                pass

            self.pages.append({
                "path": path,
                "filename": fname,
                "rotation": init_rot,
                "raw_text": "",
                "edited_text": "",
                "last_learned_text": "",
                "status": t("page_status_ready"),
                "lines_boxes": []
            })

            item = QListWidgetItem()
            item.setText(f"{fname}\n⚪ {t('page_status_ready')}")
            try:
                pix = QPixmap(path)
                if not pix.isNull():
                    thumb = pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    item.setIcon(QIcon(thumb))
            except Exception:
                pass
            self.list_pages.addItem(item)

        if initial_count == 0 and len(self.pages) > 0:
            self.list_pages.setCurrentRow(0)

        self.lbl_status.setText(f"{len(self.pages)} pages attached. Ready to scan.")
        self._update_page_list_items()
        self.save_session_state()

    def remove_selected_page(self):
        row = self.list_pages.currentRow()
        if row >= 0:
            del self.pages[row]
            self.list_pages.takeItem(row)
            if not self.pages:
                self.current_page_idx = -1
                self.editor.set_text("", "")
                self.viewer.scene.clear()
                self.lbl_status.setText(t("status_ready"))
            self._update_learn_button_status()
            self._update_page_list_items()
            self.save_session_state()

    def clear_all_pages(self):
        if not self.pages:
            return
        res = QMessageBox.question(
            self, "Clear All Pages", "Are you sure you want to remove all attached pages from this session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.pages.clear()
            self.list_pages.clear()
            self.current_page_idx = -1
            self.viewer.scene.clear()
            self.editor.set_text("", "")
            self.lbl_status.setText(t("status_ready"))
            self.clear_saved_session()
            self._update_learn_button_status()

    def on_page_selected(self, row: int):
        if row < 0 or row >= len(self.pages):
            return

        # Save previous edits before switching
        if self.current_page_idx >= 0 and self.current_page_idx < len(self.pages) and self.current_page_idx != row:
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        self.current_page_idx = row
        pdata = self.pages[row]

        # Load image into viewer
        try:
            from PIL import ImageOps
            pil_img = ImageOps.exif_transpose(Image.open(pdata["path"]))
            self.viewer.load_image(pil_img, rotation=pdata["rotation"])
        except Exception as e:
            self.lbl_status.setText(f"Error loading image: {e}")

        # Load bounding boxes into viewer if already scanned
        self.viewer.set_bounding_boxes(pdata.get("lines_boxes", []))

        # Load text into editor
        self.editor.set_text(pdata["edited_text"], pdata["raw_text"])
        self._update_learn_button_status()
        self.save_session_state()

    def on_text_edited(self):
        if self.current_page_idx >= 0 and self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()
        self._update_learn_button_status()
        self.save_session_state()

    def rotate_image_cw(self):
        if self.current_page_idx >= 0 and self.current_page_idx < len(self.pages):
            p = self.pages[self.current_page_idx]
            p["rotation"] = (p["rotation"] + 90) % 360
            self.viewer.rotate_cw()

    def rotate_image_ccw(self):
        if self.current_page_idx >= 0 and self.current_page_idx < len(self.pages):
            p = self.pages[self.current_page_idx]
            p["rotation"] = (p["rotation"] - 90) % 360
            self.viewer.rotate_ccw()

    def toggle_image_contrast(self):
        self.viewer.toggle_contrast()

    # --- OCR Execution ---
    def scan_current_page(self):
        if self.current_page_idx < 0 or self.current_page_idx >= len(self.pages):
            QMessageBox.information(self, "Notice", "Please attach and select an image to scan first.")
            return

        pdata = self.pages[self.current_page_idx]
        self.btn_scan.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"Scanning page {self.current_page_idx + 1} ({pdata['filename']})...")
        log.info(f"Scanning page {self.current_page_idx + 1}/{len(self.pages)}: {pdata['filename']} (rotation={pdata['rotation']})")

        self.active_worker = OCRWorker(
            self.ocr_engine, self.learning_engine, pdata["path"], pdata["rotation"]
        )
        self.active_worker.progress.connect(self._on_ocr_progress)
        self.active_worker.finished.connect(lambda res: self._on_ocr_finished(self.current_page_idx, res))
        self.active_worker.error.connect(self._on_ocr_error)
        self.active_worker.start()

    def _on_ocr_progress(self, cur, tot, msg):
        pct = int((cur / max(1, tot)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"{msg} ({cur}/{tot})")

    def _on_ocr_finished(self, page_idx: int, res: dict):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)

        if 0 <= page_idx < len(self.pages):
            p = self.pages[page_idx]
            p["raw_text"] = res["raw_text"]
            p["edited_text"] = res["text"]
            p["last_learned_text"] = res["text"]
            p["status"] = t("page_status_scanned")
            p["lines_boxes"] = res["lines"]

            item = self.list_pages.item(page_idx)
            if item:
                item.setText(f"{p['filename']}\n{t('page_status_scanned')}")

            if page_idx == self.current_page_idx:
                self.editor.set_text(res["text"], res["raw_text"])
                self.viewer.set_bounding_boxes(res.get("lines", []))
                if res["corrections_applied"] > 0:
                    self.lbl_learned_badge.setText(f"Applied {res['corrections_applied']} automatic learned corrections ✓")

            self._update_learn_button_status()
            self._update_page_list_items()
            self.save_session_state()
            self.lbl_status.setText(f"Page {page_idx + 1} scanned successfully ({len(res['lines'])} lines, applied {res['corrections_applied']} learned rules)!")
            log.info(f"Page {page_idx + 1} scanned successfully: {len(res['lines'])} lines, {res['corrections_applied']} corrections.")

        # If batch scanning is active, advance to next unscanned page!
        if getattr(self, "_batch_scanning", False):
            QTimer.singleShot(200, self._scan_next_batch_page)

    def _on_ocr_error(self, err_msg: str):
        self._batch_scanning = False
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        log.error(f"OCR Error: {err_msg}")
        QMessageBox.critical(self, "OCR Error", f"An error occurred during OCR recognition:\n{err_msg}")
        self.lbl_status.setText("Scan failed.")

    def scan_all_pages(self):
        if not self.pages:
            QMessageBox.information(self, "Notice", "Please attach images to scan first.")
            return

        unscanned = [i for i, p in enumerate(self.pages) if p["status"] != t("page_status_scanned")]
        if not unscanned:
            QMessageBox.information(self, "Complete", "All pages in notebook have already been scanned!")
            return

        self._batch_scanning = True
        log.info(f"Initiated 'Scan All Pages' batch mode for {len(unscanned)} unscanned page(s)...")
        self._scan_next_batch_page()

    def _scan_next_batch_page(self):
        if not getattr(self, "_batch_scanning", False):
            return

        for i, p in enumerate(self.pages):
            if p["status"] != t("page_status_scanned"):
                self.list_pages.setCurrentRow(i)
                self.scan_current_page()
                return

        # Loop completed: all pages have been scanned!
        self._batch_scanning = False
        log.info(f"Batch scan completed: all {len(self.pages)} pages scanned successfully.")
        self.lbl_status.setText(f"Batch scan complete: All {len(self.pages)} pages scanned successfully ✓")
        QMessageBox.information(
            self,
            "Batch Scan Complete",
            f"All {len(self.pages)} pages in the notebook have been transcribed successfully!"
        )

    def get_pages_with_unlearned_edits(self) -> List[Tuple[int, dict]]:
        """
        Returns list of (page_index, page_data) for all pages that have
        proofreading edits differing from their last learned/raw text.
        """
        if 0 <= self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        pending = []
        for idx, p in enumerate(self.pages):
            raw = p.get("raw_text", "").strip()
            edited = p.get("edited_text", "").strip()
            last_learned = p.get("last_learned_text", raw).strip()
            if raw and edited and edited != last_learned:
                pending.append((idx, p))
        return pending

    def _update_learn_button_status(self):
        """
        Updates the 'Save & Learn Mistakes' toolbar button appearance and tooltip
        based on whether there are pending unlearned edits across any attached pages.
        """
        if not hasattr(self, "btn_learn"):
            return

        pending = self.get_pages_with_unlearned_edits()
        if pending:
            count = len(pending)
            pages_list = ", ".join(str(idx + 1) for idx, _ in pending)
            if count == 1:
                self.btn_learn.setText(f"💾 {t('btn_learn_pending_single', page=pending[0][0] + 1)}")
            else:
                self.btn_learn.setText(f"💾 {t('btn_learn_pending_multi', count=count)}")

            self.btn_learn.setObjectName("btn_warning")
            self.btn_learn.setToolTip(t("btn_learn_pending_tooltip", pages=pages_list))
            self.btn_learn.style().unpolish(self.btn_learn)
            self.btn_learn.style().polish(self.btn_learn)
        else:
            self.btn_learn.setText(f"🎓 {t('btn_learn_short')}")
            self.btn_learn.setObjectName("")
            self.btn_learn.setToolTip("""<b>🎓 Save & Learn Mistakes (Ctrl+L)</b><br>Step 3: Saves your proofreading fixes into the handwriting memory bank so future scans automatically correct these words!""")
            self.btn_learn.style().unpolish(self.btn_learn)
            self.btn_learn.style().polish(self.btn_learn)

    def learn_current_corrections(self):
        """Action handler for 'Save & Learn Mistakes' (Ctrl+L or Toolbar Button)."""
        self.learn_all_corrections(silent=False)

    def learn_all_corrections(self, silent: bool = False) -> int:
        """
        Learns corrections across all pages with pending proofreading edits into the ACTIVE profile.
        Returns the total count of newly learned rules.
        """
        if 0 <= self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        pending = self.get_pages_with_unlearned_edits()

        if not pending:
            if 0 <= self.current_page_idx < len(self.pages):
                p = self.pages[self.current_page_idx]
                raw = p.get("raw_text", "").strip()
                if not raw:
                    if not silent:
                        QMessageBox.information(self, t("notice_title"), t("notice_page_not_scanned"))
                    return 0
            if not silent:
                QMessageBox.information(self, t("learn_none_title"), t("learn_none_msg"))
            return 0

        all_learned = []
        pages_learned = []

        for idx, p in pending:
            raw = p.get("raw_text", "")
            edited = p.get("edited_text", "")
            learned = self.learning_engine.learn_from_corrections(raw, edited, p.get("filename", ""))
            p["last_learned_text"] = edited
            if learned:
                all_learned.extend(learned)
                pages_learned.append(idx + 1)
            else:
                p["last_learned_text"] = edited

        self.update_learned_count_badge()
        self._update_learn_button_status()

        log.info(f"Learned {len(all_learned)} rules across pages {pages_learned} into profile '{self.learning_engine.get_active_profile_name()}'.")

        if not silent:
            if all_learned:
                ex_str = ""
                for raw, corr in all_learned[:5]:
                    ex_str += f" • '{raw}' ➔ '{corr}'\n"
                if len(all_learned) > 5:
                    ex_str += f"... and {len(all_learned) - 5} more corrections.\n"

                pages_str = ", ".join(str(pn) for pn in pages_learned)
                msg = t(
                    "learn_success_msg_batch",
                    count=len(all_learned),
                    pages=pages_str,
                    profile=self.learning_engine.get_active_profile_name(),
                    examples=ex_str
                )
                QMessageBox.information(self, t("learn_success_title"), msg)
            else:
                QMessageBox.information(self, t("learn_none_title"), t("learn_none_msg"))

        return len(all_learned)

    def _refresh_profiles_ui(self):
        profiles = self.learning_engine.list_profiles()
        active_pid = self.learning_engine.get_active_profile_id()
        active_pname = self.learning_engine.get_active_profile_name()
        active_count = 0

        self.profile_menu.clear()

        for p in profiles:
            is_active = (p["id"] == active_pid)
            if is_active:
                active_count = p["rule_count"]
            prefix = "✓ " if is_active else "   "
            act = self.profile_menu.addAction(f"{prefix}{p['name']} ({p['rule_count']} rules)")
            act.triggered.connect(lambda checked, pid=p["id"]: self._switch_profile(pid))

        self.profile_menu.addSeparator()

        act_new = self.profile_menu.addAction("➕ " + t("dict_btn_new_prof"))
        act_new.triggered.connect(self._quick_new_profile)

        act_studio = self.profile_menu.addAction("🧠 " + t("btn_memory_tooltip"))
        act_studio.triggered.connect(self.open_dictionary_manager)

        display_name = active_pname
        if len(display_name) > 16:
            display_name = display_name[:14] + "…"
        self.btn_profile.setText(f"👤 {display_name} ({active_count}) ▾")
        self.btn_profile.setToolTip(f"Active Handwriting Profile: {active_pname}\nClick to switch writer or manage rules.")

    def _switch_profile(self, pid: str):
        if pid != self.learning_engine.get_active_profile_id():
            self.learning_engine.set_active_profile(pid)
            self._refresh_profiles_ui()
            self.update_learned_count_badge()
            self.lbl_status.setText(t("status_switched_profile", name=self.learning_engine.get_active_profile_name()))

    def _quick_new_profile(self):
        name, ok = QInputDialog.getText(self, t("btn_new_profile_tooltip"), "Enter new profile name:")
        if ok and name.strip():
            try:
                pid = self.learning_engine.create_profile(name.strip())
                self.learning_engine.set_active_profile(pid)
                self._refresh_profiles_ui()
                self.update_learned_count_badge()
                self.lbl_status.setText(t("status_created_profile", name=name.strip()))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create profile: {str(e)}")

    def update_learned_count_badge(self):
        rules = self.learning_engine.get_all_replacements(active_only=True)
        enabled_count = len(self.learning_engine.get_enabled_profile_ids())
        stack_info = t("status_stack_info", count=enabled_count) if enabled_count > 1 else ""
        self.lbl_learned_counter.setText(
            t("status_active_rules", count=len(rules), profile=self.learning_engine.get_active_profile_name(), stack_info=stack_info)
        )

    def export_to_docx_dialog(self):
        if not self.pages:
            QMessageBox.information(self, "Notice", "Please attach and edit pages before exporting.")
            return

        # Ensure latest edits from active editor are saved into the page model
        if 0 <= self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        # Auto-learn any pending handwriting corrections into active profile before exporting
        pending = self.get_pages_with_unlearned_edits()
        if pending:
            learned_count = self.learn_all_corrections(silent=True)
            if learned_count > 0:
                log.info(f"Auto-learned {learned_count} handwriting corrections during Word (.docx) export.")
                self.lbl_status.setText(t("export_learned_notice", count=learned_count, profile=self.learning_engine.get_active_profile_name()))

        title, ok1 = QInputDialog.getText(self, t("export_dialog_title"), t("export_title_prompt"), text=t("export_default_title"))
        if not ok1:
            return
        subtitle, ok2 = QInputDialog.getText(self, t("export_dialog_title"), t("export_subtitle_prompt"), text="")
        if not ok2:
            return
        author, ok3 = QInputDialog.getText(self, t("export_dialog_title"), t("export_author_prompt"), text="")
        if not ok3:
            return

        # Choose destination file
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip() or "Notes"
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        default_file = os.path.join(docs_dir, f"{safe_title}.docx")
        out_path, _ = QFileDialog.getSaveFileName(self, t("export_dialog_title"), default_file, t("export_filter"))
        if not out_path:
            return

        pages_to_export = []
        for i, p in enumerate(self.pages):
            text = p["edited_text"].strip() if p["edited_text"] else p["raw_text"].strip()
            if text:
                pages_to_export.append({
                    "page_num": i + 1,
                    "title": f"עמוד {i + 1} ({p['filename']})",
                    "text": text
                })

        if not pages_to_export:
            QMessageBox.warning(self, "Notice", "No text has been recognized or transcribed yet.")
            return

        try:
            author_formatted = f"הערות וחידושים מאת {author}" if author else ""
            from core.docx_exporter import export_notes_to_docx
            export_notes_to_docx(
                pages_to_export,
                out_path,
                document_title=title,
                document_subtitle=subtitle,
                author_name=author_formatted,
                font_name="David"
            )
            resp = QMessageBox.question(
                self, t("export_success_title"),
                t("export_success_msg", path=out_path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.Yes:
                os.startfile(out_path)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error saving document:\n{str(e)}")

    def export_to_txt_dialog(self):
        if not self.pages:
            QMessageBox.information(self, "Notice", "Please attach and edit pages before exporting.")
            return

        # Ensure latest edits from active editor are saved into the page model
        if 0 <= self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        # Auto-learn any pending handwriting corrections into active profile before exporting
        pending = self.get_pages_with_unlearned_edits()
        if pending:
            learned_count = self.learn_all_corrections(silent=True)
            if learned_count > 0:
                log.info(f"Auto-learned {learned_count} handwriting corrections during Plain Text (.txt) export.")
                self.lbl_status.setText(t("export_learned_notice", count=learned_count, profile=self.learning_engine.get_active_profile_name()))

        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        default_file = os.path.join(docs_dir, "TorahNotes_Export.txt")
        out_path, _ = QFileDialog.getSaveFileName(self, t("btn_export_txt_opt"), default_file, "Text Files (*.txt);;All Files (*)")
        if not out_path:
            return

        pages_to_export = []
        for i, p in enumerate(self.pages):
            text = p["edited_text"].strip() if p["edited_text"] else p["raw_text"].strip()
            if text:
                pages_to_export.append(f"--- Page {i + 1}: {p['filename']} ---\n{text}\n")

        if not pages_to_export:
            QMessageBox.warning(self, "Notice", "No text has been recognized or transcribed yet.")
            return

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(pages_to_export))
            QMessageBox.information(self, "Export Successful!", f"Document saved successfully to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error saving text document:\n{str(e)}")

    def open_dictionary_manager(self):
        from ui.dictionary_dialog import DictionaryManagerDialog
        dlg = DictionaryManagerDialog(self.learning_engine, self)
        dlg.exec()
        self._refresh_profiles_ui()
        self.update_learned_count_badge()

    def open_update_dialog(self, auto_start_install: bool = False):
        from ui.update_dialog import UpdateDialog
        dlg = UpdateDialog(self, auto_start_install=auto_start_install)
        dlg.exec()

    def _start_startup_update_check(self):
        """Silently checks for updates in background after startup (if enabled)."""
        try:
            from ui.update_dialog import StartupUpdateWorker, CURRENT_VERSION
            self._startup_update_worker = StartupUpdateWorker(CURRENT_VERSION)
            self._startup_update_worker.update_available.connect(self._on_startup_update_found)
            self._startup_update_worker.start()
        except Exception:
            pass

    def _on_startup_update_found(self, data: dict):
        """Triggered when background worker finds an available update."""
        version = data.get("version", "")
        if not version:
            return
        self._remote_update_data = data
        if hasattr(self, 'update_banner') and self.update_banner:
            self.update_banner.show_update(version, data, lang=get_current_language())
        if hasattr(self, 'act_help_updates') and self.act_help_updates:
            self.act_help_updates.setText(f"{t('menu_help_check_updates')} (v{version} {t('status_update_available')})")

    def _on_banner_install_clicked(self, data: dict):
        """User clicked 'Install Update Now' on the top banner."""
        self.open_update_dialog(auto_start_install=True)

    def _on_banner_details_clicked(self, data: dict):
        """User clicked 'What's New' on the top banner."""
        self.open_update_dialog(auto_start_install=False)

    def open_help_dialog(self, initial_tab: int = 0):
        from ui.help_dialog import HelpTutorialDialog
        dlg = HelpTutorialDialog(self, initial_tab=initial_tab)
        dlg.exec()

    def open_about_dialog(self):
        from ui.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _load_theme_setting(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    saved_theme = cfg.get("theme", "light")
                    self.is_dark_theme = (saved_theme == "dark")
        except Exception:
            self.is_dark_theme = False

    def _save_theme_setting(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            cfg = {}
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["theme"] = "dark" if self.is_dark_theme else "light"
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def toggle_stats_bar(self, checked: bool):
        if hasattr(self, 'editor'):
            self.editor.set_stats_visible(checked)
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            else:
                cfg = {}
            cfg["show_editor_stats"] = checked
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self._save_theme_setting()
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_theme:
            self.setStyleSheet(DARK_THEME)
            self.btn_theme.setText("☀")
            self.btn_theme.setToolTip("Switch to Light Theme")
        else:
            self.setStyleSheet(LIGHT_THEME)
            self.btn_theme.setText("🌙")
            self.btn_theme.setToolTip("Switch to Dark Theme")

        if hasattr(self, 'update_banner') and self.update_banner:
            self.update_banner.apply_theme("dark" if self.is_dark_theme else "light")

    def center_on_screen(self):
        """Centers the window on the active monitor or primary display."""
        try:
            from PyQt6.QtGui import QGuiApplication, QCursor
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + (geo.height() - self.height()) // 2
                self.move(x, y)
        except Exception:
            pass

    def _on_viewer_line_clicked(self, line_num: int):
        """User clicked a bounding box on the document image. Jump editor cursor to that line."""
        if hasattr(self, "editor"):
            self.editor.go_to_line(line_num)

    def _on_editor_line_focused(self, line_num: int):
        """Cursor moved to a new line in the editor. Highlight line bounding box in image viewer."""
        if hasattr(self, "viewer"):
            self.viewer.highlight_line(line_num)

    def _start_model_prewarm(self):
        """Pre-warms the PyTorch neural OCR model in the background so the first scan is instant."""
        try:
            self._prewarm_worker = ModelPreWarmWorker(self.ocr_engine)
            self._prewarm_worker.start()
        except Exception as e:
            log.debug(f"Pre-warm launch note: {e}")

    def _update_page_list_items(self):
        """Updates sidebar page list items with visual status badges (⚪ Ready / 🟠 Pending / 🟢 Synced)."""
        for idx, p in enumerate(self.pages):
            raw = p.get("raw_text", "").strip()
            edited = p.get("edited_text", "").strip()
            last_learned = p.get("last_learned_text", raw).strip()
            if not raw:
                status_text = "⚪ " + t("page_status_ready")
            elif edited != last_learned:
                status_text = "🟠 " + t("page_status_pending")
            else:
                status_text = "🟢 " + t("page_status_scanned")

            item = self.list_pages.item(idx)
            if item:
                item.setText(f"{p['filename']}\n{status_text}")

    def save_session_state(self):
        """Saves current notebook session to disk for auto-recovery."""
        try:
            if not self.pages:
                if os.path.exists(SESSION_PATH):
                    os.remove(SESSION_PATH)
                return

            if 0 <= self.current_page_idx < len(self.pages):
                self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

            valid_pages = []
            for p in self.pages:
                if os.path.exists(p.get("path", "")):
                    valid_pages.append({
                        "path": p["path"],
                        "filename": p["filename"],
                        "rotation": p.get("rotation", 0),
                        "raw_text": p.get("raw_text", ""),
                        "edited_text": p.get("edited_text", ""),
                        "last_learned_text": p.get("last_learned_text", ""),
                        "status": p.get("status", ""),
                        "lines_boxes": p.get("lines_boxes", [])
                    })

            if not valid_pages:
                if os.path.exists(SESSION_PATH):
                    os.remove(SESSION_PATH)
                return

            from datetime import datetime
            data = {
                "saved_at": datetime.now().isoformat(),
                "active_page_idx": max(0, min(self.current_page_idx, len(valid_pages) - 1)),
                "pages": valid_pages
            }
            os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
            with open(SESSION_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.debug(f"Session save note: {e}")

    def check_restore_previous_session(self):
        """Offers to restore previously open session if one was saved."""
        try:
            if not os.path.exists(SESSION_PATH):
                return
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            pages = data.get("pages", [])
            valid_pages = [p for p in pages if os.path.exists(p.get("path", ""))]
            if not valid_pages:
                if os.path.exists(SESSION_PATH):
                    os.remove(SESSION_PATH)
                return

            saved_at = data.get("saved_at", "")
            date_str = saved_at.split("T")[0] if "T" in saved_at else "recently"
            res = QMessageBox.question(
                self,
                t("session_restore_title"),
                t("session_restore_msg", count=len(valid_pages), date=date_str),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res == QMessageBox.StandardButton.Yes:
                log.info(f"Restoring previous session with {len(valid_pages)} page(s)...")
                self.pages = valid_pages
                self.list_pages.clear()
                for p in self.pages:
                    item = QListWidgetItem()
                    item.setText(f"{p['filename']}\n{p.get('status', t('page_status_ready'))}")
                    try:
                        pix = QPixmap(p["path"])
                        if not pix.isNull():
                            thumb = pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            item.setIcon(QIcon(thumb))
                    except Exception:
                        pass
                    self.list_pages.addItem(item)
                target_idx = data.get("active_page_idx", 0)
                if 0 <= target_idx < len(self.pages):
                    self.list_pages.setCurrentRow(target_idx)
                self._update_learn_button_status()
                self._update_page_list_items()
            else:
                if os.path.exists(SESSION_PATH):
                    os.remove(SESSION_PATH)
        except Exception as e:
            log.error(f"Error restoring session: {e}")

    def clear_saved_session(self):
        """Clears active session file on disk."""
        try:
            if os.path.exists(SESSION_PATH):
                os.remove(SESSION_PATH)
        except Exception:
            pass

    def closeEvent(self, event):
        """
        Intercepts window close events (X button, Alt+F4, or File > Exit).
        Checks if any attached pages have unlearned proofreading corrections,
        prompting the user so their handwriting training is never accidentally lost.
        """
        log.info("Application close requested. Verifying unsaved changes and learning state...")

        # Ensure current editor text is synced
        if 0 <= self.current_page_idx < len(self.pages):
            self.pages[self.current_page_idx]["edited_text"] = self.editor.get_text()

        pending = self.get_pages_with_unlearned_edits()
        if pending:
            pages_str = ", ".join(str(idx + 1) for idx, _ in pending)
            log.info(f"Unlearned edits detected on page(s): {pages_str}. Prompting user before exit.")

            box = QMessageBox(self)
            box.setWindowTitle(t("close_confirm_title"))
            box.setText(f"<b>{t('close_confirm_heading')}</b>")
            box.setInformativeText(t("close_confirm_msg", pages=pages_str))
            box.setIcon(QMessageBox.Icon.Question)

            btn_save = box.addButton(t("close_btn_save_exit"), QMessageBox.ButtonRole.AcceptRole)
            btn_discard = box.addButton(t("close_btn_discard_exit"), QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton(t("close_btn_cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_save)

            box.exec()
            clicked = box.clickedButton()

            if clicked == btn_save:
                count = self.learn_all_corrections(silent=True)
                log.info(f"Learned {count} correction(s) across {len(pending)} page(s) on application close.")
            elif clicked == btn_discard:
                log.info("User elected to close without saving pending handwriting corrections.")
            else:
                log.info("User cancelled application close.")
                event.ignore()
                return

        # Save session snapshot on close
        self.save_session_state()

        # Stop active workers cleanly if running
        self._batch_scanning = False
        if hasattr(self, "active_worker") and self.active_worker and self.active_worker.isRunning():
            try:
                self.active_worker.quit()
                self.active_worker.wait(1000)
            except Exception:
                pass

        if hasattr(self, "_startup_update_worker") and self._startup_update_worker and self._startup_update_worker.isRunning():
            try:
                self._startup_update_worker.quit()
                self._startup_update_worker.wait(1000)
            except Exception:
                pass

        if hasattr(self, "_prewarm_worker") and self._prewarm_worker and self._prewarm_worker.isRunning():
            try:
                self._prewarm_worker.quit()
                self._prewarm_worker.wait(1000)
            except Exception:
                pass

        log.info("Ohr HaKsav shutdown complete. Exiting.")
        event.accept()
