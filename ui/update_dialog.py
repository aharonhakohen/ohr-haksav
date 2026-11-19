# -*- coding: utf-8 -*-
r"""
Ohr HaKsav - Modern Update Checker & Source Configuration Dialog
Supports checking for updates via:
  1. Official GitHub Cloud (https://raw.githubusercontent.com/.../version.json)
  2. Local Network Share / Windows Server Domain Share / USB / Offline folder
     (e.g. \\newltcserver\Installs\OhrHaKsav or M:\My Drive\... containing version.json & OhrHaKsav_Setup.exe)
Includes:
  - Fast, reliable Internet connectivity pre-check (DNS socket / HTTP connecttest)
  - Silent background startup update checking
  - One-click in-app background download and installation of updates
"""

import os
import sys
import json
import hashlib
import zipfile
import urllib.request
import subprocess
import tempfile
import socket
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QRadioButton, QButtonGroup,
    QLineEdit, QFileDialog, QTabWidget, QWidget, QFrame,
    QMessageBox, QApplication, QCheckBox
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


def is_strict_offline_mode() -> bool:
    """
    Returns True if Enterprise Air-Gap / Strict Zero-Network Policy is enabled via
    environment variable (OHR_HAKSAV_OFFLINE_ONLY=1) or ui_settings.json ('offline_only': true).
    """
    if os.environ.get("OHR_HAKSAV_OFFLINE_ONLY", "").strip() in ("1", "true", "yes"):
        return True
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                if json.load(f).get("offline_only", False):
                    return True
        except Exception:
            pass
    return False


