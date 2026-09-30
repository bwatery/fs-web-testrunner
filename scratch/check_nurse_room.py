import time, json, requests, sys, base64
sys.path.insert(0, r'D:\CSsoft\AI\googleAntiGravity\cliProject')
from fs_web_testrunner.core.login_validator import LoginValidator

validator = LoginValidator()
print("Switching identity to Nurse (Role 36, Dept 910131 内一科病区)...")
res = validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/theRoomManagement")
print("Switch result:", res)
time.sleep(4.0)

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
import websocket
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

# Inspect buttons, tabs, tables on the room management page
js = """(() => {
    const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim());
    const cards = Array.from(document.querySelectorAll('.bed-card, .el-card, .vxe-body--row, .patient-item')).map(c => c.innerText.replace(/\\s+/g, ' ').trim());
    return {
        url: window.location.href,
        btns,
        tabs,
        cardsCount: cards.length,
        cardsSample: cards.slice(0, 10)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}))
raw = ws.recv()
print("Page inspection:", json.dumps(json.loads(raw).get('result', {}).get('result', {}).get('value'), ensure_ascii=False, indent=2))

# Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\nurse_room_management.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved to:", path)

ws.close()
