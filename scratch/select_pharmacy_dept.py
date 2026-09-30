import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const target = items.find(i => i.innerText.includes('内一科') || i.innerText.includes('住院'));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false, items: items.map(i => i.innerText.trim()) };
})()""")
print("Click option:", res)
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\plan_b_act3_selected_dept.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
