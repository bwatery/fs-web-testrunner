import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inspect_dialog = """(() => {
    const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
    if (!dialog) return { error: 'No visible dialog' };
    
    const btns = Array.from(dialog.querySelectorAll('.el-button')).map(b => ({
        text: b.innerText.trim(),
        className: b.className
    }));
    
    return {
        title: dialog.querySelector('.el-dialog__title') ? dialog.querySelector('.el-dialog__title').innerText : '',
        buttons: btns
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_dialog, 'returnByValue': True}}))
print("Dialog footer:", json.loads(ws.recv())['result']['result']['value'])

ws.close()
