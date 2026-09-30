import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

click_js = """(() => {
    const btns = Array.from(document.querySelectorAll('.el-button'));
    const selBtn = btns.find(b => b.innerText.trim() === '选择');
    if (selBtn) {
        selBtn.click();
        return 'Clicked 选择';
    }
    return 'No button with text 选择';
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': click_js, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(1.5)

# Inspect dialog
inspect_dialog = """(() => {
    const dialogs = Array.from(document.querySelectorAll('.el-dialog, .el-overlay-dialog')).filter(d => d.style.display !== 'none' && d.offsetHeight > 0);
    const tables = Array.from(document.querySelectorAll('.el-table'));
    const rows = Array.from(document.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
        return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).filter(Boolean).join(' | ');
    });
    return {
        visibleDialogs: dialogs.length,
        tablesCount: tables.length,
        rowCount: rows.length,
        rows: rows.slice(0, 10),
        bodySnippet: document.body.innerText.slice(0, 500).replace(/\\n+/g, ' ')
    };
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_dialog, 'returnByValue': True}}))
print("After click:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
