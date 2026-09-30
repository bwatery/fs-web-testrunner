import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Click '内一科' in the dialog left tree
js_click_n1 = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const n1 = Array.from(d.querySelectorAll('.el-tree-node')).find(n => n.innerText && n.innerText.includes('内一科'));
    if (n1) {
        n1.click();
        return { clicked: true, text: n1.innerText.trim() };
    }
    return { clicked: false };
})()"""
print("Click 内一科:", eval_js(js_click_n1))
time.sleep(2.0)

# Check rows now
js_check = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const rows = Array.from(d.querySelectorAll('.el-table__row, tr, .vxe-body--row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    return {
        count: rows.length,
        rows
    };
})()"""
print("Rows after clicking 内一科:", eval_js(js_check))
ws.close()
