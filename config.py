"""
FS Web TestRunner - Configuration
Configuration for EMR Designer automated testing platform.
"""

import os
import warnings
from pathlib import Path

# Suppress urllib3 version warning for cleaner output
warnings.filterwarnings("ignore", category=Warning, module="requests")

# Ensure UTF-8 output on Windows console
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# EMR Target URLs
EMR_DESIGNER_URL = os.getenv("EMR_DESIGNER_URL", "http://192.168.1.198:8088/#/emr/templatesrecords/emrDesigner")
EMR_BASE_URL = os.getenv("EMR_BASE_URL", "http://192.168.1.198:8088")
EMR_API_URL = os.getenv("EMR_API_URL", "http://192.168.1.198:8081")

# Default Test Credentials (if login is required)
DEFAULT_USERNAME = os.getenv("EMR_TEST_USER", "admin")
DEFAULT_PASSWORD = os.getenv("EMR_TEST_PASS", "admin123")

# Browser Configuration
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

def find_browser_executable() -> str:
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return "chrome.exe"

BROWSER_EXECUTABLE = find_browser_executable()
CDP_PORT = int(os.getenv("CDP_PORT", "9222"))
CDP_HOST = "127.0.0.1"

# Web TestRunner Dashboard Configuration
WEB_RUNNER_HOST = "127.0.0.1"
WEB_RUNNER_PORT = 8989
