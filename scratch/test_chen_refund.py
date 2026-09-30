import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Navigate to nurse returnpremium
print("Navigating to #/inpatient/nurse/returnpremium...")
eval_js("window.location.hash = '#/inpatient/nurse/returnpremium'")
time.sleep(3.0)

# Check tree nodes on the left
js_tree = """(() => {
    const contents = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = contents.find(c => c.innerText.trim() === '陈新强(401-2)' || (c.innerText.includes('陈新强') && !c.innerText.includes('住院患者')));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false, available: contents.map(c => c.innerText.trim()) };
})()"""

print("Click patient in returnpremium:", eval_js(js_tree))
time.sleep(2.0)

# Click 查询 if available
js_q = """(() => {
    const qBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === '查询');
    if (qBtn) {
        qBtn.click();
        return { clicked: true };
    }
    return { clicked: false };
})()"""
print("Click 查询:", eval_js(js_q))
time.sleep(2.0)

# Check refundable items / table
js_table = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr.el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim());
    return {
        count: rows.length,
        rows: rows.slice(0, 5)
    };
})()"""
print("Refundable items:", eval_js(js_table))

# Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_nurse_refund.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)
ws.close()
