# -*- coding: utf-8 -*-
r"""
Ohr HaKsav - Modern Update Checker & Source Configuration Dialog
Supports checking for updates via:
  1. Official GitHub Cloud (https://raw.githubusercontent.com/.../version.json)
  2. Local Network Share / Windows Server Domain Share / USB / Offline folder
     (e.g. \\newltcserver\Installs\OhrHaKsav or M:\My Drive\... containing version.json & OhrHaKsav_Setup.exe)
Includes one-click in-app background download and installation of updates.
"""

import os
import sys
import json
import urllib.request
import subprocess
import tempfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QRadioButton, QButtonGroup,
    QLineEdit, QFileDialog, QTabWidget, QWidget, QFrame,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPixmap, QGuiApplication, QCursor

from ui.i18n import t, SETTINGS_PATH, get_current_language
from installer.setup_gui import get_resource_path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ONLINE_URL = "https://raw.githubusercontent.com/aharonhakohen/ohr-haksav/main/public/version.json"
DEFAULT_RELEASE_URL = "https://github.com/aharonhakohen/ohr-haksav/releases"
FALLBACK_ONLINE_URLS = [
    "https://raw.githubusercontent.com/aharonhakohen/ohr-haksav/main/public/version.json",
    "https://raw.githubusercontent.com/aharonhakohen/ksav-kooker/main/public/version.json",
]


def get_current_app_version() -> str:
    """Read current version from version.json."""
    vpath = get_resource_path("version.json")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "1.3.2")
    except Exception:
        return "1.3.2"


def parse_version_tuple(v_str: str) -> tuple:
    """Parse version string like 'v1.1.2' or '1.1.2' into numeric tuple (1, 1, 2)."""
    clean = str(v_str).strip().lstrip("vV")
    parts = []
    for piece in clean.split("."):
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, int)  # cur_bytes, tot_bytes, percent
    finished = pyqtSignal(str)           # downloaded_dest_path
    error = pyqtSignal(str)              # error_msg

    def __init__(self, download_url: str, version: str, fallback_url: str = ""):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self.fallback_url = fallback_url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_dir = tempfile.gettempdir()
        dest_path = os.path.join(temp_dir, f"OhrHaKsav_Setup_v{self.version}.exe")
        urls_to_try = [self.download_url]
        if self.fallback_url and self.fallback_url not in urls_to_try:
            urls_to_try.append(self.fallback_url)

        last_err = None
        for url in urls_to_try:
            if self._is_cancelled:
                return
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "OhrHaKsav-Updater/1.3"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    tot_bytes = int(resp.headers.get("Content-Length", 0))
                    cur_bytes = 0
                    chunk_size = 1024 * 128  # 128 KB chunks

                    with open(dest_path, "wb") as f:
                        while not self._is_cancelled:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            cur_bytes += len(chunk)
                            pct = int((cur_bytes / max(1, tot_bytes)) * 100) if tot_bytes > 0 else 0
                            self.progress.emit(cur_bytes, tot_bytes, pct)

                    if self._is_cancelled:
                        if os.path.exists(dest_path):
                            try:
                                os.remove(dest_path)
                            except Exception:
                                pass
                        return

                # Download succeeded
                self.finished.emit(dest_path)
                return
            except Exception as err:
                last_err = err
                continue

        if last_err:
            self.error.emit(str(last_err))
        else:
            self.error.emit("Failed to download setup installer.")


