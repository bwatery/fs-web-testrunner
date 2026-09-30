import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_click = """(() => {
    const activePanel = document.querySelector('.vxe-pulldown--panel[style*="z-index"]') || Array.from(document.querySelectorAll('.vxe-pulldown--panel')).find(p => p.querySelector('.vxe-table'));
    if (!activePanel) return { err: 'no active panel' };
    const cell = activePanel.querySelector('.vxe-body--column');
    const row = activePanel.querySelector('.vxe-body--row');
    if (!row) return { err: 'no body row' };
    
    // dispatch click and dblclick on both cell and row
    cell.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    cell.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    return { ok: true, text: row.innerText };
})()"""

print("Click result:", eval_js(js_click))
time.sleep(1.0)

js_check = """(() => {
    const diagItem = Array.from(document.querySelectorAll('.el-form-item')).find(i => i.querySelector('.el-form-item__label')?.innerText?.includes('西医诊断'));
    const input = diagItem.querySelector('.vxe-input--inner');
    const codeItem = Array.from(document.querySelectorAll('.el-form-item')).find(i => i.querySelector('.el-form-item__label')?.innerText?.includes('西医诊断编码'));
    return {
        diagVal: input?.value,
        codeVal: codeItem?.querySelector('input')?.value
    };
})()"""

print("Check result:", eval_js(js_check))
ws.close()
