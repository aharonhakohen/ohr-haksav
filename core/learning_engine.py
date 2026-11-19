# -*- coding: utf-8 -*-
r"""
TorahNotesOCR - Learning and Memory Engine (v1.1.0)
Stores user corrections, common Talmudic abbreviations, and OCR error patterns.
Supports:
- Multi-User / Handwriting Profiles (isolated databases per scribe/student/book)
- Multi-Profile Stacking (applying rules from multiple people simultaneously during OCR)
- Rule Merging (combining another person's learned rules into your active profile)
- Automatic & On-Demand Backup & Restore (.ksavbackup / .db / .json)
- Roaming Windows User Profile support (%APPDATA%\OhrHaKsav)
"""

import os
import re
import json
import shutil
import sqlite3
import difflib
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

DEFAULT_CORRECTIONS = [
    # Common OCR misreadings of Yeshiva / Torah handwriting
    ("בסייד", "בס\"ד"),
    ("בסיידן", "בס\"ד"),
    ("בסיירן", "בס\"ד"),
    ("ובסיידן", "בס\"ד"),
    ("כן בסיבן", "בס\"ד"),
    ("בסדו", "בס\"ד"),
    ("בסיד", "בס\"ד"),
    ("בסד", "בס\"ד"),
    ("שיעורא", "שיעור א'"),
    ("שיעורב", "שיעור ב'"),
    ("שיעורג", "שיעור ג'"),
    ("שיעורד", "שיעור ד'"),
    ("שיעורה", "שיעור ה'"),
    ("שיעורו", "שיעור ו'"),
    ("שיעורז", "שיעור ז'"),
    ("שיעורח", "שיעור ח'"),
    ("רשל", "רגל"),
    ("קוס", "תוס'"),
    ("קוס'", "תוס'"),
    ("תום", "תוס'"),
    ("תוס", "תוס'"),
    ("רסי", "רש\"י"),
    ("רשי", "רש\"י"),
    ("רשלי", "רש\"י"),
    ("רמבם", "רמב\"ם"),
    ("ראבד", "ראב\"ד"),
    ("הראבד", "הראב\"ד"),
    ("הנמוקי", "הנימוק\"י"),
    ("ריף", "רי\"ף"),
    ("ראס", "רא\"ש"),
    ("ראש", "רא\"ש"),
    ("חנין", "ח\"נ"),
    ("חנ", "ח\"נ"),
    ("ח\"נ'", "ח\"נ"),
    ("נס", "נ\"ש"),
    ("נש", "נ\"ש"),
    ("גש", "נ\"ש"),
    ("נפקמ", "נפק\"מ"),
    ("קמל", "קמ\"ל"),
    ("סדא", "סד\"א"),
    ("לפיז", "לפי\"ז"),
    ("ברהר", "ברה\"ר"),
    ("ברחר", "ברה\"ר"),
    ("ברהי", "ברה\"י"),
    ("משאכ", "משא\"כ"),
    ("משא\"ב", "משא\"כ"),
    ("אכ", "א\"כ"),
    ("איכ", "אי\"כ"),
    ("עיש", "עיי\"ש"),
    ("עייש", "עיי\"ש"),
    ("עכד", "עכ\"ד"),
    ("עכ\"ל", "עכ\"ל"),
    ("עכל", "עכ\"ל"),
    ("וכו", "וכו'"),
    ("וגו", "וגו'"),
    ("מנל", "מנ\"ל"),
    ("תר", "ת\"ר"),
    ("יל", "י\"ל"),
    ("צל", "צ\"ל"),
    ("צב", "צ\"ב"),
    ("צב'", "צ\"ב"),
    ("ממנ", "ממ\"נ"),
    ("מהו", "מהו'"),
    ("הגמ", "הגמ'"),
    ("גמ", "גמ'"),
    ("מתנ", "מתנ'"),
    ("מתני", "מתני'"),
    ("דכתי", "דכתיב"),
    ("איפכ", "איפכא"),
    ("כדרכ", "כדרכה"),
    ("פנ\"י", "פנ\"י"),
    ("פני", "פנ\"י"),
    ("הנציב", "הנצי\"ב"),
    ("הנצי\"ב", "הנצי\"ב"),
]

