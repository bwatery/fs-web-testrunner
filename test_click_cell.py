import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

click_cell_js = """(() => {
    const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
    const tr = Array.from(dialog.querySelectorAll('tbody tr')).find(tr => tr.innerText.includes('000028'));
    if (!tr) return 'No row 000028';
    
    const cell = tr.querySelector('.vxe-cell');
    if (!cell) return 'No cell';
    
    // Simulate real click
    ['mousedown', 'mouseup', 'click'].forEach(evtType => {
        cell.dispatchEvent(new MouseEvent(evtType, { bubbles: true, cancelable: true, view: window }));
    });
    
    return 'Clicked cell';
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': click_cell_js, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(1)

# Check if dialog closed or if row is selected
check_js = """(() => {
    const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
    return {
        dialogStillOpen: !!dialog,
        mainPageText: document.body.innerText.slice(0, 300).replace(/\\n+/g, ' ')
    };
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': check_js, 'returnByValue': True}}))
print("After click:", json.loads(ws.recv())['result']['result']['value'])

ws.close()
