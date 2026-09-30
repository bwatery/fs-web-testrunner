import requests, json, websocket, time, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator

v = LoginValidator()
print("Switching identity to Nurse (Role 36, Dept 910131 内一科病区)...")
v.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery")
time.sleep(3.0)

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_tree = """(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__content, .el-tree-node')).map(n => n.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    return Array.from(new Set(nodes));
})()"""

nodes = eval_js(js_tree)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\nurse_tree_nodes.json', 'w', encoding='utf-8') as f:
    json.dump(nodes, f, ensure_ascii=False, indent=2)
print("Nurse tree nodes count:", len(nodes) if isinstance(nodes, list) else 0)

# Capture screenshot
import base64
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_nurse_tree.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
