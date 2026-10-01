"""
FS.TestRunner Web - Launcher
Launches the automated testing web dashboard and opens it in the browser.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import socket
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

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def open_browser():
    time.sleep(1.2)
    display_host = "127.0.0.1" if WEB_RUNNER_HOST in ("0.0.0.0", "") else WEB_RUNNER_HOST
    url = f"http://{display_host}:{WEB_RUNNER_PORT}"
    print(f"\n=======================================================")
    print(f"  HIS WebRunner 控制台已上线")
    print(f"  正在打开浏览器: {url}")
    print(f"=======================================================\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    if is_port_in_use(WEB_RUNNER_PORT):
        print(f"\n=======================================================")
        print(f"  [提示] HIS WebRunner 服务已在后台正常运行中！")
        print(f"  控制台地址: http://127.0.0.1:{WEB_RUNNER_PORT}")
        print(f"  正在直接为您在浏览器中打开控制台...")
        print(f"=======================================================\n")
        try:
            webbrowser.open(f"http://127.0.0.1:{WEB_RUNNER_PORT}")
        except Exception:
            pass
        sys.exit(0)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "fs_web_testrunner.web_runner.app:app",
        host=WEB_RUNNER_HOST,
        port=WEB_RUNNER_PORT,
        log_level="info"
    )
