import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Click 陈新强(401-2) leaf node
js_click_leaf = """(() => {
    const contents = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = contents.find(c => c.innerText.trim() === '陈新强(401-2)' || (c.innerText.includes('陈新强') && !c.innerText.includes('住院患者')));
    if (target) {
        target.click();
        return { clicked: true, found: target.innerText.trim() };
    }
    return { clicked: false, available: contents.map(c => c.innerText.trim()) };
})()"""

print("Click 陈新强:", eval_js(js_click_leaf))
time.sleep(1.5)

# 2. Click 查询
js_search = """(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const qBtn = btns.find(b => b.innerText && b.innerText.trim() === '查询');
    if (qBtn) {
        qBtn.click();
        return { clicked: true };
    }
    return { clicked: false };
})()"""
print("Click 查询:", eval_js(js_search))
time.sleep(2.5)

# 3. Check table rows
js_rows = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr.el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim());
    return {
        count: rows.length,
        rows: rows.slice(0, 10)
    };
})()"""

res_rows = eval_js(js_rows)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\chen_nurse_exact_orders.json', 'w', encoding='utf-8') as f:
    json.dump(res_rows, f, ensure_ascii=False, indent=2)
print("Orders found:", res_rows.get('count'))

# 4. Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_nurse_orders_loaded.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
