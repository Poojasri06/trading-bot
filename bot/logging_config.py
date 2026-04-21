"""
logging_config.py
Centralised logging setup — writes to both console and a rotating log file.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")

_configured = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure root logger once.  Subsequent calls return the same logger.

    Args:
        level: Log level string ("DEBUG" | "INFO" | "WARNING" | "ERROR")

    Returns:
        logging.Logger: Configured root logger.
    """
    global _configured
    if _configured:
        return logging.getLogger("trading_bot")

    os.makedirs(LOG_DIR, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- File handler (rotating, max 5 MB × 3 backups) ---
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)          # always verbose in file
    file_handler.setFormatter(formatter)

    # --- Console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("trading_bot")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.propagate = False

    _configured = True
    root_logger.debug("Logging initialised — file: %s", LOG_FILE)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'trading_bot' namespace."""
    return logging.getLogger(f"trading_bot.{name}")
