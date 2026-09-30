import requests, json, websocket, time, sys
sys.path.insert(0, r'D:\CSsoft\AI\googleAntiGravity\cliProject')
from fs_web_testrunner.core.login_validator import LoginValidator

v = LoginValidator()
v.switch_identity_in_browser(36, 910131, '#/inpatient/nurse/theRoomManagement')
time.sleep(3)

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

js = """(() => {
    const beds = Array.from(document.querySelectorAll('[class*="bed"], .el-card, .grid-item'));
    return beds.map(b => ({
        tag: b.tagName,
        cls: b.className,
        text: b.innerText.replace(/\\s+/g, ' ').trim()
    })).filter(b => b.text && b.text.length < 200);
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}))
res = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\beds_data.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved beds_data.json, count:", len(res) if isinstance(res, list) else 0)
ws.close()
