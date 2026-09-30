import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()

# 切到住院护士 (Role 36, Dept 910131)
v.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/returnpremium")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/nurse/returnpremium';")
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\preview_returnpremium.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)

text = eval_js("document.body.innerText")
print("Page text snippet:", text[:600].replace('\n', ' '))
ws.close()
