import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inspect_cells = """(() => {
    const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
    if (!dialog) return { error: 'No dialog' };
    
    // Check radio or checkbox or cells
    const trs = Array.from(dialog.querySelectorAll('tbody tr')).filter(tr => tr.innerText.includes('000028'));
    if (trs.length === 0) return { error: 'No row 000028' };
    
    const tr = trs[0];
    const cells = Array.from(tr.querySelectorAll('td')).map(td => ({
        text: td.innerText.trim(),
        className: td.className,
        html: td.innerHTML.slice(0, 100)
    }));
    
    return {
        cells: cells
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_cells, 'returnByValue': True}}))
print("Cells:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
