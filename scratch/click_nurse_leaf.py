import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    const contents = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const list = contents.map((c, i) => ({ idx: i, text: c.innerText.trim() }));
    const ouwei = contents.find(c => c.innerText.trim() === '欧伟英(401-10)' || (c.innerText.includes('欧伟英') && !c.innerText.includes('住院患者')));
    if (ouwei) {
        ouwei.click();
        return { clicked: true, found: ouwei.innerText.trim(), list };
    }
    return { clicked: false, list };
})()""")
print("Click res:", json.dumps(res, ensure_ascii=False, indent=2))
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\plan_b_act2_nurse_ouwei_clicked.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