# Unambiguous cursive OCR typos that are NOT valid Hebrew/Aramaic words
BUILTIN_CURSIVE_FIXES = {
    "בסיידן": "בס\"ד",
    "בסיירן": "בס\"ד",
    "ובסיידן": "בס\"ד",
    "בסדו": "בס\"ד",
    "ביון": "כיון",
    "ביין": "כיון",
    "לבאורה": "לכאורה",
    "לכוורה": "לכאורה",
    "לבוורה": "לכאורה",
    "לבאורהן": "לכאורה",
    "בבלל": "בכלל",
    "נבלל": "נכלל",
    "הבלי": "הכלי",
    "הכלין": "הכלי",
    "הילובה": "הילוכה",
    "בהילבותיהן": "בהילכותיהן",
    "מהלבה": "מהלכה",
    "בתב": "כתב",
    "ובתב": "וכתב",
    "דבתב": "דכתב",
    "בשבתב": "כשכתב",
    "ובשבתב": "וכשכתב",
    "בקב": "כתב",
    "פקב": "כתב",
    "בריך": "צריך",
    "צריד": "צריך",
    "המוביא": "המוציא",
    "קולדה": "תולדה",
    "מקחת": "מתחת",
    "להקחייב": "להתחייב",
    "הקחייב": "התחייב",
    "נתבונה": "נתכוונה",
    "נתביונה": "נתכוונה",
    "אודחיה": "אורחיה",
    "לפיז": "לפי\"ז",
    "הראבד": "הראב\"ד",
    "הנמוקי": "הנימוק\"י",
    "משלת": "משלם",
    "האשון": "הראשון",
    "הצרודות": "הצרורות",
    "דרורות": "צרורות",
    "הברורות": "הצרורות",
    "בברורות": "בצרורות",
    "שברורות": "שצרורות",
    "דברורות": "דצרורות",
    "בופר": "כופר",
    "מבופר": "מכופר",
    "וביון": "וכיון",
    "החיבוש": "החידוש",
    "החודוש": "החידוש",
    "שחידיש": "שחידוש",
    "שהחידיש": "שהחידוש",
    "המניק": "המזיק",
    "מניק": "מזיק",
    "מגיק": "מזיק",
    "להגיק": "להזיק",
    "להזוק": "להזיק",
    "שאונו": "שאינו",
    "אונו": "אינו",
    "ןממילא": "וממילא",
    "דסדאן": "דסד\"א",
    "לברשם": "לפרשת",
    "חמשי": "חמישי",
    "נמימשלת": "נמי משלם",
    "בתבתוס": "כתב תוס'",
    "מהבחמה": "מהבהמה",
    "במזוק": "במזיק",
}

# Curated Yeshiva / Talmudic target words for single-character cursive-swap resolution
TORAH_CURSIVE_TARGETS = {
    "לכאורה", "הילוכה", "מהלכה", "בכלל", "נכלל", "הכלי", "כיון", "כיוון",
    "כתב", "וכתב", "שכתב", "דכתב", "כשכתב", "צריך", "וצריך", "המוציא",
    "תולדה", "מתחת", "להתחייב", "התחייב", "נתכוונה", "אורחיה", "החידוש",
    "המזיק", "להזיק", "הראשון", "משלם", "צרורות", "הצרורות", "בצרורות",
    "משונה", "במשונה", "דמשונה", "כדרכה", "הבהמה", "לבהמה", "מהבהמה",
    "מסתמא", "אליבא", "הלכתא", "ברייתא", "המשנה", "ראשונים", "אחרונים",
    "הגמרא", "חלוקות", "מעשות", "בגופו", "כגופו", "מחובר", "תלוש",
    "ברגליו", "הילכותיהן", "בהילכותיהן", "לפרשת", "חמישי", "מרחשון",
    "מחבירו", "הראיה", "הנושא", "באופן", "ממילא", "וממילא", "ובאמת",
    "לגמרי", "מחמת", "שאינו", "מכלל", "דכתיב", "איפכא", "הנצי\"ב",
    "לשיטת", "כשיטת", "בשיטת", "דעתו", "לדעת", "בדעת", "פירוש",
    "לפירוש", "קושיא", "תירוץ", "חילוק", "סברא", "הסברא", "בסברא",
    "מחלוקת", "במחלוקת", "תוספות", "בתוספות", "התוספות", "שבתוספות",
}

# Common valid Hebrew words that must NEVER be altered by cursive-swap heuristics
SAFE_COMMON_HEBREW = {
    "ברור", "בנו", "דבר", "דברי", "דברים", "ברך", "בדרך", "דרך", "מלך",
    "כבוד", "במקום", "מקום", "בקר", "בדין", "הדין", "דין", "כדי", "כאן",
    "באמת", "בזה", "בלי", "כלים", "כלי", "רגל", "דגל", "שבר", "ושבר",
    "שברתו", "ושברתו", "נפל", "ונפל", "הוא", "היא", "האם", "אבל", "אלא",
    "אמר", "לומר", "אומר", "אפשר", "עדיין", "קשה", "אמאי", "פשוט", "בפשוט",
    "ספק", "בספק", "חייב", "פטור", "מועד", "מועדת", "קרן", "נזק", "שלם",
    "חצי", "גוף", "כוחו", "ממש", "אחר", "אחד", "שני", "שניהם", "כולם",
    "ביחד", "לבד", "לגבי", "בעצם", "עצם", "מעשה", "לעשות", "עשה", "עושה",
    "יכול", "אינו", "אינה", "אינן", "אינם", "אין", "יש", "היה", "היתה",
    "יהיה", "להיות", "מותר", "אסור", "כשר", "פסול", "טמא", "טהור",
    "ממון", "גזל", "גניבה", "שומר", "שומרים", "בעלים", "הבעלים", "נכסים",
    "בית", "חצר", "שדה", "עיר", "עולם", "אדם", "איש", "אשה", "בן", "בת",
    "אב", "אם", "אח", "אחות", "יום", "לילה", "שבת", "חול", "שנה", "חודש",
    "תורה", "מצוה", "מצות", "עבירה", "הלכה", "משפט", "צדק", "אמת", "שקר",
    "גדול", "קטן", "טוב", "רע", "חדש", "ישן", "רב", "מעט", "הרבה", "קצת",
    "כמו", "כגון", "היינו", "דהיינו", "מכל", "בכל", "לכל", "שכל", "הכל",
    "אף", "גם", "רק", "עוד", "שוב", "כבר", "עתה", "כעת", "אז", "שם",
    "פה", "הכא", "התם", "הכי", "לאו", "נמי", "תו", "הא", "מאי", "דא",
    "בהמה", "חיה", "עוף", "עופות", "צבי", "איל", "חמור", "שור", "בור",
    "מבעה", "הבער", "אש", "מים", "עץ", "אבן", "כלב", "גדי", "עגלה",
} | TORAH_CURSIVE_TARGETS

