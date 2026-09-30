import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const table = document.querySelector('.vxe-table') || document.querySelector('table');
    const cells = Array.from(document.querySelectorAll('.vxe-body--row td, tr td'));
    const ouweiCells = cells.filter(td => td.closest('tr') && td.closest('tr').innerText.includes('欧伟英'));
    
    return {
        tableClass: table ? table.className : 'no table',
        cellDetails: ouweiCells.map((td, idx) => ({
            idx: idx,
            tag: td.tagName,
            class: td.className,
            text: td.innerText.trim(),
            html: td.innerHTML.slice(0, 150),
            hasButton: !!td.querySelector('button, a, .el-button, [class*="btn"]')
        }))
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
