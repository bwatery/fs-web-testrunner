import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_click = """(() => {
    const selBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === '选择');
    if (!selBtn) return 'btn not found';
    selBtn.click();
    return 'clicked';
})()"""

print("Click:", eval_js(js_click))
time.sleep(2.0)

js_dialog = """(() => {
    const dialogs = Array.from(document.querySelectorAll('.el-dialog')).filter(d => d.offsetHeight > 0);
    if (dialogs.length === 0) return { hasDialog: false };
    const d = dialogs[0];
    const title = d.querySelector('.el-dialog__title')?.innerText;
    const rows = Array.from(d.querySelectorAll('tr, .vxe-body--row, .el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    return {
        hasDialog: true,
        title,
        rowsCount: rows.length,
        rows: rows.slice(0, 10)
    };
})()"""

res = eval_js(js_dialog)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\admission_dialog_patients.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved admission_dialog_patients.json")
ws.close()
