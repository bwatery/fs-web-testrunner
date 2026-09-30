import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Click 陈新强(401-2)
js_click_tree = """(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node'));
    const target = nodes.find(n => n.innerText && n.innerText.includes('陈新强'));
    if (!target) return { err: 'node not found' };
    const content = target.querySelector('.el-tree-node__content') || target;
    content.click();
    return { clicked: true, text: content.innerText.trim() };
})()"""

print("Click tree node:", eval_js(js_click_tree))
time.sleep(1.5)

# Click 查询 button
js_click_search = """(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const qBtn = btns.find(b => b.innerText && b.innerText.trim() === '查询');
    if (qBtn) {
        qBtn.click();
        return { clicked: true };
    }
    return { clicked: false };
})()"""

print("Click 查询:", eval_js(js_click_search))
time.sleep(2.5)

# Check tables or orders
js_check_orders = """(() => {
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim());
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr.el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim());
    return {
        tabs,
        ordersCount: rows.length,
        ordersSample: rows.slice(0, 10)
    };
})()"""

res_orders = eval_js(js_check_orders)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\chen_nurse_orders.json', 'w', encoding='utf-8') as f:
    json.dump(res_orders, f, ensure_ascii=False, indent=2)
print("Orders found count:", res_orders.get('ordersCount'))

# Capture screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_nurse_selected.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
