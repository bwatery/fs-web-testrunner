import time, json, requests, sys
sys.path.insert(0, r'D:\CSsoft\AI\googleAntiGravity\cliProject')
from fs_web_testrunner.core.login_validator import LoginValidator

validator = LoginValidator()
print("Switching identity to Doctor (Role 35, Dept 910092 内一科)...")
res = validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/workstation")
print("Switch result:", res)

time.sleep(4.0)

# Now check patient list in doctor workstation
tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
import websocket
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

js = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row'));
    return rows.map(r => r.innerText.replace(/\\s+/g, ' ').trim());
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}))
raw = ws.recv()
patients = json.loads(raw).get('result', {}).get('result', {}).get('value', [])
print("Found patients in Doctor Workstation:")
for p in patients:
    print(" -", p)

# Capture screenshot
import base64
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\doctor_patients_loaded.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