class CheckUpdateWorker(QThread):
    check_completed = pyqtSignal(dict, bool)  # (version_data, is_update_available)
    check_failed = pyqtSignal(str)           # error_msg

    def __init__(self, source_type: str, source_path: str, current_version: str):
        super().__init__()
        self.source_type = source_type
        self.source_path = source_path
        self.current_version = current_version

    def run(self):
        try:
            data = None
            if self.source_type == "local":
                # Check local directory or network share (UNC path)
                folder = self.source_path.strip()
                if not folder or not os.path.exists(folder):
                    self.check_failed.emit(t("update_err_folder_not_found", folder=folder))
                    return

                vpath = os.path.join(folder, "version.json")
                if not os.path.exists(vpath):
                    self.check_failed.emit(t("update_err_no_version_json", folder=folder))
                    return

                with open(vpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check if setup exe is also in this folder
                setup_exe = os.path.join(folder, "OhrHaKsav_Setup.exe")
                data["_local_setup_path"] = setup_exe if os.path.exists(setup_exe) else ""
                data["_source_folder"] = folder

            else:
                # Online GitHub raw JSON with automatic fallback
                req_url = self.source_path.strip()
                if not req_url or "TorahNotesOCR" in req_url:
                    req_url = DEFAULT_ONLINE_URL

                urls_to_try = [req_url]
                for fb in FALLBACK_ONLINE_URLS:
                    if fb not in urls_to_try:
                        urls_to_try.append(fb)

                last_err = None
                for url in urls_to_try:
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={
                                "User-Agent": "OhrHaKsav-Updater/1.3",
                                "Accept": "application/json, text/plain, */*"
                            }
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            raw = resp.read().decode("utf-8")
                            candidate = json.loads(raw)
                            if candidate and "version" in candidate:
                                data = candidate
                                break
                    except Exception as err:
                        last_err = err
                        continue

                if not data:
                    if last_err:
                        raise last_err
                    self.check_failed.emit(t("update_err_invalid_data"))
                    return

            if not data or "version" not in data:
                self.check_failed.emit(t("update_err_invalid_data"))
                return

            remote_ver = data.get("version", "0.0.0")
            cur_tuple = parse_version_tuple(self.current_version)
            remote_tuple = parse_version_tuple(remote_ver)

            is_avail = remote_tuple > cur_tuple
            self.check_completed.emit(data, is_avail)

        except urllib.error.URLError as uerr:
            self.check_failed.emit(t("update_err_network", err=str(uerr.reason)))
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = get_current_app_version()
        self.worker = None
        self.download_worker = None
        self.latest_data = {}
        self.setWindowTitle(t("update_dialog_title"))
        self.resize(640, 500)
        self.setMinimumSize(560, 440)

        # Icon
        icon_path = get_resource_path(os.path.join("assets", "ohr_haksav.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._load_settings()
        self._init_ui()
        self.center_on_screen()
        self._start_check()

    def center_on_screen(self):
        """Centers the dialog on the active monitor or primary display."""
        try:
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + (geo.height() - self.height()) // 2
                self.move(x, y)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_screen()

    def closeEvent(self, event):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait(1000)
        event.accept()

    def _load_settings(self):
        self.source_type = "online"
        self.source_local_path = ""
        self.source_online_url = DEFAULT_ONLINE_URL
        self.auto_check_startup = False

        # Read from local_deploy.txt as sensible default for local share if exists
        deploy_cfg = os.path.join(BASE_DIR, "local_deploy.txt")
        if os.path.exists(deploy_cfg):
            try:
                with open(deploy_cfg, "r", encoding="utf-8") as f:
                    candidate = f.read().strip()
                    if candidate and os.path.exists(candidate):
                        self.source_local_path = candidate
            except Exception:
                pass

        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.source_type = cfg.get("update_source_type", self.source_type)
                    self.source_local_path = cfg.get("update_local_path", self.source_local_path)
                    self.source_online_url = cfg.get("update_online_url", self.source_online_url)
                    if not self.source_online_url or "TorahNotesOCR" in self.source_online_url:
                        self.source_online_url = DEFAULT_ONLINE_URL
                    self.auto_check_startup = cfg.get("update_auto_check", self.auto_check_startup)
            except Exception:
                pass

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            cfg = {}
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

            cfg["update_source_type"] = self.source_type
            cfg["update_local_path"] = self.source_local_path
            cfg["update_online_url"] = self.source_online_url
            cfg["update_auto_check"] = self.auto_check_startup

            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Notice: Failed to save update settings: {e}")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Status
        tab_status = QWidget()
        self._init_status_tab(tab_status)
        self.tabs.addTab(tab_status, t("update_tab_status"))

        # Tab 2: Settings & Source
        tab_settings = QWidget()
        self._init_settings_tab(tab_settings)
        self.tabs.addTab(tab_settings, t("update_tab_settings"))

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self.btn_close = QPushButton(t("update_btn_close"))
        self.btn_close.setMinimumWidth(90)
        self.btn_close.clicked.connect(self.close)
        bottom_bar.addWidget(self.btn_close)
        main_layout.addLayout(bottom_bar)

    def _init_status_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Header Card
        hdr_frame = QFrame()
        hdr_frame.setObjectName("hdr_frame")
        hdr_frame.setStyleSheet("""
            QFrame#hdr_frame {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QFrame#hdr_frame QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(14, 12, 14, 12)
        hdr_layout.setSpacing(14)

        logo_path = get_resource_path(os.path.join("assets", "ohr_haksav.png"))
        if os.path.exists(logo_path):
            lbl_ico = QLabel()
            pix = QPixmap(logo_path).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_ico.setPixmap(pix)
            lbl_ico.setFixedSize(42, 42)
            lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hdr_layout.addWidget(lbl_ico)

        v_box = QVBoxLayout()
        v_box.setSpacing(2)
        lbl_app = QLabel("<b>Ohr HaKsav (אור הכתב)</b>")
        lbl_app.setStyleSheet("font-size: 15px; color: #0f172a;")
        v_box.addWidget(lbl_app)

        self.lbl_ver_badge = QLabel(t("update_curr_version", version=self.current_version))
        self.lbl_ver_badge.setStyleSheet("font-size: 12px; color: #475569;")
        v_box.addWidget(self.lbl_ver_badge)
        hdr_layout.addLayout(v_box)
        hdr_layout.addStretch()

        self.btn_check_again = QPushButton(t("update_btn_check_again"))
        self.btn_check_again.clicked.connect(self._start_check)
        hdr_layout.addWidget(self.btn_check_again)
        layout.addWidget(hdr_frame)

        # Progress / Status indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel(t("update_checking_msg", source=self._get_source_display_name()))
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 500; color: #2563eb;")
        layout.addWidget(self.lbl_status)

        # Details Content Area
        self.browser_details = QTextBrowser()
        self.browser_details.setOpenExternalLinks(True)
        self.browser_details.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                color: #0f172a;
            }
        """)
        layout.addWidget(self.browser_details, stretch=1)

        # Action Buttons row
        self.action_box = QHBoxLayout()
        self.action_box.setSpacing(10)

        # Prominent "Install Now" button
        self.btn_install_now = QPushButton(t("update_btn_install_now"))
        self.btn_install_now.setObjectName("btn_install_now")
        self.btn_install_now.setStyleSheet("""
            QPushButton#btn_install_now {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 22px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btn_install_now:hover {
                background-color: #047857;
            }
            QPushButton#btn_install_now:pressed {
                background-color: #065f46;
            }
            QPushButton#btn_install_now:disabled {
                background-color: #94a3b8;
                color: #f1f5f9;
            }
        """)
        self.btn_install_now.setVisible(False)
        self.btn_install_now.clicked.connect(self._handle_install_now)
        self.action_box.addWidget(self.btn_install_now)

        self.btn_open_folder = QPushButton(t("update_btn_open_folder"))
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._open_staging_folder)
        self.action_box.addWidget(self.btn_open_folder)

        self.btn_open_web = QPushButton(t("update_btn_open_web"))
        self.btn_open_web.setObjectName("btn_primary")
        self.btn_open_web.setStyleSheet("""
            QPushButton#btn_primary {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#btn_primary:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_open_web.setVisible(False)
        self.btn_open_web.clicked.connect(self._open_web_release)
        self.action_box.addWidget(self.btn_open_web)

        self.action_box.addStretch()
        layout.addLayout(self.action_box)

    def _init_settings_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        lbl_hdr = QLabel(f"<b>{t('update_source_group')}</b>")
        lbl_hdr.setStyleSheet("font-size: 14px; color: #0f172a;")
        layout.addWidget(lbl_hdr)

        self.bg_source = QButtonGroup(self)

        # Radio 1: Online GitHub
        self.rad_online = QRadioButton(t("update_source_web"))
        self.rad_online.setStyleSheet("font-weight: 600; color: #0f172a;")
        self.bg_source.addButton(self.rad_online)
        layout.addWidget(self.rad_online)

        lbl_online_desc = QLabel(t("update_source_web_desc"))
        lbl_online_desc.setStyleSheet("color: #64748b; font-size: 12px; margin-left: 22px;")
        lbl_online_desc.setWordWrap(True)
        layout.addWidget(lbl_online_desc)

        # Radio 2: Local Network Share / Offline Folder
        self.rad_local = QRadioButton(t("update_source_local"))
        self.rad_local.setStyleSheet("font-weight: 600; color: #0f172a; margin-top: 10px;")
        self.bg_source.addButton(self.rad_local)
        layout.addWidget(self.rad_local)

        lbl_local_desc = QLabel(t("update_source_local_desc"))
        lbl_local_desc.setStyleSheet("color: #64748b; font-size: 12px; margin-left: 22px;")
        lbl_local_desc.setWordWrap(True)
        layout.addWidget(lbl_local_desc)

        # Folder Picker Row
        folder_box = QHBoxLayout()
        folder_box.setContentsMargins(22, 0, 0, 0)
        self.txt_local_path = QLineEdit(self.source_local_path)
        self.txt_local_path.setPlaceholderText(r"\newltcserver\Installs\OhrHaKsav or M:\My Drive\...")
        folder_box.addWidget(self.txt_local_path)

        btn_browse = QPushButton(t("update_folder_browse_btn"))
        btn_browse.clicked.connect(self._browse_local_folder)
        folder_box.addWidget(btn_browse)
        layout.addLayout(folder_box)

        # Sync radios
        if self.source_type == "local":
            self.rad_local.setChecked(True)
        else:
            self.rad_online.setChecked(True)

        layout.addSpacing(10)

        # Save Button
        btn_save = QPushButton(t("update_save_settings_btn"))
        btn_save.setObjectName("btn_primary")
        btn_save.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; border: none;")
        btn_save.clicked.connect(self._save_and_recheck)
        layout.addWidget(btn_save)

        layout.addStretch()

    def _browse_local_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Network Share or Folder", self.txt_local_path.text())
        if folder:
            self.txt_local_path.setText(folder)
            self.rad_local.setChecked(True)

    def _save_and_recheck(self):
        self.source_type = "local" if self.rad_local.isChecked() else "online"
        self.source_local_path = self.txt_local_path.text().strip()
        self._save_settings()
        self.tabs.setCurrentIndex(0)
        self._start_check()

    def _get_source_display_name(self) -> str:
        if self.source_type == "local":
            path = self.source_local_path or "Not configured"
            return f"Local / Network Share ({path})"
        return "GitHub Cloud"

    def _start_check(self):
        if self.worker and self.worker.isRunning():
            return

        self.btn_check_again.setEnabled(False)
        self.btn_install_now.setVisible(False)
        self.btn_open_folder.setVisible(False)
        self.btn_open_web.setVisible(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate spinner
        self.lbl_status.setText(t("update_checking_msg", source=self._get_source_display_name()))
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: 500; color: #2563eb;")
        self.browser_details.clear()

        source_path = self.source_local_path if self.source_type == "local" else self.source_online_url
        self.worker = CheckUpdateWorker(self.source_type, source_path, self.current_version)
        self.worker.check_completed.connect(self._on_check_completed)
        self.worker.check_failed.connect(self._on_check_failed)
        self.worker.start()

    def _on_check_completed(self, data: dict, is_avail: bool):
        self.progress_bar.setVisible(False)
        self.btn_check_again.setEnabled(True)
        self.latest_data = data

        remote_ver = data.get("version", self.current_version)
        release_date = data.get("releaseDate", "")
        title = data.get("releaseTitle", "")
        desc = data.get("description", "")
        features = data.get("features", [])

        if is_avail:
            self.lbl_status.setText(t("update_available_hdr", version=remote_ver))
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #047857;")

            # Build HTML details
            html = f"""
            <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.5;">
                <h3 style="color: #0f172a; margin-top: 0; margin-bottom: 4px;">{title or f"Version {remote_ver}"}</h3>
                <div style="font-size: 12px; color: #64748b; margin-bottom: 12px;">{t('update_release_date', date=release_date)}</div>
                <p style="color: #1e293b; font-size: 13px;">{desc}</p>
                <h4 style="color: #0f172a; margin-bottom: 6px;">{t('update_whats_new')}</h4>
                <ul style="color: #334155; margin-top: 0; padding-left: 20px;">
            """
            for feat in features:
                html += f"<li style='margin-bottom: 4px;'>{feat}</li>"
            html += "</ul></div>"
            self.browser_details.setHtml(html)

            # Prominent Install Now button
            self.btn_install_now.setText(t("update_btn_install_now"))
            self.btn_install_now.setEnabled(True)
            self.btn_install_now.setVisible(True)

            local_setup = data.get("_local_setup_path", "")
            if local_setup and os.path.exists(local_setup):
                self.btn_open_folder.setVisible(True)
            else:
                if self.source_type == "local":
                    self.btn_open_folder.setVisible(True)
                self.btn_open_web.setVisible(True)

        else:
            self.lbl_status.setText(t("update_up_to_date_hdr"))
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: bold; color: #059669;")

            html = f"""
            <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.5; padding: 10px;">
                <p style="font-size: 14px; color: #059669; font-weight: 600;">✓ {t('update_up_to_date_sub', version=self.current_version)}</p>
                <p style="color: #475569; font-size: 13px;">{desc}</p>
                <h4 style="color: #0f172a; margin-bottom: 6px;">{t('update_whats_new')}</h4>
                <ul style="color: #334155; margin-top: 0; padding-left: 20px;">
            """
            for feat in features:
                html += f"<li style='margin-bottom: 4px;'>{feat}</li>"
            html += "</ul></div>"
            self.browser_details.setHtml(html)

            # Also offer Reinstall / Repair option
            self.btn_install_now.setText(t("update_btn_reinstall"))
            self.btn_install_now.setEnabled(True)
            self.btn_install_now.setVisible(True)

            local_setup = data.get("_local_setup_path", "")
            if local_setup and os.path.exists(local_setup):
                self.btn_open_folder.setVisible(True)
            else:
                if self.source_type == "local":
                    self.btn_open_folder.setVisible(True)
                self.btn_open_web.setVisible(True)

    def _on_check_failed(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_check_again.setEnabled(True)
        self.lbl_status.setText(t("update_err_hdr"))
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;")

        html = f"""
        <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.5; color: #b91c1c; padding: 8px;">
            <p><b>{t('update_err_hdr')}</b></p>
            <p style="color: #475569;">{err_msg}</p>
            <p style="color: #64748b; font-size: 12px;">
                Tip: If working offline or in a Windows Server domain environment, open the <b>Update Source & Settings</b> tab to specify a local network folder or USB path containing version.json and OhrHaKsav_Setup.exe.
            </p>
        </div>
        """
        self.browser_details.setHtml(html)

    def _handle_install_now(self):
        if self.download_worker and self.download_worker.isRunning():
            return

        # 1. Local setup executable available
        local_setup = self.latest_data.get("_local_setup_path", "")
        if local_setup and os.path.exists(local_setup):
            self._run_local_installer(local_setup)
            return

        if self.source_type == "local" and self.source_local_path:
            cand = os.path.join(self.source_local_path, "OhrHaKsav_Setup.exe")
            if os.path.exists(cand):
                self._run_local_installer(cand)
                return

        # 2. Online GitHub download and install
        remote_ver = str(self.latest_data.get("version", self.current_version)).lstrip("vV")
        download_url = f"https://github.com/aharonhakohen/ohr-haksav/releases/download/v{remote_ver}/OhrHaKsav_Setup.exe"
        fallback_url = "https://github.com/aharonhakohen/ohr-haksav/releases/latest/download/OhrHaKsav_Setup.exe"

        self.btn_install_now.setEnabled(False)
        self.btn_install_now.setText(t("update_btn_downloading", pct=0))
        self.btn_check_again.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_status.setText(t("update_downloading_status", cur_mb=0.0, tot_mb=0.0, pct=0))
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #2563eb;")

        self.download_worker = DownloadWorker(download_url, remote_ver, fallback_url=fallback_url)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, cur_bytes: int, tot_bytes: int, pct: int):
        cur_mb = cur_bytes / (1024 * 1024)
        tot_mb = tot_bytes / (1024 * 1024)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(t("update_downloading_status", cur_mb=cur_mb, tot_mb=tot_mb, pct=pct))
        self.btn_install_now.setText(t("update_btn_downloading", pct=pct))

    def _on_download_finished(self, dest_path: str):
        self.progress_bar.setVisible(False)
        self.btn_check_again.setEnabled(True)
        self.btn_install_now.setEnabled(True)
        self.btn_install_now.setText(t("update_btn_install_now"))
        self.lbl_status.setText(t("update_download_complete"))
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #059669;")

        remote_ver = self.latest_data.get("version", self.current_version)
        reply = QMessageBox.question(
            self,
            t("update_download_prompt_title"),
            t("update_download_prompt_msg", version=remote_ver),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        # Launch the setup wizard
        subprocess.Popen([dest_path], shell=True)

        if reply == QMessageBox.StandardButton.Yes:
            # Exit so files can be replaced without lock conflicts
            QApplication.quit()
        else:
            self.accept()

    def _on_download_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_check_again.setEnabled(True)
        self.btn_install_now.setEnabled(True)
        self.btn_install_now.setText(t("update_btn_install_now"))
        self.lbl_status.setText(t("update_err_hdr"))
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;")

        QMessageBox.warning(
            self,
            t("update_err_hdr"),
            f"Failed to download update automatically:\n" + str(err_msg) + "\n\nYou can click 'Open Release on GitHub' to download manually."
        )

    def _run_local_installer(self, setup_exe: str = ""):
        if not setup_exe:
            setup_exe = self.latest_data.get("_local_setup_path", "")
        if not setup_exe or not os.path.exists(setup_exe):
            QMessageBox.warning(self, "Setup Not Found", f"OhrHaKsav_Setup.exe was not found in: {self.latest_data.get('_source_folder', self.source_local_path)}")
            return

        reply = QMessageBox.question(
            self,
            t("update_prompt_close_title"),
            t("update_prompt_close_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        # Launch the setup wizard
        subprocess.Popen([setup_exe], shell=True)

        if reply == QMessageBox.StandardButton.Yes:
            # Exit application so installer can replace files cleanly without lock
            QApplication.quit()
        else:
            self.accept()

    def _open_staging_folder(self):
        folder = self.latest_data.get("_source_folder", self.source_local_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)

    def _open_web_release(self):
        import webbrowser
        webbrowser.open(DEFAULT_RELEASE_URL)