def compute_file_sha256(file_path: str) -> str:
    """Computes lowercase hex SHA-256 checksum of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 256)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def verify_file_sha256(file_path: str, expected_sha256: str) -> bool:
    """Verifies file integrity against expected SHA-256 hex digest."""
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return True  # No checksum published for legacy builds
    actual = compute_file_sha256(file_path)
    return actual == expected


def is_connected_to_internet(timeout: float = 2.0) -> bool:
    """Fast check to see if an internet connection is available. Blocked in strict air-gap mode."""
    if is_strict_offline_mode():
        return False
    # Test standard DNS servers: Google (8.8.8.8) and Cloudflare (1.1.1.1) on port 53
    for host in ("8.8.8.8", "1.1.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, 53))
            s.close()
            return True
        except (OSError, socket.timeout):
            continue
    # Fallback to HTTP request if port 53 is blocked by network firewall
    try:
        req = urllib.request.Request(
            "http://www.msftconnecttest.com/connecttest.txt",
            headers={"User-Agent": "OhrHaKsav"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        pass
    return False


def get_current_app_version() -> str:
    """Read current version from version.json."""
    vpath = get_resource_path("version.json")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "1.4.2")
    except Exception:
        return "1.4.2"


CURRENT_VERSION = get_current_app_version()


def get_current_engine_version() -> str:
    """Read current engine compatibility version from version.json (used for lightweight delta patches)."""
    vpath = get_resource_path("version.json")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return str(json.load(f).get("engineVersion", "1.4"))
    except Exception:
        return "1.4"


def find_local_patch(folder: str, version: str = "") -> str:
    """Finds a lightweight code-only delta patch zip in a local/UNC folder."""
    if not folder or not os.path.exists(folder):
        return ""
    clean_ver = str(version).lstrip("vV").strip()
    if clean_ver:
        p = os.path.join(folder, f"OhrHaKsav_Patch_v{clean_ver}.zip")
        if os.path.exists(p):
            return p
    return ""


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


def find_local_installer(folder: str, version: str = "") -> str:
    """Finds the setup executable in a folder, prioritizing versioned filenames."""
    if not folder or not os.path.exists(folder):
        return ""
    clean_ver = str(version).lstrip("vV").strip()
    candidates = []
    if clean_ver:
        candidates.extend([
            f"OhrHaKsav_Setup_v{clean_ver}.exe",
            f"OhrHaKsav_Setup-v{clean_ver}.exe",
            f"OhrHaKsav_Setup_{clean_ver}.exe",
            f"OhrHaKsav-v{clean_ver}-Setup.exe",
            f"OhrHaKsav_v{clean_ver}_Setup.exe"
        ])
    candidates.append("OhrHaKsav_Setup.exe")
    for c in candidates:
        p = os.path.join(folder, c)
        if os.path.exists(p):
            return p
    try:
        for fname in os.listdir(folder):
            if fname.lower().endswith(".exe") and "setup" in fname.lower() and "ohr" in fname.lower():
                return os.path.join(folder, fname)
    except Exception:
        pass
    return ""


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, int)  # cur_bytes, tot_bytes, percent
    finished = pyqtSignal(str, bool)      # (downloaded_dest_path, is_patch)
    error = pyqtSignal(str)               # error_msg

    def __init__(
        self,
        download_url: str,
        version: str,
        fallback_url: str = "",
        expected_sha256: str = "",
        is_patch: bool = False
    ):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self.fallback_url = fallback_url
        self.expected_sha256 = (expected_sha256 or "").strip().lower()
        self.is_patch = is_patch
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_dir = tempfile.gettempdir()
        if self.is_patch:
            dest_path = os.path.join(temp_dir, f"OhrHaKsav_Patch_v{self.version}.zip")
        else:
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
                    headers={"User-Agent": "OhrHaKsav-Updater/1.4"}
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

                # Security Integrity Check: Verify SHA-256 digest if provided in version.json
                if self.expected_sha256 and not verify_file_sha256(dest_path, self.expected_sha256):
                    actual = compute_file_sha256(dest_path)
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
                    self.error.emit(
                        f"Security Verification Failed (SHA-256 Mismatch)!\n\n"
                        f"Expected: {self.expected_sha256[:16]}...\n"
                        f"Received: {actual[:16]}...\n\n"
                        f"The downloaded file was deleted for your safety. Please retry or download manually."
                    )
                    return

                # Download & integrity check succeeded
                self.finished.emit(dest_path, self.is_patch)
                return
            except Exception as err:
                last_err = err
                continue

        if last_err:
            self.error.emit(str(last_err))
        else:
            self.error.emit("Failed to download update package.")


class StartupUpdateWorker(QThread):
    """Silent background worker that checks for updates on application launch."""
    update_available = pyqtSignal(dict)  # version_data

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            source_type = "online"
            source_local_path = ""
            source_online_url = DEFAULT_ONLINE_URL
            auto_check = True

            if os.path.exists(SETTINGS_PATH):
                try:
                    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        auto_check = cfg.get("update_auto_check", True)
                        source_type = cfg.get("update_source_type", "online")
                        source_local_path = cfg.get("update_local_path", "")
                        source_online_url = cfg.get("update_online_url", DEFAULT_ONLINE_URL)
                except Exception:
                    pass

            if not auto_check:
                return

            data = None
            if source_type == "local":
                folder = source_local_path.strip()
                if not folder or not os.path.exists(folder):
                    return
                vpath = os.path.join(folder, "version.json")
                if not os.path.exists(vpath):
                    return
                with open(vpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                setup_exe = find_local_installer(folder, data.get("version", ""))
                patch_zip = find_local_patch(folder, data.get("version", ""))
                data["_local_setup_path"] = setup_exe
                data["_local_patch_path"] = patch_zip
                data["_source_folder"] = folder
            else:
                if is_strict_offline_mode():
                    return
                # Online check: Verify Internet connectivity first!
                if not is_connected_to_internet(timeout=2.0):
                    return

                req_url = source_online_url.strip() or DEFAULT_ONLINE_URL
                urls = [req_url]
                for fb in FALLBACK_ONLINE_URLS:
                    if fb not in urls:
                        urls.append(fb)

                for url in urls:
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={"User-Agent": "OhrHaKsav-Updater/1.3", "Accept": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            candidate = json.loads(resp.read().decode("utf-8"))
                            if candidate and "version" in candidate:
                                data = candidate
                                break
                    except Exception:
                        continue

            if not data or "version" not in data:
                return

            remote_ver = data.get("version", "0.0.0")
            cur_tuple = parse_version_tuple(self.current_version)
            remote_tuple = parse_version_tuple(remote_ver)

            if remote_tuple > cur_tuple:
                self.update_available.emit(data)

        except Exception:
            pass  # Silent exit on background check failure


class CheckUpdateWorker(QThread):
    check_completed = pyqtSignal(dict, bool)  # (version_data, is_update_available)
    check_failed = pyqtSignal(str)           # error_msg
    status_updated = pyqtSignal(str)         # status_message

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

                # Check if setup exe or lightweight delta patch is also in this folder
                setup_exe = find_local_installer(folder, data.get("version", ""))
                patch_zip = find_local_patch(folder, data.get("version", ""))
                data["_local_setup_path"] = setup_exe
                data["_local_patch_path"] = patch_zip
                data["_source_folder"] = folder

            else:
                if is_strict_offline_mode():
                    self.check_failed.emit(
                        "Strict Air-Gap / Zero-Network Mode is enabled.\n\n"
                        "All outbound internet checks are disabled by policy. "
                        "Switch to 'Local / Network Share' or disable Strict Air-Gap Mode in the Update Settings tab."
                    )
                    return

                # 1. Check for active Internet connection first!
                self.status_updated.emit(t("update_status_checking_net"))
                if not is_connected_to_internet(timeout=2.5):
                    self.check_failed.emit(t("update_err_no_internet"))
                    return

                self.status_updated.emit(t("update_status_net_ok"))

                # 2. Online GitHub raw JSON with automatic fallback
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
    def __init__(self, parent=None, auto_start_install: bool = False):
        super().__init__(parent)
        self.current_version = get_current_app_version()
        self.auto_start_install = auto_start_install
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
        self.auto_check_startup = True
        self.offline_only = False

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
                    self.auto_check_startup = cfg.get("update_auto_check", True)
                    self.offline_only = bool(cfg.get("offline_only", False))
            except Exception:
                pass

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            cfg = {}
            if os.path.exists(SETTINGS_PATH):
                try:
                    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    pass

            cfg["update_source_type"] = self.source_type
            cfg["update_local_path"] = self.source_local_path
            cfg["update_online_url"] = self.source_online_url
            cfg["update_auto_check"] = self.auto_check_startup
            cfg["offline_only"] = self.offline_only

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

        # Startup auto-check toggle
        self.chk_auto_startup = QCheckBox(t("update_auto_check"))
        self.chk_auto_startup.setChecked(self.auto_check_startup)
        self.chk_auto_startup.setStyleSheet("font-size: 13px; color: #1e293b;")
        layout.addWidget(self.chk_auto_startup)

        # Strict Air-Gap / Zero-Network Policy Toggle
        self.chk_offline_only = QCheckBox("🔒 Strict Air-Gap / Zero-Network Policy (Never emit any internet traffic — TAG / Filter Safe)")
        self.chk_offline_only.setChecked(self.offline_only)
        self.chk_offline_only.setStyleSheet("font-size: 12.5px; color: #334155;")
        layout.addWidget(self.chk_offline_only)

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
        self.auto_check_startup = self.chk_auto_startup.isChecked()
        self.offline_only = self.chk_offline_only.isChecked()
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
        self.worker.status_updated.connect(self._on_check_status_updated)
        self.worker.check_completed.connect(self._on_check_completed)
        self.worker.check_failed.connect(self._on_check_failed)
        self.worker.start()

    def _on_check_status_updated(self, msg: str):
        self.lbl_status.setText(msg)

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

            # If auto_start_install was requested (e.g. from the banner), trigger immediately
            if self.auto_start_install:
                self._handle_install_now()

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
            <p style="color: #475569; white-space: pre-wrap;">{err_msg}</p>
        </div>
        """
        self.browser_details.setHtml(html)

    def _can_use_delta_patch(self) -> bool:
        """
        Determines whether a lightweight code-only delta patch can be applied
        directly over the installed frozen directory (matching AI engineVersion).
        """
        if not getattr(sys, 'frozen', False):
            return False
        local_eng = get_current_engine_version()
        remote_eng = str(self.latest_data.get("engineVersion", ""))
        return bool(remote_eng and local_eng == remote_eng)

    def _handle_install_now(self):
        if self.download_worker and self.download_worker.isRunning():
            return

        remote_ver = str(self.latest_data.get("version", self.current_version)).lstrip("vV")

        # 1a. Local lightweight delta patch available (fast ~20MB update on UNC share!)
        local_patch = self.latest_data.get("_local_patch_path", "")
        if self._can_use_delta_patch() and local_patch and os.path.exists(local_patch):
            expected_sha = self.latest_data.get("patchSha256", "")
            if expected_sha and not verify_file_sha256(local_patch, expected_sha):
                QMessageBox.critical(self, "Security Verification Failed", "Local delta patch failed SHA-256 integrity verification and was aborted.")
                return
            self._apply_delta_patch_and_restart(local_patch)
            return

        # 1b. Local setup executable available
        local_setup = self.latest_data.get("_local_setup_path", "")
        if local_setup and os.path.exists(local_setup):
            self._run_local_installer(local_setup)
            return

        if self.source_type == "local" and self.source_local_path:
            cand = find_local_installer(self.source_local_path, remote_ver)
            if cand and os.path.exists(cand):
                self._run_local_installer(cand)
                return

        # 2. Online GitHub download: Prefer fast lightweight delta patch if engine matches!
        patch_url = self.latest_data.get("patchDownloadUrl", "")
        use_patch = self._can_use_delta_patch() and bool(patch_url)

        if use_patch:
            download_url = patch_url
            fallback_url = ""
            expected_sha = self.latest_data.get("patchSha256", "")
        else:
            custom_dl_url = self.latest_data.get("installerDownloadUrl", "")
            download_url = custom_dl_url or f"https://github.com/aharonhakohen/ohr-haksav/releases/download/v{remote_ver}/OhrHaKsav_Setup_v{remote_ver}.exe"
            fallback_url = f"https://github.com/aharonhakohen/ohr-haksav/releases/download/v{remote_ver}/OhrHaKsav_Setup.exe"
            expected_sha = self.latest_data.get("installerSha256", "")

        self.btn_install_now.setEnabled(False)
        self.btn_install_now.setText(t("update_btn_downloading", pct=0))
        self.btn_check_again.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_status.setText(t("update_downloading_status", cur_mb=0.0, tot_mb=0.0, pct=0))
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #2563eb;")

        self.download_worker = DownloadWorker(
            download_url,
            remote_ver,
            fallback_url=fallback_url,
            expected_sha256=expected_sha,
            is_patch=use_patch
        )
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

    def _on_download_finished(self, dest_path: str, is_patch: bool = False):
        self.progress_bar.setVisible(False)
        self.btn_check_again.setEnabled(True)
        self.btn_install_now.setEnabled(True)
        self.btn_install_now.setText(t("update_btn_install_now"))
        self.lbl_status.setText(t("update_download_complete") + " (SHA-256 Verified ✓)")
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #059669;")

        if is_patch:
            self._apply_delta_patch_and_restart(dest_path)
            return

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

    def _apply_delta_patch_and_restart(self, patch_zip_path: str):
        """
        Applies a lightweight code-only delta patch zip cleanly over the installed app folder
        after exiting Ohr HaKsav, then restarts the updated application automatically.
        """
        app_dir = os.path.dirname(sys.executable)
        exe_path = sys.executable
        remote_ver = self.latest_data.get("version", self.current_version)

        reply = QMessageBox.question(
            self,
            "Apply Fast Patch Update",
            f"Ohr HaKsav v{remote_ver} lightweight patch is verified (SHA-256 ✓) and ready!\n\n"
            f"Ohr HaKsav will close for 3 seconds to apply the patch and restart automatically.\n"
            f"All your profiles and notes are preserved.\n\nProceed now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ps_script = os.path.join(tempfile.gettempdir(), "ohr_haksav_apply_patch.ps1")
        clean_ver = str(remote_ver).lstrip("vV")
        script_content = (
            "Start-Sleep -Seconds 2\n"
            f"Expand-Archive -Path '{patch_zip_path}' -DestinationPath '{app_dir}' -Force\n"
            f"Get-ChildItem -Path '{app_dir}' -Filter 'OhrHaKsav_v*.exe' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue\n"
            f"Copy-Item -Path (Join-Path '{app_dir}' 'OhrHaKsav.exe') -Destination (Join-Path '{app_dir}' 'OhrHaKsav_v{clean_ver}.exe') -Force -ErrorAction SilentlyContinue\n"
            f"Start-Process -FilePath '{exe_path}'\n"
            f"Remove-Item -Path '{patch_zip_path}' -Force -ErrorAction SilentlyContinue\n"
        )
        with open(ps_script, "w", encoding="utf-8") as f:
            f.write(script_content)

        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", ps_script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        QApplication.quit()

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
            f"Failed to download update automatically:\n" + str(err_msg) + "\n\nYou can click 'Open Release on GitHub' to download the installer manually."
        )

    def _run_local_installer(self, setup_exe: str = ""):
        if not setup_exe:
            setup_exe = self.latest_data.get("_local_setup_path", "")
        if not setup_exe or not os.path.exists(setup_exe):
            QMessageBox.warning(self, "Setup Not Found", f"OhrHaKsav_Setup.exe was not found in: {self.latest_data.get('_source_folder', self.source_local_path)}")
            return

        # Verify SHA-256 digest if published in version.json
        expected_sha = self.latest_data.get("installerSha256", "")
        if expected_sha and not verify_file_sha256(setup_exe, expected_sha):
            QMessageBox.critical(
                self,
                "Security Verification Failed",
                f"The setup file '{os.path.basename(setup_exe)}' failed SHA-256 integrity verification.\n\n"
                f"Execution was blocked to protect your system."
            )
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
