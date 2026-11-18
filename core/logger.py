# -*- coding: utf-8 -*-
"""
TorahNotesOCR - Application Logging System
Logs events, batch OCR progress, and diagnostics to %APPDATA%\\OhrHaKsav\\app.log.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OhrHaKsav")
LOG_PATH = os.path.join(LOG_DIR, "app.log")

def setup_logger(name: str = "OhrHaKsav") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    if sys.stdout and not getattr(sys, "frozen", False):
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        except Exception:
            pass

    return logger

log = setup_logger()
