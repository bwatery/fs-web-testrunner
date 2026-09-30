import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 点击欧伟英
res = eval_js("""(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = nodes.find(n => n.innerText && n.innerText.includes('欧伟英'));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false, total: nodes.length };
})()""")
print("Click patient:", res)
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\ouwei_returnpremium_loaded.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
