import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inspect_dialog_all = """(() => {
    const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
    if (!dialog) return { error: 'No dialog' };
    
    const btns = Array.from(dialog.querySelectorAll('button, .el-button')).map(b => ({
        text: b.innerText.trim(),
        className: b.className,
        outerHTML: b.outerHTML.slice(0, 150)
    }));
    
    // Check if double click on row selects
    const rows = Array.from(dialog.querySelectorAll('.vxe-body--row'));
    
    return {
        btns: btns,
        rowCount: rows.length,
        footerHTML: dialog.querySelector('.el-dialog__footer') ? dialog.querySelector('.el-dialog__footer').innerHTML : 'no footer',
        headerHTML: dialog.querySelector('.el-dialog__header') ? dialog.querySelector('.el-dialog__header').innerText : 'no header'
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_dialog_all, 'returnByValue': True}}))
print("Dialog details:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
