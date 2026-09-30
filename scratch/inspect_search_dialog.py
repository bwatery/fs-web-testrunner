import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Check current page and dialog
js_check = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    // Check search input and dropdown
    const select = d.querySelector('.el-select');
    const input = Array.from(d.querySelectorAll('input')).find(i => i.placeholder === '请输入' || i.value === '陈新强');
    const treeSelected = d.querySelector('.el-tree-node.is-current, .el-tree-node.is-checked');
    const tableRows = Array.from(d.querySelectorAll('.el-table__row, .vxe-body--row, tr')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    
    return {
        selectText: select?.innerText?.trim(),
        inputVal: input?.value,
        treeSelected: treeSelected?.innerText?.trim(),
        tableRows
    };
})()"""

res = eval_js(js_check)
print("Current dialog state:", json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
