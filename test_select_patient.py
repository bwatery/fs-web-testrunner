import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

inspect_vxe = """(() => {
    // Find rows containing 000028 or 骨三科测试患者03
    const allRows = Array.from(document.querySelectorAll('.vxe-body--row, tr, .el-table__row'));
    const matched = allRows.filter(r => r.innerText.includes('000028') || r.innerText.includes('骨三科测试患者03'));
    return {
        vxeTables: document.querySelectorAll('.vxe-table').length,
        matchedRows: matched.length,
        matchedRowClass: matched.length > 0 ? matched[0].className : '',
        matchedRowTag: matched.length > 0 ? matched[0].tagName : ''
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_vxe, 'returnByValue': True}}))
print("Vxe inspection:", json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

# Double click or click the matched patient row
click_patient = """(() => {
    const allRows = Array.from(document.querySelectorAll('.vxe-body--row, tr, .el-table__row'));
    const target = allRows.find(r => r.innerText.includes('000028') || r.innerText.includes('骨三科测试患者03'));
    if (target) {
        // Dispatch dblclick
        target.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
        return 'Dispatched dblclick on patient row';
    }
    return 'Target row not found';
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': click_patient, 'returnByValue': True}}))
print("Click res:", json.loads(ws.recv())['result']['result']['value'])

time.sleep(2)

# Check main settlement page after patient selection
check_main = """(() => {
    return {
        bodySnippet: document.body.innerText.slice(0, 800).replace(/\\n+/g, ' ')
    };
})()"""
ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': check_main, 'returnByValue': True}}))
print("Main page after patient selected:")
print(json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))

ws.close()
