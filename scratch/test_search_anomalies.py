import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_check = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    const typeSelect = d.querySelector('.condition-search-input__type');
    const input = d.querySelector('#ConditionSearchExcludedInpatient');
    const btn = d.querySelector('.el-input-group__append button');
    
    // Check table headers and rows
    const headers = Array.from(d.querySelectorAll('.el-table__header th, .vxe-header--column')).map(h => h.innerText.trim()).filter(Boolean);
    const rows = Array.from(d.querySelectorAll('.el-table__row, .vxe-body--row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    
    return {
        typeText: typeSelect?.innerText?.trim(),
        inputVal: input?.value,
        hasButton: !!btn,
        headers,
        rowsCount: rows.length,
        rows
    };
})()"""

res = eval_js(js_check)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\search_dialog_state.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("Saved search_dialog_state.json")
ws.close()
