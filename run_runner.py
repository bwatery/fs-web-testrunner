"""
FS.TestRunner Web - Launcher
Launches the automated testing web dashboard and opens it in the browser.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import uvicorn
import webbrowser
import threading
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from fs_web_testrunner.config import WEB_RUNNER_HOST, WEB_RUNNER_PORT

def open_browser():
    time.sleep(1.2)
    url = f"http://{WEB_RUNNER_HOST}:{WEB_RUNNER_PORT}"
    print(f"\n=======================================================")
    print(f"  FS.TestRunner Web 正在启动...")
    print(f"  控制台地址: {url}")
    print(f"=======================================================\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "fs_web_testrunner.web_runner.app:app",
        host=WEB_RUNNER_HOST,
        port=WEB_RUNNER_PORT,
        log_level="info"
    )
