import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

info = eval_js("""(() => {
    const dialog = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!dialog) return { hasDialog: false };
    
    const inputs = Array.from(dialog.querySelectorAll('input')).map(i => ({
        placeholder: i.placeholder,
        value: i.value,
        className: i.className
    }));
    
    const labels = Array.from(dialog.querySelectorAll('label, .el-form-item__label')).map(l => l.innerText.trim());
    const btns = Array.from(dialog.querySelectorAll('button')).map(b => b.innerText.trim());
    
    return {
        hasDialog: true,
        title: dialog.querySelector('.el-dialog__title') ? dialog.querySelector('.el-dialog__title').innerText.trim() : '',
        labels,
        inputs,
        btns
    };
})()""")

with open("scratch/search_dialog_info.json", "w", encoding="utf-8") as f:
    json.dump(info, f, ensure_ascii=False, indent=2)

print("Dialog info:", json.dumps(info, ensure_ascii=False, indent=2))
ws.close()
