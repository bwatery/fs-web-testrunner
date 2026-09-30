import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

# Inspect all buttons and their exact text
btn_js = """(() => {
    return Array.from(document.querySelectorAll('.el-button')).map(b => ({
        text: b.innerText.trim(),
        className: b.className,
        visible: b.offsetParent !== null
    }));
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': btn_js, 'returnByValue': True}}))
buttons = json.loads(ws.recv())['result']['result']['value']
print("Buttons:", buttons)

# Click the "选择患者" button
click_js = """(() => {
    const btn = Array.from(document.querySelectorAll('.el-button')).find(b => b.innerText.includes('选择患者') || b.innerText.includes('选患者'));
    if (btn) {
        btn.click();
        return 'Clicked: ' + btn.innerText;
    }
    return 'Not found';
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': click_js, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(1.5)

# Inspect dialog and tables
dialog_js = """(() => {
    const dialog = document.querySelector('.el-dialog') || document.querySelector('.el-overlay');
    const table = document.querySelector('.el-table');
    const tableRows = Array.from(document.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
        return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).join(' | ');
    });
    return {
        hasDialog: !!dialog,
        dialogTitle: dialog ? (dialog.querySelector('.el-dialog__title') ? dialog.querySelector('.el-dialog__title').innerText : 'no title') : null,
        dialogVisible: dialog ? (dialog.style.display !== 'none') : false,
        tablesCount: document.querySelectorAll('.el-table').length,
        tableRowsCount: tableRows.length,
        firstFewRows: tableRows.slice(0, 5)
    };
})()"""
ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': dialog_js, 'returnByValue': True}}))
print("Dialog inspection:")
print(json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
