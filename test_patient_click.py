import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // 1. Try double click on 欧伟英 row
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr, [class*="row"]'));
    const targetRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
    if (!targetRow) return { found: false };

    targetRow.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    targetRow.click();
    return {
        found: true,
        text: targetRow.innerText.replace(/\\s+/g, ' ')
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
print('Clicked row:', json.loads(raw).get('result', {}).get('result', {}).get('value'))
time.sleep(2.5)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': '({ href: window.location.href, text: document.body.innerText.slice(0, 300) })', 'returnByValue': True}}))
raw2 = ws.recv()
print('After click:', json.loads(raw2).get('result', {}).get('result', {}).get('value'))

ws.close()
