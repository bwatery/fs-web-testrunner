"""
Unified Local Logging System for HIS Web TestRunner.
Stores rolling log files locally in `logs/` directory with automatic rotation.
Supports structured logging across TestEngine, WebRunner API, Business Rules, and Sessions.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Any

BASE_DIR = Path(__file__).resolve().parent.parent

# Dedicated logs directory
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Common Log Formatter
LOG_FORMAT = "[%(asctime)s] [%(levelname)-7s] [%(name)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

# Cached Loggers
_loggers: Dict[str, logging.Logger] = {}

def setup_file_handler(filename: str, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> RotatingFileHandler:
    """Creates a thread-safe rotating file handler writing UTF-8 logs to disk."""
    log_file = LOGS_DIR / filename
    handler = RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True
    )
    handler.setFormatter(formatter)
    return handler

def get_logger(name: str = "app") -> logging.Logger:
    """
    Factory function to get or create a logger with both console and local file persistence.
    
    Log destinations:
    - `logs/app.log`: General application and API server logs.
    - `logs/test_engine.log`: Execution of invasive/non-invasive test suites.
    - `logs/rules.log`: Business rules assertions and verification runs.
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"fs_runner.{name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 1. Console Output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. Main App Log (Always persists everything)
    app_handler = setup_file_handler("app.log")
    logger.addHandler(app_handler)

    # 3. Domain-specific file handlers
    if "engine" in name.lower() or "test" in name.lower():
        engine_handler = setup_file_handler("test_engine.log")
        logger.addHandler(engine_handler)
    elif "rule" in name.lower():
        rules_handler = setup_file_handler("rules.log")
        logger.addHandler(rules_handler)

    _loggers[name] = logger
    return logger

def get_recent_logs(log_type: str = "app", limit: int = 150) -> List[str]:
    """
    Reads the latest N lines from the local log file on disk.
    Used by frontend inspection and API diagnostic tools.
    """
    filename_map = {
        "app": "app.log",
        "engine": "test_engine.log",
        "test_engine": "test_engine.log",
        "rules": "rules.log"
    }
    filename = filename_map.get(log_type, "app.log")
    log_path = LOGS_DIR / filename
    if not log_path.exists():
        return []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return [line.rstrip() for line in lines[-limit:]]
    except Exception as e:
        return [f"[Error reading log file {filename}: {e}]"]

def list_log_files() -> List[Dict[str, Any]]:
    """Returns metadata for all log files currently stored in logs/."""
    files_meta = []
    for item in sorted(LOGS_DIR.glob("*.log*")):
        stat = item.stat()
        files_meta.append({
            "name": item.name,
            "size_bytes": stat.st_size,
            "size_formatted": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024 * 1024 else f"{stat.st_size / (1024*1024):.2f} MB",
            "modified": stat.st_mtime
        })
    return files_meta

def clear_logs() -> bool:
    """Clears all local log files in logs/.
    On Windows, active log files are locked by the process's file handlers,
    so unlink() throws WinError 32. We truncate active files to 0 bytes
    and unlink any rotated backup archives.
    """
    try:
        import logging
        for logger_name in ["fs_runner", "fs_runner.test_engine", "fs_runner.rules"]:
            lg = logging.getLogger(logger_name)
            for h in lg.handlers:
                try:
                    h.flush()
                except Exception:
                    pass

        for item in LOGS_DIR.glob("*.log*"):
            # 1. Truncate to 0 bytes (safely empties active files on Windows)
            try:
                with open(item, "w", encoding="utf-8") as f:
                    f.truncate(0)
            except Exception:
                pass

            # 2. For rotated backups (.log.1, .log.2), unlink if possible
            if item.suffix != ".log":
                try:
                    item.unlink(missing_ok=True)
                except Exception:
                    pass
        return True
    except Exception:
        return False