CURSIVE_CHAR_SWAPS = {
    "ב": ("כ", "צ"),
    "ק": ("ת",),
    "ד": ("ר",),
    "נ": ("ז",),
}

DEFAULT_VOCABULARY = [
    "בבא", "קמא", "מציעא", "בתרא", "כיצד", "הרגל", "מועדת", "להלך", "כדרכה",
    "ולשבר", "שן", "ורגל", "קרן", "צרורות", "חצי", "נזק", "נזק", "שלם", "שינוי",
    "אורחיה", "משונה", "כוחו", "כגופו", "תולדה", "אב", "אבות", "נזיקין",
    "רש\"י", "תוספות", "תוס'", "רמב\"ם", "ראב\"ד", "רי\"ף", "רא\"ש", "מהר\"ם",
    "רבינו", "פרץ", "הגרש\"פ", "הגרי\"ז", "ברכת", "שמואל", "אימרי", "משה",
    "רשות", "הרבים", "היחיד", "חצר", "הניזק", "פטור", "חייב", "הלכתא", "גמירי"
]


class LearningEngine:
    def __init__(self, db_path: str = None, app_dir: str = None):
        """
        Initializes the Learning Engine.
        If db_path is provided, operates on that specific database file.
        Otherwise, manages multi-user profiles in app_dir (%APPDATA%\\OhrHaKsav).
        """
        if app_dir is None:
            custom_dir = os.environ.get("OHR_HAKSAV_DATA_DIR") or os.environ.get("KSAV_KOOKER_DATA_DIR")
            if custom_dir:
                app_dir = custom_dir
            else:
                roaming_appdata = os.environ.get("APPDATA")
                base_appdata = os.path.join(roaming_appdata, "OhrHaKsav") if roaming_appdata else os.path.join(os.path.expanduser("~"), ".ohr_haksav")
                settings_cfg = os.path.join(base_appdata, "ui_settings.json")
                if os.path.exists(settings_cfg):
                    try:
                        with open(settings_cfg, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            if cfg.get("custom_data_dir") and os.path.exists(cfg["custom_data_dir"]):
                                base_appdata = cfg["custom_data_dir"]
                    except Exception:
                        pass
                app_dir = base_appdata

        self.app_dir = app_dir
        self.profiles_dir = os.path.join(self.app_dir, "profiles")
        self.backups_dir = os.path.join(self.app_dir, "backups")
        self.config_path = os.path.join(self.app_dir, "profiles_config.json")
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

        self._conn = None
        self.active_profile_id = "default"
        self.enabled_profiles = ["default"]
        self.profiles_metadata: Dict[str, Dict[str, Any]] = {}

        if db_path:
            # Standalone explicit DB mode
            self.db_path = db_path
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._init_db(self._conn)
        else:
            # Multi-profile mode
            self._init_profiles_system()

    # =========================================================================
    # Profile System Management
    # =========================================================================

    def _init_profiles_system(self):
        """Initializes profiles configuration, migrates legacy database if present."""
        legacy_db = os.path.join(self.app_dir, "learned_corrections.db")
        default_db = os.path.join(self.profiles_dir, "default.db")

        # Migrate legacy DB if default doesn't exist
        if not os.path.exists(default_db) and os.path.exists(legacy_db):
            try:
                shutil.copy2(legacy_db, default_db)
            except Exception:
                pass

        # Load or initialize profiles config
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_profile_id = data.get("active_profile", "default")
                    self.enabled_profiles = data.get("enabled_profiles", [self.active_profile_id])
                    self.profiles_metadata = data.get("profiles", {})
            except Exception:
                self.profiles_metadata = {}

        if "default" not in self.profiles_metadata:
            self.profiles_metadata["default"] = {
                "id": "default",
                "name": "ברירת מחדל (כללי)",
                "description": "מאגר כללי וראשי תיבות תורניים",
                "filename": "default.db",
                "created_at": datetime.now().isoformat()
            }

        if self.active_profile_id not in self.profiles_metadata:
            self.active_profile_id = "default"
        if "default" not in self.enabled_profiles:
            self.enabled_profiles.append("default")

        self._save_profiles_config()
        self._switch_connection_to_profile(self.active_profile_id)

    def _save_profiles_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "active_profile": self.active_profile_id,
                    "enabled_profiles": self.enabled_profiles,
                    "profiles": self.profiles_metadata
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save profiles config: {e}")

    def _get_profile_path(self, profile_id: str) -> str:
        meta = self.profiles_metadata.get(profile_id)
        if meta and "filename" in meta:
            return os.path.join(self.profiles_dir, meta["filename"])
        return os.path.join(self.profiles_dir, f"{profile_id}.db")

    def _switch_connection_to_profile(self, profile_id: str):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

        self.active_profile_id = profile_id
        self.db_path = self._get_profile_path(profile_id)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db(self._conn)

    def _get_connection(self):
        return self._conn

    def _init_db(self, conn: sqlite3.Connection):
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS replacements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_text TEXT UNIQUE COLLATE NOCASE,
                    corrected_text TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE,
                    frequency INTEGER DEFAULT 1,
                    category TEXT DEFAULT 'general'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_name TEXT,
                    raw_line TEXT,
                    corrected_line TEXT,
                    timestamp TEXT
                )
            """)

            # Seed default corrections if table is empty
            cursor.execute("SELECT COUNT(*) FROM replacements")
            if cursor.fetchone()[0] == 0:
                now = datetime.now().isoformat()
                for raw, corr in DEFAULT_CORRECTIONS:
                    cursor.execute("""
                        INSERT OR IGNORE INTO replacements 
                        (raw_text, corrected_text, count, is_active, created_at, updated_at)
                        VALUES (?, ?, 1, 1, ?, ?)
                    """, (raw, corr, now, now))

            # Seed vocabulary
            cursor.execute("SELECT COUNT(*) FROM vocabulary")
            if cursor.fetchone()[0] == 0:
                for w in DEFAULT_VOCABULARY:
                    cursor.execute("""
                        INSERT OR IGNORE INTO vocabulary (word, frequency, category)
                        VALUES (?, 5, 'talmud')
                    """, (w,))

    # =========================================================================
    # Profile Operations (List, Create, Switch, Enable/Stack, Rename, Delete)
    # =========================================================================

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Returns a list of all profiles with their metadata, rule counts, and active/enabled states."""
        result = []
        for pid, meta in self.profiles_metadata.items():
            path = self._get_profile_path(pid)
            rule_count = 0
            if os.path.exists(path):
                try:
                    with sqlite3.connect(path) as c:
                        cur = c.cursor()
                        cur.execute("SELECT COUNT(*) FROM replacements WHERE is_active = 1")
                        rule_count = cur.fetchone()[0]
                except Exception:
                    pass

            result.append({
                "id": pid,
                "name": meta.get("name", pid),
                "description": meta.get("description", ""),
                "filename": meta.get("filename", f"{pid}.db"),
                "created_at": meta.get("created_at", ""),
                "rule_count": rule_count,
                "is_active": (pid == self.active_profile_id),
                "is_enabled": (pid in self.enabled_profiles)
            })
        # Sort so active profile is at the top, followed by alphabetical
        result.sort(key=lambda p: (not p["is_active"], p["name"]))
        return result

    def get_active_profile_id(self) -> str:
        return self.active_profile_id

    def get_active_profile_name(self) -> str:
        meta = self.profiles_metadata.get(self.active_profile_id, {})
        return meta.get("name", self.active_profile_id)

    def set_active_profile(self, profile_id: str) -> bool:
        """Switches the active profile (where new learning is saved)."""
        if profile_id not in self.profiles_metadata:
            return False
        if profile_id != self.active_profile_id:
            self._switch_connection_to_profile(profile_id)
            if profile_id not in self.enabled_profiles:
                self.enabled_profiles.append(profile_id)
            self._save_profiles_config()
        return True

    def set_enabled_profiles(self, profile_ids: List[str]):
        """Sets which profiles contribute rules during OCR transcription (multi-person stacking)."""
        # Ensure active profile is always enabled
        if self.active_profile_id not in profile_ids:
            profile_ids.append(self.active_profile_id)
        self.enabled_profiles = profile_ids
        self._save_profiles_config()

    def get_enabled_profile_ids(self) -> List[str]:
        return list(self.enabled_profiles)

    def create_profile(self, name: str, description: str = "", seed_defaults: bool = True) -> str:
        """Creates a new handwriting profile and returns its profile_id."""
        name = name.strip()
        if not name:
            raise ValueError("שם הפרופיל אינו יכול להיות ריק")

        # Generate unique ID
        clean_slug = re.sub(r'[^a-zA-Z0-9_\u0590-\u05FF]', '_', name).strip('_')
        base_id = clean_slug.lower() if clean_slug else "profile"
        pid = base_id
        idx = 1
        while pid in self.profiles_metadata:
            pid = f"{base_id}_{idx}"
            idx += 1

        filename = f"{pid}.db"
        target_path = os.path.join(self.profiles_dir, filename)

        # Initialize DB
        with sqlite3.connect(target_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS replacements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_text TEXT UNIQUE COLLATE NOCASE,
                    corrected_text TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE,
                    frequency INTEGER DEFAULT 1,
                    category TEXT DEFAULT 'general'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_name TEXT,
                    raw_line TEXT,
                    corrected_line TEXT,
                    timestamp TEXT
                )
            """)
            if seed_defaults:
                now = datetime.now().isoformat()
                for raw, corr in DEFAULT_CORRECTIONS:
                    cursor.execute("""
                        INSERT OR IGNORE INTO replacements 
                        (raw_text, corrected_text, count, is_active, created_at, updated_at)
                        VALUES (?, ?, 1, 1, ?, ?)
                    """, (raw, corr, now, now))
                for w in DEFAULT_VOCABULARY:
                    cursor.execute("""
                        INSERT OR IGNORE INTO vocabulary (word, frequency, category)
                        VALUES (?, 5, 'talmud')
                    """, (w,))

        self.profiles_metadata[pid] = {
            "id": pid,
            "name": name,
            "description": description,
            "filename": filename,
            "created_at": datetime.now().isoformat()
        }
        self.enabled_profiles.append(pid)
        self._save_profiles_config()
        return pid

    def rename_profile(self, profile_id: str, new_name: str, new_description: str = None) -> bool:
        new_name = new_name.strip()
        if not new_name or profile_id not in self.profiles_metadata:
            return False
        self.profiles_metadata[profile_id]["name"] = new_name
        if new_description is not None:
            self.profiles_metadata[profile_id]["description"] = new_description
        self._save_profiles_config()
        return True

    def delete_profile(self, profile_id: str) -> bool:
        """Deletes a profile. Cannot delete if it is the only remaining profile."""
        if profile_id not in self.profiles_metadata or len(self.profiles_metadata) <= 1:
            return False

        # If deleting active profile, switch to another first
        if profile_id == self.active_profile_id:
            other_pids = [p for p in self.profiles_metadata if p != profile_id]
            self.set_active_profile(other_pids[0])

        filename = self.profiles_metadata[profile_id].get("filename")
        if filename:
            path = os.path.join(self.profiles_dir, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        if profile_id in self.enabled_profiles:
            self.enabled_profiles.remove(profile_id)
        del self.profiles_metadata[profile_id]
        self._save_profiles_config()
        return True

    def duplicate_profile(self, profile_id: str, new_name: str) -> str:
        """Clones an existing profile and all its learned rules into a new profile."""
        if profile_id not in self.profiles_metadata:
            raise ValueError("פרופיל המקור אינו קיים")

        new_pid = self.create_profile(new_name, description=f"עותק של {self.profiles_metadata[profile_id]['name']}", seed_defaults=False)
        src_path = self._get_profile_path(profile_id)
        dst_path = self._get_profile_path(new_pid)

        # Copy data
        with sqlite3.connect(src_path) as src_conn, sqlite3.connect(dst_path) as dst_conn:
            src_conn.backup(dst_conn)

        return new_pid

    # =========================================================================
    # Backup, Restore & Profile Merging
    # =========================================================================

    def quick_backup(self, profile_id: str = None) -> str:
        """Creates an instant timestamped backup of a profile in the backups directory."""
        if profile_id is None:
            profile_id = self.active_profile_id

        meta = self.profiles_metadata.get(profile_id, {})
        pname = meta.get("name", profile_id)
        safe_pname = re.sub(r'[^a-zA-Z0-9_\u0590-\u05FF]', '_', pname)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"OhrHaKsav_Backup_{safe_pname}_{timestamp}.ohrhaksav"
        target_path = os.path.join(self.backups_dir, backup_filename)

        self.backup_profile(profile_id, target_path)
        return target_path

    def backup_profile(self, profile_id: str, target_file_path: str) -> bool:
        """Backs up a single profile SQLite database using the SQLite backup API."""
        src_path = self._get_profile_path(profile_id)
        if not os.path.exists(src_path):
            return False

        os.makedirs(os.path.dirname(os.path.abspath(target_file_path)), exist_ok=True)
        with sqlite3.connect(src_path) as src_conn, sqlite3.connect(target_file_path) as dst_conn:
            src_conn.backup(dst_conn)
        return True

    def restore_profile(self, source_file_path: str, profile_name: str = "", as_new_profile: bool = True) -> str:
        """
        Restores a profile from a .ksavbackup, .db, or .json file.
        If as_new_profile is True, creates a new profile.
        If False, restores into the currently active profile (creates a safety backup first).
        """
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"קובץ הגיבוי לא נמצא: {source_file_path}")

        # Safety backup of active profile first
        self.quick_backup(self.active_profile_id)

        # JSON file restore/import
        if source_file_path.lower().endswith(".json"):
            with open(source_file_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
            if as_new_profile:
                name = profile_name or f"שוחזר מ-{os.path.basename(source_file_path)}"
                target_pid = self.create_profile(name, seed_defaults=False)
                target_path = self._get_profile_path(target_pid)
                with sqlite3.connect(target_path) as conn:
                    cur = conn.cursor()
                    now = datetime.now().isoformat()
                    for r in rules:
                        if "raw_text" in r and "corrected_text" in r:
                            cur.execute("""
                                INSERT OR IGNORE INTO replacements 
                                (raw_text, corrected_text, count, is_active, created_at, updated_at)
                                VALUES (?, ?, ?, 1, ?, ?)
                            """, (r["raw_text"], r["corrected_text"], r.get("count", 1), now, now))
                return target_pid
            else:
                for r in rules:
                    if "raw_text" in r and "corrected_text" in r:
                        self.add_or_update_replacement(r["raw_text"], r["corrected_text"], increment=r.get("count", 1))
                return self.active_profile_id

        # SQLite DB / .ksavbackup file restore
        if as_new_profile:
            name = profile_name or f"שוחזר מ-{os.path.splitext(os.path.basename(source_file_path))[0]}"
            target_pid = self.create_profile(name, seed_defaults=False)
            target_path = self._get_profile_path(target_pid)
            with sqlite3.connect(source_file_path) as src_conn, sqlite3.connect(target_path) as dst_conn:
                src_conn.backup(dst_conn)
            return target_pid
        else:
            # Overwrite active profile
            target_path = self._get_profile_path(self.active_profile_id)
            if self._conn:
                self._conn.close()
            with sqlite3.connect(source_file_path) as src_conn, sqlite3.connect(target_path) as dst_conn:
                src_conn.backup(dst_conn)
            self._switch_connection_to_profile(self.active_profile_id)
            return self.active_profile_id

    def merge_profiles(self, source_path_or_pid: str) -> int:
        """
        Merges learned rules and vocabulary from another profile or backup file into the active profile.
        Returns the number of rules inserted or updated.
        """
        if source_path_or_pid in self.profiles_metadata:
            source_path = self._get_profile_path(source_path_or_pid)
        else:
            source_path = source_path_or_pid

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"קובץ המקור למיזוג אינו קיים: {source_path}")

        merged_count = 0
        now = datetime.now().isoformat()

        if source_path.lower().endswith(".json"):
            with open(source_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
            for r in rules:
                if "raw_text" in r and "corrected_text" in r:
                    self.add_or_update_replacement(r["raw_text"], r["corrected_text"], increment=r.get("count", 1))
                    merged_count += 1
            return merged_count

        # SQLite merge
        with sqlite3.connect(source_path) as src_conn, self._get_connection() as dst_conn:
            src_cur = src_conn.cursor()
            dst_cur = dst_conn.cursor()

            # Merge replacements
            src_cur.execute("SELECT raw_text, corrected_text, count, is_active FROM replacements")
            for raw, corr, cnt, active in src_cur.fetchall():
                dst_cur.execute("""
                    INSERT INTO replacements (raw_text, corrected_text, count, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(raw_text) DO UPDATE SET
                        corrected_text = excluded.corrected_text,
                        count = replacements.count + excluded.count,
                        updated_at = excluded.updated_at
                """, (raw, corr, cnt, active, now, now))
                merged_count += 1

            # Merge vocabulary
            src_cur.execute("SELECT word, frequency, category FROM vocabulary")
            for word, freq, cat in src_cur.fetchall():
                dst_cur.execute("""
                    INSERT INTO vocabulary (word, frequency, category)
                    VALUES (?, ?, ?)
                    ON CONFLICT(word) DO UPDATE SET frequency = vocabulary.frequency + excluded.frequency
                """, (word, freq, cat))

            dst_conn.commit()

        return merged_count

    # =========================================================================
    # Rule Queries, Application & Learning (Multi-Profile Aware)
    # =========================================================================

    def get_all_replacements(self, active_only: bool = True, include_all_enabled: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves replacement rules.
        If include_all_enabled is True, aggregates rules across all enabled profiles.
        Active profile rules take precedence over secondary profiles.
        """
        if not include_all_enabled or len(self.enabled_profiles) <= 1:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id, raw_text, corrected_text, count, is_active, updated_at FROM replacements"
                if active_only:
                    query += " WHERE is_active = 1"
                query += " ORDER BY count DESC, raw_text ASC"
                cursor.execute(query)
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "raw_text": r[1],
                        "corrected_text": r[2],
                        "count": r[3],
                        "is_active": bool(r[4]),
                        "updated_at": r[5],
                        "profile_id": self.active_profile_id,
                        "profile_name": self.get_active_profile_name()
                    }
                    for r in rows
                ]

        # Multi-Profile Aggregate:
        # Load secondary profiles first, then active profile so active overrides
        combined_rules: Dict[str, Dict[str, Any]] = {}

        # 1. Secondary profiles
        for pid in self.enabled_profiles:
            if pid == self.active_profile_id:
                continue
            path = self._get_profile_path(pid)
            if not os.path.exists(path):
                continue
            pname = self.profiles_metadata.get(pid, {}).get("name", pid)
            try:
                with sqlite3.connect(path) as conn:
                    cur = conn.cursor()
                    query = "SELECT id, raw_text, corrected_text, count, is_active, updated_at FROM replacements"
                    if active_only:
                        query += " WHERE is_active = 1"
                    cur.execute(query)
                    for r in cur.fetchall():
                        raw_key = r[1].lower()
                        combined_rules[raw_key] = {
                            "id": r[0],
                            "raw_text": r[1],
                            "corrected_text": r[2],
                            "count": r[3],
                            "is_active": bool(r[4]),
                            "updated_at": r[5],
                            "profile_id": pid,
                            "profile_name": pname
                        }
            except Exception:
                pass

        # 2. Active profile (overrides secondary)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, raw_text, corrected_text, count, is_active, updated_at FROM replacements"
            if active_only:
                query += " WHERE is_active = 1"
            cursor.execute(query)
            for r in cursor.fetchall():
                raw_key = r[1].lower()
                combined_rules[raw_key] = {
                    "id": r[0],
                    "raw_text": r[1],
                    "corrected_text": r[2],
                    "count": r[3],
                    "is_active": bool(r[4]),
                    "updated_at": r[5],
                    "profile_id": self.active_profile_id,
                    "profile_name": self.get_active_profile_name()
                }

        results = list(combined_rules.values())
        results.sort(key=lambda r: (r["count"], len(r["raw_text"])), reverse=True)
        return results

    def add_or_update_replacement(self, raw_text: str, corrected_text: str, increment: int = 1) -> bool:
        raw_text = raw_text.strip()
        corrected_text = corrected_text.strip()
        if not raw_text or not corrected_text or raw_text == corrected_text:
            return False

        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO replacements (raw_text, corrected_text, count, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(raw_text) DO UPDATE SET
                    corrected_text = excluded.corrected_text,
                    count = replacements.count + excluded.count,
                    is_active = 1,
                    updated_at = excluded.updated_at
            """, (raw_text, corrected_text, increment, now, now))
            conn.commit()
        return True

    def delete_replacement(self, replacement_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM replacements WHERE id = ?", (replacement_id,))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_replacement(self, replacement_id: int, active: bool) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE replacements SET is_active = ? WHERE id = ?", (1 if active else 0, replacement_id))
            conn.commit()
            return cursor.rowcount > 0

    def extract_corrections(self, raw_text: str, corrected_text: str) -> List[Tuple[str, str]]:
        """
        Extracts candidate (raw, corrected) replacement pairs from proofreading edits
        WITHOUT writing to the database. Used for visual proofreading confirmation.
        """
        raw_tokens = [w for w in re.split(r'(\s+|[.,:;!?"\'\(\)\[\]])', raw_text) if w and not w.isspace()]
        corr_tokens = [w for w in re.split(r'(\s+|[.,:;!?"\'\(\)\[\]])', corrected_text) if w and not w.isspace()]

        matcher = difflib.SequenceMatcher(None, raw_tokens, corr_tokens)
        candidates = []
        seen = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                raw_sub = " ".join(raw_tokens[i1:i2]).strip()
                corr_sub = " ".join(corr_tokens[j1:j2]).strip()
                if 0 < len(raw_tokens[i1:i2]) <= 3 and 0 < len(corr_tokens[j1:j2]) <= 3:
                    if raw_sub and corr_sub and raw_sub != corr_sub:
                        pair = (raw_sub, corr_sub)
                        if pair not in seen:
                            seen.add(pair)
                            candidates.append(pair)
        return candidates

    def commit_corrections(
        self,
        pairs: List[Tuple[str, str]],
        page_name: str = "",
        raw_text: str = "",
        corrected_text: str = ""
    ) -> List[Tuple[str, str]]:
        """Saves an approved list of (raw, corrected) pairs into the ACTIVE profile."""
        learned = []
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for raw_sub, corr_sub in pairs:
                raw_sub = raw_sub.strip()
                corr_sub = corr_sub.strip()
                if raw_sub and corr_sub and raw_sub != corr_sub:
                    cursor.execute("""
                        INSERT INTO replacements (raw_text, corrected_text, count, is_active, created_at, updated_at)
                        VALUES (?, ?, 1, 1, ?, ?)
                        ON CONFLICT(raw_text) DO UPDATE SET
                            corrected_text = excluded.corrected_text,
                            count = replacements.count + 1,
                            updated_at = excluded.updated_at
                    """, (raw_sub, corr_sub, now, now))
                    learned.append((raw_sub, corr_sub))

            if page_name or learned:
                cursor.execute("""
                    INSERT INTO history (page_name, raw_line, corrected_line, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (page_name, raw_text[:500], corrected_text[:500], now))

            if corrected_text:
                words = re.findall(r'[\u0590-\u05FF]{2,}', corrected_text)
                for w in set(words):
                    cursor.execute("""
                        INSERT INTO vocabulary (word, frequency, category)
                        VALUES (?, 1, 'learned')
                        ON CONFLICT(word) DO UPDATE SET frequency = vocabulary.frequency + 1
                    """, (w,))

            conn.commit()

        return learned

    def learn_from_corrections(self, raw_text: str, corrected_text: str, page_name: str = "") -> List[Tuple[str, str]]:
        """
        Learns corrections from user proofreading into the ACTIVE profile.
        Returns list of (raw, corrected) pairs learned.
        """
        pairs = self.extract_corrections(raw_text, corrected_text)
        return self.commit_corrections(pairs, page_name=page_name, raw_text=raw_text, corrected_text=corrected_text)

    def _resolve_cursive_swap(self, word: str, known_targets: set) -> Optional[str]:
        """
        If `word` (Hebrew, len >= 4) is NOT in SAFE_COMMON_HEBREW / known_targets,
        checks whether swapping 1 cursive-confusable character (e.g. ב->כ, ק->ת, ב->צ, ד->ר)
        produces a unique exact match in `known_targets`.
        """
        if len(word) < 4 or word in SAFE_COMMON_HEBREW or word in known_targets:
            return None

        # 1. Check stripping a phantom trailing 'ן' glued from a vertical red margin line
        if word.endswith("ן") and len(word) >= 5:
            stem = word[:-1]
            if stem in known_targets or stem in SAFE_COMMON_HEBREW:
                return stem
            if stem in BUILTIN_CURSIVE_FIXES:
                return BUILTIN_CURSIVE_FIXES[stem]

        # 2. Check single-character cursive confusions
        matches = set()
        for idx, ch in enumerate(word):
            swaps = CURSIVE_CHAR_SWAPS.get(ch)
            if not swaps:
                continue
            for alt in swaps:
                cand = word[:idx] + alt + word[idx + 1:]
                if cand in known_targets:
                    matches.add(cand)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def apply_corrections(self, text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Applies active learned corrections to the raw OCR text in a SINGLE PASS
        (preventing double-replacement bugs like תוס' -> תוס''), followed by
        smart cursive-confusion resolution against the Torah/Yeshiva lexicon.
        Supports multi-person profile stacking across all enabled profiles.
        Returns (processed_text, applied_rules_list).
        """
        if not text:
            return "", []

        # Build unified lookup map: builtin cursive fixes first, then user profile rules override!
        rule_map: Dict[str, str] = dict(BUILTIN_CURSIVE_FIXES)
        replacements = self.get_all_replacements(active_only=True, include_all_enabled=True)
        for rule in replacements:
            raw = rule["raw_text"]
            corr = rule["corrected_text"]
            if raw and corr and raw != corr:
                rule_map[raw] = corr

        applied: List[Tuple[str, str]] = []
        result = text

        # Step 1: Single-pass longest-first regex replacement (no cascading double-apostrophe!)
        if rule_map:
            sorted_keys = sorted(rule_map.keys(), key=len, reverse=True)
            alt_pattern = "|".join(re.escape(k) for k in sorted_keys)
            # Include Hebrew letters, digits, geresh (') and gershayim (") in word boundaries
            boundary_pattern = re.compile(
                r'(?<![\u0590-\u05FF0-9\'"])(?:' + alt_pattern + r')(?![\u0590-\u05FF0-9\'"])'
            )

            def _repl_cb(m):
                matched = m.group(0)
                target = rule_map[matched]
                applied.append((matched, target))
                return target

            result = boundary_pattern.sub(_repl_cb, result)

        # Step 2: Smart Cursive-Confusion Resolution for remaining unknown words (len >= 4)
        known_targets = set(TORAH_CURSIVE_TARGETS)
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT word FROM vocabulary WHERE frequency >= 2")
                for (w,) in cur.fetchall():
                    if w and len(w) >= 4:
                        known_targets.add(w)
        except Exception:
            pass

        def _cursive_cb(m):
            tok = m.group(0)
            fixed = self._resolve_cursive_swap(tok, known_targets)
            if fixed and fixed != tok:
                applied.append((tok, fixed))
                return fixed
            return tok

        result = re.sub(r'(?<![\u0590-\u05FF\'"])[\u0590-\u05FF]{4,}(?![\u0590-\u05FF\'"])', _cursive_cb, result)

        return result, applied
